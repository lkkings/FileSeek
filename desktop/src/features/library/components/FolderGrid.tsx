import { FolderIcon } from "../fileIcons";
import type { FolderItem } from "../useLibrary";

interface FolderGridProps {
  folders: FolderItem[];
  onOpen: (name: string) => void;
  onEdit: (folder: FolderItem) => void;
  onDelete: (id: string, name: string) => void;
}

export function FolderGrid({ folders, onOpen, onEdit, onDelete }: FolderGridProps) {
  return <div className="file-library__folders-grid">
    {folders.map((folder) => <div key={folder.id} className="folder-card" onClick={() => onOpen(folder.name)}>
      <div className="folder-card__header-row">
        <FolderIcon type={folder.iconType} />
        <div className="folder-card__actions">
          <button type="button" className="results-btn" onClick={(event) => { event.stopPropagation(); onEdit(folder); }} title="编辑文件夹" aria-label="编辑文件夹">编辑</button>
          <button type="button" className="results-btn action-link-btn--danger" onClick={(event) => { event.stopPropagation(); onDelete(folder.id, folder.name); }} title="删除文件夹" aria-label="🗑">删除</button>
          <button type="button" className="results-btn folder-card__more" onClick={(event) => event.stopPropagation()} aria-label="更多操作">•••</button>
        </div>
      </div>
      <div className="folder-card__title" title={folder.name}>{folder.name}</div>
      {folder.description && <p className="folder-card__desc" title={folder.description}>{folder.description}</p>}
      <div className="folder-card__meta">{folder.modified}</div>
    </div>)}
  </div>;
}
