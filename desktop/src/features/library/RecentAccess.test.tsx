/**
 * 最近访问列表的对接部分。
 *
 * 这个列表要两趟请求才能渲染：`GET /library/recent` 只给 `{file_id, accessed_at}`，
 * 名字/体积/路径得靠 `GET /library/files/{id}` 逐条补。这里测的就是这个拼装过程，
 * 以及它的两个边界——重复访问只显示一条、详情取不到的那条直接跳过。
 */

import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import { RecentAccess } from "./RecentAccess";
import { ApiClient, type RawResponse, type Transport } from "../../api/client";
import { I18nProvider } from "../../i18n/i18nContext.tsx";

const PDF = {
  id: "f_1",
  name: "季度报告.pdf",
  FileType: "document",
  size: "13001267",
  modified: "2026-09-18T08:00:00+00:00",
  parentFolder: "d_1",
  path: "/lib/documents/季度报告.pdf",
};

const CAT = {
  id: "f_2",
  name: "猫咪.jpg",
  FileType: "image",
  size: "2516582",
  modified: "2026-09-20T09:00:00+00:00",
  parentFolder: null,
  path: "/lib/images/猫咪.jpg",
};

/**
 * 假后端。
 *
 * `files` 里没有的 id 一律回 404 —— 这正是"访问记录还在但文件已被永久删除"的样子。
 */
function backend(recent: Array<{ file_id: string; accessed_at: string }>, files: Record<string, unknown>) {
  const paths: string[] = [];

  const transport: Transport = async (_method, path): Promise<RawResponse> => {
    paths.push(path);

    if (path.startsWith("/api/v1/library/recent")) {
      return {
        status: 200,
        body: JSON.stringify({ status: "success", data: recent, error: null }),
      };
    }

    const match = /^\/api\/v1\/library\/files\/([^/?]+)$/.exec(path);
    if (match) {
      const file = files[decodeURIComponent(match[1])];
      if (!file) {
        return {
          status: 404,
          body: JSON.stringify({ status: "error", data: null, error: "文件不存在" }),
        };
      }
      return {
        status: 200,
        body: JSON.stringify({ status: "success", data: file, error: null }),
      };
    }

    return { status: 200, body: JSON.stringify({ status: "success", data: null, error: null }) };
  };

  return { client: new ApiClient(transport), paths };
}

function renderRecent(client: ApiClient, props: Record<string, unknown> = {}) {
  return render(
    <I18nProvider>
      <RecentAccess client={client} {...props} />
    </I18nProvider>,
  );
}

describe("最近访问", () => {
  it("把访问记录补成完整条目", async () => {
    const { client } = backend(
      [{ file_id: "f_1", accessed_at: "2026-09-20T11:15:00+00:00" }],
      { f_1: PDF },
    );
    renderRecent(client);

    expect(await screen.findByText("季度报告.pdf")).toBeInTheDocument();
    // 体积来自详情接口的纯数字字符串。
    expect(screen.getByText("12.4 MB")).toBeInTheDocument();
    expect(screen.getByText("/lib/documents/季度报告.pdf")).toBeInTheDocument();
  });

  it("同一个文件访问多次只取一条详情", async () => {
    const { client, paths } = backend(
      [
        { file_id: "f_1", accessed_at: "2026-09-20T11:15:00+00:00" },
        { file_id: "f_1", accessed_at: "2026-09-20T09:00:00+00:00" },
        { file_id: "f_1", accessed_at: "2026-09-19T09:00:00+00:00" },
      ],
      { f_1: PDF },
    );
    renderRecent(client);

    await screen.findByText("季度报告.pdf");

    // recent 表不去重，同一个文件访问十次就有十行；不先去重就会发十次详情请求。
    const detailCalls = paths.filter((path) => path === "/api/v1/library/files/f_1");
    expect(detailCalls).toHaveLength(1);
    expect(screen.getAllByText("季度报告.pdf")).toHaveLength(1);
  });

  it("详情取不到的那条跳过，不影响其它条目", async () => {
    const { client } = backend(
      [
        { file_id: "f_1", accessed_at: "2026-09-20T11:15:00+00:00" },
        { file_id: "f_gone", accessed_at: "2026-09-20T10:00:00+00:00" },
        { file_id: "f_2", accessed_at: "2026-09-20T09:00:00+00:00" },
      ],
      { f_1: PDF, f_2: CAT },
    );
    renderRecent(client);

    // 文件被永久删除后访问记录还留着，那一条没有可渲染的内容。
    expect(await screen.findByText("季度报告.pdf")).toBeInTheDocument();
    expect(screen.getByText("猫咪.jpg")).toBeInTheDocument();
  });

  it("按分类筛选时只留下该类型", async () => {
    const { client } = backend(
      [
        { file_id: "f_1", accessed_at: "2026-09-20T11:15:00+00:00" },
        { file_id: "f_2", accessed_at: "2026-09-20T09:00:00+00:00" },
      ],
      { f_1: PDF, f_2: CAT },
    );
    renderRecent(client, { activeCategory: "image" });

    expect(await screen.findByText("猫咪.jpg")).toBeInTheDocument();
    expect(screen.queryByText("季度报告.pdf")).not.toBeInTheDocument();
  });

  it("没有记录时给出空状态而不是一直转圈", async () => {
    const { client } = backend([], {});
    renderRecent(client);

    expect(await screen.findByText("最近没有访问记录")).toBeInTheDocument();
  });

  it("打开预览会再记一次访问", async () => {
    const { client, paths } = backend(
      [{ file_id: "f_1", accessed_at: "2026-09-20T11:15:00+00:00" }],
      { f_1: PDF },
    );
    renderRecent(client);

    const user = userEvent.setup();
    await user.click(await screen.findByText("季度报告.pdf"));

    await waitFor(() => {
      expect(paths).toContain("/api/v1/library/files/f_1/access");
    });
  });
});
