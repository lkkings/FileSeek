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
