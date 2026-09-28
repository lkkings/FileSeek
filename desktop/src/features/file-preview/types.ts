export type PreviewCategory = "document" | "image" | "video";

export type PreviewSize = "list" | "detail";

export type PreviewResourceKind = "document" | "image" | "video" | "thumbnail" | "original";

export type PreviewStatus = "idle" | "loading" | "loaded" | "unsupported" | "error";

export type PreviewEnvironment = "browser" | "tauri-development" | "tauri-packaged";

export type PreviewPlatform = "macos" | "windows" | "linux" | "android" | "ios";

export interface FilePreviewItem {
  fileId: string;
  fileName: string;
  fileType: PreviewCategory;
}

export interface PreviewUrlOptions {
  environment?: PreviewEnvironment;
  platform?: PreviewPlatform;
}

export interface PreviewRuntimeInput {
  isTauri?: boolean;
  isDevelopment?: boolean;
  platform?: PreviewPlatform;
}

export type DocumentPreviewSupport = "supported" | "unsupported";
