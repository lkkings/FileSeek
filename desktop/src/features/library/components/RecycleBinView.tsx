import { useTranslation } from "../../../i18n/useTranslation";
import { FileIcon } from "../fileIcons";
import type { RecycleItem } from "../useLibrary";

interface RecycleBinViewProps {
  items: RecycleItem[];
  error: string | null;
  onEmpty: () => void;
  onRestore: (id: string) => void;
  onDelete: (id: string) => void;
}

export function RecycleBinView({ items, error, onEmpty, onRestore, onDelete }: RecycleBinViewProps) {
  const { t } = useTranslation();
  return <div className="file-library">
    <div className="file-library__header library-header--actions">
      {items.length > 0 && <button type="button" className="theme-btn theme-btn--danger" onClick={onEmpty}>{t("lib.cleanRecycle")}</button>}
    </div>
    {error && <div className="library-error-banner" role="alert">{error}</div>}
    {items.length === 0 ? <div className="file-library__empty"><p>{t("lib.recycleEmpty")}</p></div> : <div className="file-library__table-wrapper library-section-spacing">
      <table className="file-library__table"><thead><tr><th>{t("lib.name")}</th><th>{t("lib.size")}</th><th>{t("lib.modifiedDate")}</th><th>{t("ingest.action")}</th></tr></thead>
        <tbody>{items.map((item) => <tr key={item.id}><td><div className="file-library__item-name"><FileIcon fileName={item.name} category={item.category}/>{item.name}</div></td><td>{item.size}</td><td>{item.deletedAt}</td><td className="library-actions-cell"><button type="button" className="action-link-btn" onClick={() => onRestore(item.id)}>{t("lib.restore")}</button><button type="button" className="action-link-btn action-link-btn--danger" onClick={() => onDelete(item.id)}>{t("lib.deletePermanently")}</button></td></tr>)}</tbody>
      </table>
    </div>}
  </div>;
}
