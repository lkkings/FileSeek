import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../../test/test-utils";
import { AgentSettingsCard } from "./AgentSettingsCard";
import type { AgentSettings } from "../types";

function settings(overrides: Partial<AgentSettings> = {}): AgentSettings {
  return {
    base_url: "https://api.example.com/v1",
    model: "retrieval-expert",
    api_key_configured: true,
    ...overrides,
  };
}

function successfulTest() {
  return vi.fn(async () => ({ success: true, message: "Agent 连接成功" }));
}

describe("AgentSettingsCard", () => {
  it("shows configured status without exposing the key", () => {
    renderWithProviders(
      <AgentSettingsCard
        settings={settings()}
        onSave={vi.fn(async () => true)}
        onTest={successfulTest()}
      />,
    );

    expect(screen.getByText("检索增强搜索已就绪")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("已配置，留空保留")).toBeInTheDocument();
    expect(screen.queryByDisplayValue(/secret/i)).not.toBeInTheDocument();
  });

  it("shows incomplete guidance", () => {
    renderWithProviders(
      <AgentSettingsCard
        settings={settings({ base_url: "", model: "", api_key_configured: false })}
        onSave={vi.fn(async () => true)}
        onTest={vi.fn(async () => ({ success: false, message: "Agent API Key 不能为空" }))}
      />,
    );

    expect(
      screen.getByText("请配置 Agent 地址、模型和 API Key 后使用检索增强搜索"),
    ).toBeInTheDocument();
  });

  it("saves settings and omits an unchanged key", async () => {
    const onSave = vi.fn(async () => true);
    renderWithProviders(
      <AgentSettingsCard settings={settings()} onSave={onSave} onTest={successfulTest()} />,
    );

    fireEvent.change(screen.getByLabelText("Agent 地址"), {
      target: { value: "https://api.updated.com/v1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(onSave).toHaveBeenCalledWith({
      base_url: "https://api.updated.com/v1",
      model: "retrieval-expert",
      api_key: null,
    }));
    expect(screen.getByPlaceholderText("已配置，留空保留")).toHaveValue("");
  });

  it("shows loading and a save failure", async () => {
    const onSave = vi.fn(async () => {
      throw new Error("保存检索智能体设置失败");
    });
    renderWithProviders(
      <AgentSettingsCard
        settings={settings()}
        onSave={onSave}
        onTest={successfulTest()}
        loading
      />,
    );

    expect(screen.getByText("正在读取设置...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存" })).toBeDisabled();

    const form = screen.getByLabelText("检索智能体设置");
    fireEvent.submit(form);
    await waitFor(() => expect(onSave).not.toHaveBeenCalled());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("tests the current settings and omits an unchanged key", async () => {
    const onTest = successfulTest();
    renderWithProviders(
      <AgentSettingsCard settings={settings()} onSave={vi.fn(async () => true)} onTest={onTest} />,
    );

    fireEvent.change(screen.getByLabelText("Agent 地址"), {
      target: { value: "https://api.updated.com/v1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "测试连接" }));

    await waitFor(() => expect(screen.getByText("Agent 连接成功")).toBeInTheDocument());
    expect(onTest).toHaveBeenCalledWith({
      base_url: "https://api.updated.com/v1",
      model: "retrieval-expert",
      api_key: null,
    });
  });

  it("shows a failed agent test", async () => {
    renderWithProviders(
      <AgentSettingsCard
        settings={settings()}
        onSave={vi.fn(async () => true)}
        onTest={vi.fn(async () => ({
          success: false,
          message: "Agent 服务请求失败: HTTP 401",
        }))}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "测试连接" }));

    expect(await screen.findByText("Agent 服务请求失败: HTTP 401")).toBeInTheDocument();
  });
});
