import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { SearchFilters } from "../types";
import "./search.css";

interface SearchBarProps {
  query: SearchFilters["globalQuery"];
  onQueryChange: (value: string) => void;
  onClear?: () => void;
  onOpenAdvanced: () => void;
  advancedOpen: boolean;
  onSubmit: () => void;
}

export function SearchBar({ query, onQueryChange, onClear, onOpenAdvanced, advancedOpen, onSubmit }: SearchBarProps) {
  const t = useTranslate();

  return (
    <form className="top-search-wrap" onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>
      <Icon name="search" size={16} />
      <input aria-label={t("search.global.label", "全局搜索")} placeholder={t("search.global.placeholder", "输入关键词，例如‘上个月的旅游照片’或‘Q2财务报告’")} value={query} onChange={(event) => onQueryChange(event.target.value)} />
      {query && onClear && (
        <button className="search-clear-button" type="button" aria-label={t("search.clear", "清空搜索")} title={t("search.clear", "清空搜索")} onClick={onClear}>
          <Icon name="close" size={16} />
        </button>
      )}
      <button className={`advanced-button ${advancedOpen ? "is-open" : ""}`} type="button" aria-controls="advanced-filter" aria-expanded={advancedOpen} onClick={onOpenAdvanced}>
        <Icon name="filter" size={16} />
        <span>{t("search.advanced.button", "高级筛选")}</span>
        <span className="advanced-chevron"><Icon name="chevron" size={14} /></span>
      </button>
    </form>
  );
}
