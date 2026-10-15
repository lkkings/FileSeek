import { useTranslate } from "../../../i18n/useTranslate";
import type { EnhancedSearchProgressEvent } from "../../../services/api/search";

type SearchProgressStatus = "idle" | "loading" | "success" | "error";

interface SearchProgressTimelineProps {
  events: EnhancedSearchProgressEvent[];
  status: SearchProgressStatus;
  error?: string | null | undefined;
}

export function SearchProgressTimeline({
  events,
  status,
  error,
}: SearchProgressTimelineProps) {
  const t = useTranslate();

  const categoryLabel = (category: string) => {
    if (category === "document") return t("search.progress.category.document", "文档");
    if (category === "image") return t("search.progress.category.image", "图片");
    if (category === "video") return t("search.progress.category.video", "视频");
    return category;
  };

  const eventTitle = (event: EnhancedSearchProgressEvent) => {
    if (event.type === "reasoning") return t("search.progress.reasoning", "智能体思路");
    if (event.type === "tool_call") {
      return t("search.progress.searching", "正在执行文件搜索");
    }
    if (event.type === "tool_result") {
      return t("search.progress.searchResult", "获得检索结果");
    }
    if (event.type === "error") return t("search.progress.failed", "检索失败");
    return t("search.progress.status", "检索进行中");
  };

  const eventDetail = (event: EnhancedSearchProgressEvent) => {
    if (event.type === "status") {
      if (event.message) {
        return event.phase === "cache_hit"
          ? t("search.progress.cache", "使用缓存结果")
          : event.message;
      }
      if (event.round_number !== null && event.round_number !== undefined) {
        return t("search.progress.round", "第 {round} 轮", { round: event.round_number });
      }
      return null;
    }
    if (event.type === "reasoning") return summarize(event.content);
    if (event.type === "tool_result") {
      if (event.candidate_count === null || event.candidate_count === undefined) return null;
      return t("search.progress.candidates", "找到 {count} 个候选文件", {
        count: event.candidate_count,
      });
    }
    if (event.type === "error") return event.error ?? null;

    const details: string[] = [];
    if (event.query) details.push(t("search.progress.keyword", "关键词：{query}", { query: event.query }));
    if (event.categories?.length) {
      details.push(
        t("search.progress.categories", "类型：{categories}", {
          categories: event.categories.map(categoryLabel).join("、"),
        }),
      );
    }
    if (event.name_query) {
      details.push(
        t("search.progress.nameQuery", "文件名：{query}", { query: event.name_query }),
      );
    }
    return details.length > 0 ? details.join("；") : null;
  };

  return (
    <section className="search-progress-timeline" aria-live="polite">
      {status === "loading" && (
        <div className="search-progress-header">
          <span className="search-progress-spinner" aria-hidden="true" />
          <h2>{t("search.progress.title", "智能体检索中")}</h2>
        </div>
      )}
      <ol>
        {events.map((event, index) => (
          <li
            key={`${event.type}-${index}`}
            className={`search-progress-item is-${event.type}`}
          >
            <span className="search-progress-marker" aria-hidden="true" />
            <div>
              <p className="search-progress-title">{eventTitle(event)}</p>
              {eventDetail(event) && <p className="search-progress-detail">{eventDetail(event)}</p>}
            </div>
          </li>
        ))}
        {status === "success" && (
          <li className="search-progress-item is-terminal is-success">
            <span className="search-progress-marker" aria-hidden="true" />
            <p className="search-progress-title">
              {t("search.progress.completed", "检索完成")}
            </p>
          </li>
        )}
        {status === "error" && (
          <li className="search-progress-item is-terminal is-error">
            <span className="search-progress-marker" aria-hidden="true" />
            <p className="search-progress-title">{t("search.progress.failed", "检索失败")}</p>
            <p className="search-progress-detail">{error}</p>
          </li>
        )}
      </ol>
    </section>
  );
}

function summarize(content: string | null | undefined) {
  if (!content) return null;
  return content.length > 160 ? `${content.slice(0, 157)}...` : content;
}
