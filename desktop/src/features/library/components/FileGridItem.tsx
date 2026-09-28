import { useRef } from "react";

import { Icon } from "../../../components/Icon";
import { FilePreviewCell } from "../../file-preview";
import { FileItem } from "../../../services/api/search";

interface FileGridItemProps {
  file: FileItem;
  isBatchMode: boolean;
  isCardChecked: boolean;
  onCardClick: (file: FileItem) => void;
  onCardDoubleClick: (file: FileItem) => void;
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
  onCardDoubleClick,
  onToggleCheck,
  onLongPress,
}: FileGridItemProps) {
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const longPressCompleted = useRef(false);

  const startLongPress = (id: string) => {
    longPressCompleted.current = false;
    longPressTimer.current = setTimeout(() => {
      longPressCompleted.current = true;
      onLongPress(id);
    }, 800);
  };

  const cancelLongPress = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  };

  const clearClickTimer = () => {
    if (clickTimer.current) {
      clearTimeout(clickTimer.current);
      clickTimer.current = null;
    }
  };

  const isVideo = file.category === "video";
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
      role="button"
      tabIndex={0}
      aria-label={file.file_name}
      onClick={() => {
        if (longPressCompleted.current) {
          longPressCompleted.current = false;
          return;
        }
        if (isBatchMode) {
          onToggleCheck(file);
        } else {
          clearClickTimer();
          clickTimer.current = setTimeout(() => {
            onCardClick(file);
            clickTimer.current = null;
          }, 220);
        }
      }}
      onDoubleClick={() => {
        if (isBatchMode) return;
        clearClickTimer();
        onCardDoubleClick(file);
      }}
      onKeyDown={(event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        if (isBatchMode) onToggleCheck(file);
        else onCardClick(file);
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
        <FilePreviewCell
          item={{
            fileId: file.file_id,
            fileName: file.file_name,
            fileType: file.category as "document" | "image" | "video",
          }}
        />
        {isVideo && duration && (
          <span className="video-duration-tag">{duration}</span>
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
