import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import { warmupSearch } from "../../../services/api/search";
import type { SearchFilters } from "../types";
import { warmupQueryModel } from "../warmup";
import type { SearchMode } from "../types";
import "./search.css";

interface SearchBarProps {
  query: SearchFilters["globalQuery"];
  mode: SearchMode;
  onModeChange: (mode: SearchMode) => void;
  onQueryChange: (value: string) => void;
  onClear?: () => void;
  onOpenAdvanced: () => void;
  advancedOpen: boolean;
  onSubmit: () => void;
  loading?: boolean;
  /** 预热查询模型。默认调后端预热接口，测试可替换。 */
  onWarmup?: () => Promise<unknown>;
}

export function SearchBar({
  query,
  mode,
  onModeChange,
  onQueryChange,
  onClear,
  onOpenAdvanced,
  advancedOpen,
  onSubmit,
  loading = false,
  onWarmup = warmupSearch,
}: SearchBarProps) {
  const t = useTranslate();

  const warmup = () => warmupQueryModel(onWarmup);

  return (
    <form
      className="top-search-wrap"
      onSubmit={(event) => {
        event.preventDefault();
        if (!loading) onSubmit();
      }}
    >
      <Icon name="search" size={16} />
      <input
        aria-label={t("search.global.label", "全局搜索")}
        placeholder={t("search.global.placeholder", "输入关键词，例如‘上个月的旅游照片’或‘Q2财务报告’")}
        value={query}
        onFocus={warmup}
        onChange={(event) => onQueryChange(event.target.value)}
        disabled={loading}
      />
      {query && onClear && (
        <button className="search-clear-button" type="button" aria-label={t("search.clear", "清空搜索")} title={t("search.clear", "清空搜索")} onClick={onClear}>
          <Icon name="close" size={16} />
        </button>
      )}
      <button
        type="button"
        className={`search-enhanced-toggle ${mode === "enhanced" ? "is-active" : ""}`}
        aria-pressed={mode === "enhanced"}
        disabled={loading}
        onClick={() => onModeChange(mode === "enhanced" ? "advanced" : "enhanced")}
      >
        {t("search.mode.enhancedToggle", "启动检索增强")}
      </button>
      {mode === "advanced" && (
        <button
          className={`advanced-button ${advancedOpen ? "is-open" : ""}`}
          type="button"
          aria-controls="advanced-filter"
          aria-expanded={advancedOpen}
          onClick={onOpenAdvanced}
          disabled={loading}
        >
          <Icon name="filter" size={16} />
          <span>{t("search.advanced.button", "高级筛选")}</span>
          <span className="advanced-chevron"><Icon name="chevron" size={14} /></span>
        </button>
      )}
    </form>
  );
}
