# Planning: facebook-web MCP Server

This planning document outlines the design, architecture, and testing strategy for the `facebook-web` MCP server. It is structured to ensure that any developer or agent can resume work, run tests, and understand the internal state of the server.

*   **Parent Ticket**: Trac [#3598](http://trac.home.arpa/ticket/3598)
*   **Planning Subticket**: Trac [#3599](http://trac.home.arpa/ticket/3599)
*   **Implementation Subticket**: Trac [#3600](http://trac.home.arpa/ticket/3600)

## 1. Directory Structure

The server and its test suite will reside in the `ansible-netbox` repository under:

```
mcp-servers/facebook-web/
├── server.py               # Main Python FastMCP server script
├── requirements.txt        # Dependencies (playwright, mcp, etc.)
├── planning.md             # This planning & design document
└── tests/
    ├── __init__.py
    ├── test_server.py      # Unit tests with mocks
    └── test_live_dom.py    # Integration tests using the live DOM
```

## 2. Dependencies

The server will require Python 3.10+ and the following packages:
*   `mcp` (or FastMCP library)
*   `playwright`
*   `pytest` (for running the test suite)

## 3. Tool API Specifications

The server will expose the following two tools:

### `get_group_posts`
Retrieves the most recent posts from a Facebook Group.

*   **Arguments**:
    *   `group_url` (str): The full URL of the Facebook group (e.g. `https://www.facebook.com/groups/473971729877417/`).
    *   `limit` (int, optional): Maximum number of posts to return (default: 10).
    *   `scroll_count` (int, optional): Number of slow-scrolling cycles to perform to load older posts (default: 5).
*   **Behavior**:
    1. Launches Chromium using the persistent user profile path `/home/will/.cache/ms-playwright/mcp-chrome-for-testing-f96f1ec`.
    2. Navigates to the group URL.
    3. Finds and clicks the sorting dropdown to select `"New posts"` (ensuring chronological feed sorting).
    4. Performs incremental scrolling (`scroll_count` times) to load older feed items dynamically.
    5. Locates post containers (`div.x1n2onr6.xh8yej3.x1ja2u2z.xod5an3` containing `div[data-ad-comet-preview="message"]`).
    6. For each post, extracts:
        *   **Author**: Text of the first non-empty `<a>` tag link.
        *   **Content**: `innerText` of the message preview element.
        *   **Date**: Hover over the `?__cft__` date link, wait `800ms`, and grab the text of the floating `div[role="tooltip"]`.
    7. Returns a JSON list of posts.

### `get_post_comments`
Retrieves comments for a specific post.

*   **Arguments**:
    *   `post_url` (str): The permalink URL of the Facebook post (optional, if querying directly).
    *   `post_index` (int, optional): If executing inside a loaded feed context, specifies which post index to expand and inspect (default: 0).
*   **Behavior**:
    1. Targets the post container.
    2. Locates any comment elements (`div[role="article"]` inside the container).
    3. If 0 comments are found but a comments count/expander button exists (e.g. "View comments"), clicks it to expand the thread.
    4. Extracts:
        *   **Author**: First link text inside the comment container.
        *   **Text**: Elements with `dir="auto"` that are not descendants of `<a>` tags (using `!el.closest('a')`).
        *   **Date**: The relative timestamp (e.g., `2d`, `6d`, `Yesterday`).
    5. Returns a JSON list of comments.

## 4. Test Plan

To maintain correctness over time as Facebook changes its CSS layout, we implement a two-tiered test suite:

### A. Unit Tests (`tests/test_server.py`)
*   **Purpose**: Test the FastMCP tool registration, argument parsing, and server startup without requiring a live browser or network connection.
*   **Method**: Mock the `playwright.sync_api` browser, context, and page objects. Assert that the server correctly invokes page transitions and clicks the expected mock selectors.

### B. Live DOM Integration Tests (`tests/test_live_dom.py`)
*   **Purpose**: Verify that Facebook's live DOM still matches our selectors (detects layout breakage).
*   **Method**: Run a headless browser using the real persistent user profile. Navigate to the EPSC group and assert:
    *   The feed container exists (`div[role="feed"]`).
    *   At least one post is found with message content (`div[data-ad-comet-preview="message"]`).
    *   The sort dropdown can be located.
    *   A date hover tooltip can be triggered and parsed.
*   **Trigger**: These tests should be run during automated checks or when an agent reports scraper failures.

## 5. Security & Secrets

*   **Secrets**: `None`
*   **Session Management**: The server relies entirely on the persistent browser profile in `/home/will/.cache/ms-playwright/mcp-chrome-for-testing-f96f1ec`. It does not handle passwords, MFA codes, or API tokens.
