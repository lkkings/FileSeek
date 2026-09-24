# FileSeek 前端重构优化文档

## 1. 文档目的

本文档用于指导 FileSeek Desktop 前端的渐进式重构，目标是降低 React 组件、CSS 和异步状态管理的复杂度，同时保持现有用户行为和后端接口契约不变。

CSS 架构决策：不再把所有样式长期集中在单个 `App.css` 中。全局文件只保留基础样式和设计 Token，Feature 和复杂共享组件使用就近的样式文件。

重构原则：

- 先建立行为基线，再拆分代码。
- 每次只改变一个明确的职责边界。
- UI、Feature Logic、状态和 API 通信保持分层。
- 优先消除会产生错误的竞态和状态同步问题，再处理样式冗余。
- 不进行一次性大规模重写。

## 2. 当前基线

审查范围：`desktop/src`

| 项目 | 当前情况 | 目标 |
| --- | ---: | ---: |
| `FileLibrary.tsx` | 1269 行 | 小于 300 行的容器组件 |
| `FilePreviewModal.tsx` | 772 行 | 按预览类型拆分 |
| `SearchResults.tsx` | 444 行 | 结果转换、排序、展示分离 |
| `App.tsx` | 460 行 | 只保留应用级组装和导航状态 |
| `App.css` | 2503 行 | 按 feature 和 shared token 拆分 |
| JSX `style={{...}}` | 约 268 处 | 只保留真正动态的样式 |
| `npm run lint` | 通过，2 个 warning | 0 warning |
| `npm run typecheck` | 通过 | 通过 |
| `npm test` | 41/43 通过 | 43/43 通过 |

当前已确认的风险：

1. 搜索请求没有竞态保护，旧请求可能覆盖新结果。
2. `useLibrary.reload` 没有取消或版本校验，快速切换文件夹时可能显示错误数据。
3. `SearchResults.tsx:126` 使用 `key={index}`。
4. 设置和最近访问的异步加载缺少卸载保护和统一错误状态。
5. CSS 选择器重复定义，文件末尾存在一层依赖顺序的视觉覆盖规则。
6. `FilePreviewModal` 和 `FileLibrary` 混合了业务逻辑、状态、布局和大量视觉细节。

## 3. 目标架构

```text
App / Layout
  -> Feature container
    -> Feature hook / actions
      -> API service
        -> ApiClient / Tauri transport
```

推荐的前端目录：

```text
desktop/src/
├── app/
│   ├── AppShell.tsx
│   └── navigation.ts
├── components/
│   ├── feedback/
│   ├── layout/
│   └── preview/
├── features/
│   ├── library/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── model.ts
│   │   └── library.css
│   ├── search/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── search.css
│   ├── settings/
│   └── tasks/
├── api/
├── i18n/
└── styles/
    ├── base.css
    ├── tokens.css
    └── utilities.css
```

Feature 内部的依赖方向必须保持：

```text
components -> hooks/model -> api
```

组件不得直接拼接复杂 API 请求、处理后端字段转换或承担跨 feature 状态同步。

## 4. 分阶段实施计划

### 阶段 0：建立安全基线

目标：让后续重构可验证。

任务：

- 修复当前两个失败测试。
- 为搜索、切换文件夹、导入文件、删除文件夹补充行为测试。
- 记录现有交互：加载、空状态、错误、成功、取消和重复提交。
- 启用 `noUncheckedIndexedAccess`、`noImplicitReturns` 和 `exactOptionalPropertyTypes`，逐项修复新增类型错误。
- 将 lint warning 降为 0。

验收：

```text
npm run lint       # 0 error, 0 warning
npm run typecheck  # 成功
npm test           # 43/43 或新增测试全部通过
```

### 阶段 1：修复异步竞态和错误处理

目标：先保证数据正确，再拆组件。

#### 搜索

在 `features/search/useSearch.ts` 中加入请求版本号或 `AbortController`：

- 每次搜索生成唯一 request id。
- 只有当前 request id 才能提交 `results`、`error` 和 `busy`。
- 组件卸载后不再提交状态。
- 重复提交时保留最后一次搜索的结果。

#### 文件库

在 `features/library/useLibrary.ts` 中：

