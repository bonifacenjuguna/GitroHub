# Versioning Policy

GitroHub follows [Semantic Versioning](https://semver.org) (`MAJOR.MINOR.PATCH`)
and [Keep a Changelog](https://keepachangelog.com) for release notes. This
document exists so version bumps never happen ad-hoc or inconsistently
across `package.json`, `CHANGELOG.md`, and git tags.

## The rule: one command, every time

**Never manually edit the version number in `package.json`.** Always use:

```bash
npm run release:patch -- "Fix ZIP wrapper detection edge case"
npm run release:minor -- "Add Gists support"
npm run release:major -- "Change callback_data scheme for repo actions"
```

(The `--` is required — it's how npm passes your description through to the
underlying script instead of treating it as an npm flag.)

This single command:

1. Bumps `package.json`'s `version` field — the source of truth every other
   surface reads from (`/version`, `/about`, `ℹ️ About GitroHub` screen).
2. Inserts a new dated entry at the top of `CHANGELOG.md` in the correct
   category (`Added` for minor, `Fixed` for patch, `Changed` for major).
3. Prints the exact `git commit` / `git tag` / `git push` commands to run
   next — it does **not** commit or tag automatically, so you always review
   the changelog entry before it becomes permanent history.

Nothing else needs to be touched. There is no second file with a hardcoded
version number anywhere in this project — `/version`, `/health`, and the
About screen all `require('../../../package.json')` at runtime.

## Choosing patch / minor / major

| Type | When |
|---|---|
| **patch** | Bug fixes, security patches, no new features, no behavior changes a user would notice as "new" |
| **minor** | New features, new menus, new commands — anything additive and backward-compatible |
| **major** | Breaking changes: database schema changes requiring migration, `callback_data` scheme changes that would break an in-flight session, removing a feature entirely |

When unsure between two levels, round up — it costs nothing and avoids
understating a change's impact.

## Git tags

Every release gets a tag in the form `v1.2.3` (note the `v` prefix — this
matches GitHub's own auto-suggested tag format and keeps `git tag --list`
sorted correctly). The bump script prints the exact tag command; just
run what it gives you.

## Exporting a versioned zip

If you need a standalone distributable archive (rather than deploying
straight from git), generate it **after** bumping the version and
committing:

```bash
npm run export:zip
```

This reads the version from `package.json` and writes
`dist/gitrohub-v<version>.zip` — the filename is always derived from the
actual version, never typed by hand, so it's impossible for a zip's name
to say `v1.0.0` while the code inside is actually `v1.0.1`. `node_modules/`,
`.git/`, `.env`, and any previous `dist/` output are excluded automatically.
`dist/` itself is gitignored — exported zips are build artifacts, not
something to commit.

## Why no auto-commit

The script deliberately stops short of running `git commit`/`git tag`
itself. A changelog entry nobody reviewed before it became permanent
history isn't actually documentation — it's just noise. Reviewing the
generated entry (and editing it if the auto-generated single line doesn't
capture everything worth mentioning) is a 10-second step that keeps
`CHANGELOG.md` genuinely useful months later.
