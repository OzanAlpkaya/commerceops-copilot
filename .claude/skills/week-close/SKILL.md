---
name: week-close
description: Closes the current CommerceOps Copilot week. Runs make check, verifies every Definition of Done item with evidence instead of trusting the checkboxes, writes a draft retro into PROGRESS.md, updates the README status, and marks the week's PR ready for review without merging it.
disable-model-invocation: true
---

# /week-close

1. **Read the context.** `PROGRESS.md` (the current week is the last week
   section), the same week in `docs/ROADMAP.md`, and `README.md`. Confirm you
   are on that week's branch; if not, stop and say which branch to switch to.

2. **Run `make check`.** If it fails, report the failures and stop. A week does
   not close on a red build.

3. **Verify each Definition of Done item with evidence.** Do not trust the
   checkboxes. For every item, find proof in the repo: the file exists and has
   real content, the command runs, the test passes, the endpoint answers.
   Report a table: item, verified (yes / no / needs user), evidence.
   - Items that cannot be checked from the repo (a demo video, a recording)
     are `needs user`: ask for the link and wait.
   - If any item is `no`, list what remains and stop. Never tick an item
     without evidence.

4. **Write the retro draft.** In the week's section of `PROGRESS.md`:
   - Set `Status: Done` and tick the verified items.
   - Add a `### Retro` section with four short headings: what went well, what
     did not, decisions made (link to `docs/decisions/` where they exist),
     carried over to next week. Draft it from `git log` on this branch and the
     week's `### Notes`, and mark it `Draft — Ozan to edit`.
   - Add an `Interview prep` line to the retro and ask the user what they did.

5. **Update the README.** Set the `Status:` line to what is now done and what
   comes next, and link this week's new documents.

6. **Commit and push** with `docs: close week N`.

7. **Prepare the PR, do not merge it.** Run `gh pr ready`. Then tell the user to
   review the PR and merge it themselves, and show the command:
   `gh pr merge --squash --delete-branch`. Never merge, and never enable
   auto-merge.

8. **Remind the week's client deliverables** from `docs/ROADMAP.md` (documents,
   demo video) that the user still has to share or polish.
