# Install on Raspberry Pi 400 / Raspberry Pi 4

Use a 64-bit Raspberry Pi OS or Debian installation. A Pi 4/400 is CPU- and
memory-constrained: start with a 0.5B–1.5B instruction model quantized to 4 bits,
a 1024–2048 token context, and one active generation at a time.

## Hardware recommendations

- 4 GB RAM: 0.5B–1.5B Q4 model; keep context near 1024.
- 8 GB RAM: 1B–3B Q4 model; begin with context 2048.
- Active cooling and a reliable power supply.
- SSD storage is preferable to microSD for model files and database durability.

These are starting points, not guarantees. Architecture, quantization, context,
and vocabulary all affect memory.

## Docker installation

Docker's Debian packages support ARM64. Follow the current
[official Debian instructions](https://docs.docker.com/engine/install/debian/)
rather than piping an unreviewed installer into a shell.

```bash
git clone <your-kindred-repository-url>
cd kindred
cp .env.example .env
docker compose -f docker/compose.yml up -d --build
docker compose -f docker/compose.yml logs -f kindred
```

Open `http://PI_ADDRESS:8000` from a trusted LAN device. Compose maps host model
ports through `host.docker.internal` and stores app data in a named volume.

## Install Ollama on ARM64

Ollama publishes an ARM64 package and service instructions in its
[official Linux guide](https://docs.ollama.com/linux):

```bash
curl -fsSL https://ollama.com/download/ollama-linux-arm64.tar.zst \
  | sudo tar x -C /usr
ollama serve
```

In another shell:

```bash
ollama pull llama3.2:1b
curl http://127.0.0.1:11434/api/tags
```

Review remote scripts and package URLs before running them. For a systemd
service and upgrades, follow Ollama's current documentation.

## llama.cpp alternative

llama.cpp is often the more tunable Pi option. Its official server exposes the
OpenAI-compatible endpoint Kindred uses:

```bash
sudo apt update
sudo apt install -y git cmake build-essential
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j2 --target llama-server
./build/bin/llama-server \
  -m /absolute/path/to/small-instruct-q4.gguf \
  -c 1024 -t 4 --host 127.0.0.1 --port 8080
```

The upstream [llama.cpp README](https://github.com/ggml-org/llama.cpp) documents
current build and model-loading options. Set a character's backend to
`llamacpp`.

## Non-Docker installation

```bash
sudo apt install -y python3 python3-venv nodejs npm
python3 -m venv .venv
.venv/bin/pip install -e './backend[notifications]'
cd frontend && npm ci && npm run build && cd ..
./scripts/start.sh
```

If the Pi's Node version is too old for Vite, build `frontend/dist` on a Mac and
copy that generated directory to the Pi before starting Uvicorn.

## Resource tuning

- Use initiative 0.25–1 message/day and longer cooldowns.
- Set `KINDRED_DAEMON_INTERVAL_SECONDS=300`; probability accounts for elapsed
  time, so slower checks still work.
- Keep one Kindred process. Do not add Uvicorn workers while the in-process
  daemon is enabled.
- Reduce model context before using swap. Swap is much slower and increases
  storage wear.

## LAN and HTTPS

The MVP has no authentication. Firewall port 8000 to the trusted LAN only.
Browser notifications on `http://PI_ADDRESS:8000` are normally blocked because
LAN IPs are not secure contexts. See [Notifications](NOTIFICATIONS.md).

