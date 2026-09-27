## Why

The current FolderDetailsView UI is cluttered and does not scale well to narrow viewpoints (such as when the main sidebar is fully expanded). We need to optimize and streamline this layout for visual clarity and sidebar compatibility.

## What Changes

- **Category Buttons Smaller**: Resize "全部", "文档", "图片", "视频" filter tabs to ensure they stay elegant even with the sidebar expanded.
- **Button Removal**: Remove the advanced filter button and layout grid/list toggle buttons from the file list view header.
- **Horizontal Tags Row**: Change the layout of tag selection pills to be a single-line horizontal scrollable container.
- **Local Search Bar**: Add a dedicated input field for searching files within the folder.
- **Refactored Sorting**: Match the styling and dropdown functionality of the Search Results page, only offering "时间" and "大小" sorting (no relevance sort, no separate toggle buttons).

## Capabilities

### Modified Capabilities
- None (skip_specs is true as this is visual layout refinement).

## Impact

- `FolderDetailsView.tsx` will be modified.
- `folder-details.css` will be modified.
