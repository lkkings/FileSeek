import { useCallback, useEffect, useRef } from "react";
import type { DocViewerProps, DocViewerRef, DocumentModel } from "anyview";
import { DocViewer } from "anyview";
import "anyview/styles";

const ANYVIEW_HORIZONTAL_PADDING = 48;

const containerStyle = {
  width: "100%",
  height: "100%",
} as const;

interface AdaptiveDocViewerProps extends DocViewerProps {
  initialPageNumber?: number | undefined;
}

export function AdaptiveDocViewer({ initialPageNumber, ...props }: AdaptiveDocViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<DocViewerRef | null>(null);
  const documentRef = useRef<DocumentModel | null>(null);
  const { onDocumentLoad, ...viewerProps } = props;

  const fitToWidth = useCallback(() => {
    const document = documentRef.current;
    const page = document?.pages[0];
    const container = containerRef.current;
    if (!page || !container) return;

    const isRotated = page.rotation === 90 || page.rotation === 270;
    const pageWidth = isRotated ? page.height : page.width;
    const availableWidth = container.clientWidth - ANYVIEW_HORIZONTAL_PADDING;
    if (pageWidth <= 0 || availableWidth <= 0) return;

    viewerRef.current?.setZoom(availableWidth / pageWidth);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return undefined;

    const observer = new ResizeObserver(() => fitToWidth());
    observer.observe(container);
    return () => observer.disconnect();
  }, [fitToWidth]);

  const handleDocumentLoad = useCallback(
    (document: DocumentModel) => {
      documentRef.current = document;
      fitToWidth();
      onDocumentLoad?.(document);
    },
    [fitToWidth, onDocumentLoad],
  );

  return (
    <div ref={containerRef} style={containerStyle}>
      <DocViewer
        {...viewerProps}
        {...(initialPageNumber === undefined ? {} : { page: Math.max(0, initialPageNumber - 1) })}
        ref={viewerRef}
        onDocumentLoad={handleDocumentLoad}
      />
    </div>
  );
}
