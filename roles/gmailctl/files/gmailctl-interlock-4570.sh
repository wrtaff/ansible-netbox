#!/bin/sh
# ============================================================================
# TEMPORARY SAFETY INTERLOCK -- Trac #4570
# ============================================================================
# Installed on gmailctl-ansible 2026-09-11 (WP-1.1).
#
# WHY: /root/.gmailctl/config.jsonnet symlinks into /opt/config-repo, a STALE
# checkout ~512 lines behind live Gmail. Any Gmail-mutating gmailctl command
# would DELETE ~35 filters and ~36 ktn/* labels.
#
# BLOCKS the Gmail-mutating subcommands:
#     apply  -- "Apply a configuration file to Gmail settings"
#     edit   -- "Edit the configuration and apply it to Gmail"
#     init   -- "Initialize the Gmail configuration" (can clobber config dir)
#
# ALLOWS read-only subcommands: diff, debug, download, export, test,
# version, completion, help.
#
# MATCHING: exact string equality against EVERY argument (not substring,
# not first-arg-only). Deliberately conservative -- fails CLOSED. A file
# literally named "apply"/"edit"/"init" passed to --filename would also be
# refused. That is an accepted trade-off; a false refusal is harmless, a
# false pass destroys the filter set.
#
# REMOVAL: tracked as a WP-3 task. Do not remove by hand -- see #4570 for
# the checksum-asserting restoration procedure.
# ============================================================================
SELF="$0"
for a in "$@"; do
    case "$a" in
        apply|edit|init)
            cat >&2 <<'MSG'
gmailctl: BLOCKED -- Trac #4570

A Gmail-mutating subcommand (apply/edit/init) was refused on this host.

This host's default config resolves to a STALE checkout
(/opt/config-repo, ~512 lines behind live Gmail).
Proceeding would DELETE ~35 filters and ~36 ktn/* labels.

This block covers the no-flag AND --filename forms.
Read-only diff, debug, download, export, test still work normally.

See: http://trac.gafla.us.com/ticket/4570
MSG
            exit 90
            ;;
    esac
done
exec "${SELF}.real-4570" "$@"
