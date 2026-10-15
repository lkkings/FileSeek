import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SettingsPreferencesProvider } from "../../features/settings";
import { activateLocale, defaultLocale } from "../../i18n/i18n";
import { renderWithProviders } from "../../test/test-utils";
import { LibraryPage } from "./LibraryPage";

const folder = {
  id: "folder-1",
  name: "工作资料",
  icon_type: "work",
  description: "工作文件",
  modified: "2026-01-01T00:00:00Z",
  file_count: 0,
};

const storageLocations = [
  {
    id: "local",
    type: "local",
    name: "本地存储",
    protocol: "file",
    endpoint: "file://localhost",
    root_path: "/",
    account: null,
    status: "active",
    is_system: true,
  },
];

const searchItem = {
  file_id: "file-1",
  file_name: "cat.jpg",
  file_type: "jpg",
  category: "image",
  path: "/library/cat.jpg",
  size: 100,
  modified: "2026-10-01T00:00:00Z",
  tags: [],
  score: 0.9,
  metadata: {},
  chunks: [],
};

const searchData = {
  items: [searchItem],
  total: 21,
  page_number: 1,
  page_size: 20,
  has_more: true,
  counter: { document: 0, image: 21, video: 0 },
};

function successResponse<T>(data: T) {
  return new Response(JSON.stringify({ status: "success", data, error: null }), { status: 200 });
}

function createFetchMock(
  agentConfigured = true,
  enhancedResponse: () => Promise<Response> = async () => successResponse(searchData),
  enhancedStreamResponse: () => Response = () => streamResponse(),
) {
  const calls: Array<{ method: string; path: string; body?: string }> = [];
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const path = String(input);
      const method = init?.method ?? "GET";
      const body = typeof init?.body === "string" ? init.body : undefined;
      calls.push({ method, path, body });

      if (method === "GET" && path === "/api/v1/library/folders") {
        return successResponse([folder]);
      }
      if (method === "GET" && path === "/api/v1/settings/classifier-labels") {
        return successResponse({
          document_labels: [],
          image_labels: [],
          video_labels: [],
          version: "v1",
        });
      }
      if (method === "GET" && path === "/api/v1/settings/storage-locations") {
        return successResponse(storageLocations);
      }
      if (method === "GET" && path === "/api/v1/settings/agent") {
        return successResponse({
          base_url: "https://api.example.com/v1",
          model: "retrieval-expert",
          api_key_configured: agentConfigured,
        });
      }
      if (method === "POST" && path === "/api/v1/search/enhanced") {
        return enhancedResponse();
      }
      if (method === "POST" && path === "/api/v1/search/enhanced/stream") {
        return enhancedStreamResponse();
      }
      if (path.startsWith("/api/v1/recent?")) {
        return successResponse({
          items: [],
          page_number: 1,
          page_size: 20,
          total: 0,
          has_more: false,
        });
      }
      if (path.startsWith("/api/v1/settings/storage-locations/local/directory")) {
        return successResponse({
          current_path: "/",
          entries: [
            {
              name: "report.pdf",
              kind: "file",
              source_path: "/report.pdf",
              size: 100,
              modified: "2026-01-01T00:00:00Z",
            },
          ],
        });
      }
      return successResponse(null);
    },
  );
  return { fetchMock, calls };
}

