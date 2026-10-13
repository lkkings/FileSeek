const UNITS = ["B", "KB", "MB", "GB", "TB"];

/** Decimal units, like the OS file managers that report the disk space we compare against. */
export function formatBytes(bytes: number): string {
  let value = bytes;
  let unit = 0;
  while (value >= 1000 && unit < UNITS.length - 1) {
    value /= 1000;
    unit += 1;
  }
  const digits = unit === 0 || value >= 100 ? 0 : 1;
  return `${value.toFixed(digits)} ${UNITS[unit]}`;
}

/** Seconds left at the current speed, or null when there is no meaningful estimate. */
export function etaSeconds(done: number, total: number, bytesPerSecond: number): number | null {
  if (bytesPerSecond <= 0 || total <= done) return null;
  return Math.ceil((total - done) / bytesPerSecond);
}

export function percent(done: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(100, Math.floor((done / total) * 100));
}
