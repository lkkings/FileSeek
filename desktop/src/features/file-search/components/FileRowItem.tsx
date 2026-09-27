import { useRef } from "react";
import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import { FileItem } from "../../../services/api/search";

interface FileRowItemProps {
  file: FileItem;
  isSelected: boolean;
  isBatchMode: boolean;
  isRowChecked: boolean;
  onRowClick: (file: FileItem) => void;
  onToggleCheck: (file: FileItem) => void;
  onLongPress: (fileId: string) => void;
  onOpenFile?: (file: FileItem) => void | Promise<void>;
  onLocateFile?: (file: FileItem) => void | Promise<void>;
}

export function FileRowItem({
  file,
  isSelected,
  isBatchMode,
  isRowChecked,
  onRowClick,
  onToggleCheck,
  onLongPress,
  onOpenFile,
  onLocateFile,
}: FileRowItemProps) {
  const t = useTranslate();
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const suppressNextClick = useRef(false);

  const startLongPress = (id: string) => {
    longPressTimer.current = setTimeout(() => {
      suppressNextClick.current = true;
      onLongPress(id);
    }, 800);
  };

  const cancelLongPress = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  };

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

  const isVideo = file.category === "video";
  const scene = file.metadata?.scene;
  const duration = file.metadata?.duration;

  return (
    <article
      className={`result-row ${isSelected ? "is-selected" : ""} ${isBatchMode ? "in-batch-mode" : ""} ${isRowChecked ? "is-row-selected" : ""}`}
      onClick={() => {
        if (suppressNextClick.current) {
          suppressNextClick.current = false;
          return;
        }
        if (isBatchMode) {
          onToggleCheck(file);
        } else {
          onRowClick(file);
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
          className={`search-row-checkbox ${isRowChecked ? "is-checked" : ""}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggleCheck(file);
          }}
        >
          <span className="checkbox-inner">
            {isRowChecked && "✓"}
          </span>
        </div>
      )}
      <div className="result-file">
        <div className={`file-type-icon file-type-${file.file_type.toLowerCase()}`} aria-hidden="true">
          {file.file_type}
        </div>
        <div className="result-file-copy">
          <h2>{file.file_name}</h2>
          <p className="result-path">{file.path}</p>
          <p className="result-meta">
            <Icon name="clock" size={15} />
            <span>{formattedDate}</span>
            <span>{formattedSize}</span>
          </p>
        </div>
      </div>

      <div className="result-tags">
        {(file.tags || []).map((tag, index) => {
          const tones = ["blue", "violet", "teal"];
          const tone = tones[index % tones.length];
          return (
            <span className={`result-tag tag-${tone}`} key={`tag-${index}`}>
              {tag}
            </span>
          );
        })}
      </div>

      <div className="result-preview">
        {scene ? (
          <div className={`preview-thumb scene-${scene}`} style={{ width: "100%", height: "100%" }}>
            {isVideo && (
              <span className="preview-play">
                <Icon name="video" size={18} />
              </span>
            )}
            <span className="preview-label">
              {isVideo ? duration : t("search.preview", "预览")}
            </span>
          </div>
        ) : (
          <p>{file.metadata?.description || ""}</p>
        )}
        <button
          type="button"
          className="preview-expand"
          aria-label={t("search.previewFile", "预览文件")}
          title={t("search.previewFile", "预览文件")}
          onClick={(event) => {
            event.stopPropagation();
            if (onOpenFile) void onOpenFile(file);
          }}
        >
          <Icon name="eye" size={16} />
        </button>
      </div>

      <div className="result-actions">
        <button
          type="button"
          aria-label={t("search.locateFile", "在文件夹中显示")}
          title={t("search.locateFile", "在文件夹中显示")}
          onClick={(event) => {
            event.stopPropagation();
            if (onLocateFile) void onLocateFile(file);
          }}
        >
          <Icon name="folder" size={17} />
        </button>
        <button
          type="button"
          aria-label={t("search.openFile", "打开文件")}
          title={t("search.openFile", "打开文件")}
          onClick={(event) => {
            event.stopPropagation();
            if (onOpenFile) void onOpenFile(file);
          }}
        >
          <Icon name="eye" size={17} />
        </button>
      </div>
    </article>
  );
}
