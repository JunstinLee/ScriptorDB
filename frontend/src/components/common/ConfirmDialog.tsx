import { Button, Modal } from "@heroui/react";

interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel: string;
}

export default function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel,
}: ConfirmDialogProps) {
  return (
    <Modal.Backdrop isOpen={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <Modal.Container size="sm">
        <Modal.Dialog className="sm:max-w-[360px] bg-surface">
          <Modal.CloseTrigger />
          <Modal.Header>
            <Modal.Heading>{title}</Modal.Heading>
          </Modal.Header>
          <Modal.Body>
            <p className="text-sm text-graphite leading-relaxed">{message}</p>
          </Modal.Body>
          <Modal.Footer>
            <Button variant="secondary" onPress={onClose}>
              Cancel
            </Button>
            <Button
              onPress={() => {
                onConfirm();
                onClose();
              }}
            >
              {confirmLabel}
            </Button>
          </Modal.Footer>
        </Modal.Dialog>
      </Modal.Container>
    </Modal.Backdrop>
  );
}
