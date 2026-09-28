## Why

搜索结果页仍保留冗余的分类 Tab，结果行缺少文件管理所需的核心信息，且不能像文件夹详情页一样进行批量处理或分页浏览。这使用户在搜索后仍需跳转到其他页面完成文件整理，打断文件管理流程。

## What Changes

- 移除搜索结果页顶部的“全部 / 文档 / 图片 / 视频”Tab 栏。
- 将搜索结果改为单列数据行，每个数据行展示预览、文件名、时间、大小和标签；视觉样式与文件夹详情页表格视图保持一致。
- 支持长按进入批量选择模式，并支持批量移动文件到回收站、批量移动文件到文件夹，交互与文件夹详情页一致。
- 支持点击文件行打开右侧文件详情抽屉。
- 使用共享分页组件展示和切换搜索结果页码。

## Capabilities

### New Capabilities

- `file-search/results`: 规范搜索结果页的单列数据行展示、文件详情抽屉、批量选择与批量操作，以及分页行为。

### Modified Capabilities

无。

## Impact

- `desktop/src/features/file-search/components/SearchResultsView.tsx`
- `desktop/src/features/file-search/components/search-results.css`
- `desktop/src/features/library/components/FileListRow.tsx` 或抽出的共享文件行组件
- 文件批量移动、批量移入回收站及文件详情抽屉相关调用链
- 共享分页组件在搜索结果页的接入
- 不新增第三方依赖。
