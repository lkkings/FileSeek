import type { PreviewFile, PreviewKind } from "./types";

interface PreviewHeaderProps {
  file: PreviewFile;
  kind: PreviewKind;
  page: number;
  line: number;
  initialTime: number;
  onClose: () => void;
}

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.floor(seconds % 60);
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

export function PreviewHeader({ file, kind, page, line, initialTime, onClose }: PreviewHeaderProps) {
  const extension = file.name.split(".").pop()?.toUpperCase() || "FILE";
  return (
    <header className="preview-header">
      <div className="preview-header__content">
        <div className="preview-header__title-row">
          <h2 className="preview-header__title">FilePreview — {file.name}</h2>
          <span className="preview-badge">{extension}</span>
          {initialTime > 0 && <span className="preview-badge preview-badge--location">已定位至 {formatTime(initialTime)}</span>}
          {kind === "pdf" && <span className="preview-badge preview-badge--location">第 {page} 页 / 第 {line} 行</span>}
          {kind === "document" && <span className="preview-badge preview-badge--location">第 {line} 行</span>}
        </div>
        <span className="preview-header__path">{file.path}</span>
      </div>
      <button type="button" className="preview-close" onClick={onClose} aria-label="关闭文件预览">×</button>
    </header>
  );
}
