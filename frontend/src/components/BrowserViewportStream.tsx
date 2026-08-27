import { useEffect, useRef, useState } from "react";

type StreamState = "connecting" | "connected" | "disconnected";

interface BrowserViewportStreamProps {
  takeoverActive?: boolean;
}

export function BrowserViewportStream({
  takeoverActive = false,
}: BrowserViewportStreamProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const [state, setState] = useState<StreamState>("connecting");
  const [error, setError] = useState<string | null>(null);
  const [connectionAttempt, setConnectionAttempt] = useState(0);

  useEffect(() => {
    let disposed = false;
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${location.host}/api/ws/browser`);
    wsRef.current = ws;

    const pc = new RTCPeerConnection({
      iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
    });
    pcRef.current = pc;

    pc.ontrack = (event) => {
      if (!disposed && videoRef.current && event.streams[0]) {
        videoRef.current.srcObject = event.streams[0];
        setState("connected");
      }
    };

    pc.oniceconnectionstatechange = () => {
      if (
        pc.iceConnectionState === "failed" ||
        pc.iceConnectionState === "closed"
      ) {
        setState("disconnected");
      }
    };

    let iceCandidates: RTCIceCandidateInit[] = [];

    ws.onopen = () => {
    };

    ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === "offer") {
          if (disposed || pc.signalingState === "closed") return;
          await pc.setRemoteDescription(
            new RTCSessionDescription({ type: "offer", sdp: msg.sdp })
          );
          const answer = await pc.createAnswer();
          await pc.setLocalDescription(answer);
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: "answer", sdp: answer.sdp }));
          }

          for (const c of iceCandidates) {
            if (ws.readyState !== WebSocket.OPEN) break;
            ws.send(JSON.stringify({ type: "ice_candidate", candidate: c }));
          }
          iceCandidates = [];
        }
      } catch (err: unknown) {
        if (!disposed) {
          setError(err instanceof Error ? err.message : "Video stream negotiation failed");
          setState("disconnected");
        }
      }
    };

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        const msg = JSON.stringify({
          type: "ice_candidate",
          candidate: event.candidate.toJSON(),
        });
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(msg);
        } else {
          iceCandidates.push(event.candidate.toJSON());
        }
      }
    };

    ws.onerror = () => {
      if (!disposed) {
        setError("WebSocket connection failed");
        setState("disconnected");
      }
    };

    ws.onclose = (event) => {
      if (disposed) return;
      const reason = event.reason || `Connection closed (code ${event.code})`;
      setError(reason === "Browser target unavailable" ? "Browser page no longer available. Reconnect." : reason);
      setState("disconnected");
    };

    return () => {
      disposed = true;
      if (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN) ws.close();
      pc.close();
      if (wsRef.current === ws) wsRef.current = null;
      if (pcRef.current === pc) pcRef.current = null;
    };
  }, [connectionAttempt]);

  const retry = () => {
    setError(null);
    setState("connecting");
    setConnectionAttempt((attempt) => attempt + 1);
  };

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="text-center space-y-2">
          <p className="text-sm text-danger">{error}</p>
          <button
            onClick={retry}
            className="text-sm text-accent hover:underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex-1 overflow-hidden rounded-xl border border-grid bg-surface">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="h-full w-full object-contain"
        style={{ cursor: "default" }}
      />

      {takeoverActive && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10 pointer-events-none">
          <div className="text-center space-y-2">
            <p className="text-lg font-semibold text-white">Operate directly in the Chrome window</p>
            <p className="text-sm text-white/70">Do not click inside this video view</p>
          </div>
        </div>
      )}

      {state === "connecting" && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/60">
          <div className="flex flex-col items-center gap-3">
            <div className="size-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
            <span className="text-sm text-muted">Connecting to browser...</span>
          </div>
        </div>
      )}

      {state === "disconnected" && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/60">
          <div className="flex flex-col items-center gap-3">
            <span className="text-sm text-muted">Connection lost</span>
            <button
              onClick={retry}
              className="rounded-lg bg-accent px-4 py-1.5 text-sm text-white"
            >
              Reconnect
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
