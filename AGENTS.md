# AGENTS.md

This repository keeps its Codex workflow files under version control.

## Repo-local skill

- Primary skill: `ai/skills/reputation-snapshot-workflow/SKILL.md`
- Install or refresh it into Codex with `scripts/install-codex-skills.ps1`
- Restart Codex after installation so the new skill is discovered

## Expectations

- Keep Mercari parsing deterministic where practical
- Preserve proof and verification contracts unless the task explicitly changes them
- Update fixture-backed tests together with parser changes
- Note live-capture assumptions and skipped checks clearly
