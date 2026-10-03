import { isIP } from 'node:net'

/** Canonical exact HTTP(S) origin; no wildcard, credentials or URL suffix. */
export function isExactOrigin(origin: string): boolean {
  try {
    const url = new URL(origin)
    const host = url.hostname
    const validHost = isIP(host.replace(/^\[|\]$/g, '')) > 0
      || (host.length <= 253 && host.split('.').every(label =>
        /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)))
    return ['http:', 'https:'].includes(url.protocol)
      && url.origin === origin && !url.username && !url.password
      && !origin.includes('*') && validHost
      && (!url.port || (Number(url.port) >= 1 && Number(url.port) <= 65535))
  } catch {
    return false
  }
}
