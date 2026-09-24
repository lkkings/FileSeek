/**
 * Mirrors the backend's `POST /api/v1/search` response
 * (`backend/src/fileseek/features/search/interfaces/http/schemas/__init__.py`).
 *
 * Two capabilities the UI used to assume are deliberately absent, because the endpoint
 * does not offer them and it is not ours to change:
 *
 * - **No pagination.** The request takes `limit` (top N per media type), not a page
 *   number, and the response carries no `has_more_*` flags. There is nothing to load more
 *   of, so there is no LoadMore affordance.
 * - **No video segment list.** A video hit is flat: one `start_time`/`end_time` pair for
 *   the matching moment, not an array of segments with thumbnails and summaries.
 */

/** Fields every hit carries, whatever its media type. */
interface SearchResultBase {
  file_id: string;
  filename: string;
  /** Absolute URL the backend builds from the live request host. */
  preview_url: string;
  score: number;
  /** Where the file sits in the library. Empty when its metadata could not be read. */
  path: string;
  accessible: boolean;
}

export interface DocumentResult extends SearchResultBase {
  matched_text: string;
  page_number?: number | null;
  line_number?: number | null;
}

export type ImageResult = SearchResultBase;

export interface VideoResult extends SearchResultBase {
  /** Seconds into the video where the match starts; null when unknown. */
  start_time?: number | null;
  end_time?: number | null;
}

export interface SearchResults {
  documents: DocumentResult[];
  images: ImageResult[];
  videos: VideoResult[];
}

export const EMPTY_RESULTS: SearchResults = {
  documents: [],
  images: [],
  videos: [],
};

/**
 * Counts the total number of items returned across all search groups.
 */
export function resultCount(results: SearchResults): number {
  return (
    (results.documents?.length || 0) +
    (results.images?.length || 0) +
    (results.videos?.length || 0)
  );
}
