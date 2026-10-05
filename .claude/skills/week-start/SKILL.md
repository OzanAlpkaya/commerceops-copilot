---
name: week-start
description: Starts the next CommerceOps Copilot week. Reads PROGRESS.md and docs/ROADMAP.md, refuses to advance while the current week has unchecked Definition of Done items, creates the week branch and a draft PR, copies the week's Definition of Done into PROGRESS.md, and drafts an implementation plan for approval before any code is written.
disable-model-invocation: true
---

# /week-start

1. **Read the context.** `CLAUDE.md`, `PROGRESS.md`, `docs/ROADMAP.md` and
   `docs/01-discovery.md`. The week sections in `PROGRESS.md` carry a
   `Status:` line (`In progress` or `Done`).

2. **Enforce the gate.** Find the current week: the last week section in
   `PROGRESS.md`.
   - If its status is not `Done` and any Definition of Done item is unchecked,
     do not start a new week. Report exactly which items remain, name the branch
     to resume on, and stop.
   - If every item is checked but the status is not `Done`, tell the user to run
     `/week-close` first, and stop.

3. **Check the working tree.** `git status --porcelain` must be empty. If it is
   not, list the uncommitted files and stop. Otherwise run
   `git switch main && git pull` so the new branch starts from the merged
   previous week.

4. **If all four weeks are Done**, do not start anything. Point to the
   "Project Definition of Done" in `docs/ROADMAP.md` and check it item by item
   instead.

5. **Open the week.** For the next week in `docs/ROADMAP.md`:
   - Create the branch named in that week's section and push it.
   - Add a section to `PROGRESS.md`: the week title, `Status: In progress`,
     `Branch: <name>`, the Definition of Done copied verbatim from
     `docs/ROADMAP.md`, and an empty `### Notes` heading.
   - Commit with `docs: start week N` and push.
   - Open a draft PR:
     `gh pr create --draft --base main --title "Week N: <title>"`, with the
     week's goal sentence and its Definition of Done as the body.

6. **Draft the implementation plan.** Cover:
   - Tasks grouped by day over six days (about 30 hours in total), each marked
     with its owner from the Ownership table in `docs/ROADMAP.md`:
     `Claude Code` or `Ozan`.
   - For Ozan-owned tasks: what he should build and the concepts or docs to read
     first. Do not write that code.
   - Files and packages to add or change, and any new dependencies.
   - Test strategy for the week: what is unit-tested, what needs the database or
     the mock API, and what goes into the eval set.
   - Which Definition of Done item each task closes.
   - Anything ambiguous or missing in the roadmap or the discovery summary that
     needs a decision.

7. **Post the plan and stop.** Do not write any code until the user approves the
   plan. This follows the plan-before-code rule in `CLAUDE.md`.
