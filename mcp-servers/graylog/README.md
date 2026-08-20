# Graylog MCP Server

Model Context Protocol (MCP) server for Graylog integration.
Wraps `scripts/graylog_query.py` to provide tools for pulling recent log
entries and spotting recurring problems, without hand-rolling the REST
query each time.

## Features
- **graylog_ping**: Test connectivity and authentication.
- **graylog_query**: Run an arbitrary Graylog query string over a look-back window (hours).
- **graylog_recent**: Shorthand for `graylog_query` with `search="*"`.
- **graylog_summarize**: Fetch a window of messages, normalize out variable
  substrings (IPs, ports, PIDs, hex, audit IDs), and return the top recurring
  patterns ranked by count. Use this to spot problems or confirm a fix landed
  (a pattern's count dropping to zero, or a new pattern appearing).

For day-based windows, pass `hours=days*24` — there is no separate `days`
parameter.

## Configuration
Requires `GRAYLOG_API_TOKEN` env var, managed via `~/.config/mcp-secrets.env` (or `graylog_pops_admin_token` in `vault.yml` with runtime caching under `/tmp/pops-secrets-<uid>/`).
Default URL: `http://graylog.home.arpa:9000` (override with `GRAYLOG_URL`).

## Related
- `scripts/graylog_query.py` — underlying query logic (also usable standalone via CLI)
- `skills/domain/logfile-reviewer.md` — severity ranking and noise-pattern conventions for interpreting results
