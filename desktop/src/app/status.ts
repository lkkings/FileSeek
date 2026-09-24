import { resultCount, type SearchResults } from "../features/search/types";

export function describeStatus(state: {
  busy: boolean;
  error: string | null;
  query: string | null;
  results: SearchResults;
}): string {
  if (state.busy) return "正在搜索…";
  if (state.error !== null) return "";
  if (state.query === null) return "";
  const count = resultCount(state.results);
  return count === 0 ? "" : `找到 ${count} 条结果`;
}
