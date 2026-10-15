export interface FolderRecord {
  id: string;
  name: string;
  iconType: string;
  description: string;
  modified: string;
  fileCount: number;
}

export interface FolderFormValues {
  name: string;
  iconType: string;
  description: string;
}

export type FolderSourceWatchStatus =
  | "watching"
  | "disabled"
  | "unavailable"
  | "error";

export interface FolderSourceBinding {
  id: string;
  folderId: string;
  storageId: string;
  sourcePath: string;
  recursive: boolean;
  enabled: boolean;
  watchStatus: FolderSourceWatchStatus;
  lastError: string | null;
  lastErrorAt: string | null;
}

export interface FolderSourceBindingInput {
  storageId: string;
  path: string;
  recursive: boolean;
  enabled: boolean;
}

export interface ImportFileSelection {
  storageId: string;
  path: string;
}

export type ImportProgressItemState =
  | "queued"
  | "registered"
  | "processing"
  | "completed"
  | "failed";

export interface ImportProgressItem {
  storageId: string;
  path: string;
  state: ImportProgressItemState;
  fileId: string | null;
  taskId: string | null;
  error: string | null;
}

export type BatchImportStateStatus =
  | "idle"
  | "starting"
  | "running"
  | "completed"
  | "failed";

export interface BatchImportState {
  importId: string | null;
  status: BatchImportStateStatus;
  total: number;
  succeeded: number;
  failed: number;
  items: ImportProgressItem[];
  error: string | null;
}
