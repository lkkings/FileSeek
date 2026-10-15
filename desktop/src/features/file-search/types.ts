import type { FileType as BaseFileType } from "../../types/file";

export type FileType = "all" | BaseFileType;
export type SearchMode = "advanced" | "enhanced";

export interface SearchFilters {
  globalQuery: string;
  nameQuery: string;
  fileType: FileType;
  minSize: string;
  maxSize: string;
  startDate: string;
  endDate: string;
}

export type SearchFilterKey = keyof SearchFilters;
