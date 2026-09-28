import { useState, type FormEvent } from "react";

import { Icon } from "./Icon";
import { useTranslate } from "../i18n/useTranslate";
import "./move-to-folder-dialog.css";

interface MoveToFolderDialogProps {
  isOpen: boolean;
  folders: Array<{ id: string; name: string }>;
  loading?: boolean;
  error?: string | null;
  excludeFolderId?: string | null;
  selectedCount: number;
  submitting?: boolean;
  onClose: () => void;
  onConfirm: (targetFolderId: string) => void;
}

export function MoveToFolderDialog({
  isOpen,
  folders,
  loading = false,
  error = null,
  excludeFolderId = null,
  selectedCount,
  submitting = false,
  onClose,
  onConfirm,
}: MoveToFolderDialogProps) {
  const t = useTranslate();
  const [targetFolderId, setTargetFolderId] = useState("");
  const availableFolders = folders.filter((folder) => folder.id !== excludeFolderId);

  if (!isOpen) return null;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!targetFolderId || submitting) return;
    onConfirm(targetFolderId);
  };

  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target && !submitting) onClose();
      }}
    >
      <form
        className="folder-dialog modal-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="move-to-folder-dialog-title"
        onSubmit={handleSubmit}
      >
        <div className="dialog-header">
          <div>
            <span className="dialog-icon">
              <Icon name="folder" size={18} />
            </span>
            <h3 id="move-to-folder-dialog-title">
              {t("batch.confirmMoveTitle", "确认批量移动")}
            </h3>
          </div>
          <button type="button" className="dialog-close" onClick={onClose} disabled={submitting}>
            <Icon name="close" size={16} />
          </button>
        </div>

        <p className="delete-warning">
          {t("batch.confirmMoveDesc", "将选中的")} <strong>{selectedCount}</strong>
          {t("batch.confirmMoveDescSuffix", "个文件移动到指定文件夹")}
        </p>

        {loading && <p className="folder-dialog-status">{t("common.loading", "正在加载...")}</p>}
        {error && <p className="folder-dialog-error">{error}</p>}
        {!loading && !error && availableFolders.length === 0 && (
          <p className="folder-dialog-status">{t("folder.noAvailableFolders", "没有可选的文件夹")}</p>
        )}

        {!loading && !error && availableFolders.length > 0 && (
          <div className="move-folder-options" role="radiogroup" aria-label={t("batch.moveTo", "移动到")}>
            {availableFolders.map((folder) => (
              <button
                key={folder.id}
                type="button"
                role="radio"
                aria-checked={targetFolderId === folder.id}
                className={targetFolderId === folder.id ? "is-selected" : ""}
                onClick={() => setTargetFolderId(folder.id)}
              >
                <Icon name="folder" size={16} />
                <span>{folder.name}</span>
              </button>
            ))}
          </div>
        )}

        <div className="dialog-actions">
          <button type="button" className="dialog-secondary" onClick={onClose} disabled={submitting}>
            {t("dialog.cancel", "取消")}
          </button>
          <button
            type="submit"
            className="dialog-primary"
            disabled={!targetFolderId || availableFolders.length === 0 || submitting}
          >
            <Icon name="folder" size={16} />
            <span>
              {submitting
                ? t("folder.moving", "移动中...")
                : t("folder.confirmMove", "确认移动")}
            </span>
          </button>
        </div>
      </form>
    </div>
  );
}
