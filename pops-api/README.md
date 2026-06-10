# Pops KMS REST API

Central REST API for the Pops Personal Knowledge Management System.
Trac: [#3577](http://trac.home.arpa/ticket/3577) (parent) · first client: Telegram bot [#3576](http://trac.home.arpa/ticket/3576)

Runs on **athena** (where `/home/will/pops` lives), port **8765**, single shared API key (`X-API-Key` header) for all endpoints except `/api/health`.

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

## Phase 1 subtasks

See Trac #3577 for the graded subtask breakdown (P1.1 scaffold ... P1.7 tests) and assignment status.
