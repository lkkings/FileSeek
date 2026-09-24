# 项目目录与文件约束

## 1. 总体原则

- 按职责组织代码，禁止按文件类型堆积代码。
- 页面负责组合，组件负责 UI，Hooks 负责状态/交互，Services 负责外部通信。
- 禁止在 UI 组件中直接访问 API、Tauri、文件系统等基础设施。
- 公共代码必须经过实际复用后再抽取，禁止过度封装。
- 一个文件只负责一个明确职责。
- 禁止创建无法说明职责的 `utils.ts`、`common.ts`、`helper.ts` 等万能文件。

---

## 2. 标准目录结构

```text
src/
├── app/                    # 应用层
│   ├── App.tsx
│   ├── router.tsx
│   └── providers/
│
├── pages/                  # 页面
│   └── <page>/
│       ├── index.tsx
│       └── components/
│
├── components/             # 跨页面复用组件
│   └── <Component>/
│       ├── index.ts
│       ├── <Component>.tsx
│       ├── <Component>.css
│       └── types.ts
│
├── features/               # 独立业务功能
│   └── <feature>/
│       ├── components/
│       ├── hooks/
│       ├── services/
│       ├── types.ts
│       └── index.ts
│
├── hooks/                  # 全局可复用 Hooks
│
├── services/               # 全局外部服务
│   ├── api/
│   ├── tauri/
│   └── storage/
│
├── stores/                 # 全局状态
│
├── types/                  # 全局类型
│
├── styles/                 # 全局样式
│   ├── globals.css
│   ├── reset.css
│   └── variables.css
│
├── assets/                 # 静态资源
│
├── main.tsx                # 应用入口
└── vite-env.d.ts
```

---

## 3. `app/`

职责：应用启动、路由、Provider 和应用级配置。

允许：

```text
app/
├── App.tsx
├── router.tsx
└── providers/
```

禁止：

- 业务逻辑
- API 请求实现
- 数据库操作
- 文件系统操作
- 具体业务组件

`App.tsx` 应主要负责应用组合：

```tsx
<Providers>
  <Router />
</Providers>
```

---

## 4. `pages/`

职责：页面级 UI 和页面组合。

例如：

```text
pages/
├── Home/
├── Search/
├── Settings/
└── Preview/
```

页面可以：

- 组合多个组件
- 调用 Feature
- 使用 Hooks
- 管理页面级状态

页面不应该：

- 直接调用 `fetch`
- 直接调用 Tauri API
- 直接操作文件系统
- 编写复杂业务逻辑

---

## 5. `components/`

职责：跨页面复用的通用 UI 组件。

例如：

```text
components/
├── Button/
├── Modal/
├── FileTree/
├── SearchInput/
└── EmptyState/
```

组件应该关注：

- UI
- 用户交互
- Props
- UI 状态

组件不应该直接：

```tsx
fetch(...)
```

或者：

```tsx
invoke("read_file")
```

应该通过 Hook / Service 获取数据。

---

## 6. `features/`

职责：独立业务功能。

例如：

```text
features/
├── file-search/
├── file-preview/
├── indexing/
└── settings/
```

Feature 内部可以包含：

```text
features/file-search/
├── components/
├── hooks/
├── services/
├── types.ts
└── index.ts
```

Feature 是业务逻辑的主要承载位置。

例如：

```text
features/file-search/
├── components/
│   └── SearchResult.tsx
├── hooks/
│   └── useFileSearch.ts
├── services/
│   └── search.ts
└── types.ts
```

如果某个业务只被一个 Feature 使用，不要提前放到全局目录。

---

## 7. `hooks/`

职责：全局复用的 React Hooks。

只有被多个 Feature / 页面实际复用的 Hook 才应该放这里。

例如：

```text
hooks/
├── useDebounce.ts
├── useKeyboard.ts
└── useMediaQuery.ts
```

Feature 专用 Hook 放在：

```text
features/<feature>/hooks/
```

禁止：

```text
hooks/
└── useEverything.ts
```

---

## 8. `services/`

职责：与外部系统交互。

例如：

```text
services/
├── api/
│   ├── client.ts
│   └── files.ts
│
├── tauri/
│   ├── filesystem.ts
│   └── window.ts
│
└── storage/
    └── local-storage.ts
```

允许：

- HTTP API
- Tauri `invoke`
- 本地存储
- 外部服务调用

禁止：

- React JSX
- 页面 UI
- 组件状态
- 业务页面布局

Service 应提供清晰的函数接口：

```ts
export async function searchFiles(
  query: string,
): Promise<SearchResult[]> {
  // ...
}
```

