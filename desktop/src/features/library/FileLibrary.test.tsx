/**
 * 文件库对接后端的部分。
 *
 * 这里不测样式和布局，只测**契约**：请求发到哪个路径、用什么方法、body 长什么样，以及
 * 后端的字段名怎么翻成界面上的东西。这些是最容易在后端改动后悄悄错掉的地方。
 *
 * 断言里写死了后端的真实字段名（`FileType` 大驼峰、`size` 是纯数字字符串、回收站的
 * `original_*`），所以后端一旦改名这里就会红，而不是界面上默默变空。
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import { FileLibrary } from "./FileLibrary";
import { ApiClient, type RawResponse, type Transport } from "../../api/client";
import { I18nProvider } from "../../i18n/i18nContext.tsx";

interface Call {
  method: string;
  path: string;
  body: unknown;
}

/** 按路径回固定响应的假后端，同时记下每一次请求。 */
function backend(routes: Record<string, unknown>) {
  const calls: Call[] = [];

  const transport: Transport = async (method, path, body): Promise<RawResponse> => {
    calls.push({ method, path, body: body === undefined ? undefined : JSON.parse(body) });

    // 先按 `METHOD path` 精确匹配，再退回只按路径匹配。
    const key = `${method} ${path}`;
    const data = key in routes ? routes[key] : routes[path];

    if (data === undefined) {
      return {
        status: 404,
        body: JSON.stringify({ status: "error", data: null, error: `未预置的路由: ${key}` }),
      };
    }
    return { status: 200, body: JSON.stringify({ status: "success", data, error: null }) };
  };

  return { client: new ApiClient(transport), calls };
}

const FOLDER = {
  id: "d_1",
  name: "工作文档",
  iconType: "work",
  description: "季度材料",
  modified: "2026-09-19T10:10:00+00:00",
  file_count: 1,
};

const FILE = {
  id: "f_1",
  name: "季度报告.pdf",
  FileType: "document",
  size: "13001267",
  modified: "2026-09-18T08:00:00+00:00",
  parentFolder: "d_1",
  path: "/lib/documents/季度报告.pdf",
};

function renderLibrary(client: ApiClient, props: Record<string, unknown> = {}) {
  return render(
    <I18nProvider>
      <FileLibrary viewType="all" client={client} {...props} />
    </I18nProvider>,
  );
}

describe("文件库的文件夹视图", () => {
  it("把后端的文件夹渲染成卡片", async () => {
    const { client } = backend({ "/api/v1/library/folders": [FOLDER] });
    renderLibrary(client);

    expect(await screen.findByText("工作文档")).toBeInTheDocument();
    expect(screen.getByText("季度材料")).toBeInTheDocument();
  });

  it("请求带上 /api/v1 前缀", async () => {
    const { client, calls } = backend({ "/api/v1/library/folders": [FOLDER] });
    renderLibrary(client);

    await screen.findByText("工作文档");
    expect(calls[0]).toMatchObject({ method: "GET", path: "/api/v1/library/folders" });
  });

  it("根目录不去取文件列表", async () => {
    const { client, calls } = backend({ "/api/v1/library/folders": [FOLDER] });
    renderLibrary(client);

    await screen.findByText("工作文档");
    // 根视图只渲染文件夹卡片，那一趟请求是白跑的。
    expect(calls.some((call) => call.path.startsWith("/api/v1/library/files"))).toBe(false);
  });

  it("读不到文件夹时把后端的错误显示出来", async () => {
    const transport: Transport = async () => ({
      status: 503,
      body: JSON.stringify({ status: "error", data: null, error: "数据库还没就绪" }),
    });
    renderLibrary(new ApiClient(transport));

    expect(await screen.findByRole("alert")).toHaveTextContent("数据库还没就绪");
  });

  it("新建文件夹发的是后端要的 iconType 字段", async () => {
    const { client, calls } = backend({
      "/api/v1/library/folders": [],
      "POST /api/v1/library/folders": FOLDER,
    });
    renderLibrary(client);

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /新建文件夹/ }));
    await user.type(screen.getByLabelText("文件夹名称"), "新目录");
    await user.click(screen.getByRole("button", { name: "确认" }));

    await waitFor(() => {
      const posted = calls.find((call) => call.method === "POST");
      // 后端 schema 里这个键就叫 `iconType`（驼峰），不是 `icon_type`。
      expect(posted?.body).toEqual({
        name: "新目录",
        iconType: "default",
        description: "",
      });
    });
  });

  it("删除文件夹走 DELETE 并把后端的拒绝理由显示出来", async () => {
    const transport: Transport = async (method, path) => {
      if (method === "DELETE") {
        return {
          status: 200,
          body: JSON.stringify({
            status: "error",
            data: null,
            error: "文件夹非空，无法直接删除。",
          }),
        };
      }
      if (path === "/api/v1/library/folders") {
        return {
          status: 200,
          body: JSON.stringify({ status: "success", data: [FOLDER], error: null }),
        };
      }
      return { status: 404, body: "{}" };
    };

    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderLibrary(new ApiClient(transport));

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "🗑" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("文件夹非空");
  });
});

