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

## 2. Shared Cross-Browser Assets (Unified SSOT)

All browsers (Google Chrome, Mozilla Firefox, and Dillo) share a single declarative source of truth defined in `roles/browser_baseline/defaults/main.yml`:

### 2.1 Common Bookmarks (`browser_baseline_common_bookmarks`)
A single managed bookmarks list is rendered across all three browsers:
* **Chrome**: Managed via `ManagedBookmarks` enterprise policy in `/etc/opt/chrome/policies/managed/default_policies.json`.
* **Firefox**: Managed via `ManagedBookmarks` enterprise policy in `/etc/firefox/policies/policies.json`.
* **Dillo**: Managed via `~/.dillo/bm.txt` generated from the same template.

### 2.2 Common Search Shortcut Keywords (`browser_baseline_search_shortcuts`)
A unified set of search engine shortcuts is bound across all three browsers:
* `ww <query>`: Search WWOS (`http://wwos.home.arpa/index.php?search=...`)
* `trac <query>`: Search Trac (`http://trac.gafla.us.com/search?q=...`)
* `wik <query>`: Search Wikipedia (`https://en.wikipedia.org/...`)

### 2.3 Concurrent Named Firefox Profiles
Firefox is configured out of the box with multiple concurrent, isolated named profiles:
* `firefox-esr`: Default daily driver profile.
* `ff-remote-0`: Isolated profile for remote session / workstation 0.
* `ff-remote-1`: Isolated profile for remote session / workstation 1.
* `ff-remote-2`: Isolated profile for remote session / workstation 2.

Each profile is provisioned with:
* Registration in `~/.mozilla/firefox/profiles.ini`.
* Dedicated profile directory in `~/.mozilla/firefox/<profile_name>/`.
* CLI wrapper script in `/usr/local/bin/<profile_name>` running `firefox -P <profile_name> --no-remote`.
* Dedicated desktop entry in `/usr/share/applications/<profile_name>.desktop`.

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
1. An Ansible capture playbook extracts sanitized non-binary text configuration files.
2. Binary database files (`places.sqlite`, `cookies.sqlite`, LevelDB directories) are strictly excluded to avoid profile corruption, lock contention, and credential leaks.

### Step 2: Review and Version Control
1. Extracted config templates are staged in `ansible-netbox` (`roles/browser_baseline/templates/`).
2. Changes are committed to a topic branch `agent/<host>/browser-profile-update` and reviewed before merging to `origin/master`.

### Step 3: Declarative Convergence
1. Running `playbooks/apply_browser_baseline.yml` converges all fleet workstations to the updated baseline.
2. Idempotent check-mode ensures existing unmanaged files are untouched.

---

## 5. Security & Boundary Rules

1. **Zero Secret Replication**: Bitwarden master credentials and session tokens must **never** be copied into git, Ansible, or profile seeds. Bitwarden authentication remains strictly user-interactive.
2. **Wallabag OAuth Isolation**: Upstream Wallabag client secrets are stored in Ansible Vault (`vault.yml`) and configured via supported API/UI workflows, never in plaintext dotfiles.
3. **No Direct Profile DB Edits**: SQLite and LevelDB databases must not be manipulated via direct script writes while browsers are active.
