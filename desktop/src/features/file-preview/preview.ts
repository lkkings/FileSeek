import type {
  DocumentPreviewSupport,
  FilePreviewItem,
  PreviewEnvironment,
  PreviewPlatform,
  PreviewRuntimeInput,
  PreviewResourceKind,
  PreviewSize,
  PreviewUrlOptions,
} from "./types";
import { isTauriRuntime } from "../../services/tauri/api";

const SUPPORTED_DOCUMENT_EXTENSIONS = new Set([
  "pdf",
  "docx",
  "xlsx",
  "pptx",
  "csv",
  "md",
  "markdown",
  "html",
  "htm",
  "txt",
  "xml",
  "json",
  "yaml",
  "yml",
  "toml",
  "ini",
  "log",
  "js",
  "jsx",
  "ts",
  "tsx",
  "css",
  "py",
  "rs",
  "java",
  "c",
  "h",
  "cpp",
  "cs",
  "go",
  "rb",
  "php",
  "sh",
  "sql",
]);

const API_PREFIX = "/api/v1";

export function getFileExtension(fileName: string) {
  const normalized = fileName.trim().toLowerCase();
  const extensionStart = normalized.lastIndexOf(".");
  return extensionStart === -1 ? "" : normalized.slice(extensionStart + 1);
}

export function getDocumentFormat(fileName: string) {
  const extension = getFileExtension(fileName);
  return extension ? extension.toUpperCase() : "FILE";
}

export function getDocumentPreviewSupport(item: FilePreviewItem): DocumentPreviewSupport | null {
  if (item.fileType !== "document") return null;
  return SUPPORTED_DOCUMENT_EXTENSIONS.has(getFileExtension(item.fileName)) ? "supported" : "unsupported";
}

export function getPreviewResourceKind(item: FilePreviewItem): PreviewResourceKind {
  if (item.fileType === "image" || item.fileType === "video") return "thumbnail";
  return "document";
}

export function resolvePreviewEnvironment(input: { isTauri: boolean; isDevelopment: boolean }): PreviewEnvironment {
  if (!input.isTauri) return "browser";
  return input.isDevelopment ? "tauri-development" : "tauri-packaged";
}

export function getPreviewUrlOptions(input: PreviewRuntimeInput = {}): PreviewUrlOptions {
  const environment = resolvePreviewEnvironment({
    isTauri: input.isTauri ?? isTauriRuntime(),
    isDevelopment: input.isDevelopment ?? import.meta.env.DEV,
  });

  return {
    environment,
    platform: input.platform ?? inferPreviewPlatform(),
  };
}

function inferPreviewPlatform(): PreviewPlatform {
  const userAgent = navigator.userAgent;
  if (/android/i.test(userAgent)) return "android";
  if (/iphone|ipad|ipod/i.test(userAgent)) return "ios";
  if (/windows/i.test(userAgent)) return "windows";
  if (/macintosh|mac os/i.test(userAgent)) return "macos";
  return "linux";
}

export function buildPreviewUrl(item: FilePreviewItem, size: PreviewSize, options: PreviewUrlOptions = {}): string {
  const base = getPreviewBaseUrl(options);
  const encodedFileId = encodeURIComponent(item.fileId);
  const resourceKind = getPreviewResourceKind(item);

  if (resourceKind === "thumbnail") {
    return `${base}${API_PREFIX}/library/files/${encodedFileId}/thumbnail?size=${size}`;
  }

  return `${base}${API_PREFIX}/library/files/preview/${encodedFileId}`;
}

export function buildOriginalFileUrl(item: FilePreviewItem, options: PreviewUrlOptions = {}) {
  const base = getPreviewBaseUrl(options);
  return `${base}${API_PREFIX}/library/files/preview/${encodeURIComponent(item.fileId)}`;
}

function getPreviewBaseUrl(options: PreviewUrlOptions) {
  const runtimeOptions = getPreviewUrlOptions();
  const environment = options.environment ?? runtimeOptions.environment;
  const platform = options.platform ?? runtimeOptions.platform;
  if (environment !== "tauri-packaged") return "";

  if (platform === "windows" || platform === "android") {
    return "http://fileseek-preview.localhost";
  }

  return "fileseek-preview://localhost";
}
