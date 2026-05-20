---
name: verify-branch
description: Verify the current branch and its base before making code changes — prevents reworking fixes on the wrong parent.
---

# Verify Branch Base

Run these checks and report results **before** any edits:

1. `git branch --show-current` — current branch name
2. `git log --oneline -5` — last 5 commits on this branch
3. `git merge-base HEAD main` — common ancestor with `main`
4. `git log --oneline main..HEAD` — commits unique to this branch (divergence from `main`)

Then state:

- **Current branch:** `<name>`
- **Parent / base:** `<branch>` (e.g. `main`, `feature/inference-eou`)
- **Divergence:** `<N>` commits unique to this branch

If the user mentioned a feature branch in the task (e.g. `feature/inference-eou`, `fix/sarvam`), confirm we are **on** it and **based on** it. If we are on `main` or a different feature branch, **stop and ask** which base branch the work should target — do not assume.
