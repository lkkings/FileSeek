# FileSeek Backend API 接口规范文档 (根据 UI 全量推断版)

## 1. 规范与通用响应标准

### 1.1 通用约定
- **协议与前缀**: `HTTP/1.1`, `Content-Type: application/json; charset=utf-8`
- **基础 URL**: `http://127.0.0.1:8765/api/v1` (桌面端本地与 NAS 传输代理)

### 1.2 统一响应包装 (Response Envelope)
所有接口无论成功或失败，均统一返回如下标准的 Envelope 数据包裹：

```typescript
export interface ApiResponse<T> {
  status: "success" | "error";
  data: T | null;
  error: string | null;
}
```

- **成功 HTTP 200**:
```json
{
  "status": "success",
  "data": { ... },
  "error": null
}
```

- **失败 HTTP 400 / 403 / 404 / 500**:
```json
{
  "status": "error",
  "data": null,
  "error": "目录不可写。请选择具有写权限的本地文件夹。"
}
```

---

## 2. 检索与预览 API (Search & Preview)
### 2.1 执行多模态搜索与高级筛选

#### `POST /search`

根据用户在 UI 顶栏及筛选抽屉中输入的内容，执行向量语义检索与属性组合过滤。

* **请求 Body**:

```json
{
  "query": "猫咪 窗台",
  "media_types": ["document", "image", "video"],
  "limit": 20,
  "name_query": "jpg",
  "min_size_m": 1.0,
  "max_size_m": 500.0,
  "start_date": "2026-01-01",
  "end_date": "2026-09-20"
}
```

| 参数字段          | 类型       | 必填 | UI 交互来源说明                                                                          |
| :------------ | :------- | :- | :--------------------------------------------------------------------------------- |
| `query`       | string   | 是  | 顶栏 SearchBar 文本框输入的自然语言查询。不能为空字符串，也不能仅由空格、换行符或制表符组成                                |
| `media_types` | string[] | 是  | 顶栏分类 Tab：`["document"]`、`["image"]`、`["video"]` 或 `["document", "image", "video"]` |
| `limit`       | number   | 否  | 每种媒体类型分别返回的 Top N 结果数量，默认 `20`                                                     |
| `name_query`  | string   | 否  | 高级筛选抽屉：“文件名”子串匹配                                                                   |
| `min_size_m`  | number   | 否  | 高级筛选抽屉：“最小体积 (MB)”                                                                 |
| `max_size_m`  | number   | 否  | 高级筛选抽屉：“最大体积 (MB)”                                                                 |
| `start_date`  | string   | 否  | 高级筛选抽屉：“开始日期” (`YYYY-MM-DD`)                                                       |
| `end_date`    | string   | 否  | 高级筛选抽屉：“结束日期” (`YYYY-MM-DD`)                                                       |

其中，`limit` 对每种媒体类型独立生效。例如：

```json
{
  "media_types": ["document", "image", "video"],
  "limit": 20
}
```

最多返回：

* `documents`：Top 20
* `images`：Top 20
* `videos`：Top 20

即最多返回 60 条结果，而不是所有类型合计 20 条。

`query` 必须包含至少一个非空白字符。以下值均视为非法：

```text
""
"   "
"\n"
"\t"
" \n\t "
```

---

* **响应 Body (****`SearchResults`****)**:

```json
{
  "status": "success",
  "data": {
    "documents": [
      {
        "file_id": "doc-1",
        "filename": "2026年Q2业务回顾及战略规划.pdf",
        "preview_url": "http://127.0.0.1:3000/library/files/preview/{file_id}",
        "score": 94.5,
        "matched_text": "...我们在Q2季度实现了大幅度业务增长，FileSeek 语义检索服务顺利上线...",
        "path": "/Users/lkkings/FileSeekLibrary/documents/2026年Q2业务回顾及战略规划.pdf",
        "accessible": true,
        "page_number": 2,
        "line_number": 15
      }
    ],
    "images": [
      {
        "file_id": "img-1",
        "filename": "窗台上的猫咪.jpg",
        "preview_url": "http://127.0.0.1:3000/library/files/preview/{file_id}",
        "score": 96.1,
        "path": "/Users/lkkings/FileSeekLibrary/images/窗台上的猫咪.jpg",
        "accessible": true
      }
    ],
    "videos": [
      {
        "file_id": "vid-1",
        "filename": "大理洱海骑行.mp4",
        "preview_url": "http://127.0.0.1:3000/library/files/preview/{file_id}",
        "score": 91.0,
        "path": "/Users/lkkings/FileSeekLibrary/videos/大理洱海骑行.mp4",
        "start_time": 83,
        "end_time": 120,
        "accessible": true
      }
    ]
  },
  "error": null
}
```

