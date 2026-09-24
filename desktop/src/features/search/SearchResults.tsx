import { useState } from "react";
import { useTranslation } from "../../i18n/useTranslation";
import type { SearchResults, DocumentResult } from "./types";
import { FilePreviewModal } from "../../components/ui/FilePreviewModal";

interface SearchResultsViewProps {
  results: SearchResults;
  query: string | null;
}

interface TauriOpener {
  showItemInFolder: (path: string) => Promise<void>;
  open: (path: string) => Promise<void>;
}

interface FlattenedSearchResult {
  id: string;
  filename: string;
  type: "document" | "image" | "video";
  path: string;
  score: number;
  accessible: boolean;
  rawItem: unknown; // Original item for player / preview triggers
  matchInfo: React.ReactNode;
}

export function SearchResultsView({ results, query }: SearchResultsViewProps) {
  const { t } = useTranslation();
  
  // Unified Preview Modal State
  //
  // 这里存的是不含 `matchInfo` 的部分：预览只用到 id/filename/path/type/rawItem，而
  // `matchInfo` 里的 JSX 又要能触发预览，两者互相引用的话就成了环。
  const [previewFile, setPreviewFile] = useState<{
    item: Omit<FlattenedSearchResult, "matchInfo">;
    initialTime?: number;
    initialPage?: number;
    initialLine?: number;
    matchedText?: string;
  } | null>(null);

  const hasDocuments = results.documents && results.documents.length > 0;
  const hasImages = results.images && results.images.length > 0;
  const hasVideos = results.videos && results.videos.length > 0;
  const hasAnyResults = hasDocuments || hasImages || hasVideos;

  // Render Empty State
  if (query && !hasAnyResults) {
    return (
      <div className="search-results__empty" role="region" style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "60px var(--space-md)", color: "var(--text-muted)" }}>
        <svg
          className="search-results__empty-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          width="48"
          height="48"
          style={{ marginBottom: "var(--space-md)" }}
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.3-4.3" />
          <path d="M8 11h6" />
        </svg>
        <p>{t("search.empty", { query })}</p>
      </div>
    );
  }

  const handleLocateFile = (filepath: string) => {
    const isTauri = (window as unknown as Record<string, unknown>).__TAURI__ !== undefined;
    if (isTauri) {
      import("@tauri-apps/plugin-opener").then((opener) => {
        const op = opener as unknown as TauriOpener;
        op.showItemInFolder(filepath).catch(err => {
          console.error("Failed to show item in folder:", err);
        });
      }).catch(err => {
        console.error("Failed to show item in folder:", err);
      });
    } else {
      alert(`${t("search.showInFolder")}: ${filepath}`);
    }
  };

  const handleOpenSystem = (filepath: string) => {
    const isTauri = (window as unknown as Record<string, unknown>).__TAURI__ !== undefined;
    if (isTauri) {
      import("@tauri-apps/plugin-opener").then((opener) => {
        const op = opener as unknown as TauriOpener;
        op.open(filepath).catch(err => {
          console.error("Failed to open file:", err);
        });
      }).catch(err => {
        console.error("Failed to open file:", err);
      });
    } else {
      alert(`${t("search.openInSystem")}: ${filepath}`);
    }
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  // Helper to color file names matching search query in red
  const highlightFilename = (filename: string, searchWord: string | null) => {
    if (!searchWord) return <span>{filename}</span>;
    // Escape characters to prevent regex crashes
    const escapedQuery = searchWord.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&');
    const regex = new RegExp(`(${escapedQuery})`, "gi");
    
    if (!regex.test(filename)) {
      return <span>{filename}</span>;
    }
    
    const parts = filename.split(regex);
    const occurrences = new Map<string, number>();
    return (
      <span>
        {parts.map((part) => {
          const occurrence = occurrences.get(part) ?? 0;
          occurrences.set(part, occurrence + 1);
          regex.lastIndex = 0;
          return regex.test(part) ? (
            <span key={`${part}-${occurrence}`} style={{ color: "var(--error)", fontWeight: "bold" }}>
              {part}
            </span>
          ) : (
            part
          );
        })}
      </span>
    );
  };

  // Maps individual file type icons to SVGs
  const getFileIcon = (fileName: string, type: "document" | "image" | "video") => {
    const ext = fileName.split(".").pop()?.toLowerCase();
    
    if (type === "image") {
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#10b981", flexShrink: 0 }}>
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
      );
    }
    if (type === "video") {
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
      case "xls":
      case "xlsx":
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#10b981", flexShrink: 0 }}>
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <line x1="9" y1="3" x2="9" y2="21" />
            <line x1="3" y1="9" x2="21" y2="9" />
          </svg>
        );
      case "ppt":
      case "pptx":
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#f97316", flexShrink: 0 }}>
            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
          </svg>
        );
      case "md":
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#06b6d4", flexShrink: 0 }}>
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <path d="M7 15V9l3.5 3 3.5-3v6" />
          </svg>
        );
      case "txt":
        return (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" style={{ color: "#6b7280", flexShrink: 0 }}>
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
            <polyline points="14 2 14 8 20 8" />
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

  // 1. Flatten all result types into a unified array
  const docItems: FlattenedSearchResult[] = (results.documents || []).map(doc => {
    const pageNum = doc.page_number ?? 1;
    const lineNum = doc.line_number ?? 12;

    const base: Omit<FlattenedSearchResult, "matchInfo"> = {
      id: doc.file_id,
      filename: doc.filename,
      type: "document",
      path: doc.path,
      score: doc.score,
      accessible: doc.accessible,
      rawItem: doc,
    };

    const matchInfo = (
      <div
        className="search-result-snippet"
        style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.5", cursor: doc.accessible ? "pointer" : "default" }}
        onClick={() => doc.accessible && setPreviewFile({ item: base, initialPage: pageNum, initialLine: lineNum, matchedText: doc.matched_text })}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "3px" }}>
          <span style={{ fontSize: "11px", fontWeight: "bold", backgroundColor: "var(--accent-light)", color: "var(--accent-primary)", padding: "1px 5px", borderRadius: "3px" }}>
            P.{pageNum} L.{lineNum} 定位点
          </span>
        </div>
        <div style={{ fontStyle: "italic" }}>{doc.matched_text}</div>
      </div>
    );

    return { ...base, matchInfo };
  });

  const imgItems: FlattenedSearchResult[] = (results.images || []).map(img => {
    const base: Omit<FlattenedSearchResult, "matchInfo"> = {
      id: img.file_id,
      filename: img.filename,
      type: "image",
      path: img.path,
      score: img.score,
      accessible: img.accessible,
      rawItem: img,
    };

    const matchInfo = (
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }} onClick={() => img.accessible && setPreviewFile({ item: base })}>
        <div style={{ width: "32px", height: "24px", borderRadius: "3px", background: "linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%)", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "10px", color: "white" }}>📷</div>
        <span style={{ fontSize: "13px", color: "var(--text-muted)", cursor: img.accessible ? "pointer" : "default" }}>
          {img.accessible ? "点击查看图片语义匹配预览" : "由于外部挂载点断开，图片暂不可访问"}
        </span>
      </div>
    );

    return { ...base, matchInfo };
  });

  const vidItems: FlattenedSearchResult[] = (results.videos || []).map(vid => {
    const base: Omit<FlattenedSearchResult, "matchInfo"> = {
      id: vid.file_id,
      filename: vid.filename,
      type: "video",
      path: vid.path,
      score: vid.score,
      accessible: vid.accessible,
      rawItem: vid,
    };

    // 后端给的是单个命中时刻（扁平的 start_time/end_time），不是片段数组，
    // 所以这里是一个跳转按钮而不是一列。命中时间未知时不渲染按钮——没有可跳的位置。
    const hasMoment = vid.start_time !== null && vid.start_time !== undefined;

    const matchInfo = hasMoment ? (
      <button
        type="button"
        className="segment-inline-btn"
        style={{
          background: "var(--bg-primary)",
          border: "1px solid var(--border-color)",
          padding: "4px 8px",
          borderRadius: "var(--radius-sm)",
          fontSize: "12.5px",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          cursor: vid.accessible ? "pointer" : "not-allowed",
          textAlign: "left",
          width: "fit-content",
          color: "var(--text-primary)"
        }}
        onClick={() => {
          if (vid.accessible) {
            setPreviewFile({ item: base, initialTime: vid.start_time ?? 0 });
          } else {
            alert(t("player.fileInaccessible"));
          }
        }}
      >
        <span style={{ fontWeight: "700", color: "var(--accent-primary)", display: "flex", alignItems: "center", gap: "4px" }}>
          ▶ {formatTime(vid.start_time ?? 0)}
          {vid.end_time !== null && vid.end_time !== undefined ? ` - ${formatTime(vid.end_time)}` : ""}
        </span>
        <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>({Math.round(vid.score)}%)</span>
      </button>
    ) : null;

    return { ...base, matchInfo };
  });

  // Merge and sort all results collectively by matching score
  const mergedResults = [...docItems, ...imgItems, ...vidItems];
  const sortedMergedResults = mergedResults.sort((a, b) => b.score - a.score);

  return (
    <div className="search-results" style={{ width: "100%", marginTop: "16px" }}>
      <h2 className="search-results__section-title" style={{ fontSize: "15px", fontWeight: "700", color: "var(--text-muted)", marginBottom: "12px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {t("search.resultsTitle")} ({sortedMergedResults.length})
      </h2>

      {sortedMergedResults.length > 0 && (
        <div className="file-library__table-wrapper" style={{ overflowX: "auto" }}>
          <table className="file-library__table" style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th style={{ minWidth: "180px" }}>{t("search.colName")}</th>
                <th style={{ width: "80px" }}>{t("search.colType")}</th>
                <th style={{ minWidth: "300px" }}>{t("search.colMatch")}</th>
                <th style={{ minWidth: "220px" }}>{t("search.colPath")}</th>
                <th style={{ width: "80px", textAlign: "center" }}>{t("search.colScore")}</th>
                <th style={{ width: "100px", textAlign: "right" }}>{t("ingest.action")}</th>
              </tr>
            </thead>
            <tbody>
              {sortedMergedResults.map((item) => (
                <tr key={item.id} style={{ opacity: item.accessible ? 1 : 0.65 }}>
                  {/* Filename with color highlight */}
                  <td onClick={() => item.accessible && setPreviewFile({ item })} style={{ cursor: "pointer" }}>
                    <div className="file-library__item-name" style={{ gap: "8px", display: "flex", alignItems: "center" }}>
                      {getFileIcon(item.filename, item.type)}
                      <span style={{ fontWeight: "600" }}>{highlightFilename(item.filename, query)}</span>
                    </div>
                  </td>
                  
                  {/* Styled Type Badge */}
                  <td onClick={() => item.accessible && setPreviewFile({ item })} style={{ cursor: "pointer" }}>
                    <span style={{
                      display: "inline-block",
                      padding: "2px 6px",
                      borderRadius: "4px",
                      fontSize: "11px",
                      fontWeight: "bold",
                      backgroundColor: item.type === "document" ? "var(--accent-light)" : item.type === "image" ? "#e1fcf2" : "#fffbeb",
                      color: item.type === "document" ? "var(--accent-primary)" : item.type === "image" ? "#0f766e" : "#b45309"
                    }}>
                      {item.type === "document" ? t("search.filterDocument") : item.type === "image" ? t("search.filterImage") : t("search.filterVideo")}
                    </span>
                  </td>

                  {/* Rich matching segment snippets / timestamps */}
                  <td>{item.matchInfo}</td>

                  {/* Storage paths */}
                  <td onClick={() => item.accessible && setPreviewFile({ item })} style={{ cursor: "pointer", fontSize: "12px", color: "var(--text-muted)", wordBreak: "break-all", fontFamily: "monospace" }}>
                    {item.path}
                  </td>

                  {/* Similarity Score */}
                  <td style={{ textAlign: "center", fontWeight: "700", color: "var(--accent-primary)", fontSize: "14px" }}>
                    {Math.round(item.score)}%
                  </td>

                  {/* Action Buttons */}
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                      {item.accessible && (
                        <>
                          <button
                            type="button"
                            className="results-btn"
                            style={{ padding: "4px 8px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-color)", background: "transparent", cursor: "pointer" }}
                            onClick={() => handleLocateFile(item.path)}
                            title={t("search.showInFolder")}
                          >
                            📁
                          </button>
                          <button
                            type="button"
                            className="results-btn"
                            style={{ padding: "4px 8px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-color)", background: "transparent", cursor: "pointer" }}
                            onClick={() => handleOpenSystem(item.path)}
                            title={t("search.openInSystem")}
                          >
                            ↗
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* File Preview Modal Overlay for all file types */}
      {previewFile && (
          <FilePreviewModal
            file={{
            id: previewFile.item.id,
            name: previewFile.item.filename,
            path: previewFile.item.path,
            category: previewFile.item.type,
            size: "1.5 MB",
            modified: "2026-09-20",
              ...(previewFile.initialTime === undefined ? {} : { initialTime: previewFile.initialTime }),
              initialPage: previewFile.initialPage || (previewFile.item.rawItem as DocumentResult)?.page_number || 1,
              initialLine: previewFile.initialLine || (previewFile.item.rawItem as DocumentResult)?.line_number || 12,
            matchedText: previewFile.matchedText || (previewFile.item.rawItem as DocumentResult)?.matched_text
          }}
            {...(previewFile.initialTime === undefined ? {} : { initialTime: previewFile.initialTime })}
          initialPage={previewFile.initialPage || (previewFile.item.rawItem as DocumentResult)?.page_number || 1}
          initialLine={previewFile.initialLine || (previewFile.item.rawItem as DocumentResult)?.line_number || 12}
          matchedText={previewFile.matchedText || (previewFile.item.rawItem as DocumentResult)?.matched_text}
          onClose={() => setPreviewFile(null)}
        />
      )}
    </div>
  );
}
export default SearchResultsView;
