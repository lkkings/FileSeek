import { Icon } from "../../../components/Icon";
import { useTranslate } from "../../../i18n/useTranslate";
import type { FileType, SearchFilterKey, SearchFilters } from "../types";
import "./search.css";

interface AdvancedFiltersProps {
  filters: SearchFilters;
  onUpdate: <Key extends SearchFilterKey>(key: Key, value: SearchFilters[Key]) => void;
  onReset: () => void;
}

const typeOptions: Array<{ id: FileType; labelId: string; label: string; icon: "archive" | "document" | "image" | "video" }> = [
  { id: "all", labelId: "fileType.all", label: "全部", icon: "archive" },
  { id: "document", labelId: "fileType.document", label: "文档", icon: "document" },
  { id: "image", labelId: "fileType.image", label: "图片", icon: "image" },
  { id: "video", labelId: "fileType.video", label: "视频", icon: "video" },
];

export function AdvancedFilters({ filters, onUpdate, onReset }: AdvancedFiltersProps) {
  const t = useTranslate();

  return (
    <section className="filter-panel" id="advanced-filter" aria-labelledby="filter-title">
      <div className="filter-heading">
        <div className="filter-title-compact">
          <Icon name="filter" size={16} />
          <span id="filter-title">{t("search.advanced.title", "高级筛选")}</span>
        </div>
        <button className="reset-button-compact" type="button" onClick={onReset}>
          <Icon name="refresh" size={14} />
          <span>{t("search.advanced.reset", "重置")}</span>
        </button>
      </div>

      <div className="filter-grid-row">
        <label className="filter-field">
          <span>{t("search.name.label", "文件名关键字")}</span>
          <div className="control search-control">
            <Icon name="search" size={16} />
            <input aria-label={t("search.name.label", "文件名关键字")} placeholder={t("search.name.placeholder", "模糊匹配名称")} value={filters.nameQuery} onChange={(event) => onUpdate("nameQuery", event.target.value)} />
          </div>
        </label>

        <fieldset className="type-field">
          <legend>{t("search.type.label", "文件类型")}</legend>
          <div className="type-options">
            {typeOptions.map((option) => (
              <button className={`type-option ${filters.fileType === option.id ? "is-selected" : ""}`} key={option.id} type="button" onClick={() => onUpdate("fileType", option.id)}>
                <Icon name={option.icon} size={14} />
                <span>{t(option.labelId, option.label)}</span>
              </button>
            ))}
          </div>
        </fieldset>

        <label className="filter-field">
          <span>{t("search.size.label", "文件大小范围 (MB)")}</span>
          <div className="range-controls">
            <input className="control" aria-label={t("search.size.min", "最小文件大小")} placeholder={t("search.size.min", "最小 MB")} value={filters.minSize} onChange={(event) => onUpdate("minSize", event.target.value)} />
            <b>-</b>
            <input className="control" aria-label={t("search.size.max", "最大文件大小")} placeholder={t("search.size.max", "最大 MB")} value={filters.maxSize} onChange={(event) => onUpdate("maxSize", event.target.value)} />
          </div>
        </label>

        <div className="filter-field">
          <span className="date-label-compact">{t("search.date.label", "创建时间范围")}</span>
          <div className="date-controls">
            <DateInput label={t("search.date.start", "开始")} value={filters.startDate} onChange={(value) => onUpdate("startDate", value)} />
            <b>-</b>
            <DateInput label={t("search.date.end", "结束")} value={filters.endDate} onChange={(value) => onUpdate("endDate", value)} />
          </div>
        </div>
      </div>
    </section>
  );
}

function DateInput({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  const t = useTranslate();

  return (
    <label className="control date-control">
      <input aria-label={label} type="date" value={value} onChange={(event) => onChange(event.target.value)} />
      <Icon name="calendar" size={14} />
      <span>{value || t("search.date.placeholder", "年 / 月 / 日")}</span>
    </label>
  );
}
