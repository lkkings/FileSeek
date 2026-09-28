import { useTranslate } from "../../../i18n/useTranslate";
import type { FileItem } from "../../../services/api/search";
import { FileListRow } from "./FileListRow";

interface FileListViewProps {
  files: FileItem[];
  isBatchMode: boolean;
  selectedFileIds: Set<string>;
  onRowClick: (file: FileItem) => void;
  onRowDoubleClick: (file: FileItem) => void;
  onToggleCheck: (file: FileItem) => void;
  onLongPress: (fileId: string) => void;
}

export function FileListView({
  files,
  isBatchMode,
  selectedFileIds,
  onRowClick,
  onRowDoubleClick,
  onToggleCheck,
  onLongPress,
}: FileListViewProps) {
  const t = useTranslate();

  return (
    <div className="file-list-view" role="table" aria-label={t("folder.fileList", "文件列表")}>
      <div className="file-list-header" role="row">
        <span role="columnheader">{t("folder.preview", "预览")}</span>
        <span role="columnheader">{t("folder.fileName", "文件名")}</span>
        <span role="columnheader">{t("folder.tags", "标签")}</span>
        <span role="columnheader">{t("folder.size", "大小")}</span>
      </div>

      {files.map((file) => (
        <FileListRow
          key={file.file_id}
          file={file}
          isBatchMode={isBatchMode}
          isRowChecked={selectedFileIds.has(file.file_id)}
          onRowClick={onRowClick}
          onRowDoubleClick={onRowDoubleClick}
          onToggleCheck={onToggleCheck}
          onLongPress={onLongPress}
        />
      ))}
    </div>
  );
}
