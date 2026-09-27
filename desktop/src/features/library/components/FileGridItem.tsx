import { useRef } from "react";
import { Icon } from "../../../components/Icon";
import { FileItem } from "../../../services/api/search";

interface FileGridItemProps {
  file: FileItem;
  isBatchMode: boolean;
  isCardChecked: boolean;
  onCardClick: (file: FileItem) => void;
  onToggleCheck: (file: FileItem) => void;
  onLongPress: (fileId: string) => void;
}

const BADGE_CLASS_MAP: Record<string, string> = {
  旅游: "badge-blue",
  攻略: "badge-purple",
  行程: "badge-blue",
  文档: "badge-violet",
  图片: "badge-violet",
  风景: "badge-purple",
  视频: "badge-cyan",
  Vlog: "badge-green",
  自然: "badge-green",
  海滩: "badge-cyan",
  文化: "badge-orange",
  美食: "badge-orange",
};

export function FileGridItem({
  file,
  isBatchMode,
  isCardChecked,
  onCardClick,
  onToggleCheck,
  onLongPress,
}: FileGridItemProps) {
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const startLongPress = (id: string) => {
    longPressTimer.current = setTimeout(() => {
      onLongPress(id);
    }, 800);
  };

  const cancelLongPress = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  };

  const isVideo = file.category === "video";
  const isImage = file.category === "image";
  const isDoc = file.category === "document";
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

  return (
    <article
      className={`file-item-card ${isBatchMode ? "in-batch-mode" : ""} ${isCardChecked ? "is-selected" : ""}`}
      onClick={() => {
        if (isBatchMode) {
          onToggleCheck(file);
        } else {
          onCardClick(file);
        }
      }}
      onMouseDown={() => startLongPress(file.file_id)}
      onMouseUp={cancelLongPress}
      onMouseLeave={cancelLongPress}
      onTouchStart={() => startLongPress(file.file_id)}
      onTouchEnd={cancelLongPress}
      style={{ position: "relative" }}
    >
      {isBatchMode && (
        <div
          className={`file-card-checkbox ${isCardChecked ? "is-checked" : ""}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggleCheck(file);
          }}
        >
          <span className="checkbox-inner">
            {isCardChecked && "✓"}
          </span>
        </div>
      )}

      <div className="file-card-thumb-area">
        {isImage && (
          <>
            <div className={`file-card-thumb-image simulated-bg-${scene || "mountain"}`} />
            <span className="thumb-icon-overlay">
              <Icon name="image" size={12} />
            </span>
          </>
        )}

        {isVideo && (
          <>
            <div className={`file-card-thumb-image simulated-bg-${scene || "snow"}`} />
            <div className="thumb-video-overlay">
              <span className="video-play-center-btn">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                  <polygon points="5,3 19,12 5,21" />
                </svg>
              </span>
            </div>
            {duration && (
              <span className="video-duration-tag">{duration}</span>
            )}
          </>
        )}

        {isDoc && (
          <div className={file.file_type === "pdf" ? "file-pdf-thumb" : "file-docx-thumb"}>
            {file.file_type === "pdf" ? "PDF" : "W"}
          </div>
        )}
      </div>

      <div className="file-card-info-area">
        <div className="file-card-title-row">
          <h3 className="file-title-text" title={file.file_name}>{file.file_name}</h3>
        </div>

        <div className="card-tags-row">
          {(file.tags || []).map((tag) => {
            const badgeClass = BADGE_CLASS_MAP[tag] || "badge-blue";
            return (
              <span className={`card-tag-badge ${badgeClass}`} key={tag}>
                {tag}
              </span>
            );
          })}
        </div>

        <div className="card-footer-row">
          <div className="card-time-wrap">
            <Icon name="clock" size={12} />
            <span>{formattedDate}</span>
          </div>
          <span className="card-size-label">{formattedSize}</span>
        </div>
      </div>
    </article>
  );
}
