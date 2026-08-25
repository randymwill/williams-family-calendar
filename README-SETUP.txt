GitHub Calendar Automation

Upload these files to your repo:

.github/workflows/build-calendar.yml
tools/normalize_ics.py

Then commit them to main and run the workflow once from the Actions tab.

Sports feed subscriptions now live in:

feeds.json

When adding or removing a raw sports feed:
1. Edit feeds.json
2. Run tools/sync_playmetrics.py
3. Commit the updated config plus generated calendar files

If calendar.ics conflicts during rebase or merge, do not hand-merge it.
Rebuild it from the latest main branch instead.
