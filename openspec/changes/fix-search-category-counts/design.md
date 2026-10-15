## Context

The search use case currently passes the selected resource categories to both the result query and the category counter. The repository groups that already-filtered query by category, so unselected categories are returned as zero.

## Goals / Non-Goals

**Goals:**

- Keep resource-library category counts stable when only the selected resource type changes.
- Preserve result and pagination totals for the selected resource types.
- Avoid adding an external dependency or changing the HTTP API shape.

**Non-Goals:**

- Redesigning the resource type filter UI.
- Changing how vector relevance or non-category filters are evaluated.
- Changing repository or database schemas.

## Decisions

- Compute category counts with all search filters except resource type. This keeps the counter representative of the search scope that users can switch between.
- Derive the result total from the unfiltered category counter for the selected categories. This avoids an additional database count query while preserving filtered pagination semantics.
- Keep the existing response schema. The frontend already separates `counter` from `total`, so no UI contract change is needed.

## Risks / Trade-offs

- [Category counts are database-filter counts, not vector-relevance counts] -> Keep the existing counter semantics and limit this change to removing the resource type filter.
- [An empty category list can be mistaken for no filter] -> Preserve explicit semantics while deriving the result total, and cover selected-image behavior in tests.
