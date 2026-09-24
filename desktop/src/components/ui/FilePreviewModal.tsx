import { useEffect, useState } from "react";
import { useTranslation } from "../../i18n/useTranslation";
import { DocumentPreview } from "../preview/DocumentPreview";
import { ImagePreview } from "../preview/ImagePreview";
import { PdfPreview } from "../preview/PdfPreview";
import { PresentationPreview } from "../preview/PresentationPreview";
import { PreviewLoadingState, UnsupportedPreview } from "../preview/PreviewStates";
import { PreviewHeader } from "../preview/PreviewHeader";
import { SpreadsheetPreview } from "../preview/SpreadsheetPreview";
import { VideoPreview } from "../preview/VideoPreview";
import { previewKind, type PreviewFile } from "../preview/types";
import "../preview/preview.css";

export type { PreviewFile, PreviewSegment } from "../preview/types";

interface FilePreviewModalProps { file: PreviewFile; initialTime?: number; initialPage?: number; initialLine?: number; matchedText?: string; onClose: () => void }

export function FilePreviewModal({ file, initialTime, initialPage, initialLine, matchedText, onClose }: FilePreviewModalProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(initialPage ?? file.initialPage ?? 1);
  const pageKey = `${file.id}:${initialPage ?? file.initialPage ?? 1}`;
  const [previousPageKey, setPreviousPageKey] = useState(pageKey);
  if (previousPageKey !== pageKey) {
    setPreviousPageKey(pageKey);
    setPage(initialPage ?? file.initialPage ?? 1);
  }
  const kind = previewKind(file.name);
  const line = initialLine ?? file.initialLine ?? 12;
  const time = initialTime ?? file.initialTime ?? 0;
  useEffect(() => {
    const timer = window.setTimeout(() => setLoading(false), 300);
    return () => window.clearTimeout(timer);
  }, [file.id, initialPage, file.initialPage]);
  const content = loading ? <PreviewLoadingState /> : (() => {
    switch (kind) {
      case "image": return <ImagePreview file={file} />;
      case "pdf": return <PdfPreview file={file} initialPage={page} line={line} matchedText={matchedText ?? file.matchedText ?? ""} onPageChange={setPage} />;
      case "document": return <DocumentPreview file={file} line={line} matchedText={matchedText ?? file.matchedText ?? ""} />;
      case "spreadsheet": return <SpreadsheetPreview />;
      case "presentation": return <PresentationPreview file={file} />;
      case "video": return <VideoPreview file={file} initialTime={time} />;
      default: return <UnsupportedPreview />;
    }
  })();
  return <div className="preview-backdrop" role="dialog" aria-modal="true" aria-label={`${t("search.openInSystem")}: ${file.name}`} onClick={onClose}><div className="preview-modal" onClick={(event) => event.stopPropagation()}><PreviewHeader file={file} kind={kind} page={page} line={line} initialTime={time} onClose={onClose} /><div className="preview-body">{content}</div></div></div>;
}

export default FilePreviewModal;
