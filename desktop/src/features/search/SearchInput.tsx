import { useState } from "react";
import { useTranslation } from "../../i18n/useTranslation";

interface SearchInputProps {
  onSearch: (query: string) => void;
  busy: boolean;
  filtersOpen: boolean;
  onToggleFilters: () => void;
}

/** The search field itself: icon, input, busy spinner, and the advanced-filters toggle. */
export function SearchInput({ onSearch, busy, filtersOpen, onToggleFilters }: SearchInputProps) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    onSearch(query);
  };

  return (
    <form className="search-bar" role="search" onSubmit={handleSubmit} style={{ width: "100%" }}>
      <div className="search-bar__input-wrapper" style={{ position: "relative", width: "100%" }}>
        <svg
          className="search-bar__icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <input
          type="search"
          className="search-bar__input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("search.placeholder")}
          aria-label="搜索文件库"
          disabled={busy}
          autoFocus
          style={{ paddingRight: "150px" }} // Make room on the right for the integrated advanced filter button
        />

        {busy && (
          <div
            className="search-bar__spinner"
            aria-hidden="true"
            style={{ right: "115px" }} // Align spinner to the left of the button
          />
        )}

        {/* Integrated Toggle Button INSIDE the Search Bar on the Right */}
        <button
          type="button"
          className="filter-toggle-btn"
          onClick={onToggleFilters}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="13" height="13">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
          </svg>
          <span>高级筛选</span>
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            width="11"
            height="11"
            style={{ transform: filtersOpen ? "rotate(180deg)" : "none", transition: "var(--transition-fast)" }}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </button>
      </div>
    </form>
  );
}

export default SearchInput;
