# Model recommendations

These are practical starting points for Kindred’s local-first chat use case. They assume Ollama-compatible names where available, but the same size guidance applies to llama.cpp GGUF models.

Always test on your actual hardware. Model file size is not the full memory requirement: context length, KV cache, quantization, operating-system overhead, and concurrent users all matter.

## Quick picks

| Hardware class | Fastest | Best experience | Notes |
| --- | --- | --- | --- |
| Powerful Apple Silicon / GPU workstation | `qwen3:8b` or `gemma3:12b` | `qwen3:30b` / `qwen3:32b` or `gemma3:27b` | Best for richer style, longer context, and multiple characters if memory allows. |
| Less powerful laptop / mini PC | `llama3.2:3b` or `qwen3:4b` | `gemma3:4b`, `phi4-mini`, or `qwen3:8b` | Good default range for 16 GB machines. Lower context if you see swapping. |
| Raspberry Pi 4 / 400 | `gemma3:270m` or `qwen3:0.6b` | `gemma3:1b`, `llama3.2:1b`, or `qwen3:1.7b` | CPU-only generation will be slow. Prefer small quantized models and short context. |

## Powerful hardware

Use these when you have a higher-memory MacBook Pro, Mac Studio, or a GPU workstation.

- Fastest: `qwen3:8b`
  - Official Ollama listing shows Qwen3 8B around 5.2 GB with a 40K context option.
  - It is a good balance for lively chat without jumping straight to huge models.
- Best experience: `qwen3:30b`, `qwen3:32b`, or `gemma3:27b`
  - Qwen3 30B/32B listings are around 19 to 20 GB.
  - Gemma 3 27B is listed around 17 GB with a 128K context option.
  - These are better for nuanced roleplay, stronger instruction following, and larger lore windows, but they are not Pi targets.

## Less powerful hardware

Use these for base Apple Silicon laptops, compact desktops, or older machines.

- Fastest: `llama3.2:3b` or `qwen3:4b`
  - Llama 3.2 3B is listed around 2 GB with 128K context.
  - Qwen3 4B is listed around 2.5 GB.
- Best experience: `gemma3:4b`, `phi4-mini`, or `qwen3:8b`
  - Gemma 3 4B is listed around 3.3 GB.
  - Phi-4-mini is a 3.8B model listed around 2.5 GB with a 128K context window and is positioned for constrained or latency-bound environments.
  - Qwen3 8B is a stronger option if the machine can keep it in memory without swapping.

## Raspberry Pi 4 / Raspberry Pi 400

Be conservative. The Pi can run local models, but the experience is more “small local companion” than “desktop-class assistant.”

- Fastest: `gemma3:270m` or `qwen3:0.6b`
  - Gemma 3 270M is listed around 292 MB.
  - Qwen3 0.6B is listed around 523 MB.
- Best Pi-class experience: `gemma3:1b`, `llama3.2:1b`, or `qwen3:1.7b`
  - Gemma 3 1B is listed around 815 MB.
  - Llama 3.2 1B is listed around 1.3 GB and is described as suitable for edge/local use.
  - Qwen3 1.7B is listed around 1.4 GB.

Suggested Pi settings:

- Use a short context window first, such as 2K to 4K.
- Keep retrieved lore fact limits small.
- Prefer one active user and one active generation at a time.
- If Ollama overhead is too high, use llama.cpp directly with a small Q4 GGUF.
- Avoid cloud fallbacks unless you explicitly configure rate limits and opt the character into cloud mode.

## Retrieval and model choice

Lore/fact packs help small models because they reduce how much the model has to remember. On smaller hardware, prefer:

- more atomic facts
- better keywords and aliases
- shorter chat history windows
- lower fact retrieval limits

For a Pi character, a 1B model plus a focused fact pack can feel better than a 3B model with no grounding and too much prompt context.

## Sources checked

- [Ollama Qwen3 library](https://ollama.com/library/qwen3)
- [Ollama Gemma 3 library](https://ollama.com/library/gemma3)
- [Ollama Llama 3.2 library](https://ollama.com/library/llama3.2)
- [Ollama Phi-4-mini library](https://ollama.com/library/phi4-mini)