而不是让组件直接处理底层通信细节。

---

## 9. `stores/`

职责：全局状态管理。

例如：

```text
stores/
├── appStore.ts
├── fileStore.ts
└── settingsStore.ts
```

只存储需要跨页面共享的状态。

禁止将所有状态都放入 Store。

以下状态优先放组件内部：

```tsx
const [open, setOpen] = useState(false);
```

只有真正需要跨组件 / 页面共享的数据才进入 Store。

---

## 10. `types/`

职责：跨 Feature 使用的公共类型。

例如：

```text
types/
├── file.ts
├── api.ts
└── common.ts
```

Feature 私有类型应放在 Feature 内：

```text
features/file-search/types.ts
```

不要把所有类型都放到全局 `types/`。

---

## 11. `styles/`

职责：全局 CSS。

推荐：

```text
styles/
├── reset.css
├── variables.css
└── globals.css
```

### `reset.css`

浏览器默认样式重置。

### `variables.css`

CSS Variables：

```css
:root {
  --color-primary: ...;
  --spacing-sm: ...;
}
```

### `globals.css`

全局基础样式：

```css
html,
body,
#root {
  height: 100%;
}
```

禁止在这里编写具体页面布局。

---

## 12. CSS 文件约束

组件样式跟随组件：

```text
components/
└── FileTree/
    ├── FileTree.tsx
    └── FileTree.css
```

页面样式跟随页面：

```text
pages/
└── Home/
    ├── Home.tsx
    └── Home.css
```

Feature 专用样式放 Feature 内部。

禁止：

```text
styles/
└── all.css
```

将整个项目所有组件样式集中到一个 CSS 文件。

---

## 13. `assets/`

职责：静态资源。

允许：

```text
assets/
├── images/
├── icons/
├── fonts/
└── videos/
```

禁止：

- TypeScript 业务逻辑
- API 调用
- 动态生成代码

---

## 14. `main.tsx`

`main.tsx` 只能负责应用入口初始化。

允许：

```tsx
createRoot(document.getElementById("root")!).render(
  <App />
);
```

可以加载：

```tsx
import "./styles/reset.css";
import "./styles/globals.css";
```

禁止在 `main.tsx` 中编写业务逻辑。

---

# 15. 依赖方向

必须遵循：

```text
main
  ↓
app
  ↓
pages
  ↓
features
  ↓
components / hooks
  ↓
services
```

但实际项目中推荐采用以下规则：

```text
pages
  ↓
features
  ↓
services
```

公共代码：

```text
components
hooks
types
styles
```

作为基础设施被上层使用。

---

# 16. 禁止的依赖

### UI → 基础设施

禁止：

```text
Component → Tauri API
Component → fetch
Component → filesystem
```

应该：

```text
Component
   ↓
Hook
   ↓
Service
   ↓
Tauri / HTTP
```

### Page → Tauri

禁止：

```tsx
await invoke("read_file");
```

应该：

```tsx
const { file } = useFilePreview();
```

---

# 17. 文件命名

### React 组件

使用 PascalCase：

```text
FileTree.tsx
SearchResult.tsx
PreviewPanel.tsx
```

### Hook

使用：

```text
useFileSearch.ts
usePreview.ts
```

### Service

使用：

```text
fileService.ts
searchService.ts
```

### Store

使用：

```text
fileStore.ts
settingsStore.ts
```

### 类型

优先：

```text
types.ts
```

如果类型较多：

```text
file.ts
search.ts
preview.ts
```

---

# 18. `index.ts` 使用规则

`index.ts` 只用于公开模块 API。

例如：

```text
components/FileTree/
├── FileTree.tsx
├── FileTree.css
└── index.ts
```

```ts
export { FileTree } from "./FileTree";
```

禁止在 `index.ts` 中编写业务逻辑。

---

# 19. 新建文件判断规则

创建文件前必须回答：

1. 这个文件属于哪个职责？
2. 是否已经存在相同职责的模块？
3. 是否只服务于一个 Feature？
4. 是否真的需要成为全局公共代码？
5. 是否会产生循环依赖？

如果只属于一个业务功能：

```text
features/<feature>/
```

如果多个业务功能复用：

```text
components/
hooks/
services/
types/
```

---

# 20. 核心原则

优先遵循：

```text
业务就近原则
↓
Feature 内聚
↓
公共代码复用
↓
基础设施隔离
↓
UI 与业务解耦
```

不要为了目录“看起来完整”而创建空目录或提前抽象。

目录结构应该随着业务增长逐步演进，而不是一次性建立大量没有实际用途的抽象。