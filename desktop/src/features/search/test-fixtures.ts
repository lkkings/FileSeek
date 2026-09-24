import type { DocumentResult, ImageResult, VideoResult, SearchResults } from "./types";

/** Shaped like what `POST /api/v1/search` actually returns, so tests exercise the real contract. */

export function aDocument(overrides: Partial<DocumentResult> = {}): DocumentResult {
  return {
    file_id: "doc-test",
    filename: "测试文档.pdf",
    preview_url: "http://127.0.0.1:1234/library/files/preview/doc-test",
    score: 85.0,
    matched_text: "这是一段匹配的样本文本内容...",
    path: "/mock/library/documents/测试文档.pdf",
    accessible: true,
    ...overrides,
  };
}

export function anImage(overrides: Partial<ImageResult> = {}): ImageResult {
  return {
    file_id: "img-test",
    filename: "测试图片.jpg",
    preview_url: "http://127.0.0.1:1234/library/files/preview/img-test",
    score: 92.5,
    path: "/mock/library/images/测试图片.jpg",
    accessible: true,
    ...overrides,
  };
}

export function aVideo(overrides: Partial<VideoResult> = {}): VideoResult {
  return {
    file_id: "vid-test",
    filename: "测试视频.mp4",
    preview_url: "http://127.0.0.1:1234/library/files/preview/vid-test",
    score: 78.3,
    path: "/mock/library/videos/测试视频.mp4",
    accessible: true,
    // 命中时刻是扁平的一对时间，不是片段数组。
    start_time: 10,
    end_time: 25,
    ...overrides,
  };
}

export function results(overrides: Partial<SearchResults> = {}): SearchResults {
  return {
    documents: [],
    images: [],
    videos: [],
    ...overrides,
  };
}
