import { useTranslate } from "../i18n/useTranslate";
import "./delete-confirm-dialog.css";

interface DeleteConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  selectedCount: number;
  confirmDisabled?: boolean;
  title?: string;
  description?: string;
  confirmLabel?: string;
}

export function DeleteConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  selectedCount,
  confirmDisabled = false,
  title,
  description,
  confirmLabel,
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
            {title || t("dialog.confirmDelete", "确认删除")}
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
            {description || t("dialog.deleteWarning", "确定要删除这")}{" "}
            <strong>{selectedCount}</strong>{" "}
            {description ? t("folder.filesCount", "个文件") : t("dialog.itemsUnit", "项吗？")}
            {!description && t("dialog.cannotUndo", "此操作无法撤销。")}
          </p>
        </div>
        <div className="dialog-footer">
          <button className="btn-secondary" type="button" onClick={onClose}>
            {t("dialog.cancel", "取消")}
          </button>
          <button className="btn-danger" type="button" onClick={onConfirm} disabled={confirmDisabled}>
            {confirmLabel || t("dialog.delete", "删除")}
          </button>
        </div>
      </div>
    </>
  );
}
