# CLAUDE.md

This file provides guidance to Claude Code when working with code in this
repository.

## Project Goal

Document the current project goal here in one or two concrete sentences.

## Project Status

- Record the active phase, milestone, or release target
- Keep the current source files and config as the primary source of truth

## Commands

```powershell
# Activate the intended environment if needed
# conda activate your-env

# Run the project's main entry points from the repo root
# python src\main.py
```

## Core Rules

- Start with the problem the user named
- Read the actual code before explaining behavior
- Prefer minimal, reversible changes
- Respect existing file boundaries unless a structural change is required
- Do not remove or rename code without verifying references first

## Validation

- Run the smallest useful check for the code you changed
- Prefer targeted validation before broad end-to-end runs
- Verify the expected environment when commands are environment-sensitive

## Documentation

- Keep docs aligned with the current implementation
- Add comments only where they clarify non-obvious behavior
- Do not rewrite clear code just to add comments

## Push Workflow

- When pushing code, follow this sequence unless the user explicitly asks for a different workflow:
  1. Check the working tree and confirm the intended file set
  2. Review the diff so the pushed scope is explicit
  3. Run the smallest useful validation for the changed code
  4. Choose the next version number using the repo's versioning scheme
  5. Add or update the changelog entry for that version
  6. Update any stale documentation or guidance affected by the change
  7. Stage only the files intended for the push
  8. Create a commit with a versioned, descriptive message
  9. Push the branch and, when the repo uses release tags, create and push the matching tag
