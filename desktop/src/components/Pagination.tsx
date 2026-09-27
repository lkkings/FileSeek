import { Icon } from "./Icon";
import { useTranslate } from "../i18n/useTranslate";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  variant?: "search" | "details";
}

export function Pagination({
  currentPage,
  totalPages,
  totalItems,
  onPageChange,
  variant = "search",
}: PaginationProps) {
  const t = useTranslate();
  const pages = Array.from({ length: totalPages }, (_, i) => i + 1);

  if (variant === "details") {
    return (
      <footer className="details-pagination-footer">
        <div className="pagination-controls-group">
          <button
            className="btn-pagination-action"
            type="button"
            aria-label={t("folder.prevPage", "上一页")}
            disabled={currentPage === 1}
            onClick={() => onPageChange(Math.max(1, currentPage - 1))}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 18l-6-6 6-6" />
            </svg>
          </button>
          {pages.map((number) => (
            <button
              className={`btn-pagination-number ${currentPage === number ? "is-active" : ""}`}
              type="button"
              key={number}
              onClick={() => onPageChange(number)}
            >
              {number}
            </button>
          ))}
          <button
            className="btn-pagination-action"
            type="button"
            aria-label={t("folder.nextPage", "下一页")}
            disabled={currentPage === totalPages}
            onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>
        </div>
        <span className="pagination-total-items">
          {t("folder.totalItemsPrompt", "共")} {totalItems} {t("folder.totalItemsSuffix", "条")}
        </span>
      </footer>
    );
  }

  return (
    <footer className="results-footer">
      <div className="pagination" aria-label={t("search.pagination", "分页")}>
        <button
          type="button"
          aria-label={t("search.previousPage", "上一页")}
          disabled={currentPage === 1}
          onClick={() => onPageChange(Math.max(1, currentPage - 1))}
        >
          <Icon name="chevron" size={18} />
        </button>
        {pages.map((number) => (
          <button
            className={currentPage === number ? "is-current" : ""}
            type="button"
            key={number}
            onClick={() => onPageChange(number)}
          >
            {number}
          </button>
        ))}
        <button
          type="button"
          aria-label={t("search.nextPage", "下一页")}
          disabled={currentPage === totalPages}
          onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
        >
          <Icon name="chevron" size={18} />
        </button>
      </div>
      <span className="total-count">
        {t("search.total", "共")} {totalItems} {t("search.items", "条")}
      </span>
    </footer>
  );
}
