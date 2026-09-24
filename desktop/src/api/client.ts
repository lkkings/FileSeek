/**
 * 后端 HTTP 客户端。
 *
 * 请求不直接从 WebView 发出，而是经 Tauri 的 `api_request` command 交给 Rust
 * （`src-tauri/src/connection.rs`）：后端要求每个请求带 `X-FileSeek-Token`，而 token
 * 只存在 Rust 侧——把它交给 WebView 就等于交给任何能在页面里执行脚本的东西。
 *
 * 端口也是同样的原因走 Rust：它是后端启动时动态选的，写在 `connection.json` 里，
 * 由 Rust 读出来拼成 base_url。
 */

/** Raw HTTP-like response from our transport layers. */
export interface RawResponse {
  status: number;
  body: string;
}

/** Abstract transport boundary so client is mockable/testable. */
export type Transport = (
  method: "GET" | "POST" | "PUT" | "DELETE",
  path: string,
  body?: string,
) => Promise<RawResponse>;

/**
 * 后端把所有 feature 路由挂在这个前缀下（`config/settings.py` 的 `api_prefix`）。
 * Rust 桥是 `format!("{}{}", base_url, path)` 原样拼接，不加前缀，所以只能在这里补。
 *
 * `/health` 在前缀之外：桌面端靠它判断后端是否就绪，那时还没读到 token，所以它也免鉴权。
 */
const API_PREFIX = "/api/v1";
const UNPREFIXED = ["/health"];

function withPrefix(path: string): string {
  return UNPREFIXED.some((p) => path.startsWith(p)) ? path : `${API_PREFIX}${path}`;
}

/** `POST /search` 的 error 是这个形状，其余接口是一个字符串。 */
export interface ApiError {
  code: string;
  message: string;
}

/** 后端统一的响应信封（`shared/envelope.py`）。 */
export interface ApiResponse<T> {
  status: "success" | "error";
  data: T;
  /** 多数接口是字符串；search 是 `{code, message}`。用 `errorText` 抹平。 */
  error: string | ApiError | null;
}

/** 把两种 error 形状都渲染成可以放进文本节点的字符串。 */
export function errorText(error: string | ApiError | null | undefined): string {
  if (!error) return "";
  return typeof error === "string" ? error : error.message;
}

/**
 * 任务队列条目，对应后端的 `TaskResponse`
 * （`features/tasks/interfaces/http/schemas`）。
 */
export interface IngestionTask {
  id: string;
  source_path: string;
  status: "queued" | "processing" | "completed" | "failed";
  progress: number;
  stage: "moved" | "extracted" | "encoded" | "indexed" | null;
  error_message: string | null;
  created_at: string;
}

/** 后端不可达时返回的信封，形状和真实错误一致，调用方不必分两种情况处理。 */
function unavailable(message: string): RawResponse {
  return {
    status: 503,
    body: JSON.stringify({ status: "error", data: null, error: message }),
  };
}

/** 经 Tauri 桥发请求的默认 transport。 */
function tauriTransport(): Transport {
  return async (method, path, body) => {
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      // Rust 侧返回 `{status, body}`，正好是 RawResponse——非 2xx 也是正常返回，
      // 只有"请求根本没得到应答"才会抛。
      return await invoke<RawResponse>("api_request", {
        method,
        path,
        body: body ?? null,
      });
    } catch (e) {
      const err = e as { message?: string };
      return unavailable(
        err.message || "无法连接到后端服务。请确认它是否正常启动。",
      );
    }
  };
}

/**
 * 非 Tauri 环境（`npm run dev` 直接开浏览器）下的 transport。
 *
 * 走同源相对路径，由 Vite 的 dev proxy 转给后端（见 `vite.config.ts` 的 `server.proxy`）：
 * 代理在 node 侧补上 token 和 Origin，所以浏览器里不需要、也拿不到 token，和 Tauri 侧
 * 的走法一致。
 *
 * 这里不提供假数据：mock 出来的响应是一份和后端不一致的契约，看着能跑反而误导。
 */
function browserTransport(): Transport {
  return async (method, path, body) => {
    try {
      const response = await fetch(path, {
        method,
        ...(body === undefined ? {} : {
          headers: { "Content-Type": "application/json" },
          body,
        }),
      });
      return { status: response.status, body: await response.text() };
    } catch (e) {
      const err = e as { message?: string };
      return unavailable(
        err.message ||
          "无法连接到后端服务。请确认它已启动（uv run python -m fileseek）。",
      );
    }
  };
}

export class ApiClient {
  private transport: Transport;

  constructor(transport?: Transport) {
    if (transport !== undefined) {
      this.transport = transport;
      return;
    }
    const isTauri = (window as unknown as Record<string, unknown>).__TAURI__ !== undefined;
    this.transport = isTauri ? tauriTransport() : browserTransport();
  }

  public async get<T>(path: string): Promise<ApiResponse<T>> {
    return this.send<T>("GET", path);
  }

  public async post<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.send<T>("POST", path, body);
  }

  public async put<T>(path: string, body?: unknown): Promise<ApiResponse<T>> {
    return this.send<T>("PUT", path, body);
  }

  public async delete<T>(path: string): Promise<ApiResponse<T>> {
    return this.send<T>("DELETE", path);
  }

  private async send<T>(
    method: "GET" | "POST" | "PUT" | "DELETE",
    path: string,
    body?: unknown,
  ): Promise<ApiResponse<T>> {
    const raw = await this.transport(
      method,
      withPrefix(path),
      body === undefined ? undefined : JSON.stringify(body),
    );

    try {
      return JSON.parse(raw.body) as ApiResponse<T>;
    } catch {
      // 后端总是回 JSON 信封；解析不了说明中间出了别的东西（代理页面、崩溃堆栈），
      // 这时把状态码带出去比抛一个 SyntaxError 有用。
      return {
        status: "error",
        data: null as T,
        error: `后端返回了无法解析的响应（HTTP ${raw.status}）`,
      };
    }
  }
}

export default ApiClient;
export const defaultClient = new ApiClient();
