import { useEffect, useRef, useState, useCallback } from "react";

type StreamState = "connecting" | "connected" | "disconnected";

interface BrowserViewportStreamProps {
  interactive?: boolean;
  onInteraction?: (event: InputEvent) => void;
}

interface InputEvent {
  type: "mouse_click" | "key_press" | "scroll" | "type_text";
  x?: number;
  y?: number;
  vw?: number;
  vh?: number;
  key?: string;
  deltaY?: number;
  text?: string;
}

export function BrowserViewportStream({
  interactive = false,
  onInteraction,
}: BrowserViewportStreamProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const [state, setState] = useState<StreamState>("connecting");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${location.host}/api/ws/browser`);
    wsRef.current = ws;

    const pc = new RTCPeerConnection({
      iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
    });
    pcRef.current = pc;

    pc.ontrack = (event) => {
      if (videoRef.current && event.streams[0]) {
        videoRef.current.srcObject = event.streams[0];
        setState("connected");
      }
    };

    pc.oniceconnectionstatechange = () => {
      if (
        pc.iceConnectionState === "disconnected" ||
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
      const msg = JSON.parse(event.data);

      if (msg.type === "offer") {
        if (pc.signalingState === "closed") return;
        await pc.setRemoteDescription(
          new RTCSessionDescription({ type: "offer", sdp: msg.sdp })
        );
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        ws.send(JSON.stringify({ type: "answer", sdp: answer.sdp }));

        for (const c of iceCandidates) {
          ws.send(JSON.stringify({ type: "ice_candidate", candidate: c }));
        }
        iceCandidates = [];
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
      setError("WebSocket 连接失败");
      setState("disconnected");
    };

    return () => {
      if (ws.readyState !== WebSocket.CONNECTING) ws.close();
      pc.close();
    };
  }, []);

  const sendInput = useCallback(
    (msg: InputEvent) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(msg));
      }
      onInteraction?.(msg);
    },
    [onInteraction]
  );

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLVideoElement>) => {
      if (!interactive || !videoRef.current) return;
      const rect = videoRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      sendInput({
        type: "mouse_click",
        x,
        y,
        vw: rect.width,
        vh: rect.height,
      });
    },
    [interactive, sendInput]
  );

  useEffect(() => {
    if (!interactive) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        ["Enter", "Tab", "Escape", "Backspace", "Delete",
         "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"
        ].includes(e.key)
      ) {
        e.preventDefault();
        sendInput({ type: "key_press", key: e.key });
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [interactive, sendInput]);

  const handleWheel = useCallback(
    (e: React.WheelEvent<HTMLVideoElement>) => {
      if (!interactive) return;
      sendInput({ type: "scroll", deltaY: e.deltaY });
    },
    [interactive, sendInput]
  );

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="text-center space-y-2">
          <p className="text-sm text-danger">{error}</p>
          <button
            onClick={() => {
              setError(null);
              setState("connecting");
            }}
            className="text-sm text-accent hover:underline"
          >
            重试
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
        style={{ cursor: interactive ? "crosshair" : "default" }}
        onClick={handleClick}
        onWheel={handleWheel}
      />

      {state === "connecting" && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/60">
          <div className="flex flex-col items-center gap-3">
            <div className="size-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
            <span className="text-sm text-muted">连接浏览器...</span>
          </div>
        </div>
      )}

      {state === "disconnected" && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/60">
          <div className="flex flex-col items-center gap-3">
            <span className="text-sm text-muted">连接已断开</span>
            <button
              onClick={() => {
                setState("connecting");
                setError(null);
              }}
              className="rounded-lg bg-accent px-4 py-1.5 text-sm text-white"
            >
              重新连接
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
