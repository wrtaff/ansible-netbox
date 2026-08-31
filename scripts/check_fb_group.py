#!/usr/bin/env python3
"""
Filename:       check_fb_group.py
Version:        2.3
Author:         Antigravity
Last Modified:  2026-08-31
Context:        Facebook Group Updates (EPSC)

Purpose:
    Scrape the EPSC Facebook group using Playwright with the persistent
    profile to check for new posts and comments. If new items are detected,
    notify via Email using google_workspace_manager.py.

Secrets:
    None - delegates to google_workspace_manager.py

Revision History:
    v2.3 (2026-08-31) - Harden post author extraction, fallback to "EPSC Member", permit delivery on missing author.
    v2.2 (2026-08-10) - Enforce notification metadata and aggregate health alerts.
    v2.1 (2026-08-10) - Versioned observable state with atomic writes and migration.
    v2.0 (2026-06-22) - Email notifications, comment support, hash-based state.
    v1.0 (2026-06-12) - Initial version.

Usage:
    /opt/venvs/gemini_projects/bin/python3 check_fb_group.py
"""
import os
import sys
import json
import time
import subprocess
import hashlib
import urllib.parse
import re
import tempfile
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright

# Configuration
GROUP_URL = "https://www.facebook.com/groups/473971729877417/"
STATE_FILE = "/home/will/pops/tmp/fb_group_state.json"
PROFILE_DIR = "/home/will/.cache/ms-playwright/mcp-chrome-for-testing-f96f1ec" # Default Playwright MCP chrome profile
CHROME_PATH = "/usr/bin/google-chrome"
EMAIL_TO = "wrtaff@gmail.com"
STATE_VERSION = 2
RUN_RETENTION_DAYS = 90
ITEM_RETENTION = 2000
NOTIFICATION_ID_RETENTION = 2000
MAX_SCROLLS = 12
STABLE_PASSES = 2
MAX_ITEMS = 100

def get_canonical_url(url):
    """Strips dynamic tracking parameters from Facebook URLs to create a stable unique ID."""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        canonical_qs = {}
        # Keep only the parameters that uniquely identify a post or comment
        if 'comment_id' in qs:
            canonical_qs['comment_id'] = qs['comment_id']
        if 'reply_comment_id' in qs:
            canonical_qs['reply_comment_id'] = qs['reply_comment_id']
        if 'multi_permalinks' in qs:
            canonical_qs['multi_permalinks'] = qs['multi_permalinks']
        if 'story_fbid' in qs:
            canonical_qs['story_fbid'] = qs['story_fbid']
            
        new_query = urllib.parse.urlencode(canonical_qs, doseq=True)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ''))
    except Exception:
        return url

def clean_author(author, default="EPSC Member"):
    """Strips relative time strings that Facebook occasionally includes in author elements."""
    if not author:
        return default
    pattern = r'\s+(a week ago|yesterday|just now|\d+\s+(h|m|d|w|y|hr|hrs|min|mins|day|days|week|weeks|month|months|year|years)\s+ago|last night).*$'
    cleaned = re.sub(pattern, '', author, flags=re.IGNORECASE).strip()
    return cleaned if cleaned else default


def is_facebook_permalink(url, is_comment):
    """Validate that a URL identifies the requested Facebook item type."""
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if hostname not in {"facebook.com", "www.facebook.com", "m.facebook.com"}:
            return False
        query = urllib.parse.parse_qs(parsed.query)
        if is_comment:
            return bool(query.get("comment_id") or query.get("reply_comment_id"))
        return any(
            marker in parsed.path
            for marker in ("/permalink/", "/posts/")
        ) or bool(query.get("story_fbid") or query.get("multi_permalinks"))
    except ValueError:
        return False


def get_validation_failures(post):
    """Return explicit reasons why a candidate cannot be normally notified."""
    failures = []
    display_url = post.get("display_url", "")
    if not display_url:
        failures.append("missing_url")
    elif not is_facebook_permalink(display_url, post.get("is_comment", False)):
        failures.append("invalid_permalink")
    if not post.get("content"):
        failures.append("missing_content")
    return failures

