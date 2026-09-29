import { Component, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AdaptiveDocViewer } from "./AdaptiveDocViewer";

import { useTranslate } from "../../../i18n/useTranslate";
import { DocumentFormatIcon } from "./DocumentFormatIcon";
import { buildOriginalFileUrl, buildPreviewUrl, getDocumentPreviewSupport, getImagePreviewSupport } from "../preview";
import type { FilePreviewItem, PreviewUrlOptions } from "../types";
import { VideoJsPlayer } from "./VideoJsPlayer";
import "./FileViewerOverlay.css";

export interface FileViewerOverlayProps {
  isOpen: boolean;
  item: FilePreviewItem | null;
  onClose: () => void;
  urlOptions?: PreviewUrlOptions | undefined;
}

export function FileViewerOverlay({ isOpen, item, onClose, urlOptions }: FileViewerOverlayProps) {
  const t = useTranslate();
  const closeButtonRef = useRef<HTMLButtonElement | null>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      restoreFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      closeButtonRef.current?.focus();
      return undefined;
    }

    restoreFocusRef.current?.focus();
    restoreFocusRef.current = null;
    return undefined;
  }, [isOpen]);

  if (!isOpen || !item) return null;

  return (
    <div
      className="file-viewer-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={t("preview.viewerTitle", "文件预览")}
      onKeyDown={(event) => {
        if (event.key === "Escape") onClose();
      }}
    >
      <header className="file-viewer-header">
        <h2>{item.fileName}</h2>
        <button
          ref={closeButtonRef}
          type="button"
          onClick={onClose}
          aria-label={t("dialog.close", "关闭")}
        >
          {t("dialog.close", "关闭")}
        </button>
      </header>
      <div className="file-viewer-content">
        <FileViewerSurface item={item} urlOptions={urlOptions} />
      </div>
    </div>
  );
}

function FileViewerSurface({
  item,
  urlOptions,
}: {
  item: FilePreviewItem;
  urlOptions?: PreviewUrlOptions | undefined;
}) {
  if (item.fileType === "document") {
    return <DocumentViewerSurface key={item.fileId} item={item} urlOptions={urlOptions} />;
  }

  if (item.fileType === "image") {
    return <ImageViewerSurface item={item} urlOptions={urlOptions} />;
  }

  return <VideoViewerSurface item={item} urlOptions={urlOptions} />;
}

function DocumentViewerSurface({
  item,
  urlOptions,
}: {
  item: FilePreviewItem;
  urlOptions?: PreviewUrlOptions | undefined;
}) {
  const t = useTranslate();
  const [hasError, setHasError] = useState(false);
  const documentSupport = getDocumentPreviewSupport(item);

  if (documentSupport !== "supported" || hasError) {
    return (
      <div className="file-viewer-fallback" role={hasError ? "alert" : undefined}>
        <DocumentFormatIcon
          fileName={item.fileName}
          isUnsupported={documentSupport === "unsupported" || hasError}
        />
        <p>
          {hasError
            ? t("preview.documentError", "文档预览加载失败")
            : t("preview.unsupported", "该格式暂不支持预览")}
        </p>
      </div>
    );
  }

  return (
    <DocumentViewerErrorBoundary fallback={documentErrorFallback(item, t)}>
      <AdaptiveDocViewer
        source={{
          kind: "url",
          url: buildOriginalFileUrl(item, urlOptions),
          filename: item.fileName,
        }}
        initialPageNumber={item.initialPageNumber}
        showToolbar
        showSidebar
        persistKey={`file-preview-${item.fileId}`}
        onError={() => setHasError(true)}
      />
    </DocumentViewerErrorBoundary>
  );
}

function documentErrorFallback(item: FilePreviewItem, t: ReturnType<typeof useTranslate>) {
  return (
    <div className="file-viewer-fallback" role="alert">
      <DocumentFormatIcon fileName={item.fileName} isUnsupported />
      <p>{t("preview.documentError", "文档预览加载失败")}</p>
    </div>
  );
}

class DocumentViewerErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    return this.state.hasError ? this.props.fallback : this.props.children;
  }
}

function ImageViewerSurface({
  item,
  urlOptions,
}: {
  item: FilePreviewItem;
  urlOptions?: PreviewUrlOptions | undefined;
}) {
  const [hasError, setHasError] = useState(false);
  const t = useTranslate();

  if (getImagePreviewSupport(item) === "unsupported") {
    return <div className="file-viewer-fallback" role="status">{t("preview.unsupported", "该格式暂不支持预览")}</div>;
  }

  if (hasError) {
    return <div className="file-viewer-fallback" role="alert">{t("preview.error", "预览加载失败")}</div>;
  }

  return (
    <img
      src={buildOriginalFileUrl(item, urlOptions)}
      alt={item.fileName}
      onError={() => setHasError(true)}
    />
  );
}

function VideoViewerSurface({
  item,
  urlOptions,
}: {
  item: FilePreviewItem;
  urlOptions?: PreviewUrlOptions | undefined;
}) {
  const sourceUrl = buildOriginalFileUrl(item, urlOptions);
  const posterUrl = buildPreviewUrl(item, "detail", urlOptions);

  return (
    <VideoJsPlayer
      className="file-viewer-video"
      sourceUrl={sourceUrl}
      startTime={item.startTime}
      posterUrl={posterUrl}
      testId="viewer-video-player"
    />
  );
}
