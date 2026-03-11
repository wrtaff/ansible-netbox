---
name: wikipedia-scraper
description: Scrapes Wikipedia articles (first paragraph only) to create WWOS MediaWiki pages. Use when the user requests to "make me a page like the wikipedia page" or "scrape wikipedia" for a specific title. Always checks for existing pages first.
---

# Wikipedia Scraper

This skill automates the process of importing the first paragraph of a Wikipedia article into the WWOS MediaWiki, including categories, a citation, and the `{{baseOfPage}}` template.

## Workflow

1. **Check for Existing Page**: Before scraping, always check if a page with the same title already exists on WWOS.
2. **Scrape Wikipedia**: Fetch the article from Wikipedia.
   - Extract ONLY the first paragraph of text.
   - Extract all relevant categories (filtering out maintenance/hidden categories).
3. **Format Content**:
   - Start with the title in bold: `'''Title'''`.
   - Append the first paragraph.
   - Add a citation in bookmarklet style: `<ref>URL retrieved YYYY-MM-DD</ref>`.
   - Insert `{{baseOfPage}}` above the categories.
   - Add Wikipedia-extracted categories and any user-specified categories.
4. **Create Page**: Submit the formatted content to WWOS.

## Usage

Use the provided `wikipedia_to_wwos.py` script to perform the scrape and creation.

```bash
python3 scripts/wikipedia_to_wwos.py "https://en.wikipedia.org/wiki/Article_Title" "Optional, Additional, Categories"
```

The script will:
- Check for existing pages.
- Handle authentication (using `WWOS_PASSWORD` from environment or `~/.bashrc`).
- Format the content as required.
- Provide feedback on success or failure.

## Troubleshooting

- **Existing Page**: If the script alerts that the page already exists, inform the user and skip creation unless they explicitly ask to overwrite (though current script defaults to skipping).
- **Authentication**: Ensure `WWOS_PASSWORD` is set in `~/.bashrc` as `export WWOS_PASSWORD='...'`.