- 为 `reload` 增加版本校验。
- `currentFolder`、`viewType` 变化时使旧请求失效。
- 将文件夹列表和文件列表作为同一个加载事务提交。
- 为失败状态保留可展示错误，而不是静默清空数据。

#### 其他异步加载

- `SettingsPanel` 使用可取消请求或 mounted guard。
- `RecentAccess` 增加 `error` 状态和错误 UI。
- `TaskQueueView` 的轮询统一封装，避免手动事件和定时器重复刷新。
- 所有异步 effect 都必须有清理函数或明确说明为什么不需要清理。

验收：

- 快速连续搜索只显示最后一次结果。
- 快速切换文件夹不会显示前一个文件夹的数据。
- 组件卸载后不会产生 state update warning。
- 请求失败时能进入稳定的错误状态，并可重试。

### 阶段 2：拆分 `FileLibrary`

目标：把 1269 行组件拆成容器、状态和展示模块。

建议拆分：

```text
features/library/
├── FileLibrary.tsx              # 组装页面，不超过 250-300 行
├── components/
│   ├── LibraryHeader.tsx
│   ├── FolderGrid.tsx
│   ├── FolderCard.tsx
│   ├── FileTable.tsx
│   ├── FileGrid.tsx
│   ├── LibraryToolbar.tsx
│   ├── FolderFormModal.tsx
│   ├── ImportFileModal.tsx
│   └── RecycleBinView.tsx
├── hooks/
│   ├── useLibrary.ts
│   ├── useLibrarySelection.ts
│   └── useFolderNavigation.ts
├── fileIcons.tsx
└── library.css
```

拆分规则：

- 文件夹卡片只接收 `FolderItem` 和操作回调。
- 文件表格只负责渲染和触发操作，不负责 API 请求。
- 表单 modal 自己管理表单输入和校验。
- 选择状态使用 `Set<string>` 或专用 hook 管理。
- 图标和文件类型映射放在 `fileIcons.tsx`，不要在多个组件重复实现。
- 当前文件夹导航状态只保留在实际需要它的容器中。

### 阶段 3：拆分 `FilePreviewModal`

目标：把 772 行的多格式预览器改为稳定的预览路由。

建议结构：

```text
components/preview/
├── FilePreviewModal.tsx
├── PreviewHeader.tsx
├── PreviewLoadingState.tsx
├── PreviewErrorState.tsx
├── ImagePreview.tsx
├── PdfPreview.tsx
├── DocumentPreview.tsx
├── SpreadsheetPreview.tsx
├── PresentationPreview.tsx
├── VideoPreview.tsx
└── preview.css
```

`FilePreviewModal` 只负责：

- modal 生命周期。
- 根据文件类型选择预览组件。
- 统一关闭、加载和错误状态。

动态样式可以继续使用 inline style 的范围：

- 图片旋转角度。
- PDF 缩放比例。
- 进度条宽度。
- 由运行时数据决定的坐标或尺寸。

固定布局、颜色、边框、间距、字体和按钮样式必须迁移到 `preview.css`。

### 阶段 4：清理 CSS 和 inline style

#### CSS 合并策略

CSS 不应按“每个小组件一个文件”机械拆分，也不应继续把所有页面样式堆在 `App.css`。推荐按职责和功能边界拆分为三层：

```text
styles/base.css       # reset、body、focus、无障碍基础样式
styles/tokens.css     # 颜色、间距、圆角、阴影、字体
styles/utilities.css  # 少量跨 feature 工具类
features/*/*.css      # feature 私有样式
components/**/*.css   # 复杂或跨 feature 组件样式
```

推荐的实际映射：

```text
src/styles/base.css
src/styles/tokens.css
src/styles/utilities.css
src/features/library/library.css
src/features/search/search.css
src/features/settings/settings.css
src/features/tasks/tasks.css
src/components/preview/preview.css
```

样式归属规则：

- 全局样式只负责 reset、`body`、focus ring、滚动条和设计 Token。
- `library.css` 只负责文件库、文件夹卡片、文件表格和回收站视图。
- `search.css` 只负责搜索框、高级筛选和搜索结果。
- `preview.css` 负责预览 modal 及各类预览工具栏和内容区域。
- 跨 feature 的按钮、输入框和 modal 基础规则保留在共享样式中。
- 不为只有几条规则的简单组件单独创建 CSS 文件，避免文件数量失控。

#### CSS 迁移顺序

