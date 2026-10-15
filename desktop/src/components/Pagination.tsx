import { Icon } from "./Icon";
import { useTranslate } from "../i18n/useTranslate";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  variant?: "search" | "details";
}

/** 超过该页数时折叠中间页码，改为「首/尾 + 当前页窗口 + 省略号」。 */
const MAX_VISIBLE_PAGES = 7;
/** 当前页两侧固定展示的页码数量。 */
const PAGE_WINDOW_SIZE = MAX_VISIBLE_PAGES - 2;

type PageItem = number | "ellipsis-leading" | "ellipsis-trailing";

function buildPageItems(currentPage: number, totalPages: number): PageItem[] {
  if (totalPages <= MAX_VISIBLE_PAGES) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const windowStart = Math.min(
    Math.max(currentPage - Math.floor(PAGE_WINDOW_SIZE / 2), 2),
    totalPages - PAGE_WINDOW_SIZE,
  );
  const windowEnd = windowStart + PAGE_WINDOW_SIZE - 1;
  const items: PageItem[] = [1];

  if (windowStart > 2) {
    items.push("ellipsis-leading");
  }
  for (let page = windowStart; page <= windowEnd; page += 1) {
    items.push(page);
  }
  if (windowEnd < totalPages - 1) {
    items.push("ellipsis-trailing");
  }
  items.push(totalPages);

  return items;
}

export function Pagination({
  currentPage,
  totalPages,
  totalItems,
  onPageChange,
  variant = "search",
}: PaginationProps) {
  const t = useTranslate();
  const pageItems = buildPageItems(currentPage, totalPages);

  const renderPageItems = (className: string, activeClassName: string) =>
    pageItems.map((item) => {
      if (typeof item !== "number") {
        return (
          <span className="pagination-ellipsis" key={item} aria-hidden="true">
            …
          </span>
        );
      }

      const isActive = currentPage === item;
      const classes = isActive ? `${className} ${activeClassName}`.trim() : className;

      return (
        <button
          className={classes}
          type="button"
          key={item}
          aria-current={isActive ? "page" : undefined}
          onClick={() => onPageChange(item)}
        >
          {item}
        </button>
      );
    });

  if (variant === "details") {
    return (
      <footer className="details-pagination-footer">
        <div className="pagination-controls-group" role="group" aria-label={t("search.pagination", "分页")}>
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
          {renderPageItems("btn-pagination-number", "is-active")}
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
        {renderPageItems("", "is-current")}
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
