import { SearchInput } from "./SearchInput";
import { AdvancedFiltersDrawer } from "./AdvancedFiltersDrawer";

type FileTypeFilter = "all" | "document" | "image" | "video";

interface SearchBarProps {
  onSearch: (query: string) => void;
  busy: boolean;
  filtersOpen: boolean;
  setFiltersOpen: (open: boolean) => void;
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

/** Composes the search input and the collapsible advanced-filters drawer. */
export function SearchBar({
  onSearch,
  busy,
  filtersOpen,
  setFiltersOpen,
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
}: SearchBarProps) {
  return (
    <div className="search-bar-container" style={{ width: "100%", display: "flex", flexDirection: "column", gap: "12px" }}>
      <SearchInput
        onSearch={onSearch}
        busy={busy}
        filtersOpen={filtersOpen}
        onToggleFilters={() => setFiltersOpen(!filtersOpen)}
      />

      {filtersOpen && (
        <AdvancedFiltersDrawer
          filterName={filterName}
          setFilterName={setFilterName}
          filterFileType={filterFileType}
          setFilterFileType={setFilterFileType}
          filterMinSize={filterMinSize}
          setFilterMinSize={setFilterMinSize}
          filterMaxSize={filterMaxSize}
          setFilterMaxSize={setFilterMaxSize}
          filterStartDate={filterStartDate}
          setFilterStartDate={setFilterStartDate}
          filterEndDate={filterEndDate}
          setFilterEndDate={setFilterEndDate}
          onResetFilters={onResetFilters}
        />
      )}
    </div>
  );
}

export default SearchBar;