* **响应字段描述**:

#### 1. 顶层响应字段

| 响应字段     | 类型            | 说明                                           |
| :------- | :------------ | :------------------------------------------- |
| `status` | string        | 请求处理状态。`success` 表示搜索请求执行成功；`error` 表示请求处理失败 |
| `data`   | object / null | 搜索结果数据。请求成功时返回搜索结果对象；请求失败时通常为 `null`         |
| `error`  | object / null | 错误信息。请求成功时为 `null`；请求失败时返回具体错误码及错误描述         |

#### 2. `data` 字段

| 响应字段             | 类型       | 说明                                                                           |
| :--------------- | :------- | :--------------------------------------------------------------------------- |
| `data.documents` | object[] | 文档搜索结果列表。仅返回 `media_types` 中包含 `document` 时的搜索结果，最多返回 `limit` 条，并按照匹配度从高到低排序 |
| `data.images`    | object[] | 图片搜索结果列表。仅返回 `media_types` 中包含 `image` 时的搜索结果，最多返回 `limit` 条，并按照匹配度从高到低排序    |
| `data.videos`    | object[] | 视频搜索结果列表。仅返回 `media_types` 中包含 `video` 时的搜索结果，最多返回 `limit` 条，并按照匹配度从高到低排序    |

当某一种媒体类型没有搜索结果时，对应字段返回空数组：

```json
{
  "documents": [],
  "images": [],
  "videos": []
}
```

#### 3. `data.documents[]` 文档结果字段

| 响应字段           | 类型            | 说明                                                              |
| :------------- | :------------ | :-------------------------------------------------------------- |
| `file_id`      | string        | 文件唯一标识。用于唯一定位当前文件，并可用于文件预览、详情查询等后续接口调用                          |
| `filename`     | string        | 文件名称，包含文件扩展名，例如 `2026年Q2业务回顾及战略规划.pdf`                          |
| `preview_url`  | string        | 文件预览地址。前端可通过该地址加载文件预览内容                                         |
| `score`        | number        | 当前文件与用户 `query` 的语义匹配度得分。数值越高表示搜索结果与查询内容的相关程度越高                 |
| `matched_text` | string        | 文档中与用户查询内容匹配的文本片段，用于在搜索结果页面展示命中的上下文内容                           |
| `path`         | string        | 文件在本地文件系统中的实际存储路径                                               |
| `accessible`   | boolean       | 文件当前是否可访问。`true` 表示文件存在且当前具有访问权限；`false` 表示文件不存在、已移动、已删除或当前无法访问 |
| `page_number`  | number / null | 命中文本所在的文档页码，从 `1` 开始。当无法确定命中页码时返回 `null`                        |
| `line_number`  | number / null | 命中文本所在的行号。当无法确定命中行号时返回 `null`                                   |

#### 4. `data.images[]` 图片结果字段

| 响应字段          | 类型      | 说明                                                              |
| :------------ | :------ | :-------------------------------------------------------------- |
| `file_id`     | string  | 文件唯一标识。用于唯一定位当前图片，并可用于文件预览、详情查询等后续接口调用                          |
| `filename`    | string  | 图片文件名称，包含文件扩展名，例如 `窗台上的猫咪.jpg`                                  |
| `preview_url` | string  | 图片预览地址。前端可通过该地址加载图片预览                                           |
| `score`       | number  | 当前图片与用户 `query` 的语义匹配度得分。数值越高表示图片与查询内容的相关程度越高                   |
| `path`        | string  | 图片在本地文件系统中的实际存储路径                                               |
| `accessible`  | boolean | 图片当前是否可访问。`true` 表示文件存在且当前具有访问权限；`false` 表示文件不存在、已移动、已删除或当前无法访问 |

#### 5. `data.videos[]` 视频结果字段

