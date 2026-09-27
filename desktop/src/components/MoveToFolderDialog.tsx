import { useFileLibrary } from "../features/library/hooks/useFileLibrary";
import { Icon } from "./Icon";
import { useTranslate } from "../i18n/useTranslate";
import { type FolderRecord } from "../features/library/types";

interface MoveToFolderDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (targetFolder: FolderRecord) => void;
  excludeFolderId?: string;
  selectedCount: number;
}

export function MoveToFolderDialog({
  isOpen,
  onClose,
  onConfirm,
  excludeFolderId,
  selectedCount,
}: MoveToFolderDialogProps) {
  const t = useTranslate();
  const { folders, loading, error } = useFileLibrary();

  if (!isOpen) return null;

  const availableFolders = folders.filter((f) => f.id !== excludeFolderId);

  return (
    <div
      className="modal-backdrop"
      style={{ display: "grid", placeItems: "center", zIndex: 1000 }}
      onClick={onClose}
    >
      <div
        className="folder-dialog"
        style={{
          width: "440px",
          padding: "24px",
          display: "block",
          maxHeight: "80vh",
          overflowY: "auto",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="dialog-heading">
          <h3 style={{ fontSize: "18px", fontWeight: "700" }}>
            {t("batch.confirmMoveTitle", "确认批量移动")}
          </h3>
          <p
            className="delete-warning"
            style={{ marginTop: "8px", color: "#c6d4ed", fontSize: "14px" }}
          >
            {t("batch.confirmMoveDesc", "将选中的")}{" "}
            <strong>{selectedCount}</strong>{" "}
            {t("batch.confirmMoveDescSuffix", "个文件移动到指定文件夹")}
          </p>
        </div>

        <div style={{ marginTop: "16px", marginBottom: "16px" }}>
          {loading && (
            <p style={{ color: "#a9bae1", textAlign: "center" }}>
              {t("common.loading", "正在加载...")}
            </p>
          )}
          {error && <p style={{ color: "#ff4d4f" }}>{error}</p>}
          {!loading && !error && availableFolders.length === 0 && (
            <p style={{ color: "#a9bae1", textAlign: "center" }}>
              {t("folder.noAvailableFolders", "没有可选的文件夹")}
            </p>
          )}
          {!loading && !error && availableFolders.length > 0 && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "8px",
                maxHeight: "240px",
                overflowY: "auto",
                border: "1px solid #1a2c4e",
                borderRadius: "6px",
                padding: "8px",
                backgroundColor: "#0d1b3e",
              }}
            >
              {availableFolders.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => onConfirm(f)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    width: "100%",
                    padding: "10px 12px",
                    background: "none",
                    border: "none",
                    borderRadius: "4px",
                    color: "#fff",
                    cursor: "pointer",
                    textAlign: "left",
                    fontSize: "14px",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = "rgba(39, 165, 255, 0.1)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = "transparent";
                  }}
                >
                  <Icon name="folder" size={16} />
                  <span>{f.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div
          className="dialog-actions"
          style={{ marginTop: "24px", display: "flex", justifyContent: "flex-end", gap: "12px" }}
        >
          <button
            type="button"
            className="dialog-secondary"
            onClick={onClose}
            style={{
              padding: "8px 16px",
              backgroundColor: "transparent",
              border: "1px solid #3d4f73",
              color: "#c6d4ed",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            {t("dialog.cancel", "取消")}
          </button>
        </div>
      </div>
    </div>
  );
}
