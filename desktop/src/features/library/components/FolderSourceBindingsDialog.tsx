import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { StorageLocation } from "../../settings/types";
import { useFolderSourceBindings } from "../hooks/useFolderSourceBindings";
import { useStorageDirectory } from "../hooks/useStorageDirectory";
import type { FolderSourceBinding } from "../types";
import "./library.css";

interface FolderSourceBindingsDialogProps {
  folderId: string;
  folderName: string;
  storageLocations: StorageLocation[];
  onClose: () => void;
}

function isBrowsable(location: StorageLocation) {
  return (
    location.status === "active" &&
    (location.type === "local" || (location.type === "nas" && location.protocol === "mounted"))
  );
}

function parentPath(path: string) {
  const normalized = path.replace(/[\\/]+/g, "/").replace(/\/+$/, "");
  if (normalized === "" || normalized === "/") return "";
  const separatorIndex = normalized.lastIndexOf("/");
  if (separatorIndex === -1) return "";
  if (separatorIndex === 0) return "/";
  return normalized.slice(0, separatorIndex);
}

export function FolderSourceBindingsDialog({
  folderId,
  folderName,
  storageLocations,
  onClose,
}: FolderSourceBindingsDialogProps) {
  const t = useTranslate();
  const dialogRef = useRef<HTMLElement | null>(null);
  const browsableLocations = useMemo(
    () => storageLocations.filter(isBrowsable),
    [storageLocations],
  );
  const [selectedStorageId, setSelectedStorageId] = useState(
    () => browsableLocations[0]?.id ?? "",
  );
  const [pathsByStorage, setPathsByStorage] = useState<Record<string, string>>({});
  const [recursive, setRecursive] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const activeLocation = browsableLocations.find(
    (location) => location.id === selectedStorageId,
  ) ?? browsableLocations[0];
  const activeStorageId = activeLocation?.id ?? "";
  const requestedPath = pathsByStorage[activeStorageId] ?? "";
  const directory = useStorageDirectory(activeStorageId || null, requestedPath);
  const currentPath = directory.currentPath || requestedPath;
  const canBind = currentPath.trim() !== "";
  const {
    bindings,
    loading,
    error,
    retry,
    createBinding,
    updateBinding,
    deleteBinding,
  } = useFolderSourceBindings(folderId);
  const directories = Array.isArray(directory.entries)
    ? directory.entries.filter((entry) => entry.kind === "directory")
    : [];

  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  function navigate(path: string) {
    setPathsByStorage((current) => ({
      ...current,
      [activeStorageId]: path,
    }));
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeLocation || !canBind) return;
    setActionError(null);
    const error = await createBinding({
      storageId: activeStorageId,
      path: currentPath,
      recursive,
      enabled: true,
    });
    setActionError(error);
  }

  async function handleToggle(binding: FolderSourceBinding) {
    setActionError(null);
    const error = await updateBinding(binding.id, {
      storageId: binding.storageId,
      path: binding.sourcePath,
      recursive: binding.recursive,
      enabled: !binding.enabled,
    });
    setActionError(error);
  }

  async function handleDelete(binding: FolderSourceBinding) {
    setActionError(null);
    const error = await deleteBinding(binding.id);
    setActionError(error);
  }

  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) onClose();
      }}
    >
      <section
        className="modal-dialog folder-sources-dialog"
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="folder-sources-title"
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
        }}
      >
        <header className="folder-sources-header">
          <div>
            <span className="dialog-kicker">
              <Icon name="folder" size={16} />
              {t("folderSources.kicker", "监听")}
            </span>
            <h2 id="folder-sources-title">{t("folderSources.title", "文件夹来源")}</h2>
            <p>
              {t("folderSources.description", "为")} {folderName}{" "}
              {t("folderSources.descriptionSuffix", "绑定一个或多个存储目录")}
            </p>
          </div>
          <button
            className="dialog-close"
            type="button"
            aria-label={t("dialog.close", "关闭")}
            title={t("dialog.close", "关闭")}
            onClick={onClose}
          >
            <Icon name="close" size={21} />
          </button>
        </header>

        <div className="folder-sources-body">
          <section className="folder-sources-section" aria-labelledby="folder-sources-bindings-title">
            <div className="folder-sources-section-header">
              <h3 id="folder-sources-bindings-title">
                {t("folderSources.bindingsTitle", "已绑定来源")}
              </h3>
              <span className="folder-source-count">{bindings.length}</span>
            </div>

            <div className="folder-sources-list" aria-live="polite">
              {loading && <p className="folder-sources-state">{t("folderSources.loading", "正在读取来源绑定...")}</p>}
              {!loading && error && (
                <div className="folder-sources-state is-error">
                  <p>{error}</p>
                  <button type="button" onClick={retry}>
                    {t("common.retry", "重新加载")}
                  </button>
                </div>
              )}
              {!loading && !error && bindings.length === 0 && (
                <div className="folder-sources-empty">
                  <Icon name="folder" size={24} />
                  <p>{t("folderSources.empty", "尚未绑定来源目录")}</p>
                </div>
              )}
              {!loading && !error && bindings.map((binding) => {
                const locationName = storageLocations.find(
                  (location) => location.id === binding.storageId,
                )?.name ?? binding.storageId;
                const locationIcon = storageLocations.find(
                  (location) => location.id === binding.storageId,
                )?.type === "nas" ? "nas" : "folder";
                return (
                  <article
                    className={`folder-source-item is-${binding.watchStatus}`}
                    key={binding.id}
                  >
                    <span className="folder-source-icon" aria-hidden="true">
                      <Icon name={locationIcon} size={20} />
                    </span>
                    <div className="folder-source-content">
                      <div className="folder-source-title-row">
                        <strong>{locationName}</strong>
                        <span className="folder-source-status">
                          {watchStatusText(binding.watchStatus, t)}
                        </span>
                      </div>
                      <span className="folder-source-path">{binding.sourcePath}</span>
                      <span className="folder-source-scope">
                        {binding.recursive
                          ? t("folderSources.recursive", "包含子目录")
                          : t("folderSources.directOnly", "仅当前目录")}
                      </span>
                      {binding.lastError && <small>{binding.lastError}</small>}
                    </div>
                    <div className="folder-source-actions">
                      <label className="folder-source-switch">
                        <input
                          type="checkbox"
                          checked={binding.enabled}
                          onChange={() => void handleToggle(binding)}
                        />
                        <span className="folder-source-switch-track" aria-hidden="true" />
                        <span>{t("folderSources.enabled", "启用")}</span>
                      </label>
                      <button type="button" onClick={() => void handleDelete(binding)}>
                        <Icon name="trash" size={15} />
                        {t("folderSources.delete", "删除")}
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          </section>

          <form className="folder-sources-form" onSubmit={handleCreate}>
            <div className="folder-sources-section-header">
              <h3>{t("folderSources.addTitle", "添加来源")}</h3>
              <p>{t("folderSources.addDescription", "绑定后扫描现有可识别文件，新文件会自动导入并进入任务队列")}</p>
            </div>
            {browsableLocations.length === 0 ? (
              <p className="folder-sources-state">{t("import.noBrowsableStorage", "没有可浏览的存储位置")}</p>
            ) : (
              <>
              <div className="import-storage-tabs" role="tablist" aria-label={t("import.storageTabs", "存储位置")}>
                {browsableLocations.map((location) => (
                  <button
                    key={location.id}
                    type="button"
                    role="tab"
                    aria-selected={activeStorageId === location.id}
                    className={activeStorageId === location.id ? "is-active" : ""}
                    onClick={() => setSelectedStorageId(location.id)}
                  >
                    <Icon name={location.type === "local" ? "folder" : "nas"} size={16} />
                    <span>{location.name}</span>
                  </button>
                ))}
              </div>

              <div className="import-directory">
                <div className="import-directory-toolbar">
                  <div className="import-path-controls">
                    <button
                      type="button"
                      className="import-parent-button"
                      disabled={currentPath === "" || currentPath === "/"}
                      onClick={() => navigate(parentPath(currentPath))}
                    >
                      <Icon name="arrowUp" size={16} />
                    </button>
                    <input
                      type="text"
                      key={`${activeStorageId}:${currentPath}`}
                      defaultValue={currentPath}
                      aria-label={t("import.path", "路径")}
                      onBlur={(event) => {
                        const value = event.currentTarget.value.trim();
                        if (value !== currentPath) navigate(value);
                      }}
                    />
                  </div>
                </div>
                {directory.loading && <p className="import-empty">{t("import.loading", "正在读取目录...")}</p>}
                {directory.error && <p className="import-error">{directory.error}</p>}
                {!directory.loading && !directory.error && directories.length === 0 && (
                  <p className="import-empty">{t("import.emptyDirectory", "此目录没有内容")}</p>
                )}
                <ul className="import-entry-list">
                  {directories.map((entry) => (
                    <li key={entry.source_path}>
                      <button
                        type="button"
                        className="import-directory-button"
                        onClick={() => navigate(entry.source_path)}
                      >
                        <Icon name="folder" size={18} />
                        <span>{entry.name}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>

              <label className="folder-source-recursive">
                <input
                  type="checkbox"
                  checked={recursive}
                  onChange={(event) => setRecursive(event.target.checked)}
                />
                <span>{t("folderSources.recursive", "包含子目录")}</span>
              </label>
              {actionError && <p className="dialog-error" role="alert">{actionError}</p>}
              <div className="dialog-actions">
                <button className="dialog-primary" type="submit" disabled={!canBind}>
                  <Icon name="plus" size={18} />
                  <span>{t("folderSources.add", "绑定当前目录")}</span>
                </button>
              </div>
              </>
            )}
          </form>
        </div>
      </section>
    </div>
  );
}

function watchStatusText(
  status: FolderSourceBinding["watchStatus"],
  t: ReturnType<typeof useTranslate>,
) {
  if (status === "watching") return t("folderSources.status.watching", "监听中");
  if (status === "unavailable") return t("folderSources.status.unavailable", "来源不可用");
  if (status === "error") return t("folderSources.status.error", "出现错误");
  return t("folderSources.status.disabled", "已停用");
}
