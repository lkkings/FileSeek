export interface PreviewSegment {
  id: string;
  start_time: number;
  end_time: number;
  summary: string;
  score: number;
}

export interface PreviewFile {
  id: string;
  name: string;
  path: string;
  category?: "image" | "video" | "document" | "other";
  size?: string;
  modified?: string;
  initialTime?: number;
  initialPage?: number;
  initialLine?: number;
  matchedText?: string;
  segments?: PreviewSegment[];
}

export type PreviewKind = "image" | "pdf" | "document" | "spreadsheet" | "presentation" | "video" | "unsupported";

export function previewKind(fileName: string): PreviewKind {
  const extension = fileName.split(".").pop()?.toLowerCase() ?? "";
  if (["jpg", "jpeg", "png", "gif", "webp", "svg"].includes(extension)) return "image";
  if (extension === "pdf") return "pdf";
  if (["doc", "docx"].includes(extension)) return "document";
  if (["xls", "xlsx", "csv"].includes(extension)) return "spreadsheet";
  if (["ppt", "pptx"].includes(extension)) return "presentation";
  if (["mp4", "mkv", "avi", "mov", "flv", "wmv", "ts"].includes(extension)) return "video";
  return "unsupported";
}
