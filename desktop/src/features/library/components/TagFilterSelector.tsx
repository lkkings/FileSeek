import { useTranslate } from "../../../i18n/useTranslate";
import { useLibraryTags } from "../hooks/useLibraryTags";

interface TagFilterSelectorProps {
  selectedTag: string;
  onTagChange: (tag: string) => void;
}

export function TagFilterSelector({ selectedTag, onTagChange }: TagFilterSelectorProps) {
  const t = useTranslate();
  const { tags, loading, error, refetch } = useLibraryTags();

  return (
    <div className="tag-filter-selector">
      <div className="tag-pills-list">
        <button
          className={`tag-pill-btn ${selectedTag === "全部" ? "is-active" : ""}`}
          type="button"
          onClick={() => onTagChange("全部")}
          aria-pressed={selectedTag === "全部"}
        >
          全部
        </button>
        {loading && <span className="tag-row-state">{t("loading.tags", "加载标签...")}</span>}
        {error && (
          <span className="tag-row-state tag-row-error">
            {error}
            <button type="button" onClick={() => void refetch()}>
              {t("common.retry", "重试")}
            </button>
          </span>
        )}
        {!loading && tags.map((tag) => (
          <button
            key={tag}
            className={`tag-pill-btn ${tag === selectedTag ? "is-active" : ""}`}
            type="button"
            onClick={() => onTagChange(tag)}
            aria-pressed={tag === selectedTag}
          >
            {tag}
          </button>
        ))}
        {!loading && !error && tags.length === 0 && (
          <span className="tag-row-state">{t("folder.noTags", "暂无标签")}</span>
        )}
      </div>
    </div>
  );
}
