import type { FileMetadata } from "../../../services/api/search";

export type Translate = (
  id: string,
  message: string,
  values?: Record<string, unknown>,
) => string;

const MATCH_TEXT_LIMIT = 80;

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function truncateMatchText(text: string, limit: number = MATCH_TEXT_LIMIT): string {
  const characters = Array.from(text.trim());
  if (characters.length <= limit) return characters.join("");
  return `${characters.slice(0, limit).join("")}…`;
}

export function formatSearchMatchNotice(metadata: FileMetadata | null | undefined, t: Translate): string | null {
  if (!metadata) return null;

  const startTime = isFiniteNumber(metadata.start_time) ? metadata.start_time : undefined;
  if (startTime !== undefined) {
    const endTime = isFiniteNumber(metadata.end_time) ? metadata.end_time : undefined;
    return t(
      "search.matchVideo",
      "命中时间：{range} 秒",
      { range: endTime === undefined ? `${startTime}` : `${startTime}-${endTime}` },
    );
  }

  const text = typeof metadata.text === "string" ? metadata.text.trim() : "";
  const pageNumber = isFiniteNumber(metadata.page_number) ? metadata.page_number : undefined;
  if (!text && pageNumber === undefined) return null;

  const details = [
    pageNumber === undefined ? null : t("search.matchPage", "第 {page} 页", { page: pageNumber }),
    isFiniteNumber(metadata.line_number)
      ? t("search.matchLine", "第 {line} 行", { line: metadata.line_number })
      : null,
    isFiniteNumber(metadata.chunk_index)
      ? t("search.matchChunk", "片段 {chunk}", { chunk: metadata.chunk_index })
      : null,
  ].filter((detail): detail is string => detail !== null);

  const content = truncateMatchText(text);
  if (details.length === 0) return t("search.matchText", "命中文本：{text}", { text: content });
  return t("search.matchDocument", "命中：{text}（{details}）", {
    text: content,
    details: details.join("，"),
  });
}
