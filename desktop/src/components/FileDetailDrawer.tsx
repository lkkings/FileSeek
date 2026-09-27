import { Icon } from "./Icon";
import { useTranslate } from "../i18n/useTranslate";
import type { FileItem } from "../services/api/search";

interface FileDetailDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  file: FileItem | null;
  onOpenAction: (file: FileItem) => void;
}

export function FileDetailDrawer({
  isOpen,
  onClose,
  file,
  onOpenAction,
}: FileDetailDrawerProps) {
  const t = useTranslate();

  if (!isOpen || !file) return null;

  const isVideo = file.category === "video";
  const scene = file.metadata?.scene;
  const duration = file.metadata?.duration;

  const formattedSize = file.size
    ? `${(file.size / (1024 * 1024)).toFixed(1)} MB`
    : "0.0 MB";

  let formattedDate = file.modified || "";
  if (formattedDate && formattedDate.includes("T")) {
    const date = new Date(formattedDate);
    if (!Number.isNaN(date.getTime())) {
      const pad = (part: number) => part.toString().padStart(2, "0");
      formattedDate = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
    }
  }

  const handleOpenAction = () => {
    onOpenAction(file);
  };

  return (
    <>
      <div className="sidebar-backdrop" onClick={onClose} />
      <aside className="result-sidebar">
        <div className="sidebar-header">
          <h3>{t("search.details", "文件详情")}</h3>
        </div>
        <div className="sidebar-scroll-content">
          <div className="sidebar-preview-container">
            {scene ? (
              <div className={`preview-thumb scene-${scene}`} style={{ width: "100%", height: "100%" }}>
                {isVideo && (
                  <span className="preview-play">
                    <Icon name="video" size={18} />
                  </span>
                )}
                <span className="preview-label">
                  {isVideo ? duration : t("search.previewLabel", "预览")}
                </span>
              </div>
            ) : (
              <div className="sidebar-preview-fallback">
                <Icon name="document" size={36} />
              </div>
            )}
          </div>
          <div className="sidebar-file-info">
            <h4 className="sidebar-file-title">{file.file_name}</h4>
            <div className="sidebar-meta-grid">
              <span className="sidebar-meta-label">{t("search.filePath", "路径")}</span>
              <span className="sidebar-meta-value">{file.path}</span>
              <span className="sidebar-meta-label">{t("search.fileDate", "日期")}</span>
              <span className="sidebar-meta-value">{formattedDate}</span>
              <span className="sidebar-meta-label">{t("search.fileSize", "大小")}</span>
              <span className="sidebar-meta-value">{formattedSize}</span>
            </div>
            {file.tags && file.tags.length > 0 && (
              <div className="sidebar-tags-container">
                {file.tags.map((tag, idx) => (
                  <span className="result-tag tag-blue" key={`tag-${idx}`}>
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="sidebar-actions">
            <button
              className="sidebar-action-btn btn-primary"
              type="button"
              onClick={handleOpenAction}
            >
              <Icon name="eye" size={18} />
              <span>{t("search.open", "打开")}</span>
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
