/**
 * The search page as one assembled view.
 *
 * The parts each have their own tests; what is verified here is only what appears when they
 * are put together — the landmarks, the skip link, the announcement of an outcome, and a
 * query travelling from the field to the client and back into the groups.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import App from "./App";
import { describeStatus } from "./app/status";
import { ApiClient, type RawResponse, type Transport } from "./api/client";
import { EMPTY_RESULTS, type SearchResults } from "./features/search/types";
import { aDocument, aVideo, anImage, results } from "./features/search/test-fixtures";

/** A client that answers `/search` with a fixed page, recording what it was asked. */
function clientReturning(
  page: SearchResults | SearchResults[],
  { fail = false }: { fail?: boolean } = {},
) {
  const pages = Array.isArray(page) ? page : [page];
  const asked: unknown[] = [];
  let call = 0;
  const transport: Transport = async (_method, _path, body): Promise<RawResponse> => {
    asked.push(body === undefined ? undefined : JSON.parse(body));
    if (fail) {
      return {
        status: 503,
        body: JSON.stringify({ status: "error", data: null, error: "索引服务尚未就绪。" }),
      };
    }
    const data = pages[Math.min(call, pages.length - 1)];
    call += 1;
    return { status: 200, body: JSON.stringify({ status: "success", data, error: null }) };
  };
  return { client: new ApiClient(transport), asked };
}

async function searchFor(query: string) {
  const user = userEvent.setup();
  await user.type(screen.getByRole("searchbox", { name: "搜索文件库" }), query);
  await user.keyboard("{Enter}");
  return user;
}

describe("the search page", () => {
  it("opens on the search field rather than a placeholder page", () => {
    const { client } = clientReturning(EMPTY_RESULTS);
    render(<App client={client} />);

    // The template it replaced had none of this.
    expect(screen.getByRole("searchbox", { name: "搜索文件库" })).toBeInTheDocument();
    expect(screen.queryByText("Welcome to Tauri + React")).not.toBeInTheDocument();
  });

  it("puts the search bar and the results in their own landmarks", () => {
    const { client } = clientReturning(EMPTY_RESULTS);
    render(<App client={client} />);

    expect(screen.getByRole("banner")).toContainElement(
      screen.getByRole("search") as HTMLElement,
    );
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("offers the skip link as the first tab stop", async () => {
    const { client } = clientReturning(EMPTY_RESULTS);
    const user = userEvent.setup();
    render(<App client={client} />);
    // The field is autofocused, so tabbing from it moves forward rather than to the top of
    // the page. What is asserted here is document order: from a clean slate, the skip link is
    // what a keyboard user reaches first.
    (document.activeElement as HTMLElement | null)?.blur();

    await user.tab();

    const link = screen.getByRole("link", { name: "跳到搜索结果" });
    expect(link).toHaveFocus();
    // It has to point at a target that can actually take focus.
    expect(link).toHaveAttribute("href", "#results");
    expect(screen.getByRole("main")).toHaveAttribute("id", "results");
    expect(screen.getByRole("main")).toHaveAttribute("tabindex", "-1");
  });

  it("sends the typed query and renders the groups that come back", async () => {
    const { client, asked } = clientReturning(
      results({ documents: [aDocument()], images: [anImage()], videos: [aVideo()] }),
    );
    render(<App client={client} />);

    await searchFor("猫在窗台");

    expect(asked[0]).toMatchObject({ query: "猫在窗台" });
    expect(await screen.findByText("测试文档.pdf")).toBeInTheDocument();
    expect(screen.getByText("测试图片.jpg")).toBeInTheDocument();
    expect(screen.getByText("测试视频.mp4")).toBeInTheDocument();
  });

  it("limits the query to the type selected in advanced filters", async () => {
    const { client, asked } = clientReturning(results({ videos: [aVideo()] }));
    const user = userEvent.setup();
    render(<App client={client} />);

    // The search bar (and its advanced filters) only live on the Library root page.
    await user.click(screen.getByRole("button", { name: "高级筛选" }));
    await user.click(screen.getByRole("button", { name: "视频" }));
    await searchFor("山间徒步");

    // The file-type chip fires its own live-filter search as soon as it's clicked (before
    // the query is typed), so the query-bearing request is the last one, not the first.
    expect(asked.at(-1)).toMatchObject({ query: "山间徒步", file_types: ["video"] });
  });

  it("announces how many results were found", async () => {
    const { client } = clientReturning(
      results({ documents: [aDocument()], images: [anImage()] }),
    );
    render(<App client={client} />);

    await searchFor("综述");

    // A search replaces the page without moving focus; without this it is silent.
    expect(await screen.findByRole("status")).toHaveTextContent("找到 2 条结果");
  });

  it("reports a failure once, as an alert", async () => {
    const { client } = clientReturning(EMPTY_RESULTS, { fail: true });
    render(<App client={client} />);

    await searchFor("综述");

    expect(await screen.findByRole("alert")).toHaveTextContent("索引服务尚未就绪");
    // Not also in the status line: two live regions with the same text is read twice.
    expect(screen.getByRole("status")).toHaveTextContent("");
  });

  it("explains an empty page without also announcing a count", async () => {
    const { client } = clientReturning(EMPTY_RESULTS);
    render(<App client={client} />);

    await searchFor("不存在的东西");

    // `EmptyResults` is itself a status region, so it is the one that speaks.
    expect(await screen.findByText(/未找到与“不存在的东西”匹配的内容/)).toBeInTheDocument();
  });
});

describe("describeStatus", () => {
  const base = { busy: false, error: null, query: null, results: EMPTY_RESULTS };

  it("says nothing before a search has run", () => {
    expect(describeStatus(base)).toBe("");
  });

  it("reports that a search is in flight", () => {
    expect(describeStatus({ ...base, busy: true })).toBe("正在搜索…");
  });

  it("counts every group", () => {
    expect(
      describeStatus({
        ...base,
        query: "猫",
        results: results({ documents: [aDocument()], images: [anImage(), anImage()] }),
      }),
    ).toBe("找到 3 条结果");
  });

  it("defers to the alert on a failure", () => {
    expect(describeStatus({ ...base, query: "猫", error: "后端未运行" })).toBe("");
  });

  it("defers to the empty state when nothing matched", () => {
    expect(describeStatus({ ...base, query: "猫" })).toBe("");
  });
});
