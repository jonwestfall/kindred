# Lore and fact packs

Kindred supports lightweight retrieval augmented generation through local lore files, also called fact packs. A fact pack is a JSON file of small, source-aware facts that can be assigned to one or more characters.

The default retrieval engine is local and dependency-free: Kindred searches assigned facts with a simple lexical scorer, injects the top matches into the character prompt, and logs how many facts were used in the message audit summary. It does not require embeddings, a vector database, or a cloud service.

Kindred can also use an optional semantic embedding store. When enabled, it calls a local Ollama embedding model, caches fact vectors in SQLite, ranks facts by cosine similarity, and falls back to lexical retrieval if embeddings are unavailable.

## When to use fact packs

Use a fact pack for information that should ground a character without bloating the character card:

- setting lore
- relationship facts
- chronology
- recurring objects or locations
- character-specific canon details
- worldbuilding rules
- project notes that should only apply to certain characters

Character cards should describe the persona. Fact packs should describe retrievable facts.

## Import flow

1. Sign in as the administrator.
2. Open **Lore**.
3. Click **Import fact pack** and choose a `kindred.fact_pack.v1` JSON file.
4. Choose a character in **Assign to character**.
5. Check the fact packs that character should use.
6. Click **Save lore assignment**.

During chat and daemon messages, the character retrieves only from the packs assigned to that character.

## JSON format

See [fact_pack.schema.json](fact_pack.schema.json) for the machine-readable schema.

```json
{
  "schema": "kindred.fact_pack.v1",
  "name": "Lantern Roads facts",
  "description": "Grounding facts for Ada of the Lantern.",
  "source_title": "Example Field Notes",
  "source_author": "Kindred Tests",
  "source_reference": "notes supplied by the user",
  "facts": [
    {
      "title": "Dusk roads",
      "content": "The lantern roads appear only after sunset and fade at dawn.",
      "keywords": ["lantern", "roads", "dusk"],
      "tags": ["setting"],
      "source_reference": "chapter 2 summary",
      "weight": 1.5
    }
  ]
}
```

`content` should be short and atomic. A good fact answers one likely retrieval need. Prefer 20 smaller facts over one long essay.

## API routes

- `GET /api/lore-packs` lists imported packs.
- `POST /api/lore-packs/import` imports a `kindred.fact_pack.v1` file.
- `GET /api/lore-packs/{pack_id}` returns one pack with facts.
- `GET /api/lore-packs/{pack_id}/export` downloads one portable fact pack.
- `DELETE /api/lore-packs/{pack_id}` deletes a pack.
- `GET /api/characters/{character_id}/lore-packs` returns assigned pack IDs.
- `PUT /api/characters/{character_id}/lore-packs` replaces assigned pack IDs.

All lore-management routes are administrator-only.

## Optional semantic embeddings

Semantic retrieval is useful when user language does not share keywords with the fact file. For example, a query about a "family home" may retrieve a fact about "Eld House" even if the words do not overlap.

The implementation stays local-first:

- embeddings are disabled by default;
- the only MVP provider is local Ollama;
- vectors are cached in SQLite in `lore_fact_embeddings`;
- cached vectors are refreshed when fact text, provider, model, or configured dimensions change;
- chat falls back to lexical retrieval if Ollama embeddings fail.

Example setup using Ollama's small [`all-minilm`](https://ollama.com/library/all-minilm) embedding model:

```bash
ollama pull all-minilm
```

```dotenv
KINDRED_EMBEDDINGS_ENABLED=true
KINDRED_EMBEDDINGS_PROVIDER=ollama
KINDRED_EMBEDDINGS_MODEL=all-minilm
# 0 means "use the model default". Set a positive value only for models that support it.
KINDRED_EMBEDDINGS_DIMENSIONS=0
```

Kindred uses Ollama's [`/api/embed`](https://docs.ollama.com/api/embed) endpoint. The first chat after enabling embeddings may be slower because Kindred lazily embeds the assigned facts for that character. Later chats reuse the SQLite cache.

## LLM prompt for generating a Kindred fact pack

Use this when you want an LLM to produce an importable file directly. Replace the bracketed material with the source notes or a lawful summary. For copyrighted books, provide your own notes/summaries and ask for paraphrased facts rather than copied prose.

```text
You are creating a Kindred fact pack for retrieval augmented generation.

Output valid JSON only. Do not wrap it in Markdown. Do not include comments.

Target schema:
- schema must be "kindred.fact_pack.v1"
- name: short title for this fact pack
- description: one-sentence description of what this pack grounds
- source_title: title of the source or project
- source_author: author/creator if known, otherwise ""
- source_reference: brief provenance note
- facts: 20 to 80 atomic facts unless I ask for a different count

Each fact must have:
- title: short human-readable label
- content: one concise, paraphrased fact useful during character chat
- keywords: 3 to 8 retrieval keywords, including names, locations, objects, and concepts
- tags: 1 to 5 broad labels such as character, relationship, setting, timeline, rule, object, theme
- source_reference: chapter/scene/page/notes reference if available
- weight: 0.5 for background, 1.0 for normal facts, 1.5 to 2.0 for facts central to the character or world

Rules:
- Do not invent facts beyond the source notes I provide.
- If a detail is uncertain, include "Uncertain:" in the content and use a lower weight.
- Do not include long copyrighted passages or distinctive source prose.
- Preserve names and factual relationships accurately.
- Split compound facts into separate items.
- Keep content text-message useful: concise, concrete, and easy for a roleplay model to use.
- Avoid spoilers unless I explicitly allow them.

Source/project:
[paste title, author, public-domain status if known, and spoiler policy]

Character or world focus:
[paste which character(s), location(s), period, or world areas this pack should support]

Source notes or summary to transform:
[paste your notes, outline, chapter summaries, or public-domain text excerpt]
```

## Practical limitations

- Lexical retrieval remains the safe fallback. Include obvious keywords and aliases even when embeddings are enabled.
- Semantic retrieval currently supports Ollama only. Cloud embeddings are deliberately not wired into the MVP because lore retrieval should remain local by default.
- Facts are sent to whichever backend the character uses. If a character is configured for a cloud backend, retrieved facts are included in that cloud prompt.
- Fact packs are local SQLite records after import. Export them when you want backups or tradeable files.
