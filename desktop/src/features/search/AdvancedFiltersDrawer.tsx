import type { ReactNode } from "react";
import { useTranslation } from "../../i18n/useTranslation";

type FileTypeFilter = "all" | "document" | "image" | "video";

interface AdvancedFiltersDrawerProps {
  filterName: string;
  setFilterName: (name: string) => void;
  filterFileType: FileTypeFilter;
  setFilterFileType: (type: FileTypeFilter) => void;
  filterMinSize: string;
  setFilterMinSize: (min: string) => void;
  filterMaxSize: string;
  setFilterMaxSize: (max: string) => void;
  filterStartDate: string;
  setFilterStartDate: (start: string) => void;
  filterEndDate: string;
  setFilterEndDate: (end: string) => void;
  onResetFilters: () => void;
}

const FILE_TYPE_ICONS: Record<FileTypeFilter, ReactNode> = {
  all: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <line x1="9" y1="3" x2="9" y2="21" />
    </svg>
  ),
  document: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
      <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  ),
  image: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <polyline points="21 15 16 10 5 21" />
    </svg>
  ),
  video: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
      <circle cx="12" cy="12" r="9" />
      <polygon points="10 8 16 12 10 16 10 8" fill="currentColor" stroke="none" />
    </svg>
  ),
};

const FILE_TYPE_OPTIONS: { key: FileTypeFilter; labelKey: "search.filterAll" | "search.filterDocument" | "search.filterImage" | "search.filterVideo" }[] = [
  { key: "all", labelKey: "search.filterAll" },
  { key: "document", labelKey: "search.filterDocument" },
  { key: "image", labelKey: "search.filterImage" },
  { key: "video", labelKey: "search.filterVideo" },
];

/** The collapsible advanced-filters panel: filename, file type, size range, date range. */
export function AdvancedFiltersDrawer({
  filterName,
  setFilterName,
  filterFileType,
  setFilterFileType,
  filterMinSize,
  setFilterMinSize,
  filterMaxSize,
  setFilterMaxSize,
  filterStartDate,
  setFilterStartDate,
  filterEndDate,
  setFilterEndDate,
  onResetFilters,
}: AdvancedFiltersDrawerProps) {
  const { t } = useTranslation();

  return (
    <div className="advanced-filters-drawer" style={{ width: "100%", boxSizing: "border-box" }}>
      <div className="advanced-filters-header">
        <div className="advanced-filters-header__heading">
          <svg className="advanced-filters-header__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="20" height="20">
            <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
          </svg>
          <div>
            <div className="advanced-filters-header__label">高级筛选</div>
            <div className="advanced-filters-header__sublabel">精确查找您需要的文件</div>
          </div>
        </div>
        <button type="button" className="theme-btn theme-btn--outline theme-btn--sm" onClick={onResetFilters}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="12" height="12" style={{ marginRight: "5px" }}>
            <polyline points="1 4 1 10 7 10" />
            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
          </svg>
          重置筛选
        </button>
      </div>

      <div className="advanced-filters-grid">
        {/* Filter 1: By Filename */}
        <div className="form-group">
          <label>文件名关键字</label>
          <input
            type="text"
            className="theme-input"
            value={filterName}
            onChange={(e) => setFilterName(e.target.value)}
            placeholder="模糊匹配名称"
          />
        </div>

        {/* Filter 2: By File Type */}
        <div className="form-group">
          <label>文件类型</label>
          <div className="filetype-chip-row">
            {FILE_TYPE_OPTIONS.map((opt) => (
              <button
                key={opt.key}
                type="button"
                className={`filetype-chip ${filterFileType === opt.key ? "filetype-chip--active" : ""}`}
                onClick={() => setFilterFileType(opt.key)}
              >
                {FILE_TYPE_ICONS[opt.key]}
                {t(opt.labelKey)}
              </button>
            ))}
          </div>
        </div>

        {/* Filter 3: By Size Range (Min - Max MB) */}
        <div className="form-group">
          <label>文件大小范围 (MB)</label>
          <div className="filters-range-row">
            <input
              type="number"
              className="theme-input"
              value={filterMinSize}
              onChange={(e) => setFilterMinSize(e.target.value)}
              placeholder="最小 MB"
              min="0"
            />
            <span>-</span>
            <input
              type="number"
              className="theme-input"
              value={filterMaxSize}
              onChange={(e) => setFilterMaxSize(e.target.value)}
              placeholder="最大 MB"
              min="0"
            />
          </div>
        </div>
      </div>

      {/* Filter 4: By Date Range (Start - End Date), full width row below the divider */}
      <div className="advanced-filters-daterow">
        <label>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14" style={{ marginRight: "6px", verticalAlign: "-2px" }}>
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          创建时间范围
        </label>
        <div className="filters-range-row advanced-filters-daterow__inputs">
          <input
            type="date"
            className="theme-input"
            value={filterStartDate}
            onChange={(e) => setFilterStartDate(e.target.value)}
            onClick={(e) => e.currentTarget.showPicker?.()}
          />
          <span>-</span>
          <input
            type="date"
            className="theme-input"
            value={filterEndDate}
            onChange={(e) => setFilterEndDate(e.target.value)}
            onClick={(e) => e.currentTarget.showPicker?.()}
          />
        </div>
      </div>
    </div>
  );
}

export default AdvancedFiltersDrawer;
