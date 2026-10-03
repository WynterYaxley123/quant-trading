/** Exact origins shared with the launcher's DASHBOARD_ORIGINS setting. */
import { isIP } from 'node:net';

export function isExactOrigin(origin) {
  try {
    const url = new URL(origin);
    const host = url.hostname;
    const validHost = isIP(host.replace(/^\[|\]$/g, '')) > 0
      || (host.length <= 253 && host.split('.').every(label =>
        /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)));
    return ['http:', 'https:'].includes(url.protocol)
      && url.origin === origin && !url.username && !url.password
      && !origin.includes('*') && validHost
      && (!url.port || (Number(url.port) >= 1 && Number(url.port) <= 65535));
  } catch { return false; }
}

export function allowedOrigins(env = process.env) {
  const port = env.ETF_QUANT_DASHBOARD_PORT ?? '5173';
  if (!/^\d+$/.test(port) || Number(port) < 1024 || Number(port) > 65535) {
    throw new Error('INVALID_DASHBOARD_PORT');
  }
  const defaults = [port, '4173'].flatMap(p => [`http://127.0.0.1:${p}`, `http://localhost:${p}`]);
  const origins = env.DASHBOARD_ORIGINS === undefined ? defaults : env.DASHBOARD_ORIGINS.split(',').map(v => v.trim());
  for (const origin of origins) {
    if (!isExactOrigin(origin)) throw new Error('INVALID_DASHBOARD_ORIGIN');
  }
  return new Set(origins);
}
