# XFCE Desktop SOE

Source ticket: [Trac #4190](http://trac.gafla.us.com/ticket/4190)
Parent project: [Trac #4187](http://trac.gafla.us.com/ticket/4187)

## Current Scope

The XFCE profile is being built incrementally. The broad `desktop_soe` role is
not yet the source of truth for user XFCE configuration. Do not run
`apply_desktop_soe.yml` as a way to apply this profile.

The current validated profile applies to `limbo-f0` and user `will`:

- Twelve XFCE workspaces named after Athena: `cal-wfl`, `in`, `todo`, `E/lc`, `F/c&p`, `dev-pd`, `s-prj`, `s-ops`, `H-fd`, `b/Geeks`, `m/r`, `msgs`
- Athena workspace movement shortcuts: `Ctrl+Alt+End` and `Ctrl+Alt+Home`
- Workspace pager immediately after the Applications Menu
- Workspace pager in a 2-row layout
- Workspace names displayed instead of pager thumbnails
- Panel size `37`, matching Athena
- Panel position locked
- Tasklist grouping disabled
- Athena separator order and separator styling preserved
- Athena panel plugins added: PulseAudio, power manager, notifications, system load, timer
- Session defaults aligned: save on exit, `Default` session name, no session lock
- Bottom, full-width panel position preserved

Display geometry, backdrop state, plugin runtime values, X2Go virtual-monitor
state, caches, and host-specific paths are not copied.

## Playbooks

Apply and rollback playbooks are separate by XFCE channel:

- `playbooks/apply_xfce_workspaces.yml`
- `playbooks/rollback_xfce_workspaces.yml`
- `playbooks/apply_xfce_workspace_shortcuts.yml`
- `playbooks/rollback_xfce_workspace_shortcuts.yml`
- `playbooks/apply_xfce_workspace_pager.yml`
- `playbooks/rollback_xfce_workspace_pager.yml`
- `playbooks/apply_xfce_session_settings.yml`
- `playbooks/rollback_xfce_session_settings.yml`

Run from the Ansible controller with a host limit. The inventory retains the
older `limbo-bd` alias for existing playbooks and also defines `limbo-f0` for
this host.

## Safety Procedure

Each apply playbook:

1. Confirms the remote hostname is `limbo-f0`.
2. Reads the current XFCE values.
3. Backs up only the channel file being changed when a change is required.
4. Applies only the declared channel settings.
5. Verifies the resulting values.

Each rollback playbook requires an explicit timestamped backup path. Rollback
restores only the channel file and reloads the affected user process.

The session playbook also handles hosts where XFCE has not yet persisted an
`xfce4-session.xml` file; in that case it applies the settings through xfconf
without pretending that a file backup exists.

## XFCE Runtime Reload

Ansible can update the persisted xfconf XML while the running XFCE daemon or
window manager retains old in-memory state. After a successful channel apply,
reload the affected user process when the live desktop does not reflect the
new values:

- Workspace layout: reload `xfwm4`
- Panel presentation: restart `xfconfd`, then reload `xfce4-panel`

No logout is normally required.

## Compatibility

- `limbo-f0`: XFCE 4.20.4
- `athena`: XFCE 4.20.x and canonical current behavior
- `zeus` / `opti-CC76`: XFCE 4.16, preference reference only

Do not copy a complete `~/.config/xfce4` tree across these hosts. XFCE
channels and plugin IDs must be compared and migrated individually.

## Incident Notes

- XFCE workspace arrays require all type declarations before all values when
  using `xfconf-query`.
- Boolean values passed to `xfconf-query` must be lowercase strings such as
  `false`, not YAML-rendered `False`.
- Athena's XFCE 4.20 backdrop configuration previously caused the null-folder
  failure tracked in [Trac #3220](http://trac.gafla.us.com/ticket/3220). Its
  backdrop and display state remain excluded.
