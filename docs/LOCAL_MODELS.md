# Local models

Kindred defaults to local inference and never downloads a model itself. Run one
of the supported servers, then choose its backend and model in the character
editor.

For current fastest/best-experience picks by hardware class, see
[Model recommendations](MODEL_RECOMMENDATIONS.md).

## Ollama

Kindred calls `POST {OLLAMA_BASE_URL}/api/chat`.

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:1b
```

```bash
ollama pull llama3.2:1b
ollama serve
```

The character's model field is sent as Ollama's model name. The global
`OLLAMA_MODEL` is used only if that field is empty.

## Optional Ollama embeddings

Kindred can use Ollama's [`/api/embed`](https://docs.ollama.com/api/embed)
endpoint for semantic lore/fact-pack retrieval. This is off by default and only
affects lore retrieval; chat generation still uses the character's selected
backend/model.

```bash
ollama pull all-minilm
```

```dotenv
KINDRED_EMBEDDINGS_ENABLED=true
KINDRED_EMBEDDINGS_PROVIDER=ollama
KINDRED_EMBEDDINGS_MODEL=all-minilm
KINDRED_EMBEDDINGS_DIMENSIONS=0
```

The [`all-minilm`](https://ollama.com/library/all-minilm) model is small enough
to be a practical default for local embedding experiments. Kindred stores fact
vectors in SQLite and falls back to lexical retrieval if embeddings are
unavailable. On Raspberry Pi hardware, keep fact packs focused because first-use
indexing is CPU work.

## llama.cpp

llama.cpp describes Apple Silicon as a first-class target and provides a
lightweight OpenAI-compatible server. See the
[upstream project](https://github.com/ggml-org/llama.cpp) and
[server documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).

```bash
llama-server \
  -m /absolute/path/to/model.gguf \
  --alias kindred-local \
  -c 2048 \
  --port 8080
```

Kindred calls `POST {LLAMACPP_BASE_URL}/v1/chat/completions`.

```dotenv
LLAMACPP_BASE_URL=http://127.0.0.1:8080
```

Set the character backend to `llamacpp` and model to `kindred-local`.

## Choosing a model for Raspberry Pi 4/400

Approximate weight-only sizes for Q4 quantization are:

| Parameter count | Weight file starting range | Pi guidance |
| --- | ---: | --- |
| 0.5B | 0.35–0.5 GB | Comfortable starting point on 4 GB |
| 1B–1.5B | 0.7–1.2 GB | Default MVP range |
| 3B | 1.8–2.5 GB | Prefer an 8 GB Pi and shorter context |
| 7B+ | 4+ GB | Not recommended for this MVP target |

Runtime memory is higher than file size because of KV cache, working buffers,
the OS, and Kindred. Context length can matter as much as model size. Use a Q4
instruction/chat GGUF, context 1024 or 2048, and one generation at a time.
Measure your actual model rather than treating the table as a guarantee.

## Character quality on tiny models

Small models benefit from concrete, compact profiles:

- one or two sentences each for personality and speaking style;
- only backstory details that affect the current voice;
- explicit goals and boundaries;
- short world notes;
- lower temperature (0.3–0.7) for consistency.

Kindred sends at most the last 20 user/character messages. A long profile
consumes the same limited context needed for conversation.

## Health and failures

The System screen probes Ollama at `/api/tags` and llama.cpp at `/health`. A
healthy process can still fail generation if the model is missing, the chat
template is unsupported, or memory is exhausted. Kindred returns `503` and
preserves the user's message in the local log.

Model files are ignored by Git. Keep them outside this repository and review
each model's license, acceptable-use terms, provenance, and prompt template.
