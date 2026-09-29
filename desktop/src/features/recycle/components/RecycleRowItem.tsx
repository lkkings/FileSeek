import { useRef } from "react";

import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import { formatDateTime } from "../../../i18n/formatDateTime";
import type { RecycleItem } from "../../../services/api/recycle";
import "./recycle.css";

interface RecycleRowItemProps {
  item: RecycleItem;
  isBatchMode: boolean;
  isRowChecked: boolean;
  onToggleCheck: (item: RecycleItem) => void;
  onLongPress: (itemId: string) => void;
}

function formatSize(value: string) {
  const size = Number(value);
  if (!Number.isFinite(size)) return value;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function RecycleRowItem({
  item,
  isBatchMode,
  isRowChecked,
  onToggleCheck,
  onLongPress,
}: RecycleRowItemProps) {
  const t = useTranslate();
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const suppressNextClick = useRef(false);

  const startLongPress = () => {
    longPressTimer.current = setTimeout(() => {
      suppressNextClick.current = true;
      onLongPress(item.id);
    }, 800);
  };

  const cancelLongPress = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
  };

  return (
    <article
      className={`recycle-row ${isBatchMode ? "in-batch-mode" : ""} ${isRowChecked ? "is-row-selected" : ""}`}
      onClick={() => {
        if (suppressNextClick.current) {
          suppressNextClick.current = false;
          return;
        }
        onToggleCheck(item);
      }}
      onMouseDown={startLongPress}
      onMouseUp={cancelLongPress}
      onMouseLeave={cancelLongPress}
      onTouchStart={startLongPress}
      onTouchEnd={cancelLongPress}
    >
      {isBatchMode && (
        <button
          type="button"
          className={`recycle-row-checkbox ${isRowChecked ? "is-checked" : ""}`}
          aria-label={t("recycle.toggleSelection", "切换选择")}
          aria-pressed={isRowChecked}
          onClick={(event) => {
            event.stopPropagation();
            onToggleCheck(item);
          }}
        >
          <span className="checkbox-inner">{isRowChecked ? "✓" : ""}</span>
        </button>
      )}

      <div className="recycle-file">
        <div className={`recycle-file-type recycle-file-type-${item.file_type.toLowerCase()}`} aria-hidden="true">
          {item.file_type}
        </div>
        <div className="recycle-file-copy">
          <h2>{item.original_name}</h2>
          <p className="recycle-file-path">{item.original_path}</p>
          <p className="recycle-file-meta">
            <Icon name="clock" size={15} />
            <span>{formatDateTime(item.deleted_at)}</span>
            <span>{formatSize(item.size)}</span>
          </p>
        </div>
      </div>

      <div className="recycle-row-status">
        <Icon name="trash" size={16} />
        <span>{t("recycle.inTrash", "已移入回收站")}</span>
      </div>
    </article>
  );
}
