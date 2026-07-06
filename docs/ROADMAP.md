# Roadmap

## MVP — implemented

- Local SQLite character CRUD and duplication
- SMS-style responsive chat and multiple threads
- Ollama and llama.cpp adapters
- Optional OpenAI-compatible adapter with dry run and budgets
- Autonomous daemon with quiet hours, cooldowns, randomness, and global limits
- WebSocket live updates, service worker, and optional Web Push
- Searchable local activity and Markdown/JSON export
- Backend, smoke, and desktop/mobile end-to-end tests
- macOS and Raspberry Pi deployment paths
- Dry-run image-provider interface placeholder

## 0.2 — hardening

- Versioned SQLite migrations and backup/restore UI
- Authentication suitable for trusted-LAN multi-device access
- CSRF protection for subscription and mutation endpoints
- Atomic cloud-budget reservation for concurrent requests
- Streaming model responses with cancellation
- Notification subscription management and delivery diagnostics
- Daemon run history and next-window explanation in the UI
- Per-character thread rename, archive, and deletion controls
- Keyboard, screen-reader, contrast, and motion accessibility audit

## 0.3 — richer writing and research

- Character/world-note collections with local document retrieval
- Source citations and a research mode separating evidence from invention
- Import/export of portable character cards
- Configurable summarization for long threads
- Local embeddings adapter
- Side-by-side writer notebook and conversation
- Live image-provider adapters behind the existing metered interface

## Later

- Optional external worker for multi-process scheduling
- Multi-user profiles and encrypted-at-rest data
- Progressive Web App offline shell and queued sending
- Additional local runtimes and provider-specific cloud adapters
- Plugin hooks with explicit permissions

## Non-goals for this MVP

- Public internet hosting without a reverse proxy and authentication
- Claims that a character is sentient or a real person
- Storage or display of hidden chain-of-thought
- Bundling model files in the repository or application image
- Making a cloud account necessary for core chat

