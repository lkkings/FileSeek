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
