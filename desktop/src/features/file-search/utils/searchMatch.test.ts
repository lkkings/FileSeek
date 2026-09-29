import { describe, expect, it } from "vitest";

import { formatSearchMatchNotice, truncateMatchText } from "./searchMatch";
import type { FileMetadata } from "../../../services/api/search";

function createTranslate() {
  return (id: string, message: string, values?: Record<string, unknown>) =>
    message.replace(/\{(\w+)\}/g, (_match, key: string) => String(values?.[key] ?? ""));
}

describe("searchMatch", () => {
  it("describes a video hit time range", () => {
    const metadata: FileMetadata = { start_time: 191.191, end_time: 192.192 };

    expect(formatSearchMatchNotice(metadata, createTranslate())).toBe(
      "命中时间：191.191-192.192 秒",
    );
  });

  it("describes a document hit with its location", () => {
    const metadata: FileMetadata = {
      text: "命中文本",
      page_number: 1,
      line_number: 1,
      chunk_index: 0,
    };

    expect(formatSearchMatchNotice(metadata, createTranslate())).toBe(
      "命中：命中文本（第 1 页，第 1 行，片段 0）",
    );
  });

  it("truncates long matched text", () => {
    const text = "一".repeat(100);
    const metadata: FileMetadata = { text };

    expect(formatSearchMatchNotice(metadata, createTranslate())).toBe(
      `命中文本：${"一".repeat(80)}…`,
    );
    expect(truncateMatchText(text, 10)).toBe(`${"一".repeat(10)}…`);
  });

  it("ignores metadata without user-facing hit information", () => {
    expect(formatSearchMatchNotice({ raw_score: 0.8 }, createTranslate())).toBeNull();
  });
});
