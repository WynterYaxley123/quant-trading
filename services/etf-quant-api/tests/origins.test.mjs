import { test } from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { readFileSync } from 'node:fs';
import { allowedOrigins } from '../origins.mjs';
import { createApi, PREFIX } from '../server.mjs';

const cases = JSON.parse(readFileSync(new URL('../../security/origin-cases.json', import.meta.url), 'utf8'));
for (const value of cases.valid) {
  test(`shared origin accepts ${value}`, () => assert(allowedOrigins({DASHBOARD_ORIGINS:value}).has(value)));
}
for (const value of cases.invalid) {
  test(`shared origin rejects ${value}`, () => assert.throws(() => allowedOrigins({DASHBOARD_ORIGINS:value})));
}

test('default and configurable local dashboard ports', () => {
  assert(allowedOrigins({}).has('http://localhost:5173'));
  assert(allowedOrigins({}).has('http://127.0.0.1:4173'));
  const custom = allowedOrigins({ETF_QUANT_DASHBOARD_PORT:'5199'});
  assert(custom.has('http://localhost:5199'));
  assert(!custom.has('http://localhost:5173'));
  assert.deepEqual([...allowedOrigins({DASHBOARD_ORIGINS:'http://localhost:5200,http://127.0.0.1:5200'})],
    ['http://localhost:5200', 'http://127.0.0.1:5200']);
});
for (const value of ['*', '', 'null', 'http://localhost:5173/path', 'http://localhost:5173/',
  'http://user:pass@localhost:5173', 'http://localhost:5173?query', 'file:///tmp', 'http://*.invalid']) {
  test(`reject malformed origin ${value}`, () => assert.throws(() => allowedOrigins({DASHBOARD_ORIGINS:value})));
}
for (const port of ['0','1023','65536','NaN','51.5']) {
  test(`reject invalid dashboard port ${port}`, () => assert.throws(() => allowedOrigins({ETF_QUANT_DASHBOARD_PORT:port})));
}
test('custom origin controls CORS and stale defaults are rejected', async t => {
  const server = createApi({origins:allowedOrigins({DASHBOARD_ORIGINS:'http://localhost:5200'})});
  server.listen(0,'127.0.0.1');
  await once(server,'listening');
  t.after(() => new Promise(resolve => server.close(resolve)));
  const url = `http://127.0.0.1:${server.address().port}${PREFIX}status`;
  const good = await fetch(url,{headers:{Origin:'http://localhost:5200'}});
  assert.equal(good.status,200);
  assert.equal(good.headers.get('access-control-allow-origin'),'http://localhost:5200');
  assert.equal((await fetch(url,{headers:{Origin:'http://localhost:5173'}})).status,403);
});
