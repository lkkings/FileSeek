import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "../../i18n/useTranslation";
import { FilePreviewModal } from "../../components/ui/FilePreviewModal";
import {
  fetchRecentFiles,
  formatModified,
  formatSize,
  recordAccess,
  toCategory,
} from "../../api/library";
import { defaultClient, type ApiClient } from "../../api/client";

interface RecentFileItem {
  id: string;
  name: string;
  category: "image" | "video" | "document" | "other";
  size: string;
  /** 访问时间，已格式化成 `YYYY-MM-DD HH:mm`。 */
  date: string;
  path: string;
}

interface RecentAccessProps {
  activeCategory?: "all" | "document" | "image" | "video";
  /** 覆盖用的客户端，只给测试用。 */
  client?: ApiClient;
}

export function RecentAccess({ activeCategory = "all", client }: RecentAccessProps) {
  const api = client ?? defaultClient;
  const { t } = useTranslation();
  const [layoutMode, setLayoutMode] = useState<"list" | "grid">("list");
  const [previewFile, setPreviewFile] = useState<RecentFileItem | null>(null);
  const [recentFiles, setRecentFiles] = useState<RecentFileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const loadVersion = useRef(0);

  /**
   * 读最近访问。
   *
   * `GET /library/recent` 只给 `{file_id, accessed_at}`，名字/体积/路径要靠
   * `GET /library/files/{id}` 逐条补——`fetchRecentFiles` 负责去重和跳过已被永久删除的
   * 文件（见 api/library.ts）。
   */
  const load = useCallback(async () => {
    const version = ++loadVersion.current;
    setLoading(true);
    setError(null);
    try {
      const records = await fetchRecentFiles(api);
      if (version !== loadVersion.current) return;
      setRecentFiles(
        records.map(({ file, accessedAt }) => ({
          id: file.id,
          name: file.name,
          category: toCategory(file.FileType),
          size: formatSize(file.size),
          date: formatModified(accessedAt),
          path: file.path,
        })),
      );
    } catch (cause) {
      if (version === loadVersion.current) {
        setError(cause instanceof Error ? cause.message : "无法读取最近访问记录");
      }
    } finally {
      if (version === loadVersion.current) setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    // 同 useLibrary：推到微任务里，避免在 effect 里同步 setState 触发级联渲染。
    void Promise.resolve().then(load);
    return () => { loadVersion.current += 1; };
  }, [load]);

  /** 打开预览也算一次访问，记一笔并把本条挪到最前。 */
  const handleOpenPreview = (file: RecentFileItem) => {
    setPreviewFile(file);
    void recordAccess(file.id, api).then(load);
  };

  // Helper to dynamically calculate human-friendly relative dates
  const getRelativeTimeStr = (dateStr: string) => {
    try {
      const now = new Date();
      const fileDate = new Date(dateStr.replace(" ", "T"));
      const diffMs = now.getTime() - fileDate.getTime();
      if (diffMs <= 0) return `刚刚 (${dateStr})`;
      
      const diffMins = Math.floor(diffMs / (1000 * 60));
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
      const diffMonths = Math.floor(diffMs / (1000 * 60 * 60 * 24 * 30.5));
      
      if (diffMins < 60) return `${diffMins}分钟前 (${dateStr.substring(11, 16)})`;
      if (diffHours < 24) return `${diffHours}小时前 (${dateStr.substring(11, 16)})`;
      if (diffDays < 30) return `${diffDays}天前`;
      return `${diffMonths}个月前`;
    } catch {
      return dateStr;
    }
  };

  // Filter based on globally passed activeCategory
  const filteredFiles = activeCategory === "all"
    ? recentFiles
    : recentFiles.filter(f => f.category === activeCategory);

  const getIcon = (fileName: string, category: string) => {
    const ext = fileName.split(".").pop()?.toLowerCase();
    if (category === "image") {
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#10b981", flexShrink: 0 }}>
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
      );
    }
    if (category === "video") {
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#f59e0b", flexShrink: 0 }}>
          <polygon points="23 7 16 12 23 17 23 7" />
          <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
        </svg>
      );
    }

    switch (ext) {
      case "pdf":
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#ef4444", flexShrink: 0 }}>
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        );
      case "doc":
      case "docx":
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#3b82f6", flexShrink: 0 }}>
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="8" y1="13" x2="16" y2="13" />
          </svg>
        );
      case "sh":
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#a855f7", flexShrink: 0 }}>
            <polyline points="16 18 22 12 16 6" />
            <polyline points="8 6 2 12 8 18" />
          </svg>
        );
      default:
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#9ca3af", flexShrink: 0 }}>
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
        );
    }
  };

  const getThumbnailStyle = (fileName: string, category: string) => {
    if (category === "image") {
      if (fileName.includes("猫")) {
        return { background: "linear-gradient(135deg, #ff9a9e 0%, #fecfef 99%, #fecfef 100%)" };
      }
      return { background: "linear-gradient(135deg, #f6d365 0%, #fda085 100%)" };
    }
    if (category === "video") {
      return { background: "linear-gradient(135deg, #30cfd0 0%, #33086f 100%)" };
    }
    return { background: "linear-gradient(135deg, #f3f4f6 0%, #d1d5db 100%)" };
  };

  return (
    <div className="file-library" style={{ width: "100%" }}>
      <div className="file-library__header" style={{ display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
        {/* Layout Modes Toggle buttons */}
        <div className="layout-toggle-group">
          <button
            type="button"
            className={`layout-toggle-btn ${layoutMode === "list" ? "layout-toggle-btn--active" : ""}`}
            onClick={() => setLayoutMode("list")}
            title={t("lib.layoutList")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
              <line x1="8" y1="6" x2="21" y2="6" />
              <line x1="8" y1="12" x2="21" y2="12" />
              <line x1="8" y1="18" x2="21" y2="18" />
              <line x1="3" y1="6" x2="3.01" y2="6" />
              <line x1="3" y1="12" x2="3.01" y2="12" />
              <line x1="3" y1="18" x2="3.01" y2="18" />
            </svg>
          </button>
          <button
            type="button"
            className={`layout-toggle-btn ${layoutMode === "grid" ? "layout-toggle-btn--active" : ""}`}
            onClick={() => setLayoutMode("grid")}
            title={t("lib.layoutGrid")}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
              <rect x="3" y="3" width="7" height="7" />
              <rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" />
              <rect x="3" y="14" width="7" height="7" />
            </svg>
          </button>
        </div>
      </div>

      {error && <div className="library-error-banner" role="alert">{error}</div>}
      <div className="file-library__section" style={{ marginTop: "16px" }}>
        {filteredFiles.length === 0 ? (
          <div className="file-library__empty">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" width="48" height="48">
              <polyline points="12 8 12 12 14 14" />
              <circle cx="12" cy="12" r="10" />
            </svg>
            <p>{loading ? "正在加载…" : "最近没有访问记录"}</p>
          </div>
        ) : layoutMode === "list" ? (
          /* List layout: table rows with relative dates & absolute paths */
          <div className="file-library__table-wrapper">
            <table className="file-library__table">
              <thead>
                <tr>
                  <th>{t("lib.name")}</th>
                  <th>{t("lib.size")}</th>
                  <th>{t("lib.modifiedDate")}</th>
                  <th>{t("search.colPath")}</th>
                </tr>
              </thead>
              <tbody>
                {filteredFiles.map((file) => (
                  <tr key={file.id} style={{ cursor: "pointer" }} onClick={() => handleOpenPreview(file)}>
                    <td>
                      <div className="file-library__item-name">
                        {/* Image & Video small inline previews */}
                        {(file.category === "image" || file.category === "video") ? (
                          <div className="list-thumbnail" style={getThumbnailStyle(file.name, file.category)}>
                            {file.category === "video" && (
                              <span className="list-thumbnail-play">▶</span>
                            )}
                            {file.category === "image" && (
                              <span style={{ fontSize: "10px" }}>📷</span>
                            )}
                          </div>
                        ) : (
                          getIcon(file.name, file.category)
                        )}
                        <span style={{ fontWeight: "600" }}>{file.name}</span>
                      </div>
                    </td>
                    <td>{file.size}</td>
                    {/* Display Relative Modification Date */}
                    <td>{getRelativeTimeStr(file.date)}</td>
                    <td style={{ fontSize: "12px", color: "var(--text-muted)", fontFamily: "monospace" }}>{file.path}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          /* Grid layout: matrix of files cards with relative dates & paths */
          <div className="file-grid-layout">
            {filteredFiles.map((file) => (
              <div key={file.id} className="file-card" onClick={() => handleOpenPreview(file)}>
                <div className="file-card__thumbnail" style={getThumbnailStyle(file.name, file.category)}>
                  {file.category === "video" && (
                    <div className="file-card__thumbnail-overlay">
                      <div className="thumbnail-play-icon">▶</div>
                    </div>
                  )}
                  {file.category === "image" && (
                    <div className="file-card__thumbnail-overlay" style={{ background: "rgba(0,0,0,0.05)" }}>
                      <span style={{ fontSize: "28px" }}>📷</span>
                    </div>
                  )}
                  {file.category === "document" && (
                    <div style={{ transform: "scale(1.8)" }}>
                      {getIcon(file.name, file.category)}
                    </div>
                  )}
                  {file.category === "other" && (
                    <span style={{ fontSize: "32px" }}>📦</span>
                  )}
                </div>
                <div className="file-card__details">
                  <div className="file-card__title" title={file.name}>{file.name}</div>
                  <div style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: "2px" }} title={file.path}>
                    {file.path}
                  </div>
                  <div className="file-card__meta" style={{ marginTop: "6px" }}>
                    <span>{file.size}</span>
                    {/* Show Relative Time inside Card meta */}
                    <span style={{ fontWeight: "600", color: "var(--accent-primary)" }}>{getRelativeTimeStr(file.date).split(" (")[0]}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {previewFile && (
        <FilePreviewModal
          file={{
            id: previewFile.id,
            name: previewFile.name,
            path: previewFile.path,
            category: previewFile.category === "other" ? "other" : previewFile.category,
            size: previewFile.size,
            modified: previewFile.date
          }}
          onClose={() => setPreviewFile(null)}
        />
      )}
    </div>
  );
}
export default RecentAccess;
