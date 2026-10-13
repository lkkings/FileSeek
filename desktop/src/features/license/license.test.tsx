import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../test/test-utils";
import type { Entitlement } from "../../services/tauri/license";
import { ActivationScreen, LicenseCard, LicenseProvider } from ".";

const license = vi.hoisted(() => {
  let listener: ((e: Entitlement) => void) | undefined;
  return {
    emit(e: Entitlement) {
      listener?.(e);
    },
    getEntitlement: vi.fn(),
    onEntitlementChange: vi.fn(async (fn: (e: Entitlement) => void) => {
      listener = fn;
      return () => {};
    }),
    activateLicense: vi.fn(),
    deactivateLicense: vi.fn(),
    recheckLicense: vi.fn(),
    openLibraryFolder: vi.fn(async () => {}),
  };
});

vi.mock("../../services/tauri/license", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../services/tauri/license")>();
  return { ...actual, ...license };
});

const opener = vi.hoisted(() => ({ openExternalUrl: vi.fn(async () => true) }));
vi.mock("../../services/tauri/opener", () => opener);

const BUY = "https://licenses.tuodianyuan.com/buy/fileseek";

function entitlement(partial: Partial<Entitlement>): Entitlement {
  return {
    state: "unlicensed",
    reason: "none",
    licenseId: null,
    planName: null,
    validUntil: null,
    updatesUntil: null,
    offlineDaysLeft: null,
    clockAnomaly: false,
    purchaseUrl: BUY,
    ...partial,
  };
}

const licensed = entitlement({ state: "licensed", reason: null, licenseId: "lic_1", planName: "Pro" });

function renderWith(initial: Entitlement, ui: ReactNode) {
  license.getEntitlement.mockResolvedValue(initial);
  return renderWithProviders(<LicenseProvider>{ui}</LicenseProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("activation screen", () => {
  it("says why, links to the purchase page and opens the library folder", async () => {
    renderWith(entitlement({ reason: "none" }), <ActivationScreen />);

    expect(await screen.findByText(/尚未激活/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "购买许可证" }));
    expect(opener.openExternalUrl).toHaveBeenCalledWith(BUY);
    fireEvent.click(screen.getByRole("button", { name: "打开文件库目录" }));
    expect(license.openLibraryFolder).toHaveBeenCalled();
  });

  it("activates with the key typed in", async () => {
    license.activateLicense.mockResolvedValue(licensed);
    renderWith(entitlement({}), <ActivationScreen />);

    const input = await screen.findByLabelText("许可证密钥");
    fireEvent.change(input, { target: { value: "KG-AAAA" } });
    fireEvent.click(screen.getByRole("button", { name: "激活" }));

    await waitFor(() => expect(license.activateLicense).toHaveBeenCalledWith("KG-AAAA"));
  });

  it("shows the activation limit with its counts", async () => {
    license.activateLicense.mockRejectedValue({ kind: "activation_limit", current: 2, max: 2 });
    renderWith(entitlement({}), <ActivationScreen />);

    fireEvent.change(await screen.findByLabelText("许可证密钥"), { target: { value: "KG-AAAA" } });
    fireEvent.click(screen.getByRole("button", { name: "激活" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("2/2");
  });

  it("tells a revoked license apart from needing to go online", async () => {
    const { unmount } = renderWith(entitlement({ reason: "revoked" }), <ActivationScreen />);
    expect(await screen.findByText(/许可证已失效/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重试" })).not.toBeInTheDocument();
    unmount();

    license.recheckLicense.mockResolvedValue(licensed);
    renderWith(entitlement({ reason: "offline_expired" }), <ActivationScreen />);
    expect(await screen.findByText(/需要联网验证许可/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    await waitFor(() => expect(license.recheckLicense).toHaveBeenCalled());
  });

  it("does not offer activation when the machine cannot be identified", async () => {
    renderWith(entitlement({ reason: "no_device" }), <ActivationScreen />);

    expect(await screen.findByText(/无法识别本机/)).toBeInTheDocument();
    expect(screen.queryByLabelText("许可证密钥")).not.toBeInTheDocument();
  });
});

describe("license card", () => {
  it("shows the plan, a perpetual license and the offline grace", async () => {
    renderWith({ ...licensed, offlineDaysLeft: 5 }, <LicenseCard />);

    expect(await screen.findByText("Pro")).toBeInTheDocument();
    expect(screen.getByText("有效期：永久")).toBeInTheDocument();
    expect(screen.getByText("离线中，请在 5 天内联网验证")).toBeInTheDocument();
  });

  it("follows the entitlement Rust pushes", async () => {
    renderWith(licensed, <LicenseCard />);
    await screen.findByText("Pro");

    act(() => license.emit({ ...licensed, planName: "Team", validUntil: "2027-01-31T00:00:00Z" }));

    expect(await screen.findByText("Team")).toBeInTheDocument();
    expect(screen.getByText("有效期至 2027-01-31")).toBeInTheDocument();
  });

  it("unbinds after confirmation", async () => {
    license.deactivateLicense.mockResolvedValue(entitlement({ reason: "none" }));
    renderWith(licensed, <LicenseCard />);

    fireEvent.click(await screen.findByRole("button", { name: "解绑本机" }));
    fireEvent.click(screen.getByRole("button", { name: "确定解绑" }));

    await waitFor(() => expect(license.deactivateLicense).toHaveBeenCalled());
  });

  it("keeps the license and says so when unbinding offline", async () => {
    license.deactivateLicense.mockRejectedValue({ kind: "network" });
    renderWith(licensed, <LicenseCard />);

    fireEvent.click(await screen.findByRole("button", { name: "解绑本机" }));
    fireEvent.click(screen.getByRole("button", { name: "确定解绑" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("客户门户");
  });
});
