import { useTranslate } from "../i18n/useTranslate";

interface DeleteConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  selectedCount: number;
}

export function DeleteConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  selectedCount,
}: DeleteConfirmDialogProps) {
  const t = useTranslate();

  if (!isOpen) return null;

  return (
    <>
      <div className="dialog-overlay" onClick={onClose} />
      <div
        className="dialog-content"
        role="dialog"
        aria-labelledby="delete-dialog-title"
        aria-modal="true"
      >
        <div className="dialog-header">
          <h2 id="delete-dialog-title">
            {t("dialog.confirmDelete", "确认删除")}
          </h2>
          <button
            className="dialog-close"
            type="button"
            aria-label={t("dialog.close", "关闭")}
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <div className="dialog-body">
          <p>
            {t("dialog.deleteWarning", "确定要删除这")}{" "}
            <strong>{selectedCount}</strong> {t("dialog.itemsUnit", "项吗？")}
            {t("dialog.cannotUndo", "此操作无法撤销。")}
          </p>
        </div>
        <div className="dialog-footer">
          <button className="btn-secondary" type="button" onClick={onClose}>
            {t("dialog.cancel", "取消")}
          </button>
          <button className="btn-danger" type="button" onClick={onConfirm}>
            {t("dialog.delete", "删除")}
          </button>
        </div>
      </div>
    </>
  );
}
