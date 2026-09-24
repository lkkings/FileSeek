import type { PreviewFile } from "./types";

export function DocumentPreview({ file, line, matchedText }: { file: PreviewFile; line: number; matchedText: string }) {
  return <div className="preview-paper-stage"><article className="preview-paper preview-paper--word"><h1>{file.name.replace(/\.docx?$/i, "")}</h1><p className="preview-paper__meta">文档预览 · {file.size || "未知大小"}</p><h2>报告概述与分析背景</h2><p>该文档通过统一的预览路由呈现，业务状态与具体格式渲染相互隔离。</p><div className="preview-match"><strong>搜索高亮定位（第 {line} 行）</strong><p>{matchedText || "这是搜索结果命中的文档内容。"}</p></div><h2>实验结果与评估</h2><p>组件拆分后，各格式预览可以独立维护和测试。</p></article></div>;
}
