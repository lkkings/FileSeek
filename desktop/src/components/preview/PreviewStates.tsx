export function PreviewLoadingState() {
  return <div className="preview-state" role="status"><div className="search-bar__spinner preview-state__spinner" /><span>正在解码并加载文件预览...</span></div>;
}

export function PreviewErrorState({ message }: { message: string }) {
  return <div className="preview-state preview-state--error" role="alert">{message}</div>;
}

export function UnsupportedPreview() {
  return <div className="preview-state" role="status">暂不支持此文件格式的预览。</div>;
}
