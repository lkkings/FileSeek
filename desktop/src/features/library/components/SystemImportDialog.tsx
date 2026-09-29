import { useState } from "react";

import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { BatchImportState, FolderRecord, ImportFileSelection } from "../types";
import "./library.css";

interface SystemImportDialogProps {
  requestPaths: string[];
  requestErrors: string[];
  selections: ImportFileSelection[];
  invalidPaths: string[];
  unmappedPaths: string[];
  storageRequired: boolean;
  folders: FolderRecord[];
  foldersLoading: boolean;
  foldersError: string | null;
  importState: BatchImportState;
  onConfirm: (folderId: string) => Promise<boolean>;
  onRetry: () => void;
  onClose: () => void;
}

export function SystemImportDialog({
  requestPaths,
  requestErrors,
  selections,
  invalidPaths,
  unmappedPaths,
  storageRequired,
  folders,
  foldersLoading,
  foldersError,
  importState,
  onConfirm,
  onRetry,
  onClose,
}: SystemImportDialogProps) {
  const t = useTranslate();
  const [selectedFolderId, setSelectedFolderId] = useState("");
  const [confirming, setConfirming] = useState(false);
  const importing = importState.status === "starting" || importState.status === "running";
  const hasBlockingErrors = invalidPaths.length > 0 || unmappedPaths.length > 0;

  async function handleConfirm() {
    setConfirming(true);
    await onConfirm(selectedFolderId);
    setConfirming(false);
  }

  return (
    <div className="modal-backdrop">
      <section
        className="dialog import-dialog system-import-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="system-import-title"
      >
        <header className="dialog-header import-dialog-header">
          <div className="dialog-copy import-dialog-copy">
            <p className="dialog-kicker">{t("systemImport.kicker", "系统导入")}</p>
            <h2 id="system-import-title">{t("systemImport.title", "添加文件到 FileSeek")}</h2>
            <p>{t("systemImport.description", "选择目标文件夹后开始批量导入。")}</p>
          </div>
        </header>

        <div className="system-import-content">
          <div>
            <h3>{t("systemImport.receivedFiles", "收到的文件")}</h3>
            <ul className="system-import-file-list" aria-label={t("systemImport.receivedFiles", "收到的文件")}>
              {requestPaths.map((path) => (
                <li key={path} title={path}>
                  <Icon name="document" size={18} />
                  <span>{path}</span>
                </li>
              ))}
            </ul>
          </div>

          {storageRequired && (
            <p className="system-import-error" role="alert">
              {t("systemImport.storageRequired", "需要至少一个可用的存储来源")}
            </p>
          )}
          {requestErrors.length > 0 && (
            <div className="system-import-error" role="alert">
              <p>{t("systemImport.requestErrors", "无法读取以下文件：")}</p>
              <ul>
                {requestErrors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </div>
          )}
          {invalidPaths.length > 0 && (
            <div className="system-import-error" role="alert">
              <p>{t("systemImport.invalidPaths", "以下路径无效：")}</p>
              <ul>
                {invalidPaths.map((path) => (
                  <li key={path}>{path}</li>
                ))}
              </ul>
            </div>
          )}
          {unmappedPaths.length > 0 && (
            <div className="system-import-error" role="alert">
              <p>{t("systemImport.unmappedPaths", "以下路径无法映射到可用存储：")}</p>
              <ul>
                {unmappedPaths.map((path) => (
                  <li key={path}>{path}</li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <h3>{t("systemImport.targetFolder", "目标文件夹")}</h3>
            {foldersLoading && (
              <p className="import-empty">{t("systemImport.loadingFolders", "正在加载文件夹...")}</p>
            )}
            {foldersError && (
              <div className="import-error" role="alert">
                <p>{foldersError}</p>
                <button type="button" onClick={onRetry}>
                  {t("common.retry", "重新加载")}
                </button>
              </div>
            )}
            {!foldersLoading && !foldersError && folders.length === 0 && (
              <p className="import-empty">{t("systemImport.emptyFolders", "暂无可用文件夹")}</p>
            )}
            {!foldersLoading && !foldersError && folders.length > 0 && (
              <fieldset className="system-import-folder-group">
                <legend>{t("systemImport.targetFolder", "目标文件夹")}</legend>
                {folders.map((folder) => (
                  <label key={folder.id}>
                    <input
                      type="radio"
                      name="system-import-folder"
                      value={folder.id}
                      checked={selectedFolderId === folder.id}
                      onChange={() => setSelectedFolderId(folder.id)}
                    />
                    <span>{folder.name}</span>
                  </label>
                ))}
              </fieldset>
            )}
          </div>

          {importState.status !== "idle" && (
            <div className="import-progress" aria-live="polite">
              <div className="import-progress-summary">
                <div className="import-progress-metric">
                  <span>{t("import.total", "总计")}</span>
                  <strong>{importState.total}</strong>
                </div>
                <div className="import-progress-metric">
                  <span>{t("import.succeeded", "成功")}</span>
                  <strong>{importState.succeeded}</strong>
                </div>
                <div className="import-progress-metric">
                  <span>{t("import.failed", "失败")}</span>
                  <strong>{importState.failed}</strong>
                </div>
              </div>
              {importState.error && (
                <p className="import-progress-error" role="alert">
                  {importState.error}
                </p>
              )}
              <ul className="import-progress-list">
                {importState.items.map((item) => (
                  <li key={`${item.storageId}:${item.path}`} className="import-progress-item">
                    <span className="import-progress-file">
                      <Icon name="document" size={18} />
                      <span>{item.path}</span>
                    </span>
                    <span className={`import-progress-state is-${item.state}`}>
                      {t(`import.state.${item.state}`, item.state)}
                    </span>
                    {item.error && <span className="import-progress-details">{item.error}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <div className="dialog-actions import-dialog-actions">
          <span className="import-selected-count">
            {t("systemImport.receivedCount", "文件")}
            <strong>{requestPaths.length}</strong>
          </span>
          <button type="button" className="dialog-secondary" onClick={onClose}>
            {importing
              ? t("import.closeProgress", "关闭进度")
              : t("common.cancel", "取消")}
          </button>
          <button
            type="button"
            className="dialog-primary"
            disabled={
              confirming ||
              importing ||
              selectedFolderId === "" ||
              selections.length === 0 ||
              hasBlockingErrors
            }
            onClick={() => void handleConfirm()}
          >
            <Icon name="import" size={16} />
            {t("import.start", "开始导入")}
          </button>
        </div>
      </section>
    </div>
  );
}
