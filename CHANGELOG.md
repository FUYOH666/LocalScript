# Changelog

Notable changes to this project are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

The pre–public-release changelog granularity was **not carried over** to this root commit; if you need the old narrative, use a **local backup** or any private clone that still had the previous `main`.

## [Unreleased]

### Changed

- **Git history on GitHub** was replaced with a single public root commit (no prior private-era commit objects on `main`).
- Public documentation and navigation reduced; see [README.md](README.md) and [docs/README.md](docs/README.md).
- Operator-specific GPU/SSH notes are **not** committed: keep a private copy as `stands/REMOTE_GPU.md` (see [.gitignore](.gitignore)). A neutral template is [stands/REMOTE_GPU.example.md](stands/REMOTE_GPU.example.md).

## [0.2.34]

### Added

- Optional `GITLAB_BASE_URL` / `GITLAB_TOKEN` comments in [`.env.example`](.env.example) for local tooling only.
