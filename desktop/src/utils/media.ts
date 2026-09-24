/**
 * 媒体字节的取用地址。
 *
 * WebView 不能直接请求后端：`<img src>` / `<video src>` 设不了请求头，而后端要求每个
 * 请求带 `X-FileSeek-Token`。token 也不能交给 WebView（把它留在 Rust 侧正是
 * `src-tauri/src/connection.rs` 的用意），更不能放进查询串——那会落进日志和历史。
 *
 * 所以走 `fileseek://` 自定义协议：`src-tauri/src/media.rs` 接住它，映射到后端的
 * `/api/v1/library/files/preview/<id>`，补上 token，并双向转发 `Range`（播放器靠它 seek）。
 */

/**
 * Tauri 在 Windows 和 Android 上把自定义协议映射成 `http://<scheme>.localhost/...`，
 * 其他平台才是 `<scheme>://localhost/...`（见 tauri 的 `convertFileSrc`）。写死一种
 * 形式会在另一类平台上 404，而 macOS 开发时看不出来。
 */
function protocolBase(): string {
  const isWindowsLike = /windows|android/i.test(navigator.userAgent);
  return isWindowsLike ? "http://fileseek.localhost" : "fileseek://localhost";
}

/** 取一个 file_id 的字节地址。 */
export function mediaUrl(fileId: string): string {
  return `${protocolBase()}/media/${encodeURIComponent(fileId)}`;
}

/**
 * 从搜索结果的 `preview_url` 取出字节地址。
 *
 * 后端给的 `preview_url` 是一个 `http://127.0.0.1:<port>/...` 直链，WebView 用不了它
 * （没有 token 头，必然 401），所以这里只取末尾的 file_id，重新拼成 `fileseek://`。
 * 取不到 id 时返回空串，调用方据此回退到占位图而不是请求一个坏地址。
 */
export function mediaUrlFromPreviewUrl(previewUrl: string | undefined): string {
  if (!previewUrl) return "";
  const fileId = previewUrl.split("/").filter(Boolean).pop();
  return fileId ? mediaUrl(decodeURIComponent(fileId)) : "";
}
