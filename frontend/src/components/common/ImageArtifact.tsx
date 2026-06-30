import { useCallback, useState } from "react";
import { Image as ImageIcon, Maximize2, AlertTriangle } from "lucide-react";
import { getImageUrl } from "../../api/files";
import ImageLightbox from "./ImageLightbox";

interface ImageArtifactProps {
  fileId: string;
  title?: string;
  chartType?: string;
}

export default function ImageArtifact({
  fileId,
  title,
  chartType,
}: ImageArtifactProps) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  const url = getImageUrl(fileId);

  const handleOpen = useCallback(() => {
    if (loaded) setLightboxOpen(true);
  }, [loaded]);

  return (
    <div className="my-2">
      <div
        className="group relative inline-block max-w-[320px] cursor-zoom-in overflow-hidden rounded-md border border-grid bg-surface focus-cobalt"
        onDoubleClick={handleOpen}
        role="button"
        tabIndex={0}
        aria-label={title || "Generated chart"}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === " ") && loaded) {
            e.preventDefault();
            setLightboxOpen(true);
          }
        }}
      >
        <div className="relative">
          {!error ? (
            <img
              src={url}
              alt={title || "Generated chart"}
              draggable={false}
              onLoad={() => setLoaded(true)}
              onError={() => setError(true)}
              className={`block max-h-[280px] max-w-full object-contain transition-opacity duration-200 ${
                loaded ? "opacity-100" : "opacity-0"
              }`}
            />
          ) : (
            <div className="flex h-[180px] w-[280px] flex-col items-center justify-center gap-1 text-graphite">
              <AlertTriangle className="h-5 w-5" />
              <span className="text-xs">Image failed to load</span>
            </div>
          )}

          {!loaded && !error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="h-5 w-5 animate-spin rounded-full border-2 border-grid border-t-cobalt" />
            </div>
          )}

          {loaded && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setLightboxOpen(true);
              }}
              className="absolute right-2 top-2 rounded-md bg-surface/90 p-1 text-graphite opacity-0 transition-opacity hover:text-cobalt focus-visible:opacity-100 focus-visible:outline-none group-hover:opacity-100"
              aria-label="Open full view"
              title="Open full view"
            >
              <Maximize2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <div className="flex items-center gap-1.5 border-t border-grid bg-surface px-2 py-1.5">
          <ImageIcon className="h-3 w-3 text-graphite" />
          <span className="truncate font-mono text-[11px] text-foreground">
            {title || (chartType ? `${chartType} chart` : fileId)}
          </span>
          <span className="ml-auto truncate font-mono text-[10px] uppercase tracking-[0.08em] text-graphite">
            {chartType || "image"}
          </span>
        </div>
      </div>

      <ImageLightbox
        fileId={fileId}
        title={title}
        isOpen={lightboxOpen}
        onClose={() => setLightboxOpen(false)}
      />
    </div>
  );
}
