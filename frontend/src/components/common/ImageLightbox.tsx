import { useEffect } from "react";
import { Modal } from "@heroui/react";
import { Download, X } from "lucide-react";
import { getImageUrl, downloadImage } from "../../api/files";

interface ImageLightboxProps {
  fileId: string;
  title?: string;
  isOpen: boolean;
  onClose: () => void;
}

export default function ImageLightbox({
  fileId,
  title,
  isOpen,
  onClose,
}: ImageLightboxProps) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose]);

  return (
    <Modal.Backdrop
      isOpen={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      className="bg-ink/80 backdrop-blur-sm"
    >
      <Modal.Container
        size="full"
        scroll="inside"
        className="max-w-none max-h-none bg-transparent shadow-none"
      >
        <Modal.Dialog className="flex h-screen max-h-screen w-screen max-w-none flex-col items-center justify-center gap-3 bg-transparent p-4 shadow-none sm:p-8">
          <div className="absolute right-3 top-3 z-10 flex items-center gap-2">
            <button
              type="button"
              onClick={() => downloadImage(fileId, title || fileId)}
              className="flex items-center gap-1.5 rounded-md border border-grid bg-surface/95 px-3 py-1.5 text-xs text-foreground transition-colors hover:text-cobalt focus-cobalt"
              aria-label="Download image"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Download</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-grid bg-surface/95 p-1.5 text-foreground transition-colors hover:text-cobalt focus-cobalt"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <img
            src={getImageUrl(fileId)}
            alt={title || "Generated chart"}
            draggable={false}
            className="max-h-[80vh] max-w-[90vw] rounded-md border border-grid bg-surface object-contain shadow-2xl"
          />

          {title && (
            <div className="max-w-[90vw] truncate text-center font-mono text-xs text-graphite">
              {title}
            </div>
          )}
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  );
}
