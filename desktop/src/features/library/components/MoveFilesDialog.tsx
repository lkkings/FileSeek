import { useState, type FormEvent } from "react";

import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FolderRecord } from "../types";
import "./library.css";

interface MoveFilesDialogProps {
  folders: FolderRecord[];
  currentFolderId: string;
  selectedCount: number;
  submitting: boolean;
  onClose: () => void;
  onConfirm: (targetFolderId: string) => void;
}

export function MoveFilesDialog({
  folders,
  currentFolderId,
  selectedCount,
  submitting,
  onClose,
  onConfirm,
}: MoveFilesDialogProps) {
  const t = useTranslate();
  const [targetFolderId, setTargetFolderId] = useState("");
  const destinations = folders.filter((folder) => folder.id !== currentFolderId);

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
        aria-labelledby="move-files-dialog-title"
        onSubmit={handleSubmit}
      >
        <div className="dialog-header">
          <div>
            <span className="dialog-kicker">{t("folder.moveKicker", "整理文件")}</span>
            <h2 id="move-files-dialog-title">{t("folder.moveTitle", "移动文件")}</h2>
            <p>
              {t("folder.moveCountPrefix", "已选择")} {selectedCount}{" "}
              {t("folder.moveCountSuffix", "个文件，请选择目标文件夹。")}
            </p>
          </div>
          <button
            className="dialog-close"
            type="button"
            aria-label={t("dialog.close", "关闭")}
            onClick={onClose}
            disabled={submitting}
          >
            <Icon name="close" size={21} />
          </button>
        </div>

        {destinations.length === 0 ? (
          <p className="dialog-error" role="alert">
            {t("folder.noMoveDestinations", "暂无其他可选择的文件夹。")}
          </p>
        ) : (
          <label className="dialog-field">
            <span>{t("folder.moveDestination", "目标文件夹")}</span>
            <span className="dialog-select-wrap">
              <select
                value={targetFolderId}
                onChange={(event) => setTargetFolderId(event.target.value)}
                disabled={submitting}
                required
              >
                <option value="">{t("folder.selectDestination", "请选择文件夹")}</option>
                {destinations.map((folder) => (
                  <option key={folder.id} value={folder.id}>
                    {folder.name}
                  </option>
                ))}
              </select>
              <Icon name="chevron" size={17} />
            </span>
          </label>
        )}

        <div className="dialog-actions">
          <button className="dialog-secondary" type="button" onClick={onClose} disabled={submitting}>
            {t("dialog.cancel", "取消")}
          </button>
          <button
            className="dialog-primary"
            type="submit"
            disabled={!targetFolderId || destinations.length === 0 || submitting}
          >
            <Icon name="folder" size={18} />
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
