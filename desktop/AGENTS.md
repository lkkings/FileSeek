# AGENTS.md

## 1. 项目

本项目是基于 **React + TypeScript + Vite + Tauri 2** 的桌面应用。

必须支持 **i18n**，统一使用 **Lingui**。

核心原则：

- Feature-based Architecture
- UI、业务逻辑、基础设施分离
- 单向依赖，禁止循环依赖
- Feature 高内聚、低耦合
- 类型安全
- 就近组织代码
- 按实际复用程度抽取公共代码
- 优先简单实现，禁止过度抽象

Agent 在新增、修改或重构代码前，必须遵守本文件以及 `architecture/` 下的相关规则。

---

## 2. 技术栈

| 领域 | 技术 |
|---|---|
| Desktop | Tauri 2 |
| UI | React 19 |
| Language | TypeScript |
| Build | Vite |
| Package Manager | pnpm |
| UI Components | shadcn/ui |
| CSS | Tailwind CSS |
| State | Zustand |
| Server State | TanStack Query |
| Router | React Router |
| i18n | Lingui |
| Form | React Hook Form |
| Validation | Zod |
| HTTP | fetch |
| Test | Vitest + React Testing Library |
| E2E | Playwright |
| Lint | ESLint |
| Format | Prettier |
| Architecture | dependency-cruiser |

未经明确需求，不得引入功能重复的第三方库。

例如已经使用 Zustand 时，不得新增 Redux；已经使用 fetch 封装 API 时，不得新增 Axios。

---

## 3. 项目结构

```text
src/
├── app/                    # 应用装配、Router、Provider、全局配置
│   ├── App.tsx
│   ├── router.tsx
│   └── providers/
│
├── pages/                  # 页面级 UI，只负责组合 Feature
│   └── <page>/
│
├── features/               # 业务功能，核心业务代码所在
│   └── <feature>/
│       ├── components/
│       ├── hooks/
│       ├── services/
│       ├── types.ts
│       └── index.ts
│
├── components/             # 跨 Feature 复用的 UI
├── hooks/                  # 跨 Feature 复用的 React Hooks
│
├── services/               # 全局基础设施
│   ├── api/                # Backend API
│   ├── tauri/              # Tauri API
│   └── storage/            # 浏览器/客户端存储
│
├── stores/                 # 跨页面 / 跨 Feature 的客户端状态
├── types/                  # 跨 Feature 公共类型
├── i18n/                   # Lingui 配置与语言资源
├── styles/                 # 全局样式
├── assets/                 # 静态资源
└── main.tsx
```

---

## 4. 依赖方向

整体依赖方向：

```text
app
 ↓
pages
 ↓
features
 ↓
shared infrastructure
```

其中：

```text
components
hooks
services
stores
types
i18n
```

属于公共能力，但**不代表它们可以互相任意依赖**。

必须遵循：

```text
UI
 ↓
Feature / Hook
 ↓
Service
 ↓
External System
```

禁止反向依赖：

```text
services → pages
services → components
services → app

components → pages
components → app

types → React UI
types → services

infrastructure → business UI
```

禁止循环依赖。

---

## 5. Feature 规则

Feature 是业务代码的主要组织单位。

例如：

```text
features/
├── file-search/
├── file-preview/
├── file-indexing/
└── settings/
```

Feature 私有代码必须优先放在 Feature 内部：

```text
features/file-search/
├── components/
├── hooks/
├── services/
├── types.ts
└── index.ts
```

默认规则：

> **代码首先属于 Feature，而不是公共模块。**

禁止因为“以后可能复用”提前抽取公共代码。

---

## 6. Feature 之间禁止直接依赖

禁止：

```text
file-search → file-preview
file-preview → file-search
```

如果两个 Feature 需要共享能力：

```text
Feature A
   ↓
公共模块
   ↑
Feature B
```

公共模块只能承载真正通用的能力。

如果是业务上的 Feature 组合关系，由 `pages/` 或 `app/` 负责组合，而不是让 Feature 相互调用。

---

## 7. Page 规则

`pages/` 只负责：

- 页面布局
- Feature 组合
- 路由参数处理
- 页面级状态组织

页面可以使用 Feature 的公开 API。

禁止：

```text
Page → fetch()
Page → invoke()
Page → localStorage
Page → IndexedDB
Page → 复杂业务逻辑
```

页面不应该成为业务逻辑的容器。

推荐：

```text
Page
 ↓
Feature Hook
 ↓
Feature / Service
```

---

## 8. Component 规则

`components/` 只存放跨 Feature 复用的 UI。

组件负责：

- UI
- Props
- 用户交互
- 展示状态

组件禁止直接访问：

