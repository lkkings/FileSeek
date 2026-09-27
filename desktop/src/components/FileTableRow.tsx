import { useRef } from "react";

import { Icon } from "./Icon";
import { useTranslate } from "../i18n/useTranslate";
import type { FileItem } from "../services/api/search";
import "./file-table.css";

interface FileTableRowProps {
  file: FileItem;
  variant: "search" | "folder";
  isBatchMode: boolean;
  isRowChecked: boolean;
  onToggleCheck: (file: FileItem) => void;
  onLongPress: (fileId: string) => void;
  onOpenFile: (file: FileItem) => void;
}

export function FileTableRow({
  file,
  variant,
  isBatchMode,
  isRowChecked,
  onToggleCheck,
  onLongPress,
  onOpenFile,
}: FileTableRowProps) {
  const t = useTranslate();
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const suppressNextClick = useRef(false);
  const clearClickSuppression = useRef<ReturnType<typeof setTimeout> | null>(null);

  const startLongPress = () => {
    longPressTimer.current = setTimeout(() => {
      suppressNextClick.current = true;
      onLongPress(file.file_id);
    }, 800);
  };

  const cancelLongPress = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current);
      longPressTimer.current = null;
    }
    if (suppressNextClick.current) {
      if (clearClickSuppression.current) clearTimeout(clearClickSuppression.current);
      clearClickSuppression.current = setTimeout(() => {
        suppressNextClick.current = false;
      }, 300);
    }
  };

  const handleRowClick = () => {
    if (suppressNextClick.current) {
      suppressNextClick.current = false;
      return;
    }
    onOpenFile(file);
  };

  const formatSize = () => {
    if (file.size === null || file.size === undefined) return "-";
    return `${(file.size / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = () => {
    if (!file.modified) return "-";
    if (!file.modified.includes("T")) return file.modified;
    const date = new Date(file.modified);
    if (Number.isNaN(date.getTime())) return file.modified;
    const pad = (part: number) => part.toString().padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  };

  const firstChunk = Array.isArray(file.chunks) ? file.chunks[0] : null;
  const matchInfo = file.metadata?.description || (typeof firstChunk === "string" ? firstChunk : "");

  return (
    <tr
      className={`file-table-row ${isBatchMode ? "in-batch-mode" : ""} ${isRowChecked ? "is-selected" : ""}`}
      onClick={handleRowClick}
      onMouseDown={startLongPress}
      onMouseUp={cancelLongPress}
      onMouseLeave={cancelLongPress}
      onTouchStart={startLongPress}
      onTouchEnd={cancelLongPress}
    >
      {isBatchMode && (
        <td className="file-table-checkbox-cell">
          <input
            type="checkbox"
            checked={isRowChecked}
            aria-label={`${t("batch.selectFile", "选择")} ${file.file_name}`}
            onChange={() => onToggleCheck(file)}
            onClick={(event) => event.stopPropagation()}
          />
        </td>
      )}
      <td>
        <button type="button" className="file-name-button" onClick={(event) => {
          event.stopPropagation();
          onOpenFile(file);
        }}>
          <span className={`file-type-icon file-type-${file.file_type.toLowerCase()}`} aria-hidden="true">
            {file.file_type}
          </span>
          <span>{file.file_name}</span>
        </button>
      </td>
      {variant === "search" ? (
        <>
          <td>{file.category}</td>
          <td className="file-table-match">{matchInfo}</td>
          <td className="file-table-score">{Math.round(file.score)}%</td>
        </>
      ) : (
        <>
          <td>{formatSize()}</td>
          <td>{formatDate()}</td>
        </>
      )}
      <td className="file-table-path">{file.path}</td>
      <td className="file-table-actions">
        <button type="button" onClick={(event) => {
          event.stopPropagation();
          onOpenFile(file);
        }}>
          <Icon name="eye" size={14} />
        </button>
      </td>
    </tr>
  );
}
