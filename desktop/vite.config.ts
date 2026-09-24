import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// @ts-expect-error type error without @types/node package
import process from "node:process";
// @ts-expect-error type error without @types/node package
import fs from "node:fs";
// @ts-expect-error type error without @types/node package
import os from "node:os";
// @ts-expect-error type error without @types/node package
import path from "node:path";

const host = process.env.TAURI_DEV_HOST;

/**
 * 后端发布的 `{port, token}`。
 *
 * 位置和 `backend/src/fileseek/config/paths.py::AppPaths` 以及 Rust 侧的
 * `sidecar::connection_file_path` 必须一致——三处算的是同一个文件。
 */
function connectionFile(): string {
  const home = os.homedir();
  if (process.platform === "win32") {
    const roaming = process.env.APPDATA || path.join(home, "AppData", "Roaming");
    return path.join(roaming, "FileSeek", "connection.json");
  }
  if (process.platform === "darwin") {
    return path.join(home, "Library", "Application Support", "FileSeek", "connection.json");
  }
  const xdg = process.env.XDG_CONFIG_HOME || path.join(home, ".config");
  return path.join(xdg, "fileseek", "connection.json");
}

function readConnection(): { port: number; token: string } | null {
  try {
    const raw = fs.readFileSync(connectionFile(), "utf-8");
    const parsed = JSON.parse(raw);
    if (typeof parsed.port === "number" && typeof parsed.token === "string") return parsed;
    return null;
  } catch {
    // 后端没起或还没写出连接文件。代理照常挂着，请求会失败并在控制台里说明原因。
    return null;
  }
}

// https://vite.dev/config/
export default defineConfig(() => ({
  plugins: [react()],

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },

    // 4. 把 API 请求转给后端，让 `npm run dev` 的浏览器预览也能连真后端。
    //
    // 浏览器直接发请求过不去，两道坎：token 只在 Rust 侧（WebView 拿不到，交给它就等于
    // 交给任何能在页面里执行脚本的东西），而且后端只认同源请求——浏览器会带上
    // `Origin: http://localhost:1420`，和后端的 `127.0.0.1:<port>` 不符，直接 403。
    //
    // 代理跑在 Vite 的 node 进程里：它从连接文件读 token 补上头，并把 Origin 改写成后端
    // 认的那个。token 不进浏览器，和 Tauri 里的走法一致。
    proxy: {
      "^/(api|health)": {
        // 端口在 `proxyReq` 里按当次请求改写，这里只是个占位：dev server 比后端活得久，
        // 后端重启会换端口（启动时动态选的），写死在这儿就会指向一个已经没人听的端口。
        target: `http://127.0.0.1:${readConnection()?.port ?? 8765}`,
        changeOrigin: false,
        configure: (proxy: {
          on: (event: string, handler: (...args: never[]) => void) => void;
        }) => {
          proxy.on("proxyReq", ((proxyReq: {
            setHeader: (name: string, value: string) => void;
            host?: string;
            port?: number;
            path: string;
          }) => {
            const connection = readConnection();
            if (!connection) return;

            // token 在 node 侧补：浏览器里没有它，也不该有。
            proxyReq.setHeader("X-FileSeek-Token", connection.token);
            // 后端只认同源请求（`bootstrap/auth.py::is_same_origin_request`），
            // 浏览器带来的 `http://localhost:1420` 会被 403。
            proxyReq.setHeader("Origin", `http://127.0.0.1:${connection.port}`);
            proxyReq.setHeader("Host", `127.0.0.1:${connection.port}`);
          }) as never);

          proxy.on("proxyReqWs", (() => {}) as never);
        },
      },
    },
  },

  test: {
    // Component tests render into a DOM; the API client tests do not need one but are
    // cheap enough to run in the same environment.
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: true,
  },
}));
