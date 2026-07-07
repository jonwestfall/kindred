# Example literary characters

Kindred includes importable public-domain examples under
[`data/examples/literary/`](../data/examples/literary/). They are meant for
testing richer character cards plus lore/fact-pack retrieval.

Included examples:

- Elizabeth Bennet from Jane Austen's *Pride and Prejudice*
- Captain Nemo from Jules Verne's *Twenty Thousand Leagues Under the Seas*
- Scheherazade from the frame tradition of *One Thousand and One Nights*

The examples are paraphrased character adaptations and fact packs. They do not
quote long source passages.

## Import them

1. Sign in as the administrator.
2. Open **Characters**.
3. Click **Import JSON** and choose
   `data/examples/literary/characters.json`.
4. Open **Lore**.
5. Import each matching fact pack:
   - `data/examples/literary/elizabeth-bennet-facts.json`
   - `data/examples/literary/captain-nemo-facts.json`
   - `data/examples/literary/scheherazade-facts.json`
6. In **Lore**, select each character and assign the matching fact pack.

The examples use local Ollama defaults, so they should run on the same local
model setup as the seed characters.

## Why they are separate files

Character cards describe persona and chat behavior. Fact packs describe
retrievable lore. Keeping them separate lets you swap or expand lore without
editing the character's core identity.
