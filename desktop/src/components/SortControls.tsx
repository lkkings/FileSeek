import { useState, useRef, useEffect } from "react";
import { Icon } from "./Icon";
import { useTranslate } from "../i18n/useTranslate";

export type SortMode = "relevance" | "created_at" | "size";

export interface SortOption {
  value: SortMode;
  label: string;
}

interface SortControlsProps {
  options: SortOption[];
  sortBy: SortMode;
  sortOrder: "asc" | "desc";
  onSortByChange: (sortBy: SortMode) => void;
  onSortOrderChange: (order: "asc" | "desc") => void;
}

export function SortControls({
  options,
  sortBy,
  sortOrder,
  onSortByChange,
  onSortOrderChange,
}: SortControlsProps) {
  const t = useTranslate();
  const [sortOpen, setSortOpen] = useState(false);
  const sortMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (sortMenuRef.current && !sortMenuRef.current.contains(event.target as Node)) {
        setSortOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const activeOption = options.find((opt) => opt.value === sortBy) || options[0];

  return (
    <div className="sort-controls-wrap" ref={sortMenuRef}>
      <div className="sort-wrap">
        <button
          className="sort-button"
          type="button"
          aria-expanded={sortOpen}
          onClick={() => setSortOpen((current) => !current)}
        >
          <Icon name={sortOrder === "asc" ? "sort-asc" : "sort-desc"} size={19} />
          <span>{t(`search.sort.${sortBy}`, activeOption?.label || "")}</span>
        </button>
        {sortOpen && (
          <div className="sort-menu" role="menu">
            {options.map((option) => (
              <button
                className={option.value === sortBy ? "is-selected" : ""}
                key={option.value}
                type="button"
                role="menuitem"
                onClick={() => {
                  if (option.value === sortBy) {
                    onSortOrderChange(sortOrder === "asc" ? "desc" : "asc");
                  } else {
                    onSortByChange(option.value);
                    onSortOrderChange("desc");
                  }
                  setSortOpen(false);
                }}
              >
                {t(`search.sort.${option.value}`, option.label)}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
