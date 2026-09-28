import { useRef } from "react";

import { Icon } from "../../../components/Icon";
import type { FileItem } from "../../../services/api/search";

interface FileListRowProps {
  file: FileItem;
  isBatchMode: boolean;
  isRowChecked: boolean;
  onRowClick: (file: FileItem) => void;
  onRowDoubleClick: (file: FileItem) => void;
  onToggleCheck: (file: FileItem) => void;
  onLongPress: (fileId: string) => void;
}

export function FileListRow({
  file,
  isBatchMode,
  isRowChecked,
  onRowClick,
  onRowDoubleClick,
  onToggleCheck,
  onLongPress,
}: FileListRowProps) {
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const longPressCompleted = useRef(false);
  const clickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isVideo = file.category === "video";
  const isImage = file.category === "image";
  const scene = file.metadata?.scene;
  const formattedSize = file.size ? `${(file.size / (1024 * 1024)).toFixed(1)} MB` : "0.0 MB";

  const clearClickTimer = () => {
    if (clickTimer.current) {
      clearTimeout(clickTimer.current);
      clickTimer.current = null;
    }
  };

  const startLongPress = (fileId: string) => {
    longPressCompleted.current = false;
    longPressTimer.current = setTimeout(() => {
      longPressCompleted.current = true;
      onLongPress(fileId);
    }, 800);
  };

  const cancelLongPress = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  };

  const handleRowClick = () => {
    if (longPressCompleted.current) {
      longPressCompleted.current = false;
      return;
    }

    if (isBatchMode) {
      onToggleCheck(file);
      return;
    }

    clearClickTimer();
    clickTimer.current = setTimeout(() => {
      onRowClick(file);
      clickTimer.current = null;
    }, 220);
  };

  const handleRowDoubleClick = () => {
    clearClickTimer();
    if (!isBatchMode) {
      onRowDoubleClick(file);
    }
  };

  return (
    <div
      role="row"
      aria-selected={isRowChecked}
      className={`file-list-row ${isRowChecked ? "is-selected" : ""}`}
      onClick={handleRowClick}
      onDoubleClick={handleRowDoubleClick}
      onMouseDown={() => startLongPress(file.file_id)}
      onMouseUp={cancelLongPress}
      onMouseLeave={cancelLongPress}
      onTouchStart={() => startLongPress(file.file_id)}
      onTouchEnd={cancelLongPress}
    >
      <div role="cell" className="file-list-preview">
        {isBatchMode && (
          <div
            className={`file-list-checkbox ${isRowChecked ? "is-checked" : ""}`}
            role="checkbox"
            aria-checked={isRowChecked}
            aria-label={file.file_name}
            tabIndex={0}
            onClick={(event) => {
              event.stopPropagation();
              onToggleCheck(file);
            }}
            onKeyDown={(event) => {
              if (event.key !== "Enter" && event.key !== " ") return;
              event.preventDefault();
              event.stopPropagation();
              onToggleCheck(file);
            }}
          >
            <span className="checkbox-inner">{isRowChecked && "✓"}</span>
          </div>
        )}
        <div className={`file-list-preview-thumb ${isImage || isVideo ? `simulated-bg-${scene || "mountain"}` : ""}`}>
          <Icon name={isVideo ? "video" : isImage ? "image" : "document"} size={18} />
        </div>
      </div>

      <div role="cell" className="file-list-name">
        <span title={file.file_name}>{file.file_name}</span>
      </div>

      <div role="cell" className="file-list-tags">
        {(file.tags || []).slice(0, 3).map((tag) => (
          <span className="card-tag-badge" key={tag}>
            {tag}
          </span>
        ))}
      </div>

      <div role="cell" className="file-list-size">
        {formattedSize}
      </div>
    </div>
  );
}
