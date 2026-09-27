import { useState, useEffect, useRef } from "react";
import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FolderRecord } from "../types";
import "./library.css";

interface FolderSectionProps {
  onEnterFolder: (folder: FolderRecord) => void;
  folders: FolderRecord[];
  loading: boolean;
  error: string | null;
  onCreateFolder: () => void;
  onEditFolder: (folder: FolderRecord) => void;
  onRequestDeleteFolder: (folder: FolderRecord) => void;
  onFolderAction: (message: string) => void;
  onRetry: () => void;
}

function formatModifiedDate(dateStr: string): string {
  if (!dateStr) return "";
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    const hr = String(date.getHours()).padStart(2, "0");
    const min = String(date.getMinutes()).padStart(2, "0");
    return `${y}-${m}-${d} ${hr}:${min}`;
  } catch {
    return dateStr;
  }
}

export function FolderSection({ folders, loading, error, onCreateFolder, onEditFolder, onRequestDeleteFolder, onFolderAction, onRetry, onEnterFolder }: FolderSectionProps) {
  const t = useTranslate();
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setActiveMenuId(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

 return (
   <section className="library-section" aria-labelledby="library-title">
     <div className="section-heading">
       <div className="section-title-wrap">
          <Icon name="folder" size={32} />
         <h2 id="library-title">{t("library.title", "全部文件夹")}</h2>
       </div>
        <button className="create-button" type="button" onClick={onCreateFolder}><Icon name="plus" size={14} /><span>{t("library.create", "新建文件夹")}</span></button>
     </div>

      <div className="section-heading-divider" />

     <div className="folder-grid">
        {loading && <div className="empty-state"><p>{t("library.loading", "正在读取文件夹...")}</p></div>}
        {!loading && error && <div className="empty-state"><p>{error}</p><button type="button" onClick={onRetry}>{t("library.retry", "重新加载")}</button></div>}
        {!loading && !error && folders.map((folder, index) => {
          const isMenuOpen = activeMenuId === folder.id;
          return (
            <article className="folder-card" key={folder.id} style={{ cursor: "pointer" }} onClick={(e) => { if (e.target instanceof HTMLElement && (e.target.closest(".folder-actions") || e.target.closest(".more-dropdown-container"))) return; onEnterFolder(folder); }}>
              <div className="folder-card-top">
                <div className="folder-illustration"><Icon name="folder" size={58} /></div>
                <div className="folder-actions">
                  <button type="button" aria-label={t("folder.importFile", "导入文件")} title={t("folder.importFile", "导入文件")} onClick={(e) => { e.stopPropagation(); onFolderAction(`${t("folder.importFileSuccess", "已导入文件到")} “${folder.name}”`); }}><Icon name="document" size={18} /></button>
                  <button type="button" aria-label={t("folder.importFolder", "导入文件夹")} title={t("folder.importFolder", "导入文件夹")} onClick={(e) => { e.stopPropagation(); onFolderAction(`${t("folder.importFolderSuccess", "已导入文件夹到")} “${folder.name}”`); }}><Icon name="folder" size={18} /></button>
                  <div className="more-dropdown-container" style={{ position: "relative" }} ref={isMenuOpen ? dropdownRef : null}>
                    <button type="button" aria-label={t("folder.more", "更多")} title={t("folder.more", "更多")} onClick={(e) => { e.stopPropagation(); setActiveMenuId(isMenuOpen ? null : folder.id); }}><Icon name="more" size={21} /></button>
                    {isMenuOpen && (
                      <div className="folder-more-dropdown">
                        <button type="button" onClick={(e) => { e.stopPropagation(); onEditFolder(folder); setActiveMenuId(null); }}><Icon name="edit" size={14} /><span>{t("folder.edit", "编辑")}</span></button>
                        <button type="button" onClick={(e) => { e.stopPropagation(); onRequestDeleteFolder(folder); setActiveMenuId(null); }}><Icon name="trash" size={14} /><span>{t("folder.delete", "删除")}</span></button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <h3>{folder.name}</h3>
              <p>{folder.description}</p>
              <div className="folder-meta-row">
                <time><Icon name="clock" size={14} />{formatModifiedDate(folder.modified)}</time>
                <span className="folder-files-count">
                  <Icon name="document" size={14} />
                  <span>{folder.fileCount} {t("folder.filesCountUnit", "个文件")}</span>
                </span>
              </div>
              {index > 0 && <span className="folder-index">{index + 1}</span>}
            </article>
          );
        })}
        {!loading && !error && folders.length === 0 && <div className="empty-state"><Icon name="search" size={28} /><p>{t("library.empty", "没有找到匹配的文件夹")}</p><button type="button" onClick={onCreateFolder}>{t("library.emptyAction", "新建文件夹")}</button></div>}
      </div>
    </section>
  );
}