function streamResponse() {
  const progress = [
    { type: "status", phase: "starting", message: "正在理解搜索意图" },
    {
      type: "tool_call",
      round_number: 1,
      tool_name: "search_files",
      query: "上个月旅行的猫照片",
      categories: ["image"],
    },
    {
      type: "tool_result",
      round_number: 1,
      tool_name: "search_files",
      candidate_count: 21,
      total: 21,
    },
    { type: "result", result: searchData },
  ];
  const body = progress
    .map((event) => `event: progress\ndata: ${JSON.stringify(event)}\n\n`)
    .join("");
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

let fetchMock: ReturnType<typeof createFetchMock>["fetchMock"];

function renderLibraryPage(onNavigateSettings = vi.fn()) {
  return renderWithProviders(
    <SettingsPreferencesProvider>
      <LibraryPage onNavigateSettings={onNavigateSettings} />
    </SettingsPreferencesProvider>,
  );
}

function submitEnhancedSearch() {
  fireEvent.click(screen.getByRole("button", { name: "启动检索增强" }));
  fireEvent.change(screen.getByLabelText("全局搜索"), {
    target: { value: "上个月旅行的猫照片" },
  });
  fireEvent.submit(screen.getByLabelText("全局搜索").closest("form"));
}

describe("LibraryPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
    activateLocale(defaultLocale);
    ({ fetchMock } = createFetchMock());
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
    activateLocale(defaultLocale);
  });

  it("opens and closes the import-file dialog without an import-folder action", async () => {
    renderLibraryPage();

    expect(await screen.findByText("工作资料")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "导入文件" }));

    expect(await screen.findByRole("dialog", { name: "导入文件到 工作资料" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "导入文件夹" })).not.toBeInTheDocument();
    expect(await screen.findByText("report.pdf")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("streams the initial enhanced search and keeps pagination and sorting on the enhanced endpoint", async () => {
    renderLibraryPage();
    await screen.findByText("工作资料");

    submitEnhancedSearch();

    expect(await screen.findByText("找到 21 条结果")).toBeInTheDocument();
    const calls = fetchMock.mock.calls as Array<[RequestInfo | URL, RequestInit?]>;
    const enhancedCalls = () =>
      calls.filter(([input]) => String(input) === "/api/v1/search/enhanced");
    const streamCalls = () =>
      calls.filter(([input]) => String(input) === "/api/v1/search/enhanced/stream");
    expect(streamCalls()).toHaveLength(1);
    expect(JSON.parse(streamCalls()[0][1]?.body)).toMatchObject({
      query: "上个月旅行的猫照片",
      sort_by: "relevance",
      sort_order: "desc",
      page_number: 1,
    });

    fireEvent.click(screen.getByRole("button", { name: "相关度" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "文件大小" }));

    await waitFor(() => {
      expect(enhancedCalls()).toHaveLength(1);
    });
    expect(JSON.parse(enhancedCalls().at(-1)?.[1]?.body)).toMatchObject({
      sort_by: "size",
      page_number: 1,
    });

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));

    await waitFor(() => {
      expect(enhancedCalls()).toHaveLength(2);
    });
    expect(JSON.parse(enhancedCalls().at(-1)?.[1]?.body)).toMatchObject({
      sort_by: "size",
      page_number: 2,
    });
  });

  it("does not cover enhanced retrieval progress with the search loading page", async () => {
    let resolveEnhanced: (response: Response) => void = () => undefined;
    const enhancedResponse = new Promise<Response>((resolve) => {
      resolveEnhanced = resolve;
    });
    let resolveStreamBody: ((body: string) => void) | undefined;
    const streamPromise = new Promise<string>((resolve) => {
      resolveStreamBody = resolve;
    });
    const stream = new Response(
      new ReadableStream<Uint8Array>({
        async start(controller) {
          const body = await streamPromise;
          controller.enqueue(new TextEncoder().encode(body));
          controller.close();
        },
      }),
      { status: 200, headers: { "Content-Type": "text/event-stream" } },
    );
    ({ fetchMock } = createFetchMock(
      true,
      () => enhancedResponse,
      () => stream,
    ));
    vi.stubGlobal("fetch", fetchMock);
    renderLibraryPage();
    await screen.findByText("工作资料");
    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(([input]) => String(input) === "/api/v1/settings/agent"),
      ).toBe(true);
    });
    await act(async () => undefined);

    submitEnhancedSearch();

    expect(screen.queryByText("正在搜索，请稍候...")).not.toBeInTheDocument();
    expect(screen.queryByText("智能体检索中")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeDisabled();
    const form = screen.getByLabelText("全局搜索").closest("form");
    fireEvent.submit(form!);
    const streamCalls = () =>
      fetchMock.mock.calls.filter(
        ([input]) => String(input) === "/api/v1/search/enhanced/stream",
      );
    await waitFor(() => expect(streamCalls()).toHaveLength(1));

    await act(async () => {
      resolveStreamBody?.(
        [
          'event: progress\ndata: {"type":"status","phase":"starting","message":"正在理解搜索意图"}\n\n',
          'event: progress\ndata: {"type":"tool_call","round_number":1,"tool_name":"search_files","query":"上个月旅行的猫照片","categories":["image"]}\n\n',
          `event: progress\ndata: ${JSON.stringify({ type: "result", result: searchData })}\n\n`,
        ].join(""),
      );
      await streamPromise;
    });

    expect(await screen.findByText("找到 21 条结果")).toBeInTheDocument();
    expect(screen.queryByText("正在搜索，请稍候...")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "智能体检索中" })).not.toBeInTheDocument();
  });

  it("guides users to settings when the agent is not configured", async () => {
    const onNavigateSettings = vi.fn();
    ({ fetchMock } = createFetchMock(false));
    vi.stubGlobal("fetch", fetchMock);
    renderLibraryPage(onNavigateSettings);
    await screen.findByText("工作资料");

    submitEnhancedSearch();

    expect(
      await screen.findByText("检索增强需要先配置 Agent 地址、模型和 API Key"),
    ).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input, init]) => {
      return String(input) === "/api/v1/search/enhanced" && (init?.method ?? "GET") === "POST";
    })).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "前往系统设置" }));
    expect(onNavigateSettings).toHaveBeenCalledTimes(1);
  });
});
