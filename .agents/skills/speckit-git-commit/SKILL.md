---
name: speckit-git-commit
description: Prepare feature-scoped commits subject to Miner Alerts manual Git authorization
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: git:commands/speckit.git.commit.md
---

# Prepare Authorized Commits

## Miner Alerts project override

AGENTS.md and the constitution require manual, feature-scoped Git publication.
An automatic hook or skill invocation does not grant commit/push authorization.
Prepare and validate the concrete change first; execute Git publication only when
the user has explicitly authorized that feature's commit/push. Otherwise preserve
the reviewable work and report publication as pending. Never stage config/state.
Documentation-only edits do not require a service restart or hardware checks.

Prepare a reviewable, feature-scoped change after a Spec Kit command. A hook
may request preparation, but only explicit project authorization permits publication.

## Behavior

1. Identify the feature, event and concrete changed files.
2. Review diff, secrets, validation and authorization scope before staging.
3. Preserve unrelated work and all private config/state files outside the commit.
4. If publication is not authorized, leave the validated result reviewable and report Git as pending.
5. When authorized, stage explicit feature paths and use a reviewed message; push only within its authorized scope.

## Legacy extension interface

The repository still contains auto-commit scripts and an auto_commit configuration
section. Their existence or an enabled event is not project authorization. The legacy
scripts stage the complete worktree using git add .; do not invoke them against a
mixed checkout. Use explicit feature-scoped staging under the manual project policy.
No executable script or hook configuration was changed during documentation normalization.

Script locations for maintenance reference:

- Bash: `.specify/extensions/git/scripts/bash/auto-commit.sh <event_name>`.
- PowerShell: `.specify/extensions/git/scripts/powershell/auto-commit.ps1 <event_name>`.
- Configuration: `.specify/extensions/git/git-config.yml`.

Missing Git/configuration, no changes, or incomplete validation must result in an
explicit pending/skipped outcome, never a claim that a commit or push completed.
