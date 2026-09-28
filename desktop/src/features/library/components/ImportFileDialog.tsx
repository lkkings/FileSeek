import { useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { StorageLocation } from "../../settings/types";
import type { BatchImportState, ImportFileSelection } from "../types";
import { useStorageDirectory } from "../hooks/useStorageDirectory";
import "./library.css";

interface ImportFileDialogProps {
  folderName: string;
  storageLocations: StorageLocation[];
  importState: BatchImportState;
  onStart: (selections: ImportFileSelection[]) => Promise<boolean>;
  onClose: () => void;
}

function selectionKey(selection: ImportFileSelection) {
  return `${selection.storageId}:${selection.path}`;
}

function isBrowsable(location: StorageLocation) {
  return (
    location.status === "active" &&
    location.type !== "external" &&
    (location.type === "local" || location.protocol === "mounted")
  );
}

function fileName(path: string) {
  const parts = path.split("/").filter(Boolean);
  return parts[parts.length - 1] ?? path;
}

function parentPath(path: string) {
  const normalized = path.replace(/[\\/]+/g, "/").replace(/\/+$/, "");
  if (normalized === "" || normalized === "/") return "";
  const separatorIndex = normalized.lastIndexOf("/");
  if (separatorIndex === -1) return "";
  if (separatorIndex === 0) return "/";
  return normalized.slice(0, separatorIndex);
}

export function ImportFileDialog({
  folderName,
  storageLocations,
  importState,
  onStart,
  onClose,
}: ImportFileDialogProps) {
  const t = useTranslate();
  const browsableLocations = useMemo(
    () => storageLocations.filter(isBrowsable),
    [storageLocations],
  );
  const [selectedStorageId, setSelectedStorageId] = useState(
    () => browsableLocations[0]?.id ?? "",
  );
  const dialogRef = useRef<HTMLElement | null>(null);
  const [pathsByStorage, setPathsByStorage] = useState<Record<string, string>>({});
  const [selections, setSelections] = useState<Record<string, ImportFileSelection>>({});
  const activeLocation = browsableLocations.find(
    (location) => location.id === selectedStorageId,
  ) ?? browsableLocations[0];
  const activeStorageId = activeLocation?.id ?? "";
  const requestedPath = pathsByStorage[activeStorageId] ?? "";
  const directory = useStorageDirectory(activeStorageId || null, requestedPath);
  const currentPath = directory.currentPath || requestedPath;
  const canNavigateUp = currentPath !== "" && currentPath !== "/";
  const selectedItems = Object.values(selections);
  const importing = importState.status === "starting" || importState.status === "running";
  const showProgress =
    importing || importState.status === "completed" || importState.status === "failed";
  const totalItems = importState.total || importState.items.length;
  const importProgressPercent = totalItems === 0
    ? 0
    : Math.round(((importState.succeeded + importState.failed) / totalItems) * 100);

  useEffect(() => {
    dialogRef.current?.focus();
  }, []);


  function navigate(path: string) {
    setPathsByStorage((current) => ({
      ...current,
      [activeStorageId]: path,
    }));
  }

  function toggleSelection(path: string) {
    const selection: ImportFileSelection = {
      storageId: activeStorageId,
      path,
    };
    setSelections((current) => {
      const next = { ...current };
      const key = selectionKey(selection);
      if (next[key]) delete next[key];
      else next[key] = selection;
      return next;
    });
  }

  function selectAll() {
    setSelections((current) => {
      const next = { ...current };
      for (const entry of directory.entries) {
        if (entry.kind !== "file") continue;
        const selection: ImportFileSelection = {
          storageId: activeStorageId,
          path: entry.source_path,
        };
        next[selectionKey(selection)] = selection;
      }
      return next;
    });
  }

  function invertSelection() {
    setSelections((current) => {
      const next = { ...current };
      for (const entry of directory.entries) {
        if (entry.kind !== "file") continue;
        const key = `${activeStorageId}:${entry.source_path}`;
        if (next[key]) delete next[key];
        else {
          next[key] = {
            storageId: activeStorageId,
            path: entry.source_path,
          };
        }
      }
      return next;
    });
  }

  async function handleStart() {
    await onStart(selectedItems);
  }

  return (
    <div
      className="modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="modal-dialog import-dialog"
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="import-dialog-title"
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
        }}
      >
        <header className="dialog-header import-dialog-header">
          <div>
            <p className="dialog-kicker">{t("import.kicker", "批量导入")}</p>
            <h2 id="import-dialog-title">
              {t("import.title", "导入文件到")} {folderName}
            </h2>
            <p>
              {showProgress
                ? t("import.progressDescription", "导入会继续在后台运行，关闭窗口不会取消任务。")
                : t("import.description", "选择一个或多个文件，导入过程不会修改原始文件。")}
            </p>
          </div>
          <button
            type="button"
            className="dialog-close"
            aria-label={t("dialog.close", "关闭")}
            onClick={onClose}
          >
            <Icon name="close" size={18} />
          </button>
        </header>

        {showProgress ? (
          <div className="import-progress" aria-live="polite">
            <div className="import-progress-summary">
              <span>
                {t("import.total", "总计")} {importState.total}
              </span>
              <span>
                {t("import.succeeded", "成功")} {importState.succeeded}
              </span>
              <span>
                {t("import.failed", "失败")} {importState.failed}
              </span>
              <span>
                {t("import.progress", "进度")}{" "}
                {importProgressPercent}%
              </span>
            </div>
            <div
              className="import-progress-bar"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={importProgressPercent}
            >
              <span style={{ width: `${importProgressPercent}%` }} />
            </div>
            <ul className="import-progress-list">
              {importState.items.map((item) => (
                <li
                  key={`${item.storageId}:${item.path}`}
                  className={`import-progress-item is-${item.state}`}
                >
                  <Icon name="document" size={16} />
                  <span>{fileName(item.path)}</span>
                  <span>{t(`import.state.${item.state}`, item.state)}</span>
                  {item.stage && <span>{item.stage}</span>}
                  {item.progress > 0 && item.state === "processing" && (
                    <span>{item.progress}%</span>
                  )}
                  {item.error && <span>{item.error}</span>}
                </li>
              ))}
            </ul>
            {importState.error && <p className="dialog-error">{importState.error}</p>}
          </div>
        ) : (
          <>
            {browsableLocations.length === 0 ? (
              <p className="import-empty">
                {t("import.noBrowsableStorage", "没有可浏览的存储位置")}
              </p>
            ) : (
              <>
                <div
                  className="import-storage-tabs"
                  role="tablist"
                  aria-label={t("import.storageTabs", "存储位置")}
                  onKeyDown={(event) => {
                    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
                    const delta = event.key === "ArrowRight" ? 1 : -1;
                    const currentIndex = browsableLocations.findIndex(
                      (location) => location.id === activeStorageId,
                    );
                    const nextIndex =
                      (currentIndex + delta + browsableLocations.length) % browsableLocations.length;
                    const nextLocation = browsableLocations[nextIndex];
                    if (!nextLocation) return;
                    setSelectedStorageId(nextLocation.id);
                    document
                      .getElementById(`import-tab-${nextLocation.id}`)
                      ?.focus();
                    event.preventDefault();
                  }}
                >
                  {browsableLocations.map((location) => (
                    <button
                      key={location.id}
                      id={`import-tab-${location.id}`}
                      type="button"
                      role="tab"
                      aria-selected={activeStorageId === location.id}
                      aria-controls="import-directory-panel"
                      tabIndex={activeStorageId === location.id ? 0 : -1}
                      className={activeStorageId === location.id ? "is-active" : ""}
                      onClick={() => setSelectedStorageId(location.id)}
                    >
                      <Icon name={location.type === "local" ? "folder" : "nas"} size={16} />
                      <span>{location.name}</span>
                    </button>
                  ))}
                </div>

                <div
                  className="import-directory"
                  id="import-directory-panel"
                  role="tabpanel"
                  aria-labelledby={activeStorageId ? `import-tab-${activeStorageId}` : undefined}
                >
                  <form
                    className="import-directory-toolbar"
                    onSubmit={(event) => {
                      event.preventDefault();
                      const input = event.currentTarget.elements.namedItem("import-path");
                      if (input instanceof HTMLInputElement) navigate(input.value.trim());
                    }}
                  >
                    <button
                      type="button"
                      className="import-parent-button"
                      aria-label={t("import.parentDirectory", "返回上一级")}
                      title={t("import.parentDirectory", "返回上一级")}
                      disabled={!canNavigateUp}
                      onClick={() => navigate(parentPath(currentPath))}
                    >
                      <Icon name="arrowUp" size={16} />
                    </button>
                    <input
                      name="import-path"
                      type="text"
                      key={`${activeStorageId}:${currentPath}`}
                      defaultValue={currentPath}
                      aria-label={t("import.path", "路径")}
                      placeholder={t("import.pathPlaceholder", "粘贴路径或输入上级目录")}
                      spellCheck={false}
                    />
                    <div>
                      <button type="button" onClick={selectAll}>
                        {t("import.selectAll", "全选")}
                      </button>
                      <button type="button" onClick={invertSelection}>
                        {t("import.invertSelection", "反选")}
                      </button>
                    </div>
                  </form>

                  {directory.loading && (
                    <p className="import-empty">{t("import.loading", "正在读取目录...")}</p>
                  )}
                  {directory.error && (
                    <div className="import-error">
                      <p>{directory.error}</p>
                      <button type="button" onClick={directory.retry}>
                        {t("common.retry", "重新加载")}
                      </button>
                    </div>
                  )}
                  {!directory.loading && !directory.error && directory.entries.length === 0 && (
                    <p className="import-empty">{t("import.emptyDirectory", "此目录没有内容")}</p>
                  )}
                  {!directory.loading && !directory.error && directory.entries.length > 0 && (
                    <ul className="import-entry-list">
                      {directory.entries.map((entry) => {
                        const key = `${activeStorageId}:${entry.source_path}`;
                        const selected = Boolean(selections[key]);
                        return (
                          <li key={key}>
                            {entry.kind === "directory" ? (
                              <button
                                type="button"
                                className="import-directory-button"
                                onClick={() => navigate(entry.source_path)}
                              >
                                <Icon name="folder" size={18} />
                                <span>{entry.name}</span>
                              </button>
                            ) : (
                              <label className={selected ? "is-selected" : ""}>
                                <input
                                  type="checkbox"
                                  checked={selected}
                                  onChange={() => toggleSelection(entry.source_path)}
                                />
                                <Icon name="document" size={18} />
                                <span>{entry.name}</span>
                              </label>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              </>
            )}

            <div className="dialog-actions import-dialog-actions">
              <span className="import-selected-count">
                {t("import.selectedCount", "已选择")} {selectedItems.length}
              </span>
              <button type="button" className="dialog-secondary" onClick={onClose}>
                {showProgress
                  ? t("import.closeProgress", "关闭进度")
                  : t("common.cancel", "取消")}
              </button>
              <button
                type="button"
                className="dialog-primary"
                disabled={selectedItems.length === 0}
                onClick={() => void handleStart()}
              >
                <Icon name="import" size={16} />
                {t("import.start", "开始导入")}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
