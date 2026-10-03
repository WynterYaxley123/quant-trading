/** Exact origins shared with the launcher's DASHBOARD_ORIGINS setting. */
export function allowedOrigins(env = process.env) {
  const port = env.ETF_QUANT_DASHBOARD_PORT ?? '5173';
  if (!/^\d+$/.test(port) || Number(port) < 1024 || Number(port) > 65535) {
    throw new Error('INVALID_DASHBOARD_PORT');
  }
  const defaults = [port, '4173'].flatMap(p => [`http://127.0.0.1:${p}`, `http://localhost:${p}`]);
  const origins = env.DASHBOARD_ORIGINS === undefined ? defaults : env.DASHBOARD_ORIGINS.split(',').map(v => v.trim());
  for (const origin of origins) {
    let url;
    try { url = new URL(origin); } catch { throw new Error('INVALID_DASHBOARD_ORIGIN'); }
    if (!['http:', 'https:'].includes(url.protocol) || url.origin !== origin || url.username || url.password
        || origin.includes('*') || url.hostname.includes('%')) throw new Error('INVALID_DASHBOARD_ORIGIN');
  }
  return new Set(origins);
}
