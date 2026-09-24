import { useTranslation } from "../../../i18n/useTranslation";
import { FileIcon } from "../fileIcons";
import { thumbnailStyle } from "../fileIconStyles";
import type { FileItem } from "../useLibrary";

interface FileListViewProps { files: FileItem[]; layout: "list" | "grid"; selectedIds: string[]; allSelected?: boolean; onSelectAll?: (checked: boolean) => void; onToggle: (id: string) => void; onPreview: (file: FileItem) => void; onDelete: (file: FileItem) => void }

export function FileListView({ files, layout, selectedIds, allSelected = false, onSelectAll, onToggle, onPreview, onDelete }: FileListViewProps) {
  const { t } = useTranslation();
  if (layout === "grid") return <div className="file-grid-layout">{files.map((file) => <div key={file.id} className="file-card"><input type="checkbox" checked={selectedIds.includes(file.id)} onChange={() => onToggle(file.id)} aria-label={`选择 ${file.name}`} /><div className="file-card__thumbnail" style={thumbnailStyle(file.name, file.category)} onClick={() => onPreview(file)}><FileIcon fileName={file.name} category={file.category}/></div><div className="file-card__details" onClick={() => onPreview(file)}><div className="file-card__title">{file.name}</div><div className="file-card__meta">{file.size} · {file.modified.substring(0, 10)}</div></div><button type="button" onClick={() => onDelete(file)} aria-label={`删除 ${file.name}`}>删除</button></div>)}</div>;
  return <div className="file-library__table-wrapper"><table className="file-library__table"><thead><tr><th><input type="checkbox" checked={allSelected} onChange={(event) => onSelectAll?.(event.target.checked)} aria-label="全选文件" /></th><th>{t("lib.name")}</th><th>{t("lib.size")}</th><th>{t("lib.modifiedDate")}</th><th>{t("search.colPath")}</th><th>操作</th></tr></thead><tbody>{files.map((file) => <tr key={file.id}><td><input type="checkbox" checked={selectedIds.includes(file.id)} onChange={() => onToggle(file.id)} aria-label={`选择 ${file.name}`}/></td><td><button type="button" className="file-name-button" onClick={() => onPreview(file)}><FileIcon fileName={file.name} category={file.category}/>{file.name}</button></td><td>{file.size}</td><td>{file.modified}</td><td>{file.path}</td><td><button type="button" onClick={() => onDelete(file)} aria-label={`删除 ${file.name}`}>删除</button></td></tr>)}</tbody></table></div>;
}
