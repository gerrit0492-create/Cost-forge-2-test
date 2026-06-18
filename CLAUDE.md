# Project notes

A Streamlit costing tool — the test/staging sibling of `cost-forge-2`. Mirror that
project's conventions unless this repo's code clearly differs.

- For changes spanning several files, make all edits in one commit
- Match the style of the surrounding code — don't introduce new patterns
- Don't refactor or rename things that weren't part of the requested change
- Address the user as **Gerrit** in every suggestion and question
- **Always Excel, never CSV** — all data exports use `.xlsx` via `df_to_excel_bytes()` or `openpyxl`
- **Keep Excel in sync** — when a page gains a new feature or data view, update the corresponding Excel report in the same commit so the download always matches the UI

## Before pushing to git
Before running `git push`, always do the following in order:
1. **Back up**: create a git tag from current HEAD (`git tag backup/pre-<description> HEAD`)
2. **Verify MCP**: confirm GitHub MCP tools are available
3. Once the backup is done and MCP is verified, push

## Security constraints
- Only push to `gerrit0492-create/cost-forge-2-test` — never to `cost-forge-2` or any other repo
- Never force-push or `reset --hard` without explicit user instruction
