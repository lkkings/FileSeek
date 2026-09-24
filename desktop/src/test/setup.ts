import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock Tauri system call and opener plugins to prevent errors in tests
vi.mock("@tauri-apps/plugin-opener", () => ({
  showItemInFolder: vi.fn(),
  open: vi.fn(),
}));

vi.mock("@tauri-apps/api/core", () => ({
  invoke: vi.fn(),
}));
