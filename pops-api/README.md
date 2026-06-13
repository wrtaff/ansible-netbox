# Pops KMS REST API

Central REST API for the Pops Personal Knowledge Management System.
Trac: [#3577](http://trac.home.arpa/ticket/3577) (parent) · first client: Telegram bot [#3576](http://trac.home.arpa/ticket/3576)

Runs on **athena** (where `/home/will/pops` lives), port **8765**, single shared API key (`X-API-Key` header) for all endpoints except `/api/health`.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness, version, pops-root status (no auth) |
| POST | `/api/inbox` | Timestamped capture to `raw/journal/` + `wiki/log.md` |
| GET | `/api/search` | ripgrep over `wiki/` (q, max_results, context) |
| POST | `/api/tasks` | Create Vikunja task (title, description, project_id, labels, due) |
| POST | `/api/tickets` | Create Trac ticket (markdown auto-converted to MoinMoin) |
| POST | `/api/transcribe` | Multipart audio upload; background job, returns `job_id` (202) |
| GET | `/api/transcribe/{job_id}` | Job status; transcript text/path when done |

Transcription jobs stage uploads in `POPS_ROOT/tmp/api-uploads/`, keep state JSON in `POPS_ROOT/tmp/api-jobs/`, and deliver transcripts to `raw/transcripts/`.

## Layout

```
pops-api/
  app/
    main.py            FastAPI entry point; mounts routers under /api
    config.py          env-driven settings (POPS_ROOT, POPS_API_KEY, ...)
    auth.py            X-API-Key dependency (P1.3)
    routers/           one module per endpoint; register in routers/__init__.py
    services/          filesystem/subprocess logic (journal, ripgrep, ...)
  tests/               pytest + TestClient; temp pops-root fixture (P1.7)
  systemd/             pops-api.service unit (Phase 4)
```

## Run as a service (production)

The API runs as a persistent systemd service on athena, deployed by `playbooks/deploy_pops_api.yml`.

```bash
# Check status
systemctl status pops-api

# Restart after a config or code change
systemctl restart pops-api
```

The production API key is stored at `/etc/pops-api/env` (mode 0640, root:will).
A copy is kept at `/home/will/pops/tmp/pops-api-key.txt` (mode 0600) for convenience.
To re-deploy or update the service unit:

```bash
cd ~/ansible-netbox
ansible-playbook -i inventory.ini playbooks/deploy_pops_api.yml --limit athena
```

## Run (development, athena)

```bash
cd ~/ansible-netbox/pops-api
POPS_API_KEY=devkey /opt/venvs/gemini_projects/bin/python3 -m uvicorn app.main:app \
    --host 0.0.0.0 --port 8765
```

Dependencies live in the shared project venv `/opt/venvs/gemini_projects` (installed by `playbooks/deploy_pops_api.yml`), not in system python.

Dependencies (`fastapi`, `uvicorn[standard]`, `python-multipart`) and the `ripgrep` binary are installed via the Ansible provisioning subtask (P1.2) - no ad-hoc `pip install` / `apt install`.

## Conventions (skills/domain/dev.md)

- Every source file carries the WWOS [Source code headers](http://wwos.home.arpa/index.php/Source_code_headers) block: Filename, Version, Author, Last Modified, Context (Trac URL), Purpose, **Secrets** (or explicit `None`), Usage, Revision History. Bump the version and annotate the history on every change.
- Commit format: `pops-api: <description>  ref #3577`. Stage specific files only; push to GitHub (`origin master`) on completion.
- Routers stay thin; logic lives in `app/services/`. New endpoint = router module + one import/list entry in `app/routers/__init__.py`.

## Tests

Pytest + FastAPI `TestClient` suite (P1.7). Every test runs against a throwaway
pops tree under pytest's `tmp_path` (via the `POPS_ROOT` env var), so the suite
never reads or writes the real `/home/will/pops`.

```bash
cd ~/ansible-netbox/pops-api
/opt/venvs/gemini_projects/bin/python3 -m pytest tests/ -v
```

Test dependencies (`pytest`, `httpx`) live in the shared project venv and are
pinned in `requirements.txt` under the `# pops-api test deps` comment; install
them by re-running `playbooks/deploy_pops_api.yml`. The search tests require the
`rg` binary (already installed at `/usr/bin/rg`).

`tests/smoke.sh` is a manual smoke test against an already-running server:

```bash
POPS_API_KEY=devkey ./tests/smoke.sh
POPS_API_URL=http://athena:8765 POPS_API_KEY=devkey ./tests/smoke.sh
```

WARNING: `smoke.sh` performs a real `/api/inbox` capture, which WRITES to the
live `POPS_ROOT` of the server under test (a `raw/journal/` file and a
`wiki/log.md` line).

## Project history

See Trac #3577 (parent: blueprint, decisions, phase reports), #3585 (Phase 2 action endpoints), #3586 (systemd deployment), #3596 (Phase 3 transcription).
