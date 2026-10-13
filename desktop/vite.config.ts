import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
// @ts-expect-error type error without @types/node package
import process from "node:process";
// @ts-expect-error type error without @types/node package
import fs from "node:fs";
// @ts-expect-error type error without @types/node package
import os from "node:os";
// @ts-expect-error type error without @types/node package
import path from "node:path";
// @ts-expect-error type error without @types/node package
import http, { type IncomingMessage, type ServerResponse } from "node:http";

const host = process.env.TAURI_DEV_HOST;

/**
 * 后端发布的 `{port, token}`。
 *
 * 位置和 `backend/src/fileseek/config/paths.py::AppPaths` 以及 Rust 侧的
 * `preview_protocol::connection_file_path` 必须一致——三处算的是同一个文件。
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
    // 后端没起或还没写出连接文件：代理对这次请求回 503。
    return null;
  }
}

/**
 * 把 `/api`、`/health` 转给后端，让 `pnpm dev` 的浏览器预览也能连真后端。
 *
 * 后端由 Tauri 的 Rust 侧启动（`src-tauri/src/sidecar.rs`），比 Vite 晚起来，崩溃重启后
 * 还可能换端口，所以每个请求都重新读一次连接文件，而不是在配置时把端口定死。
 * 只跑 `pnpm dev`、不经过 Tauri 时，要自己在 backend/ 下 `uv run python -m fileseek`。
 *
 * 浏览器直接发请求过不去，两道坎：token 只在 Rust 侧（WebView 拿不到，交给它就等于
 * 交给任何能在页面里执行脚本的东西），而且后端只认同源请求——浏览器会带上
 * `Origin: http://localhost:1420`，和后端的 `127.0.0.1:<port>` 不符，直接 403。
 * 代理跑在 Vite 的 node 进程里：它从连接文件读 token 补上头，并把 Origin 改写成后端
 * 认的那个。token 不进浏览器，和 Tauri 里的走法一致。
 */
function backendProxy(): Plugin {
  const unavailable = (res: ServerResponse) => {
    if (res.headersSent) {
      res.end();
      return;
    }
    res.statusCode = 503;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({ status: "error", data: null, error: { code: "API_UNAVAILABLE", message: "backend is not running" } }));
  };

  return {
    name: "fileseek-backend-proxy",
    configureServer(server) {
      server.middlewares.use((req: IncomingMessage, res: ServerResponse, next: () => void) => {
        if (!req.url || !/^\/(api|health)(\/|\?|$)/.test(req.url)) {
          next();
          return;
        }
        const connection = readConnection();
        if (!connection) {
          unavailable(res);
          return;
        }
        const target = `127.0.0.1:${connection.port}`;
        const upstream = http.request(
          {
            host: "127.0.0.1",
            port: connection.port,
            method: req.method,
            path: req.url,
            headers: { ...req.headers, host: target, origin: `http://${target}`, "x-fileseek-token": connection.token },
          },
          (backendRes) => {
            res.writeHead(backendRes.statusCode ?? 502, backendRes.headers);
            backendRes.pipe(res);
          },
        );
        upstream.on("error", () => unavailable(res));
        // SSE 等长连接：浏览器断开时把上游也关掉。
        res.on("close", () => upstream.destroy());
        req.pipe(upstream);
      });
    },
  };
}

// https://vite.dev/config/
export default defineConfig(() => {
  return {
    plugins: [react(), backendProxy()],

    // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
    //
    // 1. prevent Vite from obscuring rust errors
    clearScreen: false,
    // 2. tauri expects a fixed port, fail if that port is not available
    server: {
      port: 1420,
      strictPort: true,
      host: host || false,
      fs: {
        allow: [path.resolve(process.cwd(), "..")],
      },
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
    },

    test: {
      // Component tests render into a DOM; the API client tests do not need one but are
      // cheap enough to run in the same environment.
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}", "../compatibility-tests/file-types/**/*.test.ts"],
      css: true,
    },
  };
});
