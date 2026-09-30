import { warmupSearch } from "../../services/api/search";

/** 两次预热之间的最短间隔。查询模型进程默认空闲 15 分钟才退出，30 秒内反复聚焦没必要再打一次。 */
export const WARMUP_THROTTLE_MS = 30_000;

// 放在模块级而不是组件状态里：切换页面会卸载重挂 SearchBar，节流不该因此重置。
let lastWarmupAt = Number.NEGATIVE_INFINITY;

export function resetWarmupThrottleForTests() {
  lastWarmupAt = Number.NEGATIVE_INFINITY;
}

/**
 * 节流地预热查询模型。预热只是加速，失败了也不影响输入和搜索本身，所以静默处理、不提示。
 */
export function warmupQueryModel(warmup: () => Promise<unknown> = warmupSearch) {
  const now = Date.now();
  if (now - lastWarmupAt < WARMUP_THROTTLE_MS) return;
  lastWarmupAt = now;
  warmup().catch(() => undefined);
}