describe("文件夹里的文件列表", () => {
  const routes = {
    "/api/v1/library/folders": [FOLDER],
    "/api/v1/library/files?folder=%E5%B7%A5%E4%BD%9C%E6%96%87%E6%A1%A3&page=1&page_size=100": [FILE],
  };

  it("按当前文件夹的名字去取文件", async () => {
    const { client, calls } = backend(routes);
    renderLibrary(client, { selectedFolder: "工作文档" });

    await screen.findByText("季度报告.pdf");
    const listed = calls.find((call) => call.path.includes("/library/files"));
    // 后端这个参数收的是文件夹**名字**，用例内部再查 id。
    expect(listed?.path).toContain(`folder=${encodeURIComponent("工作文档")}`);
  });

  it("把纯数字的 size 格式化成可读体积", async () => {
    const { client } = backend(routes);
    renderLibrary(client, { selectedFolder: "工作文档" });

    // 后端给的是 "13001267" 这样的字节数字符串，不带单位。
    expect(await screen.findByText("12.4 MB")).toBeInTheDocument();
  });

  it("批量删除发到 batch-delete，body 是 file_ids", async () => {
    const { client, calls } = backend({
      ...routes,
      "POST /api/v1/library/files/batch-delete": null,
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderLibrary(client, { selectedFolder: "工作文档" });

    const user = userEvent.setup();
    // 表头的全选框和每行的勾选框都没有可访问名字，按顺序取第一个（全选）。
    await screen.findByText("季度报告.pdf");
    await user.click(screen.getAllByRole("checkbox")[0]);
    await user.click(screen.getByRole("button", { name: /批量删除/ }));

    await waitFor(() => {
      const posted = calls.find((call) => call.path.endsWith("/batch-delete"));
      expect(posted?.body).toEqual({ file_ids: ["f_1"] });
    });
  });

  it("打开预览时记一次访问", async () => {
    const { client, calls } = backend({
      ...routes,
      "POST /api/v1/library/files/f_1/access": null,
    });
    renderLibrary(client, { selectedFolder: "工作文档" });

    const user = userEvent.setup();
    await user.click(await screen.findByText("季度报告.pdf"));

    // 没有这一笔，"最近访问"列表永远是空的。
    await waitFor(() => {
      expect(calls.some((call) => call.path === "/api/v1/library/files/f_1/access")).toBe(true);
    });
  });

  it("导入文件发的是 folder_id / filename / path", async () => {
    const { client, calls } = backend({
      ...routes,
      "POST /api/v1/library/files": { file_id: "f_2" },
    });
    renderLibrary(client, { selectedFolder: "工作文档" });

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /添加文件/ }));
    await user.type(screen.getByLabelText("文件路径"), "/tmp/审计.xlsx");
    await user.click(screen.getByRole("button", { name: "确认" }));

    await waitFor(() => {
      const posted = calls.find(
        (call) => call.method === "POST" && call.path === "/api/v1/library/files",
      );
      // folder_id 是 id 而不是名字；filename 从路径尾段取。
      expect(posted?.body).toEqual({
        folder_id: "d_1",
        filename: "审计.xlsx",
        path: "/tmp/审计.xlsx",
      });
    });
  });
});

describe("回收站视图", () => {
  const ITEM = {
    id: "r_1",
    original_file_id: "f_9",
    original_name: "废弃草稿.pdf",
    original_path: "/lib/documents/废弃草稿.pdf",
    deleted_at: "2026-09-18T14:30:00+00:00",
    file_type: "document",
    size: "14680064",
  };

  const routes = { "/api/v1/library/recycle?page=1&page_size=100": [ITEM] };

  it("渲染的是 original_name 和 deleted_at", async () => {
    const { client } = backend(routes);
    render(
      <I18nProvider>
        <FileLibrary viewType="recycle" client={client} />
      </I18nProvider>,
    );

    expect(await screen.findByText("废弃草稿.pdf")).toBeInTheDocument();
    // `formatModified` 按本机时区渲染，所以只断言日期部分，免得测试跟着 TZ 飘。
    expect(screen.getByText(/2026-09-1[89] \d{2}:\d{2}/)).toBeInTheDocument();
  });

  it("还原走 POST /recycle/{id}/restore", async () => {
    const { client, calls } = backend({
      ...routes,
      "POST /api/v1/library/recycle/r_1/restore": null,
    });
    render(
      <I18nProvider>
        <FileLibrary viewType="recycle" client={client} />
      </I18nProvider>,
    );

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "恢复" }));

    await waitFor(() => {
      expect(
        calls.some((call) => call.path === "/api/v1/library/recycle/r_1/restore"),
      ).toBe(true);
    });
  });

  it("彻底删除走 DELETE /recycle/{id}", async () => {
    const { client, calls } = backend(routes);
    render(
      <I18nProvider>
        <FileLibrary viewType="recycle" client={client} />
      </I18nProvider>,
    );

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "永久删除" }));

    await waitFor(() => {
      expect(
        calls.some(
          (call) => call.method === "DELETE" && call.path === "/api/v1/library/recycle/r_1",
        ),
      ).toBe(true);
    });
  });

  it("清空回收站走 DELETE /recycle", async () => {
    const { client, calls } = backend(routes);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <I18nProvider>
        <FileLibrary viewType="recycle" client={client} />
      </I18nProvider>,
    );

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: /清空回收站/ }));

    await waitFor(() => {
      expect(
        calls.some(
          (call) => call.method === "DELETE" && call.path === "/api/v1/library/recycle",
        ),
      ).toBe(true);
    });
  });
});
