# Contributing to aw-tauri

Thanks for your interest in contributing to aw-tauri! This guide covers the development workflow.

## Getting started

1. Fork and clone the repository:
   ```sh
   git clone --recursive https://github.com/YOUR_USERNAME/aw-tauri.git
   cd aw-tauri
   ```

2. Install prerequisites:
   - [Tauri v2 prerequisites](https://v2.tauri.app/start/prerequisites/) for your platform
   - [Node.js](https://nodejs.org/)
   - [Rust](https://rustup.rs/) (stable toolchain)

3. Build and run:
   ```sh
   npm install
   make dev
   ```

## Code style

- **Rust**: Format with `cargo fmt`, lint with `cargo clippy -- -D warnings`
- **Commits**: Use [Conventional Commits](https://www.conventionalcommits.org/) format (`feat:`, `fix:`, `refactor:`, `docs:`, `ci:`, `chore:`)

Run `make precommit` before submitting to check formatting and lints.

## Project structure

All Rust source lives in `src-tauri/src/`:

| File | Responsibility |
|------|---------------|
| `main.rs` | Entry point (4 lines — just calls `lib::run()`) |
| `lib.rs` | Application setup: Tauri builder, embedded server, tray icon, config, window management |
| `manager.rs` | Module process manager: discovery, start/stop, crash recovery, tray menu updates |
| `dirs.rs` | Platform-specific paths for config, data, logs, runtime |
| `logging.rs` | Log configuration with `fern`, rotation at 32 MB |

The aw-webui frontend is a git submodule at `aw-webui/`, built separately and served via WebView.

## Submitting changes

1. Create a branch from `master`
2. Make your changes
3. Run `make precommit` to verify formatting and lints
4. Run `cd src-tauri && cargo test` to run tests
5. Submit a pull request against `master`

## Areas where help is wanted

- Test coverage (currently minimal — `dirs.rs` only)
- Mobile support (Android/iOS via Tauri mobile)
- Documentation improvements
- Accessibility of the tray menu and dashboard
