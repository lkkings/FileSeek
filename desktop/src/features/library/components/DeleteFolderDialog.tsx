import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FolderRecord } from "../types";
import "./library.css";

interface DeleteFolderDialogProps {
  folder: FolderRecord;
  submitting: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}

export function DeleteFolderDialog({ folder, submitting, error, onClose, onConfirm }: DeleteFolderDialogProps) {
  const t = useTranslate();
  const hasFiles = folder.fileCount > 0;

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target && !submitting) onClose(); }}>
      <div className="delete-dialog modal-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-dialog-title">
        <div className="delete-dialog-heading">
          <div className="warning-icon"><Icon name="trash" size={27} /></div>
          <div className="dialog-header delete-header">
            <div>
              <span className="dialog-kicker is-danger">{t("folder.deleteKicker", "危险操作")}</span>
              <h2 id="delete-dialog-title">{t("folder.deleteTitle", "删除文件夹")}</h2>
              <p>{t("folder.deleteTarget", "确定要删除这个文件夹吗？")}</p>
            </div>
            <button className="dialog-close" type="button" aria-label={t("dialog.close", "关闭")} onClick={onClose} disabled={submitting}><Icon name="close" size={21} /></button>
          </div>
        </div>

        <div className="delete-target"><Icon name="folder" size={28} /><strong>{folder.name}</strong></div>
        <p className={`delete-warning ${hasFiles ? "is-blocked" : ""}`} role="alert">
          {hasFiles ? `${t("folder.nonEmpty", "该文件夹包含")} ${folder.fileCount} ${t("folder.fileCountSuffix", "个文件，无法删除。请先处理文件后再试。")}` : t("folder.deleteWarning", "删除后文件夹将无法恢复，请确认此操作。")}
        </p>
        {error && <p className="dialog-error" role="alert">{error}</p>}
        <div className="dialog-actions">
          <button className="dialog-secondary" type="button" onClick={onClose} disabled={submitting}>{t("dialog.cancel", "取消")}</button>
          <button className="dialog-danger" type="button" onClick={onConfirm} disabled={hasFiles || submitting}><Icon name="trash" size={18} /><span>{submitting ? t("dialog.deleting", "删除中...") : t("folder.confirmDelete", "确认删除")}</span></button>
        </div>
      </div>
    </div>
  );
}
