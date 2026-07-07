# Install on macOS Apple Silicon

These steps target an M-series Mac and keep the model server outside Kindred so
it can be upgraded or replaced independently.

## 1. Prerequisites

Install Python 3.11+, Node 22+, Git, and Ollama. Homebrew is convenient:

```bash
brew install python@3.12 node git ollama
```

Use a Python version between 3.11 and 3.14. Kindred's tested code has no native
runtime extension beyond optional Web Push cryptography wheels.

## 2. Install Kindred

```bash
git clone <your-kindred-repository-url>
cd kindred
cp .env.example .env
# Edit KINDRED_ADMIN_PASSWORD and KINDRED_SESSION_SECRET in .env.
python3 -m venv .venv
.venv/bin/pip install -e './backend[dev,notifications]'
cd frontend
npm install
cd ..
```

The `.env` file is ignored by Git. Keep API keys and VAPID configuration there.

## 3. Start a local model

Ollama is the simplest default:

```bash
ollama pull llama3.2:1b
ollama serve
```

On macOS, the Ollama app may already run the service. Verify it:

```bash
curl http://127.0.0.1:11434/api/tags
```

Alternatively:

```bash
brew install llama.cpp
llama-server -m /absolute/path/to/model.gguf -c 2048 --port 8080
```

Then set the character backend to `llamacpp`. See
[Local models](LOCAL_MODELS.md).

## 4. Run

Development with reload:

```bash
./scripts/dev.sh
```

- Web client: `http://127.0.0.1:5173`
- API docs: `http://127.0.0.1:${KINDRED_PORT:-8000}/docs`

Sign in with `KINDRED_ADMIN_USERNAME` and `KINDRED_ADMIN_PASSWORD` from `.env`.

To use another backend port, set `KINDRED_PORT` in `.env` before running
`./scripts/dev.sh` or `./scripts/start.sh`:

```dotenv
KINDRED_PORT=8081
```

The development web server remains on `5173`; its `/api` proxy follows
`KINDRED_PORT`. Development mode binds the API to `127.0.0.1` by default; set
`KINDRED_DEV_HOST=0.0.0.0` only if you intentionally want other devices to reach
the reload server.

Production-style static serving:

```bash
./scripts/start.sh
```

Open `http://127.0.0.1:8000`.

## Docker alternative

Install Docker Desktop, then:

```bash
docker compose -f docker/compose.yml up --build
```

If Ollama runs on the Mac host, Compose reaches it through
`host.docker.internal`.

See [Docker Compose examples](DOCKER_COMPOSE.md) for VAPID, custom-domain, and
Tailscale Serve examples.

## Verification

```bash
./scripts/test.sh
python3 scripts/smoke_test.py http://127.0.0.1:8000
```

Open System in Kindred. Ollama or llama.cpp should show Available. If neither
does, check `.env`, the provider port, and macOS firewall prompts.

`http://localhost` is accepted as a secure context by modern browsers for
development, but another device opening your Mac's LAN IP needs HTTPS for
service workers and Web Push. Follow [Notifications](NOTIFICATIONS.md).
