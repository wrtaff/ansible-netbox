# WWOS MCP Server

This Model Context Protocol (MCP) server provides tools to interface with Will's World of Stuff (WWOS) MediaWiki instance. It wraps existing Python scripts from the `scripts/` directory.

## Usage

The server requires `WWOS_PASSWORD` to be set in the environment or available in `~/.bashrc`.

### Environment Variables

*   `WWOS_PASSWORD`: The password for the `will` user on MediaWiki.

### Running

```bash
export WWOS_PASSWORD="your_password"
python server.py
```

## Tools

*   `wwos_ping()`: Verify connectivity.
*   `wwos_get_page(page_name)`: Retrieve the raw wikitext of a page.
*   `wwos_create_page(page_name, categories, content, summary)`: Create a new wiki page.
*   `wwos_update_page(page_name, content, summary)`: Update an existing wiki page with full content.
*   `wwos_list_categories()`: List all available categories.
*   `wwos_get_category_members(category_name)`: List all pages in a category.
*   `wwos_get_category_info(category_name)`: Get the description of a category page.
