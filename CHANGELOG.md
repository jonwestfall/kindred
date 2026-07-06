# Changelog

All notable changes to Kindred are documented here. The project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses semantic
versioning once the first release is tagged.

## [Unreleased]

### Added

- Initial repository structure and product design direction.
- FastAPI API with SQLite character, thread, message, settings, daemon-state,
  usage, and push-subscription persistence.
- Ollama, llama.cpp, and opt-in OpenAI-compatible chat adapters.
- Autonomous scheduling with quiet hours, cooldowns, and global rate limits.
- WebSocket events, optional Web Push delivery, avatar uploads, searchable logs,
  Markdown/JSON export, cloud budgets, and dry-run image-provider scaffolding.
- Backend tests for character CRUD, message logging, rate limiting, and daemon
  scheduling.
- Responsive React/Vite client with SMS-style chat, character editing,
  recent-conversation and all-activity views, settings, local backend status,
  cloud warnings, and notification permission flow.
- Service worker and WebSocket live-event fallback for character messages.
- Deterministic Ollama-shaped test server plus desktop/mobile Playwright
  end-to-end coverage for the complete MVP flow.
- Multi-stage ARM64-compatible Docker deployment, development/production/smoke
  scripts, VAPID key generation, and complete macOS/Raspberry Pi documentation.
- Preflight cloud spend checks that reject a request before it would cross the
  configured ceiling.