```text
HTTP API
Tauri
文件系统
数据库
localStorage
IndexedDB
```

Feature 专属组件必须放在：

```text
features/<feature>/components/
```

不要把所有组件都放入全局 `components/`。

---

## 9. Hook 规则

跨 Feature 使用的 Hook：

```text
hooks/
```

Feature 专属 Hook：

```text
features/<feature>/hooks/
```

Hook 可以负责：

- React 状态
- 生命周期
- 用户交互
- TanStack Query
- Feature 状态组合

Hook 不应成为隐藏业务逻辑和基础设施访问的万能层。

---

## 10. API 规则

所有 Backend API 必须通过：

```text
services/api/
```

例如：

```text
services/api/
├── client.ts
├── files.ts
├── search.ts
└── settings.ts
```

调用链：

```text
Page
 ↓
Feature Hook
 ↓
API Service
 ↓
API Client
 ↓
fetch
 ↓
FastAPI
```

`client.ts` 负责：

- Base URL
- Headers
- 请求封装
- 错误处理
- 序列化 / 反序列化
- 通用请求逻辑

业务 API Service 负责具体接口。

禁止：

```ts
fetch(...)
axios(...)
```

出现在 Page、Component 或 Feature UI 中。

---

## 11. Tauri 规则

所有 Tauri API 必须通过：

```text
services/tauri/
```

例如：

```text
services/tauri/
├── filesystem.ts
├── window.ts
├── dialog.ts
└── clipboard.ts
```

调用链：

```text
React
 ↓
Hook / Feature
 ↓
Tauri Service
 ↓
invoke()
 ↓
Rust
```

禁止 Page、Component 或普通 Hook 直接调用：

```ts
invoke(...)
```

Tauri API 必须进行语义化封装。

例如：

```ts
export function readFile(path: string) {
    return invoke("read_file", { path });
}
```

---

## 12. Storage 规则

所有客户端持久化必须通过：

```text
services/storage/
```

包括：

- localStorage
- sessionStorage
- IndexedDB
- 其他客户端存储

业务代码禁止直接访问底层 Storage API。

---

## 13. 状态管理

严格区分：

```text
Server State → TanStack Query
Client State → Zustand
Local State  → useState / useReducer
```

### TanStack Query

用于：

- API 数据
- 查询结果
- 服务端缓存
- 请求状态
- 数据同步

### Zustand

只保存真正需要跨页面 / 跨 Feature 共享的客户端状态。

### Local State

组件内部状态优先使用：

```ts
useState()
useReducer()
```

禁止为了避免 Props 传递而创建全局 Store。

---

## 14. i18n 规则

所有用户可见文本必须支持 i18n。

统一使用：

```text
Lingui
```

禁止在 UI 中硬编码用户可见文本：

```tsx
// ❌
<span>文件不存在</span>
```

必须使用：

```tsx
// ✅
<Trans>文件不存在</Trans>
```

语言资源统一放在：

```text
src/i18n/
```

禁止在 Feature 中自行实现另一套 i18n 机制。

---

## 15. UI 与业务逻辑

React Component 不负责复杂业务逻辑。

禁止在 Component 中同时处理：

```text
UI
+ API
+ 文件操作
+ 数据转换
+ 复杂计算
+ 状态同步
```

推荐：

```text
Component
 ↓
Hook
 ↓
Feature / Service
 ↓
API / Tauri
```

职责：

```text
Component → UI
Hook      → React 状态与交互
Feature   → 业务逻辑
Service   → 外部系统访问
```

---

## 16. 公共代码抽取

代码默认就近放置。

只有满足以下条件之一才允许提升到公共模块：

1. 至少两个 Feature 已实际使用；
2. 明确属于基础设施；
3. 明确属于通用 UI；
4. 明确属于全局状态或公共类型。

禁止为了未来可能复用而提前抽象。

禁止创建职责不明确的：

```text
utils.ts
helpers.ts
common.ts
misc.ts
```

公共代码必须具有明确职责和明确命名。

---

## 17. TypeScript

必须保持严格类型安全。

禁止：

```ts
any
```

除非存在明确且无法避免的技术原因，并说明原因。

优先：

```ts
unknown
```

而不是：

```ts
any
```

API 数据必须具有明确类型。

避免滥用：

```ts
as Type
```

优先通过类型定义、Schema 校验和类型收窄解决问题。

---

## 18. 类型位置

Feature 私有类型：

```text
features/<feature>/types.ts
```

跨 Feature 公共类型：

```text
types/
```

禁止无条件把所有类型放入：

```text
types/
```

类型应该放在离使用方最近的位置。

---

## 19. CSS

全局样式仅用于：

```text
styles/
├── reset.css
├── variables.css
└── globals.css
```

