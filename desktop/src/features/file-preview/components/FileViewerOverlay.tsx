import { useEffect, useRef, useState } from "react";
import { DocViewer } from "anyview";
import videojs from "video.js";

import { useTranslate } from "../../../i18n/useTranslate";
import { DocumentFormatIcon } from "./DocumentFormatIcon";
import { buildOriginalFileUrl, buildPreviewUrl, getDocumentPreviewSupport } from "../preview";
import type { FilePreviewItem, PreviewUrlOptions } from "../types";
import "./FileViewerOverlay.css";

type VideoPlayer = ReturnType<typeof videojs>;

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
    return <DocumentViewerSurface item={item} urlOptions={urlOptions} />;
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
  const documentSupport = getDocumentPreviewSupport(item);

  if (documentSupport !== "supported") {
    return (
      <div className="file-viewer-fallback">
        <DocumentFormatIcon fileName={item.fileName} isUnsupported />
        <p>{t("preview.unsupported", "该格式暂不支持预览")}</p>
      </div>
    );
  }

  return (
    <DocViewer
      source={{
        kind: "url",
        url: buildOriginalFileUrl(item, urlOptions),
        filename: item.fileName,
      }}
      showToolbar
      showSidebar
      persistKey={`file-preview-${item.fileId}`}
    />
  );
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
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<VideoPlayer | null>(null);
  const sourceUrl = buildOriginalFileUrl(item, urlOptions);
  const posterUrl = buildPreviewUrl(item, "detail", urlOptions);

  useEffect(() => {
    const videoElement = containerRef.current?.querySelector("video");
    if (!videoElement) return;

    const player = videojs(videoElement, {
      controls: true,
      preload: "auto",
      responsive: true,
      poster: posterUrl,
    });
    playerRef.current = player;

    return () => {
      playerRef.current?.dispose();
      playerRef.current = null;
    };
  }, [posterUrl, sourceUrl]);

  return (
    <div className="file-viewer-video" ref={containerRef}>
      <video src={sourceUrl} controls playsInline data-testid="viewer-video-player" />
    </div>
  );
}