1. 从 `App.css` 中提取 `tokens.css`、`base.css` 和通用工具类。
2. 将 `FilePreviewModal.tsx` 的静态样式迁移到 `components/preview/preview.css`。
3. 将 `FileLibrary.tsx` 的静态样式迁移到 `features/library/library.css`。
4. 将搜索和设置相关规则迁移到各自 feature 样式文件。
5. 合并重复选择器，并删除文件末尾的 screenshot override layer。
6. 删除未使用选择器，最后再缩减 `App.css`，必要时将其改名为 `app-shell.css`。

迁移过程中每个样式文件都应有明确的入口导入位置，避免依赖 CSS 文件导入顺序解决冲突。新样式优先使用 BEM 风格或 feature 前缀，例如 `.library-toolbar`、`.preview-toolbar`，不要创建过于通用的 `.container`、`.header`、`.item` 等容易冲突的选择器。

清理步骤：

1. 删除 `App.css` 末尾依赖顺序的 screenshot override layer。
2. 将最终生效值合并回原始选择器。
3. 每个 class 只保留一处主定义，响应式规则集中在对应 class 附近。
4. 删除未使用 selector，并通过搜索 JSX className 复核。
5. 统一使用 `tokens.css` 的颜色、间距和圆角变量。
6. 对同一语义只保留一套按钮、输入框、modal 和表格基础样式。

#### inline style 迁移规则

以下样式应优先迁移：

- `display`、`flexDirection`、`gap`、`padding`、`margin`
- `fontSize`、`fontWeight`、`lineHeight`
- `background`、`border`、`borderRadius`
- `width`、`height`、`position`
- 静态颜色和静态阴影

以下样式可以保留：

- `transform` 中的运行时旋转/缩放值
- 进度和百分比计算值
- 由用户输入或文件数据决定的尺寸

迁移示例：

```tsx
// 重构前
<div style={{ display: "flex", gap: "16px", flexDirection: "column" }} />

// 重构后
<div className="modal-body modal-body--stacked" />
```

```css
.modal-body--stacked {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}
```

### 阶段 5：统一共享 UI 和类型

- 将文件图标、文件分类和扩展名映射集中到共享模块。
- 将 `PreviewFile`、`FileItem` 等相近类型明确区分，避免使用 `unknown` 后再重复断言。
- 为按钮提供统一的可访问名称，不依赖 emoji 或 CSS 图标作为测试契约。
- 为 icon-only button 添加稳定的 `aria-label`。
- 为表单控件补齐 `label`、`htmlFor`、`aria-describedby` 和错误提示关联。

## 5. 测试策略

重构前先写行为测试，不测试组件内部 state 或 DOM 层级。

必须覆盖：

- 搜索成功、失败、空结果和重复提交。
- 搜索结果只接受最后一次请求。
- 根目录、文件夹目录和回收站的加载。
- 快速切换文件夹时不串数据。
- 创建、编辑、删除文件夹。
- 非空文件夹删除失败时显示后端错误。
- 文件预览的加载、关闭和错误状态。
- 浅色/深色主题下的核心组件。
- modal 和 icon-only button 的键盘操作及 accessible name。

测试命令：

```bash
npm run lint
npm run typecheck
npm test
npm run build
```

## 6. 合并门禁

每个重构 PR 必须满足：

- 不引入新的 `style={{...}}`，除非是运行时动态值。
- 不新增 `key={index}`。
- 不新增无清理的异步 effect。
- 不直接在组件内新增 API 请求和后端字段转换。
- 组件文件不超过 300 行，超过时必须说明原因或拆分计划。
- `npm run lint` 无 warning。
- `npm run typecheck` 通过。
- `npm test` 全部通过。
- 保留行为测试，而不是用快照掩盖结构变化。

## 7. 推荐实施顺序

```text
1. 修复失败测试和异步竞态
2. 启用更严格的 TypeScript 检查
3. 拆分 FileLibrary
4. 抽取共享文件图标和按钮样式
5. 拆分 FilePreviewModal
6. 清理 App.css 重复规则
7. 批量迁移静态 inline style
8. 补齐无障碍和主题测试
```

不建议先进行全量 CSS 重写。应先把组件职责和共享 UI 边界稳定下来，再移动样式，避免在组件结构不稳定时反复搬运 CSS。