全局 CSS 负责：

- Reset
- CSS Variables
- html / body / root
- 全局基础样式

组件样式就近组织。

禁止创建：

```text
styles/everything.css
```

或其他包含整个项目业务样式的巨大 CSS 文件。

---

## 20. 命名

### Component

使用 PascalCase：

```text
FileTree.tsx
PreviewPanel.tsx
SearchResult.tsx
```

### Hook

必须以 `use` 开头：

```text
useFileSearch.ts
usePreview.ts
useKeyboard.ts
```

### Service

使用明确职责命名：

```text
fileService.ts
searchService.ts
filesystem.ts
```

禁止使用无法表达职责的名称：

```text
utils.ts
helper.ts
common.ts
misc.ts
```

### Store

```text
fileStore.ts
settingsStore.ts
```

---

## 21. index.ts

`index.ts` 只用于定义模块公开 API。

允许：

```ts
export { FileTree } from "./FileTree";
export { useFileSearch } from "./hooks/useFileSearch";
```

禁止在 `index.ts` 中编写业务逻辑。

Feature 应通过 `index.ts` 暴露公开能力：

```ts
import { useFileSearch } from "@/features/file-search";
```

禁止其他模块依赖 Feature 内部实现：

```ts
// ❌
import { useFileSearch } from "@/features/file-search/hooks/useFileSearch";
```

---

## 22. 新增功能

新增功能时按以下顺序判断：

```text
是否属于现有 Feature？
       │
      是
       ↓
放入现有 Feature

      否
       ↓
创建新的 Feature
```

不要因为存在一个 API 就直接创建：

```text
services/search.ts
```

业务功能应该首先归属 Feature。

例如：

```text
features/file-search/
```

API Service 只负责外部 API 访问。

---

## 23. 新建文件

创建文件前必须确认：

1. 文件职责是什么？
2. 属于哪个 Feature？
3. 是否已经存在相同职责的实现？
4. 是否应该保持 Feature 私有？
5. 是否真的需要公共化？
6. 是否违反依赖方向？
7. 是否会产生循环依赖？

无法明确职责时，不创建文件。

---

## 24. 修改代码

修改代码前：

1. 阅读目标 Feature；
2. 阅读相关调用方；
3. 检查已有 Service / Hook / Type；
4. 检查依赖方向；
5. 优先复用现有实现；
6. 避免重复实现；
7. 避免无关重构。

除非需求明确要求，否则不要顺手重构无关代码。

---

## 25. Agent 工作流程

执行任务必须遵循：

```text
理解需求
  ↓
定位 Feature
  ↓
检查现有实现
  ↓
确定职责与依赖
  ↓
实现最小变更
  ↓
接入 API / Tauri / Store
  ↓
运行类型检查
  ↓
运行 Lint / Test
  ↓
运行架构检查
  ↓
确认 Build
```

完成任务前必须进行与修改范围匹配的验证。

不得声称“完成”而未实际执行可执行的验证。

---

## 26. 禁止事项

禁止：

- Component 直接调用 API
- Component 直接调用 Tauri
- Page 直接调用 API
- Page 直接操作 Storage
- Feature 直接依赖其他 Feature
- Service 依赖 Page
- Service 依赖 Component
- Component 依赖 Page
- Infrastructure 依赖 UI
- 创建万能 `utils.ts`
- 创建万能 `common.ts`
- 创建万能 `helpers.ts`
- 把所有状态放入 Store
- 把所有类型放入全局 `types/`
- 把所有 CSS 放入一个文件
- 使用 `any` 隐藏类型问题
- 引入重复功能的第三方库

---

## 27. 架构文档

详细架构规则不全部写入本文件。

以下文档用于详细约束：

```text
architecture/
├── architecture.md
├── dependency-rules.md
├── technology-rules.md
└── testing.md
```

当任务涉及：

- 架构调整 → 阅读 `architecture/architecture.md`
- 修改模块依赖 → 阅读 `architecture/dependency-rules.md`
- 引入或替换技术 → 阅读 `architecture/technology-rules.md`
- 测试策略 → 阅读 `architecture/testing.md`

`AGENTS.md` 保存长期、全局、必须始终遵守的规则；详细流程和专项规则放入对应文档。

---

## 28. 核心原则

```text
Feature First
     ↓
高内聚
     ↓
低耦合
     ↓
UI / Business / Infrastructure 分离
     ↓
单向依赖
     ↓
就近组织代码
     ↓
按实际复用抽取
     ↓
最小必要抽象
     ↓
可验证
```

**架构的目标是降低复杂度，而不是增加目录数量。**

任何架构设计都必须优先考虑：

> 简单、清晰、可测试、可修改、可验证。