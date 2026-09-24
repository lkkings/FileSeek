/**
 * 后端客户端。
 *
 * 两件事在这里定死：路径前缀（后端的 feature 路由全挂在 `/api/v1` 下，`/health` 在前缀外），
 * 以及浏览器模式**确实会发请求**——它走同源相对路径，由 Vite 的 dev proxy 转给后端
 * （见 `vite.config.ts`），不是假数据、也不是一句"不支持"。
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClient, errorText, type RawResponse, type Transport } from "./client";

function recordingTransport(response?: Partial<RawResponse>) {
  const calls: Array<{ method: string; path: string; body?: string }> = [];
  const transport: Transport = async (method, path, body) => {
    calls.push({ method, path, body });
    return {
      status: response?.status ?? 200,
      body: response?.body ?? JSON.stringify({ status: "success", data: null, error: null }),
    };
  };
  return { client: new ApiClient(transport), calls };
}

describe("路径前缀", () => {
  it("业务路径补上 /api/v1", async () => {
    const { client, calls } = recordingTransport();

    await client.get("/library/folders");

    expect(calls[0].path).toBe("/api/v1/library/folders");
  });

  it("/health 不加前缀", async () => {
    const { client, calls } = recordingTransport();

    await client.get("/health");

    // 桌面端靠它判断后端是否就绪，那时还没读到 token，所以它在前缀和鉴权之外。
    expect(calls[0].path).toBe("/health");
  });

  it("查询串原样带过去", async () => {
    const { client, calls } = recordingTransport();

    await client.get("/library/files?folder=%E5%B7%A5%E4%BD%9C&page=1");

    expect(calls[0].path).toBe("/api/v1/library/files?folder=%E5%B7%A5%E4%BD%9C&page=1");
  });

  it("四个方法都能发", async () => {
    const { client, calls } = recordingTransport();

    await client.get("/a");
    await client.post("/b", { x: 1 });
    await client.put("/c", { y: 2 });
    await client.delete("/d");

    expect(calls.map((call) => call.method)).toEqual(["GET", "POST", "PUT", "DELETE"]);
    // 有 body 的才序列化，没 body 的不该发一个 "undefined" 字符串出去。
    expect(calls[1].body).toBe('{"x":1}');
    expect(calls[3].body).toBeUndefined();
  });
});

describe("响应解析", () => {
  it("解析不了的响应带上状态码而不是抛异常", async () => {
    const { client } = recordingTransport({ status: 502, body: "<html>proxy error</html>" });

    const response = await client.get("/library/folders");

    expect(response.status).toBe("error");
    expect(errorText(response.error)).toContain("502");
  });

  it("errorText 抹平两种 error 形状", () => {
    // 多数接口的 error 是字符串，search 的是 {code, message}。
    expect(errorText("文件不存在")).toBe("文件不存在");
    expect(errorText({ code: "INVALID_QUERY", message: "查询不能为空" })).toBe("查询不能为空");
    expect(errorText(null)).toBe("");
  });
});

describe("浏览器预览模式", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    delete (window as unknown as Record<string, unknown>).__TAURI__;
  });

  it("走 fetch 打同源相对路径，交给 dev proxy 转发", async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify({ status: "success", data: [], error: null })),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    // 没有 __TAURI__ 就是浏览器模式。
    const response = await new ApiClient().get("/library/folders");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    // 相对路径：经 Vite 代理走，同源，所以不触发 CORS，也不需要知道后端端口。
    expect(path).toBe("/api/v1/library/folders");
    expect(init.method).toBe("GET");
    expect(response.status).toBe("success");
  });

  it("不在浏览器侧带 token", async () => {
    const fetchMock = vi.fn(
      async () => new Response(JSON.stringify({ status: "success", data: null, error: null })),
    );
    globalThis.fetch = fetchMock as unknown as typeof fetch;

    await new ApiClient().post("/library/files/f_1/access");

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const headers = new Headers(init.headers ?? {});
    // token 由代理在 node 侧补上：放进浏览器就等于交给任何能在页面里执行脚本的东西。
    expect(headers.has("X-FileSeek-Token")).toBe(false);
  });

  it("后端没起时回一个信封，而不是抛异常", async () => {
    globalThis.fetch = vi.fn(async () => {
      throw new Error("Failed to fetch");
    }) as unknown as typeof fetch;

    const response = await new ApiClient().get("/library/folders");

    // 调用方只处理信封，不必额外 try/catch。
    expect(response.status).toBe("error");
    expect(errorText(response.error)).toBeTruthy();
  });
});
