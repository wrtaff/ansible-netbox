#!/usr/bin/env python3
"""Create and report Kill the Newsletter! feeds without browser automation.

The KTN web application accepts normal form submissions when the request
includes its client-side CSRF header. Re-run with --feed-id after recording a
created ID so a provisioning workflow never creates a duplicate feed.
"""

import argparse
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_KTN_URL = "https://ynh2.van-bee.ts.net/kill-the-newsletter/"
FEED_ID_PATTERN = re.compile(r"^[a-z0-9]+$")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Return KTN's creation redirect so its feed ID can be inspected."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def normalize_base_url(url):
    return url.rstrip("/") + "/"


def feed_url(base_url, feed_id):
    parsed = urllib.parse.urlsplit(base_url)
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, f"/feeds/{feed_id}.xml", "", "")
    )


def print_feed(base_url, feed_id):
    print(f"Feed ID: {feed_id}")
    print(f"Feed URL: {feed_url(base_url, feed_id)}")
    print(f"Gmail label: ktn/{feed_id}")


def verify_service(base_url, timeout):
    request = urllib.request.Request(base_url, headers={"Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")

    if 'action="/feeds"' not in body:
        raise RuntimeError("KTN feed creation form was not found at the configured URL")


def create_feed(base_url, title, timeout):
    payload = urllib.parse.urlencode({"title": title}).encode("utf-8")
    endpoint = urllib.parse.urljoin(base_url, "feeds")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "Accept": "text/html",
            "Content-Type": "application/x-www-form-urlencoded",
            "CSRF-Protection": "true",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(NoRedirect())

    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as error:
        response = error

    location = response.headers.get("Location")
    if response.code not in (302, 303) or not location:
        body = response.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"KTN did not return a feed-creation redirect (HTTP {response.code}): {body}"
        )

    match = re.search(r"/feeds/([a-z0-9]+)(?:/|$)", location)
    if not match:
        raise RuntimeError(f"Could not extract a feed ID from KTN redirect: {location}")
    return match.group(1)


def main():
    parser = argparse.ArgumentParser(
        description="Create a Kill the Newsletter! feed and print its routing details."
    )
    parser.add_argument("--title", help="Title for a new feed")
    parser.add_argument(
        "--feed-id",
        help="An already-created ID; prints its routing details without creating a feed",
    )
    parser.add_argument("--url", default=DEFAULT_KTN_URL, help="KTN web UI URL")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify the KTN form is reachable without creating a feed",
    )
    args = parser.parse_args()

    if args.feed_id and args.title:
        parser.error("--title and --feed-id cannot be used together")
    if not args.feed_id and not args.title and not args.dry_run:
        parser.error("provide --title to create a feed or --feed-id to report an existing feed")
    if args.feed_id and not FEED_ID_PATTERN.fullmatch(args.feed_id):
        parser.error("--feed-id must contain only lowercase letters and digits")

    base_url = normalize_base_url(args.url)
    try:
        if args.dry_run:
            verify_service(base_url, args.timeout)
            print(f"KTN creation form verified: {base_url}")
            return

        if args.feed_id:
            print_feed(base_url, args.feed_id)
            return

        verify_service(base_url, args.timeout)
        print_feed(base_url, create_feed(base_url, args.title, args.timeout))
    except (RuntimeError, urllib.error.URLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
