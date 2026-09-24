import { useState } from "react";
import type { PreviewFile } from "./types";

interface PdfPreviewProps { file: PreviewFile; initialPage: number; line: number; matchedText: string; onPageChange: (page: number) => void }

export function PdfPreview({ file, initialPage, line, matchedText, onPageChange }: PdfPreviewProps) {
  const [page, setPage] = useState(initialPage);
  const [scale, setScale] = useState(1);
  const totalPages = 5;
  const changePage = (next: number) => { setPage(next); onPageChange(next); };
  return (
    <div className="preview-document">
      <div className="preview-toolbar">
        <div className="preview-toolbar__group">
          <button type="button" disabled={page === 1} onClick={() => changePage(Math.max(1, page - 1))} aria-label="上一页">←</button>
          <span>第 {page} / {totalPages} 页</span>
          <button type="button" disabled={page === totalPages} onClick={() => changePage(Math.min(totalPages, page + 1))} aria-label="下一页">→</button>
        </div>
        <div className="preview-toolbar__group">
          <button type="button" onClick={() => setScale((value) => Math.max(0.5, value - 0.1))} aria-label="缩小 PDF">−</button>
          <span>{Math.round(scale * 100)}%</span>
          <button type="button" onClick={() => setScale((value) => Math.min(2, value + 0.1))} aria-label="放大 PDF">＋</button>
        </div>
      </div>
      <div className="preview-paper-stage">
        <article className="preview-paper" style={{ width: 595 * scale, minHeight: 842 * scale, fontSize: 13 * scale }}>
          <h1>{file.name.replace(/\.pdf$/i, "")}</h1>
          <p className="preview-paper__meta">PDF 格式档案 · 第 {page} 页</p>
          <h2>{page === 1 ? "核心要点及分析" : `技术附录与架构（第 ${page} 页）`}</h2>
          <p>FileSeek 使用多模态索引为文档、图片和视频提供统一的语义检索体验，并保持文件库元数据与搜索结果一致。</p>
          {page === initialPage && <div className="preview-match"><strong>匹配高亮 L.{line}</strong><p>{matchedText || "搜索结果命中的文档内容。"}</p></div>}
        </article>
      </div>
    </div>
  );
}
