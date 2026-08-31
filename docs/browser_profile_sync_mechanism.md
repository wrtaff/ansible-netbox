# Browser & Workstation Profile Synchronization Architecture

**Author**: Pops AI / Gemini  
**Date**: 2026-08-31  
**Trac Tickets**: #2783, #4407, #4408, #4409, #4410, #4411, #4412  
**Components**: `sysadmin` (FCAPS: `fcaps-config`, `fcaps-security`)

---

## 1. Executive Summary

To provide a consistent, portable, and easily maintainable browser experience across all Pops workstations (including `zeus`/`opti-cc76`, `limbo-f0`, `titan2`, `athena`), we implement a **Three-Tier Architecture**:
1. **Tier 1: Declarative Enterprise Policy Baseline (Ansible `roles/browser_baseline`)**
2. **Tier 2: Browser-Native Cloud Sync (Firefox Sync & Google Sync)**
3. **Tier 3: Git-Backed Config & Dotfile Synchronization (`workstation_profile_sync`)**

This architecture ensures that new workstations converge automatically without manual friction, while allowing ongoing profile and configuration tweaks made on primary workstations (such as `zeus` for Chrome/Firefox, and `limbo-f0` for Dillo) to be captured, versioned, and synchronized safely.

---

## 2. The Three-Tier Architecture

```
+-------------------------------------------------------------------------------+
| Tier 1: Declarative System Baseline (Ansible)                                 |
| - Packages: google-chrome-stable, firefox-esr, dillo                         |
| - Enterprise Managed Policies: /etc/opt/chrome/policies/, /etc/firefox/policies|
| - Staged / Force-Installed Extensions: Bitwarden, Wallabag                     |
| - Security Defaults: Disable built-in password store (delegate to Bitwarden)   |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| Tier 2: Browser-Native Cloud Sync (User Interactive)                          |
| - Firefox Sync: Bookmarks, history, tabs, add-on state, synced preferences    |
| - Google Chrome Sync: Bookmarks, history, open tabs, synced extensions        |
| - Bitwarden: Interactive master vault login (zero secrets in Ansible/git)      |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| Tier 3: Git-Backed Config & Dotfile Synchronization                           |
| - Dillo: ~/.dillo/ (dillorc, cookiesrc, bm.txt) baselined from limbo-f0       |
| - Firefox Advanced Tweaks: user.js, chrome/userChrome.css from zeus/opti-cc76 |
| - Chrome Flags & SOE Desktop shortcuts                                        |
| - Capture & Distribute Playbooks: automated drift detection & git sync        |
+-------------------------------------------------------------------------------+
```

---

## 3. Host Roles & Reference Baselines

* **`zeus` (`opti-cc76`)**: **Primary Reference Workstation for Chrome and Firefox**. Ongoing GUI preferences, advanced flag adjustments, and custom profile extensions are authored and validated here first.
* **`limbo-f0`**: **Reference Workstation for Dillo & Lightweight SOE**. Minimalist browser configurations, Dillo search engines, and cookie whitelist rules are baselined here.
* **`athena`**: **Ansible Controller & Hub**. Central repository checkout (`/home/will/ansible-netbox`), orchestrating syntax validation, check-mode verification, and deployment.

---

## 4. Continuous Synchronization & Capture Workflow

To keep configurations current as Will tweaks settings over time without clobbering live browser SQLite/LevelDB databases:

### Step 1: Capture Tweaks from Reference Workstations
When customizations are refined on `zeus` (e.g. `user.js` options) or `limbo-f0` (e.g. `~/.dillo/dillorc` updates):
1. An Ansible capture playbook (`playbooks/capture_browser_configs.yml`) extracts sanitized non-binary text configuration files.
2. Binary database files (`places.sqlite`, `cookies.sqlite`, LevelDB directories) are strictly excluded to avoid profile corruption, lock contention, and credential leaks.

### Step 2: Review and Version Control
1. Extracted config templates are staged in `ansible-netbox` (`roles/browser_baseline/files/` or `templates/`).
2. Changes are committed to a topic branch `agent/<host>/browser-profile-update` and reviewed before merging to `origin/master`.

### Step 3: Declarative Convergence
1. Running `playbooks/apply_browser_baseline.yml` converges all fleet workstations to the updated baseline.
2. Idempotent check-mode ensures existing unmanaged files are untouched.

---

## 5. Security & Boundary Rules

1. **Zero Secret Replication**: Bitwarden master credentials and session tokens must **never** be copied into git, Ansible, or profile seeds. Bitwarden authentication remains strictly user-interactive.
2. **Wallabag OAuth Isolation**: Upstream Wallabag client secrets are stored in Ansible Vault (`vault.yml`) and configured via supported API/UI workflows, never in plaintext dotfiles.
3. **No Direct Profile DB Edits**: SQLite and LevelDB databases must not be manipulated via direct script writes while browsers are active.
