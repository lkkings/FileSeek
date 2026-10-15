## Why

资源库搜索中选择“图片”资源种类后，文档等其他种类的计数被错误地重置为 0。分类计数应反映当前搜索范围内可切换查看的数量，而不是只反映当前已选种类。

## What Changes

- 搜索结果列表和分页继续按已选资源种类过滤。
- 分类计数不再应用资源种类筛选；它保留关键词、标签、文件夹、大小和日期等其他搜索条件。
- 搜索总数继续表示当前已选资源种类下的结果数量，用于前端结果数与分页。
- 更新后端搜索用例测试，覆盖“结果过滤、计数不随种类选择变化”的行为。

## Capabilities

### New Capabilities
- `search-results`: 资源库搜索结果的分类计数、总数和分页语义。

### Modified Capabilities

## Impact

- 后端搜索用例：`backend/src/fileseek/features/search/application/use_cases/search_files.py`
- 后端搜索测试：`backend/tests/search/test_search_files.py`
- 前端搜索 API 契约保持不变，预期无需修改 UI 代码。
