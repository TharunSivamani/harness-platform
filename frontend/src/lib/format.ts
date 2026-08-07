export function formatTokens(value: number | null | undefined): string {
  const n = Number(value || 0);
  if (!Number.isFinite(n) || n < 0) return "0";
  if (n < 1000) return String(Math.round(n));
  if (n < 1_000_000) {
    const k = n / 1000;
    if (k < 10) return `${trimFixed(k, 1)}k`;
    return `${Math.round(k)}k`;
  }
  const m = n / 1_000_000;
  if (m < 10) return `${trimFixed(m, 2)}M`;
  if (m < 100) return `${trimFixed(m, 1)}M`;
  return `${Math.round(m)}M`;
}

function trimFixed(value: number, digits: number): string {
  return value.toFixed(digits).replace(/\.?0+$/, "");
}

export function formatBytes(value: number | null | undefined): string {
  const n = Number(value || 0);
  if (n < 1024) return `${n}B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}KB`;
  return `${(n / (1024 * 1024)).toFixed(1)}MB`;
}
