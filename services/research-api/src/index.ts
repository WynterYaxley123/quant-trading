import { serve } from '@hono/node-server'
import { createApp, rawUrlGuardResponse } from './app.js'
import { loadConfig } from './config.js'

const config = loadConfig()
const app = createApp(config)
const server = serve({
  // The Node adapter can normalize literal dot segments before Hono route matching.
  // Guard the original IncomingMessage URL at the HTTP boundary as well.
  fetch: (request, env) => {
    const rejection = rawUrlGuardResponse(env.incoming.url ?? request.url)
    if (rejection) return rejection
    return app.fetch(request, env)
  },
  hostname: config.host, port: config.port,
}, (info) => {
  console.log(`Research API v1 listening on http://${config.host}:${info.port}/api/v1`)
})

for (const signal of ['SIGINT', 'SIGTERM'] as const) {
  process.on(signal, () => server.close())
}
