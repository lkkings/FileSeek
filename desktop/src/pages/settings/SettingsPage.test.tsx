import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SettingsPreferencesProvider } from "../../features/settings";
import { activateLocale, defaultLocale } from "../../i18n/i18n";
import { ApiClient, type RawResponse } from "../../services/api/client";
import type { ClassifierLabels, StorageLocation } from "../../services/api/settings";
import { renderWithProviders } from "../../test/test-utils";
import { SettingsPage } from "./SettingsPage";

const initialLabels: ClassifierLabels = {
  document_labels: ["合同"],
  image_labels: ["风景"],
  video_labels: ["会议"],
  version: "labels-v1",
};

const initialLocations: StorageLocation[] = [
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

function success<T>(data: T): RawResponse {
  return {
    status: 200,
    body: JSON.stringify({ status: "success", data, error: null }),
  };
}

function failure(message: string): RawResponse {
  return {
    status: 200,
    body: JSON.stringify({ status: "error", data: null, error: message }),
  };
}

function createSettingsClient() {
  let labels = structuredClone(initialLabels);
  let locations = structuredClone(initialLocations);
  const calls: Array<{ method: string; path: string; body?: string }> = [];

  const transport = vi.fn(async (method: string, path: string, body?: string): Promise<RawResponse> => {
    calls.push({ method, path, body });
    if (method === "GET" && path === "/api/v1/settings/classifier-labels") {
      return success(labels);
    }
    if (method === "GET" && path === "/api/v1/settings/storage-locations") {
      return success(locations);
    }
    if (method === "PUT" && path === "/api/v1/settings/classifier-labels") {
      const request = JSON.parse(body ?? "{}") as Omit<ClassifierLabels, "version">;
      if (request.document_labels.includes("保存失败")) return failure("标签保存失败");
      labels = { ...request, version: "labels-v2" };
      return success(labels);
    }
    if (method === "POST" && path === "/api/v1/settings/storage-locations") {
      const request = JSON.parse(body ?? "{}") as { id?: string };
      if (request.id === "duplicate") return failure("存储标识已存在");
      locations = [
        ...locations,
        {
          id: request.id ?? "generated",
          type: "nas",
          name: "家庭 NAS",
          protocol: "mounted",
          endpoint: "/Volumes/nas1",
          root_path: "/Volumes/nas1",
          account: "user",
          status: "active",
          is_system: false,
        },
      ];
      return success(locations.at(-1));
    }
    if (method === "POST" && path === "/api/v1/settings/storage-locations/nas1/test") {
      return success({ success: true, message: "连接正常" });
    }
    return failure("Unexpected request");
  });

  return { client: new ApiClient(transport), transport, calls };
}

function renderSettingsPage(client: ApiClient) {
  return renderWithProviders(
    <SettingsPreferencesProvider client={client}>
      <SettingsPage />
    </SettingsPreferencesProvider>,
  );
}

describe("SettingsPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    activateLocale(defaultLocale);
  });

  it("switches language", () => {
    const { client } = createSettingsClient();
    renderSettingsPage(client);

    expect(screen.getByRole("heading", { name: "语言设置" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "English" }));
    expect(screen.getByRole("heading", { name: "Language settings" })).toBeInTheDocument();
  });

  it("loads backend labels and adds a document label", async () => {
    const { client, calls } = createSettingsClient();
    renderSettingsPage(client);

    expect(await screen.findByText("合同")).toBeInTheDocument();
    const documentGroup = screen.getByRole("region", { name: "文档标签" });
    fireEvent.change(within(documentGroup).getByLabelText("标签名称"), {
      target: { value: "合同文件" },
    });
    fireEvent.click(within(documentGroup).getByRole("button", { name: "添加标签" }));

    expect(await screen.findByText("合同文件")).toBeInTheDocument();
    expect(calls).toContainEqual({
      method: "PUT",
      path: "/api/v1/settings/classifier-labels",
      body: JSON.stringify({
        document_labels: ["合同", "合同文件"],
        image_labels: ["风景"],
        video_labels: ["会议"],
      }),
    });
  });

  it("shows a backend label mutation failure", async () => {
    const { client } = createSettingsClient();
    renderSettingsPage(client);

    await screen.findByText("合同");
    const documentGroup = screen.getByRole("region", { name: "文档标签" });
    fireEvent.change(within(documentGroup).getByLabelText("标签名称"), {
      target: { value: "保存失败" },
    });
    fireEvent.click(within(documentGroup).getByRole("button", { name: "添加标签" }));

    expect(await screen.findByText("标签保存失败")).toBeInTheDocument();
  });

  it("adds and tests a NAS location without fabricated capacity data", async () => {
    const { client, calls } = createSettingsClient();
    renderSettingsPage(client);

    await screen.findByText("本地存储");
    fireEvent.click(screen.getByRole("button", { name: "添加存储驱动" }));
    fireEvent.change(screen.getByLabelText("驱动名称"), { target: { value: "家庭 NAS" } });
    fireEvent.change(screen.getByLabelText("存储标识"), { target: { value: "nas1" } });
    fireEvent.change(screen.getByLabelText("主机地址"), { target: { value: "/Volumes/nas1" } });
    fireEvent.change(screen.getByLabelText("用户名"), { target: { value: "user" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "secret" } });
    fireEvent.click(screen.getByRole("button", { name: "添加驱动" }));

    expect(await screen.findByText("家庭 NAS")).toBeInTheDocument();
    expect(screen.getByText("/Volumes/nas1")).toBeInTheDocument();
    expect(screen.queryByText(/TB/)).not.toBeInTheDocument();
    const createCall = calls.find((call) => call.method === "POST" && call.path === "/api/v1/settings/storage-locations");
    expect(createCall).toBeDefined();
    expect(JSON.parse(createCall?.body ?? "{}")).toEqual({
      id: "nas1",
      name: "家庭 NAS",
      protocol: "mounted",
      endpoint: "/Volumes/nas1",
      root_path: "/Volumes/nas1",
      account: "user",
      password: "secret",
    });

    fireEvent.click(screen.getAllByRole("button", { name: "测试连接" }).at(-1)!);
    expect(await screen.findByText("连接正常")).toBeInTheDocument();
    expect(calls).toContainEqual({ method: "POST", path: "/api/v1/settings/storage-locations/nas1/test" });
  });

  it("protects the built-in local location", async () => {
    const { client } = createSettingsClient();
    renderSettingsPage(client);

    const removeButton = await screen.findByRole("button", { name: "移除 本地存储" });
    expect(removeButton).toBeDisabled();
    expect(removeButton).toHaveAttribute("title", "系统存储不可移除");
  });

  it("shows a backend storage mutation failure", async () => {
    const { client } = createSettingsClient();
    renderSettingsPage(client);

    await screen.findByText("本地存储");
    fireEvent.click(screen.getByRole("button", { name: "添加存储驱动" }));
    fireEvent.change(screen.getByLabelText("驱动名称"), { target: { value: "重复 NAS" } });
    fireEvent.change(screen.getByLabelText("存储标识"), { target: { value: "duplicate" } });
    fireEvent.change(screen.getByLabelText("主机地址"), { target: { value: "/Volumes/nas" } });
    fireEvent.click(screen.getByRole("button", { name: "添加驱动" }));

    expect(await screen.findByText("存储标识已存在")).toBeInTheDocument();
  });
});