def notify_via_email(subject, message):
    """Call Google Workspace Manager to send an email notification."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gws_manager = os.path.join(script_dir, "google_workspace_manager.py")
    
    try:
        subprocess.run(
            [sys.executable, gws_manager, "gmail-send", EMAIL_TO, subject, message],
            check=True,
            capture_output=True,
            text=True
        )
        print("Notification sent via Email.")
        return True
    except Exception as e:
        print(f"Failed to send email notification: {e}", file=sys.stderr)
        if hasattr(e, 'stderr') and e.stderr:
            print(e.stderr, file=sys.stderr)
        return False


def utc_now():
    """Return a stable UTC timestamp for state and run records."""
    return datetime.now(timezone.utc).isoformat()


def empty_state():
    """Return the versioned state shape used by the scraper."""
    return {
        "version": STATE_VERSION,
        "updated_at": None,
        "notification_ids": [],
        "items": {},
        "runs": [],
    }


def load_state(path):
    """Load state and migrate the pre-v2 hash-only format in memory."""
    state = empty_state()
    migrated = False
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                loaded = json.load(f)
            if loaded.get("version") == STATE_VERSION:
                state.update(loaded)
                state["notification_ids"] = list(state.get("notification_ids", []))
                state["items"] = dict(state.get("items", {}))
                state["runs"] = list(state.get("runs", []))
            else:
                # Preserve old notification identities so migration cannot replay them.
                state["notification_ids"] = list(loaded.get("notified_hashes", []))
                latest = loaded.get("latest_post")
                if isinstance(latest, dict):
                    old_hash = hashlib.md5(
                        (latest.get("author", "") + latest.get("content", "")).encode("utf-8")
                    ).hexdigest()
                    if old_hash not in state["notification_ids"]:
                        state["notification_ids"].append(old_hash)
                migrated = True
        except Exception as e:
            print(f"Warning: Failed to load old state: {e}")
            migrated = True
    return state, migrated


def save_state(path, state):
    """Atomically replace the state file so interrupted writes cannot truncate it."""
    state["version"] = STATE_VERSION
    state["updated_at"] = utc_now()
    directory = os.path.dirname(path) or "."
    fd, temporary_path = tempfile.mkstemp(prefix=".fb_group_state.", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def prune_state(state, now_epoch=None):
    """Apply the WP-0 retention bounds and return whether pruning occurred."""
    pruned = False
    cutoff = (now_epoch if now_epoch is not None else time.time()) - (RUN_RETENTION_DAYS * 86400)
    runs = state.get("runs", [])
    kept_runs = [run for run in runs if run.get("started_epoch", 0) >= cutoff]
    if len(kept_runs) != len(runs):
        pruned = True
    state["runs"] = kept_runs[-RUN_RETENTION_DAYS * 12:]

    items = state.get("items", {})
    if len(items) > ITEM_RETENTION:
        ordered = sorted(items.items(), key=lambda pair: pair[1].get("last_seen_at", ""))
        state["items"] = dict(ordered[-ITEM_RETENTION:])
        pruned = True

    ids = state.get("notification_ids", [])
    if len(ids) > NOTIFICATION_ID_RETENTION:
        state["notification_ids"] = ids[-NOTIFICATION_ID_RETENTION:]
        pruned = True
    return pruned


def extract_feed_items(page):
    """Extract structured candidates without adding state to the page DOM."""
    return page.evaluate('''() => {
        const feed = document.querySelector('div[role="feed"]');
        if (!feed) return [];

        const isCandidateUrl = (href) => href && (
            href.includes('/permalink/') ||
            href.includes('/posts/') ||
            href.includes('multi_permalinks=') ||
            href.includes('story_fbid=') ||
            href.includes('comment_id=') ||
            href.includes('reply_comment_id=')
        );
        const isGroupRootUrl = (href) => {
            if (!href) return false;
            try {
                const u = new URL(href);
                const path = u.pathname.replace(/\/$/, '');
                return path === '/groups/473971729877417' || path === '' || path === '/';
            } catch (e) {
                return false;
            }
        };
        const text = (element) => element ? element.innerText.trim() : '';
        const records = [];
        const seen = new Set();

        const addRecord = (record) => {
            if (!record.content) return;
            const key = record.url || [record.type, record.author, record.content].join('|');
            if (seen.has(key)) return;
            seen.add(key);
            records.push(record);
        };

        feed.querySelectorAll('div[data-ad-comet-preview="message"]').forEach((message) => {
            const article = message.closest('div[role="article"]');
            if (!article) return;
            const links = Array.from(article.querySelectorAll('a'));
            const urlLink = links.find((link) => isCandidateUrl(link.href));

            // Hardened post author extraction strategy:
            // 1. Heading element link (h2, h3, h4, role="heading", strong)
            const heading = article.querySelector('h2, h3, h4, [role="heading"]');
            let authorLink = null;
            let authorSource = 'missing';

            if (heading) {
                authorLink = Array.from(heading.querySelectorAll('a')).find((link) => text(link) && !isCandidateUrl(link.href) && !isGroupRootUrl(link.href));
                if (authorLink) authorSource = 'heading-link';
            }

            // 2. Strong tag enclosing or inside an anchor
            if (!authorLink) {
                const strongLinks = Array.from(article.querySelectorAll('strong a, a strong'));
                for (const sl of strongLinks) {
                    const a = sl.tagName === 'A' ? sl : sl.closest('a');
                    if (a && text(a) && !isCandidateUrl(a.href) && !isGroupRootUrl(a.href)) {
                        authorLink = a;
                        authorSource = 'strong-link';
                        break;
                    }
                }
            }

            // 3. User profile link patterns (href contains /user/ or /profile.php)
            if (!authorLink) {
                authorLink = links.find((link) => {
                    const href = link.href || '';
                    return (href.includes('/user/') || href.includes('/profile.php')) && text(link);
                });
                if (authorLink) authorSource = 'profile-link';
            }

            // 4. Any non-candidate, non-group anchor with text appearing before the message
            if (!authorLink) {
                authorLink = links.find((link) => text(link) && !isCandidateUrl(link.href) && !isGroupRootUrl(link.href));
                if (authorLink) authorSource = 'link';
            }

            let author = text(authorLink);

            // 5. If authorLink wasn't found but heading has text
            if (!author && heading) {
                const hText = text(heading);
                if (hText) {
                    author = hText.split(/\s+(?:in|shared|posted|at)\s+/i)[0].trim();
                    if (author) authorSource = 'heading-text';
                }
            }

            // 6. Check aria-label on article
            if (!author) {
                const articleLabel = article.getAttribute('aria-label') || '';
                const match = articleLabel.match(/(?:Post|Story)\s+by\s+([^,]+)/i);
                if (match && match[1].trim()) {
                    author = match[1].trim();
                    authorSource = 'aria-label';
                }
            }

            addRecord({
                type: 'post',
                author: author || 'EPSC Member',
                author_source: author ? authorSource : 'fallback',
                author_status: author ? 'present' : 'missing',
                content: text(message),
                url: urlLink ? urlLink.href : ''
            });
        });

        feed.querySelectorAll('div[role="article"]').forEach((article) => {
            const label = article.getAttribute('aria-label') || '';
            if (!/^Comment/.test(label)) return;
            const commentText = article.querySelector('div[dir="auto"]');
            const commentLink = Array.from(article.querySelectorAll('a')).find(
                (link) => link.href && (link.href.includes('comment_id=') || link.href.includes('reply_comment_id='))
            );
            const author = label.replace(/^Comment (by|from) /, '').trim();
            addRecord({
                type: 'comment',
                author: author || 'EPSC Member',
                author_source: author ? 'aria-label' : 'fallback',
                author_status: author ? 'present' : 'missing',
                content: text(commentText),
                url: commentLink ? commentLink.href : ''
            });
        });

        return records;
    }''')

def main():
    if not os.path.exists(PROFILE_DIR):
        # Fallback to standard Chrome profile if testing one doesn't exist
        alt_profile = "/home/will/.cache/ms-playwright/mcp-chrome-f96f1ec"
        if os.path.exists(alt_profile):
            profile_path = alt_profile
        else:
            print(f"Error: Profile directory {PROFILE_DIR} not found.", file=sys.stderr)
            notify_via_email(
                "EPSC Facebook Scraper: Browser unavailable",
                f"The configured Playwright profile was not found: {PROFILE_DIR}",
            )
            sys.exit(1)
    else:
        profile_path = PROFILE_DIR

    print(f"Using profile path: {profile_path}")

    # Ensure state directory exists
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    state, state_migrated = load_state(STATE_FILE)
    run_started_at = utc_now()
    run_started_epoch = time.time()

    with sync_playwright() as p:
        # Launch using persistent context (headless)
        print("Launching browser context...")
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                executable_path=CHROME_PATH,
                headless=True
            )
        except Exception as e:
            # If browser is locked by a running MCP server, we'll get an error
            print(f"Error launching context. Playwright may be locked by another process: {e}", file=sys.stderr)
            notify_via_email(
                "EPSC Facebook Scraper: Browser unavailable",
                "Playwright could not launch the persistent browser context. "
                "The profile may be locked by another process.\n\n"
                f"Error: {e}",
            )
            sys.exit(1)

        page = context.new_page()
        
        print(f"Navigating to group URL: {GROUP_URL}")
        page.goto(GROUP_URL, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(5000)
        
        # Check if we got redirected to login (session expired)
        if "login" in page.url or page.locator("input[name='email']").first.is_visible():
            print("Session expired or not logged in. Sending notification.")
            notify_via_email("EPSC Facebook Scraper: Session Expired", "Facebook session has expired. Please log back in using the Facebook Messenger skill to refresh the session.")
            context.close()
            sys.exit(0)

        # Click the sorting dropdown to select 'New posts'
        print("Checking sort option...")
        sort_btn = page.locator('div[role="button"]:has-text("Most relevant")').first
        if sort_btn.count() > 0:
            print("Clicking Sort button...")
            sort_btn.click()
            page.wait_for_timeout(2000)
            new_posts_item = page.locator('div[role="menuitem"], div[role="menuitemradio"]').filter(has_text='New posts').first
            if new_posts_item.count() > 0:
                print('Selecting "New posts"...')
                new_posts_item.click()
                page.wait_for_timeout(5000)

        # Expand comments if possible
        print("Expanding comments...")
        comment_buttons = page.locator('div[role="button"]').filter(has_text=' comments')
        for i in range(min(comment_buttons.count(), 3)):
            try:
                comment_buttons.nth(i).click()
                page.wait_for_timeout(1000)
            except:
                pass
        
        # Walk the feed until it stops changing or reaches the safety limit.
        print("Walking feed progressively to load posts and comments...")
        posts = []
        previous_signature = None
        stable_passes = 0
        walk_termination = "safety_limit"
        scroll_count = 0
        for pass_number in range(MAX_SCROLLS + 1):
            raw_items = extract_feed_items(page)
            posts = []
            for item in raw_items[:MAX_ITEMS]:
                posts.append({
                    "author": clean_author(item.get("author", "")),
                    "author_source": item.get("author_source", "missing"),
                    "author_status": item.get("author_status", "missing"),
                    "content": item.get("content", "").strip(),
                    "is_comment": item.get("type") == "comment",
                    "display_url": item.get("url", "").strip(),
                    "canonical_url": get_canonical_url(item.get("url", ""))
                })

            signature = hashlib.sha256(
                "\n".join(
                    f"{item['is_comment']}|{item['canonical_url']}|{item['author']}|{item['content']}"
                    for item in posts
                ).encode("utf-8")
            ).hexdigest()
            if signature == previous_signature:
                stable_passes += 1
            else:
                stable_passes = 0
            previous_signature = signature

            if len(raw_items) >= MAX_ITEMS:
                walk_termination = "item_limit"
                break
            if stable_passes >= STABLE_PASSES:
                walk_termination = "stable_boundary"
                break
            if pass_number == MAX_SCROLLS:
                break

            page.evaluate("window.scrollBy(0, Math.max(window.innerHeight * 0.8, 800))")
            page.wait_for_timeout(1500)
            scroll_count += 1

        item_count = len(posts)
        print(f"Found {item_count} items (posts and comments); walk ended at {walk_termination} after {scroll_count} scrolls.")

        # Take screenshot for debugging if no posts found
        if not posts:
            screenshot_path = "/home/will/pops/tmp/fb_group_error.png"
            page.screenshot(path=screenshot_path)
            print(f"Debug screenshot saved to {screenshot_path}")

        context.close()

    if not posts:
        print("No items found. Facebook page layout might have changed or feed failed to load.")
        state["runs"].append({
            "started_at": run_started_at,
            "started_epoch": run_started_epoch,
            "finished_at": utc_now(),
            "status": "no_items",
            "discovered_count": item_count,
            "parsed_count": 0,
            "new_item_count": 0,
            "delivered_count": 0,
            "state_migrated": state_migrated,
            "scroll_count": scroll_count,
            "walk_termination": walk_termination,
        })
        state["runs"][-1]["pruned"] = prune_state(state, run_started_epoch)
        save_state(STATE_FILE, state)
        sys.exit(1)

    print(f"Successfully extracted {len(posts)} items.")

    notification_ids = state["notification_ids"]
    new_item_count = 0
    delivered_count = 0
    eligible_count = 0
    invalid_item_count = 0
    validation_counts = {}
    health_examples = []

    new_items_found = False
    
    # Process from oldest to newest if we want to notify in order, but we grabbed them top-down (newest first).
    # Reversing the list so we process older items first if they are on the page.
    for post in reversed(posts):
        old_hash = hashlib.md5((post["author"] + post["content"]).encode('utf-8')).hexdigest()
        failures = get_validation_failures(post)
        canonical_url = post.get("canonical_url", "")
        unique_id = canonical_url if not failures else f"candidate:{old_hash}"

        seen_at = utc_now()
        validation_status = "eligible" if not failures else "incomplete"
        for reason in failures:
            validation_counts[reason] = validation_counts.get(reason, 0) + 1
        if failures:
            invalid_item_count += 1
            if len(health_examples) < 5:
                health_examples.append({
                    "type": "comment" if post["is_comment"] else "post",
                    "author": post.get("author", "Unknown Author"),
                    "failures": failures,
                    "url": post.get("display_url", "")
                })
        else:
            eligible_count += 1

        existing_item = state["items"].get(unique_id, {})
        item_record = {
            "identity": unique_id,
            "url": post.get("display_url", ""),
            "canonical_url": canonical_url,
            "author": post.get("author", ""),
            "author_source": post.get("author_source", "missing"),
            "content_fingerprint": old_hash,
            "type": "comment" if post["is_comment"] else "post",
            "first_seen_at": existing_item.get("first_seen_at", seen_at),
            "last_seen_at": seen_at,
            "validation_status": validation_status,
            "validation_failures": failures,
            "notified_at": existing_item.get("notified_at"),
        }
        state["items"][unique_id] = item_record
        if not existing_item:
            new_item_count += 1

        if not failures and unique_id not in notification_ids and old_hash not in notification_ids:
            print(f"New {'comment' if post['is_comment'] else 'post'} detected by {post['author']}!")
            subject = f"EPSC FB {'Comment' if post['is_comment'] else 'Post'}: {post['author']}"
            msg_body = f"Author: {post['author']}\n\n{post['content']}"
            msg_body += f"\n\nLink: {post['display_url']}"
            if notify_via_email(subject, msg_body):
                item_record["notified_at"] = utc_now()
                notification_ids.append(unique_id)
                delivered_count += 1
                new_items_found = True

    health_alert_sent = False
    if invalid_item_count:
        examples = "\n".join(
            f"- {example['type']} by {example['author']}: {', '.join(example['failures'])}"
            + (f" ({example['url']})" if example["url"] else "")
            for example in health_examples
        )
        health_body = (
            f"Run observed {invalid_item_count} incomplete Facebook item(s) out of {len(posts)}.\n"
            f"Normal notifications suppressed for these items.\n\n"
            f"Failure counts: {json.dumps(validation_counts, sort_keys=True)}\n\n"
            f"Examples:\n{examples}"
        )
        health_alert_sent = notify_via_email(
            "EPSC Facebook Scraper: Data quality warning", health_body
        )

    if not new_items_found:
        print("No new posts/comments detected.")

    state["runs"].append({
        "started_at": run_started_at,
        "started_epoch": run_started_epoch,
        "finished_at": utc_now(),
        "status": "complete",
        "discovered_count": item_count,
        "parsed_count": len(posts),
        "new_item_count": new_item_count,
        "delivered_count": delivered_count,
        "eligible_count": eligible_count,
        "invalid_item_count": invalid_item_count,
        "validation_counts": validation_counts,
        "health_alert_sent": health_alert_sent,
        "state_migrated": state_migrated,
        "scroll_count": scroll_count,
        "walk_termination": walk_termination,
    })
    state["runs"][-1]["pruned"] = prune_state(state, run_started_epoch)
    save_state(STATE_FILE, state)

if __name__ == "__main__":
    main()