| 响应字段          | 类型            | 说明                                                              |
| :------------ | :------------ | :-------------------------------------------------------------- |
| `file_id`     | string        | 文件唯一标识。用于唯一定位当前视频，并可用于视频预览、详情查询等后续接口调用                          |
| `filename`    | string        | 视频文件名称，包含文件扩展名，例如 `大理洱海骑行.mp4`                                  |
| `preview_url` | string        | 视频预览地址。前端可通过该地址加载视频预览                                           |
| `score`       | number        | 当前视频与用户 `query` 的语义匹配度得分。数值越高表示视频与查询内容的相关程度越高                   |
| `path`        | string        | 视频在本地文件系统中的实际存储路径                                               |
| `start_time`  | number / null | 视频命中片段的开始时间，单位为秒。用于定位与用户查询相关的视频片段；无法确定时返回 `null`                |
| `end_time`    | number / null | 视频命中片段的结束时间，单位为秒。用于定位与用户查询相关的视频片段；无法确定时返回 `null`                |
| `accessible`  | boolean       | 视频当前是否可访问。`true` 表示文件存在且当前具有访问权限；`false` 表示文件不存在、已移动、已删除或当前无法访问 |

#### 6. `error` 字段

当请求成功时：

```json
{
  "error": null
}
```

当请求失败时：

```json
{
  "status": "error",
  "data": null,
  "error": {
    "code": "INVALID_QUERY",
    "message": "query cannot be empty or contain only whitespace characters"
  }
}
```

| 响应字段            | 类型     | 说明                 |
| :-------------- | :----- | :----------------- |
| `error.code`    | string | 错误码，用于程序判断具体错误类型   |
| `error.message` | string | 错误描述，用于说明请求失败的具体原因 |

---

* **响应描述**:

请求成功后，接口按照 `media_types` 指定的媒体类型分别返回文档、图片和视频搜索结果。

每一种媒体类型独立按照 `score` 从高到低排序，并最多返回 `limit` 条 Top N 结果。不同媒体类型之间不共享 `limit` 数量。

文档结果额外返回 `matched_text`、`page_number` 和 `line_number`，用于定位具体的文本命中位置；图片结果返回文件本身的匹配信息；视频结果额外返回 `start_time` 和 `end_time`，用于定位视频中的具体命中片段。

`accessible` 表示搜索索引中的文件当前是否仍然可以访问。即使文件不可访问，该文件仍可能作为搜索结果返回，但前端应根据该字段决定是否允许执行预览、播放或其他文件操作。

当某一媒体类型没有匹配结果时，对应数组返回 `[]`，不会影响其他媒体类型的搜索结果。

---

## 3. 文件夹与文件库资产 API (Library & Folder Management)

### 3.1 文件夹管理

#### `GET /library/folders`
获取文件库根层级的自定义文件夹列表。

- **响应 Body**:
```json
{
  "status": "success",
  "data": [
    {
      "id": "f1",
      "name": "2026 毕业旅行",
      "iconType": "travel",
      "description": "2026年毕业季大理洱海及周边的珍贵旅行合影与骑行视频。",
      "modified": "2026-09-19 10:10",
      "file_count": 5
    }
  ],
  "error": null
}
```

#### `POST /library/folders`
在 UI 根层级点击“+ 新建文件夹”创建新文件夹。

- **请求 Body**:
```json
{
  "name": "工作文档",
  "iconType": "work",
  "description": "FileSeek 项目开发及 Q2 战略规划文档"
}
```

#### `PUT /library/folders/{id}`
编辑已有文件夹的属性（修改名称、图标或描述）。

- **请求 Body**:
```json
{
  "name": "工作与战略文档",
  "iconType": "work",
  "description": "更新后的描述"
}
```

#### `DELETE /library/folders/{id}`
删除空文件夹（非空时返回 400 阻止删除）。

- **失败响应示例 (400 Bad Request)**:
```json
{
  "status": "error",
  "data": null,
  "error": "文件夹非空，无法直接删除。请先清空或转移其中的文件。"
}
```

---

### 3.2 子文件夹文件检索与批量操作

#### `GET /library/files`
获取子文件夹内的文件列表，支持 UI 侧的排序与筛选。

- **Query 参数**:
  - `folder_name`: 父级文件夹名称（选填）
  - `category`: 媒体分类过滤（`all` | `document` | `image` | `video`）
  - `sort_by`: 排序维度（`name` | `size` | `time`）
  - `sort_order`: 排序方向（`asc` | `desc`）

- **响应 Body**:
```json
{
  "status": "success",
  "data": [
    {
      "id": "file-1",
      "name": "2026年Q2业务回顾及战略规划.pdf",
      "mediaType": "document",
      "size": "12.4 MB",
      "modified": "2026-09-19 11:15",
      "parentFolder": "工作文档",
      "path": "/Users/lkkings/FileSeekLibrary/documents/2026年Q2业务回顾及战略规划.pdf"
    }
  ],
  "error": null
}
```


