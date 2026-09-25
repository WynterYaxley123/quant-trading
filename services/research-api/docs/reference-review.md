# Hono reference review

Reviewed before implementation:

- [honojs/hono](https://github.com/honojs/hono/blob/main/README.md) and the [Hono Node guide](https://hono.dev/docs/getting-started/nodejs): use the small Web-Standards router with the separate `@hono/node-server` adapter; keep the request handler separately testable from the listening process.
- [Hono error handling](https://hono.dev/docs/api/hono): use one top-level `onError` and a stable JSON envelope, with internal artifact context logged but no filesystem path in HTTP errors.
- [Hono CORS middleware](https://hono.dev/docs/middleware/builtin/cors): configure exact allowed origins and only GET/HEAD/OPTIONS. Its default wildcard and mutation methods are explicitly not used.
- [Hono testing](https://hono.dev/docs/guides/testing): exercise the Fetch-style `app.request()` in unit and artifact integration tests, then verify the Node adapter through real HTTP.

Rejected: static-file serving, WebSockets, Hono RPC, a database, ORM, generic filesystem routes, and any mutation or research-execution route. None belongs to an artifact-only data adapter. The frozen Python research environment is never an API runtime.
