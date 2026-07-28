# Dashboard deployment boundary

No service, reverse proxy, firewall rule, process manager, or persistent process
is created in the foundation phase.

Future defaults:

- API: `127.0.0.1:8101`
- frontend: `127.0.0.1:3101`

The API entrypoint is
`trading_signals.interfaces.dashboard_api.main:app`. Before any future
deployment it still requires authentication, hardening, a dedicated service
user, read-only filesystem permissions, and a protected Nginx route.

`dashboard.env.example` contains names and non-secret defaults only. Active
release-relative sources must be configured explicitly; the API does not infer
or import the scheduler runtime.
