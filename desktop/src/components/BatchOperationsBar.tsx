import { Icon } from "./Icon";
import { useTranslate } from "../i18n/useTranslate";

interface BatchOperationsBarProps {
  selectedCount: number;
  onSelectAll: () => void;
  onInvertSelection: () => void;
  onDelete: () => void;
  onRestore?: () => void;
  onMoveTo?: () => void;
  onCancel: () => void;
  deleteLabel?: string;
}

export function BatchOperationsBar({
  selectedCount,
  onSelectAll,
  onInvertSelection,
  onDelete,
  onRestore,
  onMoveTo,
  onCancel,
  deleteLabel,
}: BatchOperationsBarProps) {
  const t = useTranslate();

  return (
    <div className="batch-operations-bar">
      <div className="batch-bar-left">
        <span>
          {t("batch.selectedCount", "已选择")}{" "}
          <strong>{selectedCount}</strong>{" "}
          {t("batch.filesUnit", "个文件")}
        </span>
        <div
          className="batch-select-toggles"
          style={{ display: "inline-flex", gap: "10px", marginLeft: "15px" }}
        >
          <button
            type="button"
            className="btn-batch-select-all"
            style={{
              background: "none",
              border: "none",
              color: "#27a5ff",
              fontSize: "13px",
              cursor: "pointer",
            }}
            onClick={onSelectAll}
          >
            {t("batch.selectAll", "全选")}
          </button>
          <button
            type="button"
            className="btn-batch-deselect-all"
            style={{
              background: "none",
              border: "none",
              color: "#a9bae1",
              fontSize: "13px",
              cursor: "pointer",
            }}
            onClick={onInvertSelection}
          >
            {t("batch.deselectAll", "反选")}
          </button>
        </div>
      </div>
      <div className="batch-bar-actions">
        {onRestore && (
          <button
            type="button"
            className="btn-batch-action btn-primary"
            onClick={onRestore}
          >
            <Icon name="cornerDownLeft" size={16} />
            <span>{t("recycle.restore", "恢复")}</span>
          </button>
        )}
        <button
          type="button"
          className="btn-batch-action btn-danger"
          onClick={onDelete}
        >
          <Icon name="trash" size={16} />
          <span>{deleteLabel || t("batch.delete", "删除")}</span>
        </button>
        {onMoveTo && (
          <button
            type="button"
            className="btn-batch-action btn-primary"
            onClick={onMoveTo}
          >
            <Icon name="folder" size={16} />
            <span>{t("batch.moveTo", "移动到")}</span>
          </button>
        )}
        <button type="button" className="btn-batch-cancel" onClick={onCancel}>
          {t("dialog.cancel", "取消")}
        </button>
      </div>
    </div>
  );
}
