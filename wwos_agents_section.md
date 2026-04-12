### WWOS (`wwos/server.py`)
Wraps existing WWOS scripts. Provides tools for fetching, creating, and updating wiki pages on Will's World of Stuff (WWOS).

| Tool | Purpose |
|---|---|
| `wwos_ping` | Connectivity check |
| `wwos_get_page` | Fetch raw wikitext of a page |
| `wwos_create_page` | Create a new page with categories and summary |
| `wwos_update_page` | Update an existing page with full content and summary |
| `wwos_list_categories` | List all available categories |
| `wwos_get_category_members` | List all pages in a category |
| `wwos_get_category_info` | Get description/content of a Category page |
| `wwos_generate_citation` | Generate a WWOS-style citation |
| `wwos_import_from_wikipedia` | Scrape Wikipedia and create a WWOS page |

*   **Auth**: `WWOS_PASSWORD`, `WWOS_USER` (default: `will`). Fallback to `~/.bashrc`.
*   **Integration**: Direct access to MediaWiki via `scripts/` wrappers.
