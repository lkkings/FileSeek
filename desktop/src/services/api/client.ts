import { isTauriRuntime, requestApi } from "../tauri/api";

export interface RawResponse {
  status: number;
  body: string;
}

export type Transport = (
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: string,
) => Promise<RawResponse>;

export interface ApiError {
  code: string;
  message: string;
}

export interface ApiResponse<T> {
  status: "success" | "error";
  data: T | null;
  error: string | ApiError | null;
}

const API_PREFIX = "/api/v1";
const UNPREFIXED_PATHS = ["/health"];

function withApiPrefix(path: string) {
  return UNPREFIXED_PATHS.some((prefix) => path.startsWith(prefix)) ? path : `${API_PREFIX}${path}`;
}

export function errorText(error: string | ApiError | null | undefined) {
  if (!error) return "";
  return typeof error === "string" ? error : error.message;
}

function unavailable(): RawResponse {
  return { status: 503, body: JSON.stringify({ status: "error", data: null, error: { code: "API_UNAVAILABLE", message: "" } }) };
}

function browserTransport(): Transport {
  return async (method, path, body) => {
    try {
      const response = await fetch(path, {
        method,
        ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body }),
      });
      return { status: response.status, body: await response.text() };
    } catch {
      return unavailable();
    }
  };
}

function tauriTransport(): Transport {
  return async (method, path, body) => {
    try {
      return await requestApi(method, path, body);
    } catch {
      return unavailable();
    }
  };
}

export class ApiClient {
  private readonly transport: Transport;

  constructor(transport?: Transport) {
    this.transport = transport ?? (isTauriRuntime() && !import.meta.env.DEV ? tauriTransport() : browserTransport());
  }

  get<T>(path: string) {
    return this.send<T>("GET", path);
  }

  post<T>(path: string, body?: unknown) {
    return this.send<T>("POST", path, body);
  }

  put<T>(path: string, body?: unknown) {
    return this.send<T>("PUT", path, body);
  }

  patch<T>(path: string, body?: unknown) {
    return this.send<T>("PATCH", path, body);
  }

  delete<T>(path: string, body?: unknown) {
    return this.send<T>("DELETE", path, body);
  }

  private async send<T>(method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE", path: string, body?: unknown): Promise<ApiResponse<T>> {
    const response = await this.transport(method, withApiPrefix(path), body === undefined ? undefined : JSON.stringify(body));
    try {
      return JSON.parse(response.body) as ApiResponse<T>;
    } catch {
      return { status: "error", data: null, error: { code: "INVALID_RESPONSE", message: "" } };
    }
  }
}

export const defaultClient = new ApiClient();
