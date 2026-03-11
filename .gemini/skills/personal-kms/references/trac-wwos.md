# Trac & WWOS Cross-linking

This reference provides the mandatory formatting rules and automated workflows for linking Trac tickets to WWOS MediaWiki pages.

## Mandatory Link Formats

All cross-linking must adhere to these specific formats to match the user's manual bookmarklets:

### To WWOS (Prepended to content)
When adding a Trac ticket link to a WWOS page, **prepend** it to the very top of the page content in this format:
```wikitext
'''[http://trac.gafla.us.com/ticket/<ID> trac #<ID> "<SUMMARY>"]'''
```
- `<ID>`: The numeric Trac ticket ID.
- `<SUMMARY>`: The exact summary string of the Trac ticket.

### To Trac (Added as comment)
When adding a WWOS page link to a Trac ticket, add it as a **new comment** in this format:
```text
'''[http://192.168.0.99/mediawiki/index.php/<PAGE_NAME> "WWOS PAGE: <PAGE_NAME>"]'''
```
- `<PAGE_NAME>`: The exact title/name of the MediaWiki page.

## Core Workflow

To cross-link a Trac ticket and a WWOS page:

1.  **Fetch Trac Info**: Use `trac_get_ticket` to get the summary and ID.
2.  **Fetch WWOS Info**: Use `scripts/get_wwos_page.py` to get the page content and confirm the exact name.
3.  **Update WWOS**:
    - Format the link to Trac as defined above.
    - Prepend the link to the existing content.
    - Use `scripts/update_wwos_page.py --full-content` to push the update.
4.  **Update Trac**:
    - Format the link to WWOS as defined above.
    - Use `trac_update_ticket` to add the link as a comment.

## Edge Cases

- **Page Does Not Exist**: If the WWOS page doesn't exist, use `scripts/create_wwos_page.py` to create it first with a placeholder summary before linking.
- **Multiple Links**: If the WWOS page already has a Trac link at the top, add the new link on its own line above it.
