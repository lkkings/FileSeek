import type { FileItem } from "./useLibrary";

export interface FileFilters {
  activeCategory: "all" | "document" | "image" | "video";
  searchQuery: string | null;
  filterName: string;
  filterMinSize: string;
  filterMaxSize: string;
  filterStartDate: string;
  filterEndDate: string;
}

export function filterFiles(files: FileItem[], filters: FileFilters): FileItem[] {
  return files.filter((item) => {
    if (filters.activeCategory !== "all" && item.category !== filters.activeCategory) return false;
    const query = filters.searchQuery?.toLowerCase();
    if (query && !item.name.toLowerCase().includes(query)) return false;
    if (filters.filterName && !item.name.toLowerCase().includes(filters.filterName.toLowerCase())) return false;
    const sizeMb = item.sizeBytes / (1024 * 1024);
    if (filters.filterMinSize && sizeMb < Number(filters.filterMinSize)) return false;
    if (filters.filterMaxSize && sizeMb > Number(filters.filterMaxSize)) return false;
    const date = item.modified.substring(0, 10);
    if (filters.filterStartDate && date < filters.filterStartDate) return false;
    if (filters.filterEndDate && date > filters.filterEndDate) return false;
    return true;
  });
}

export function sortFiles(files: FileItem[], sortBy: "name" | "size" | "time", sortOrder: "asc" | "desc"): FileItem[] {
  return [...files].sort((a, b) => {
    const comparison = sortBy === "name" ? a.name.localeCompare(b.name, "zh-CN") : sortBy === "size" ? a.sizeBytes - b.sizeBytes : new Date(a.modified).getTime() - new Date(b.modified).getTime();
    return sortOrder === "asc" ? comparison : -comparison;
  });
}