#### `POST /library/files/batch-delete`
勾选多个文件后，批量移入回收站。

- **请求 Body**:
```json
{
  "file_ids": ["file-1", "file-2"]
}
```

---

### 3.3 回收站 API (Recycle Bin)

#### `GET /library/recycle`
查看已移入回收站的文件列表。

#### `POST /library/recycle/{id}/restore`
将某文件从回收站还原至原位置。

#### `DELETE /library/recycle/{id}`
彻底永久删除回收站中的某文件。

#### `DELETE /library/recycle`
在 UI 侧点击“清空回收站”时彻底清除全部回收站内容。

---

### 3.4 最近访问记录 API (Recent Access)

#### `GET /library/recent`
获取最近预览或打开过的文件记录列表（支持相对时间倒序计算）。

---

## 4. 文件导入与任务队列 API (Ingest & Tasks)

### 4.1 提交导入任务

#### `POST /library/files/add`
在子文件夹内点击“+ 添加文件”导入新文件。
import_sourc: 本地文件｜nas ｜ 云盘
- **请求 Body**:
```json
{
  "parent_folder": "工作文档",
  "import_source": "nas",
  "path_input": "project_specs.docx",
  "batch_import_folder": false
}
```

- **响应 Body**:
```json
{
  "status": "success",
  "data": {
    "accepted": 2,
    "skipped": 0,
    "task_ids": ["task-1726798000-0", "task-1726798000-1"]
  },
  "error": null
}
```

---

### 4.2 任务队列查询与重试

#### `GET /tasks`
获取后台全量任务队列列表与状态计数（用于更新左侧边栏处理中任务 Badge 数量）。

- **Query 参数**: `?status=all|processing|queued|completed|failed`

- **响应 Body**:
```json
{
  "status": "success",
  "data": {
    "tasks": [
      {
        "id": "task-1726798000-0",
        "source_path": "/Users/lkkings/Documents/2026会议纪要.docx",
        "status": "processing",
        "progress": 45,
        "stage": "extracted",
        "completed_stages": ["moved", "extracted"],
        "priority": 1,
        "error_message": null,
        "created_at": "2026-09-20 02:30:00"
      }
    ],
    "counts": {
      "queued": 1,
      "processing": 2,
      "completed": 12,
      "failed": 1
    },
    "pagination": {
      "page": 1,
      "page_size": 50,
      "total": 16
    }
  },
  "error": null
}
```

#### `POST /tasks/{id}/retry`
重试失败的任务（保留断点 `completed_stages`）。

---

## 5. 系统设置与 NAS 存储 API (Settings & NAS)

### 5.1 通用设置与目录校验

#### `GET /settings`
读取系统存储根路径与 NAS 状态。

#### `POST /settings`
修改存储根路径 `lib_root`。如路径不可写，返回 400 错误。

- **请求 Body**:
```json
{
  "lib_root": "/Users/lkkings/FileSeekLibrary_New"
}
```

---

### 5.2 NAS 挂载连通性测试

#### `POST /settings/nas/test`
测试 NAS 网络凭据连通性。

- **请求 Body**:
```json
{
  "protocol": "smb",
  "host": "192.168.1.100",
  "share_path": "/FileSeekShare",
  "username": "nas_user",
  "password": "secret_password"
}
```

- **响应 Body**:
```json
{
  "status": "success",
  "data": "Connection successful!",
  "error": null
}
```

---

## 6. 系统底层控制与媒体流服务 (System & Streaming)

### 6.1 在系统文件管理器中打开 / 定位文件

#### `POST /system/locate`
在操作系统 Finder / 资源管理器中选中高亮文件。

- **请求 Body**: `{ "filepath": "/Users/lkkings/Documents/report.pdf" }`

#### `POST /system/open`
唤起操作系统默认绑定的外部软件打开文件。

- **请求 Body**: `{ "filepath": "/Users/lkkings/Documents/report.pdf" }`

---

### 6.2 视频与媒体流播放服务

#### `GET /media/{file_id}`
为 `FilePreviewModal` 中的 VideoJS 提供渐进式视频流播放服务。

- **HTTP 响应 Headers 格式**:
  - `Accept-Ranges: bytes`
  - `Content-Type: video/mp4`
  - `Content-Range: bytes 0-1048575/52428800`
  - 支持 HTTP `206 Partial Content` 响应状态码，确保秒级时间戳 Seek。
