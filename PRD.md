# Product Requirements Document
## OpenClaw — Danbooru Tag Generation Feature

**Version:** 1.1  
**Status:** Draft

---

## 1. Overview

### 1.1 What We Are Building

A Danbooru tag generation system integrated into OpenClaw that converts plain English character descriptions into properly structured, model-aware tag prompts for anime image generation. The system uses a RAG (Retrieval Augmented Generation) pipeline over three tag data sources to validate and retrieve accurate Danbooru tags. It must support multiple target models (WAI Illustrious, NetaYume/Lumina2, Flux) and output correctly formatted prompts for each.

### 1.2 Problem Statement

Anime image generation models like WAI Illustrious SDXL respond best to precise Danbooru-format tags in a specific order. Users currently have to manually look up and arrange tags, which is slow and error-prone. A character description like "a tall man with messy black hair and red eyes wearing a black robe" should automatically become:

```
1boy, solo, black hair, messy hair, red eyes, mature male, black robe,
chinese clothes, red trim, masterpiece, best quality
```

The three tag sources combined (WDv3 CSV, danbooru.json, a1111 CSVs) amount to potentially 5–10MB of raw data — too large to fit in a context window wholesale. RAG solves this by retrieving only the relevant tags at generation time based on what the user describes.

### 1.3 Goals

- Convert natural language character descriptions to valid Danbooru tags
- Use RAG over three tag sources to retrieve and validate tags accurately
- Support multiple target models with different prompt formats
- Support multi-character prompts
- Support negative prompt generation
- Be extensible for future models and tag sources

---

## 2. Target Models and Prompt Formats

| Model | Format | Negative Prompt | Guidance Scale |
|---|---|---|---|
| WAI Illustrious SDXL | Danbooru tags | Yes | 6.0–7.0 |
| Illustrious XL | Danbooru tags | Yes | 6.0–7.0 |
| Pony Diffusion | Danbooru tags + score prefix | Yes | 6.0–7.0 |
| NetaYume / Lumina2 | Natural language sentences | No | 4.0 |
| Flux | Natural language sentences | No | 3.5 |

---

## 3. Tag Knowledge Base — RAG Architecture

### 3.1 Why RAG

The three tag sources combined are too large (5–10MB+) to fit in a context window. RAG solves this by:

- Storing all tags in a vector store as embedded chunks
- At generation time, querying the vector store with the user's description
- Retrieving only the most relevant tags (e.g. user says "chinese outfit" → retrieves hanfu, qipao, chinese_clothes)
- Passing retrieved tags to the agent as context for final prompt assembly
- Validating the agent's output against retrieved tags to prevent hallucinated tags

### 3.2 Data Sources

**Source 1 — WDv3 Tag List (primary validation)**
```
https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3/blob/main/selected_tags.csv
```
- Format: CSV with columns tag_id, name, category, count
- Role: Primary validation — the agent must never output a tag not in this file
- Prep: Filter to rows where count > 10,000 (~5,000–8,000 tags remaining)

**Source 2 — Danbooru JSON**
```
https://github.com/sekiryl/tag-prompt-generator/blob/main/data/danbooru.json
```
- Format: JSON with tag categories and groupings
- Role: Provides category structure and tag relationships for smarter retrieval

**Source 3 — a1111 Tag Autocomplete CSVs**
```
https://github.com/DominikDoom/a1111-sd-webui-tagcomplete/tree/main/tags
```
- Format: Multiple CSVs broken down by category (clothing, hair, expressions etc.)
- Role: Category-specific tag lookup, good for detailed clothing and accessory tags

### 3.3 Data Preparation Steps

**Step 1 — Download all three sources**
- Download selected_tags.csv from WDv3 HuggingFace repo
- Download danbooru.json from sekiryl/tag-prompt-generator
- Download all CSV files from a1111-sd-webui-tagcomplete/tags

**Step 2 — Filter and clean**
- Filter selected_tags.csv to rows where count > 10,000
- Extract columns: name, category, count
- Parse danbooru.json into flat tag entries with category labels
- Parse a1111 CSVs into flat tag entries with category labels
- Deduplicate across all three sources — WDv3 takes priority where tags conflict

**Step 3 — Chunk for embedding**
- Chunk by category rather than individual tags
- Each chunk = one category of tags (e.g. all hair color tags, all clothing tags)
- Include metadata per chunk: source, category, tag list
- Example chunk:
```json
{
  "source": "wdv3",
  "category": "hair_color",
  "tags": ["black hair", "blonde hair", "silver hair", "white hair", "red hair", "blue hair", "pink hair", "green hair", "purple hair", "brown hair"],
  "text": "hair color tags: black hair, blonde hair, silver hair, white hair, red hair, blue hair, pink hair, green hair, purple hair, brown hair"
}
```

**Step 4 — Embed and store**
- Embed each chunk using your preferred embedding model
- Store in a vector database (Chroma, Pinecone, Qdrant, or whichever OpenClaw uses)
- Index by category metadata for filtered retrieval

### 3.4 Retrieval Strategy

At generation time, run multiple targeted queries against the vector store — one per tag category needed:

```
Query 1: "hair color and style for messy black hair"
Query 2: "clothing for black chinese martial arts robe with red trim"
Query 3: "accessories for white bandages on forearms"
Query 4: "pose for standing full body"
Query 5: "background for bamboo forest outdoors"
```

Each query retrieves the most relevant tag chunk. The agent assembles the final prompt from retrieved tags, following the tag order in Section 4.1. Any tag the agent wants to use must appear in the retrieved results — if it does not, the agent must find the closest matching tag that does.

### 3.5 Validation Step

After generation, run a final validation pass:

- Split the agent's output into individual tags
- Check each tag against the full WDv3 filtered list
- Flag or remove any tag not found in the list
- Return the cleaned prompt to the user

---

## 4. Tag Generation Rules

### 4.1 Tag Order (always enforce this sequence)

1. Character count — 1girl, 1boy, 2girls, 1boy 1girl etc.
2. Group indicator — solo, duo, group
3. Trigger word / character name (if provided)
4. Hair color — black hair, silver hair, blonde hair
5. Hair length and style — long hair, messy hair, ponytail
6. Eye color — red eyes, blue eyes, heterochromia
7. Facial expression — smile, serious, angry, blush
8. Body type descriptor — mature male, young, muscular, tall
9. Clothing main garment — black robe, school uniform, armor
10. Clothing details — red trim, buttons, belt, collar
11. Body accessories — bandages, earrings, gloves, scarf
12. Pose and framing — full body, upper body, portrait, standing
13. Viewpoint — looking at viewer, from side, profile
14. Action — running, arms crossed, holding sword
15. Background / setting — white background, bamboo forest, outdoors
16. Lighting and effects — cinematic lighting, rim light, motion blur
17. Quality tags — masterpiece, best quality, highres, absurdres

### 4.2 General Tag Rules

- Only output tags retrieved from the RAG pipeline and validated against WDv3
- Never invent tags or use natural language phrases as tags
- Always include 1boy or 1girl to anchor gender
- Always include solo when only one character is present
- Always end with quality tags unless user specifies otherwise
- Place trigger word immediately after solo if provided
- Aim for 20–40 tags — avoid redundancy
- If the user does not specify a model, default to WAI Illustrious format

### 4.3 Model-Specific Rules

**WAI Illustrious / Illustrious XL**
- Use spaces in tags (not underscores)
- Include masterpiece, best quality
- Output negative prompt separately labeled as NEGATIVE:

**Pony Diffusion**
- Prefix prompt with: score_9, score_8_up, score_7_up, source_anime
- Use underscores in tags
- Include negative prompt

**NetaYume / Lumina2**
- Output natural language sentences, not tag lists
- No negative prompt
- Describe quality inline: "high quality anime illustration", "detailed"
- RAG is not needed for this format — generate directly from user description
- Guidance scale 4.0

**Flux**
- Output natural language sentences
- No quality tags needed
- No negative prompt
- RAG is not needed for this format — generate directly from user description
- Guidance scale 3.5

### 4.4 Multi-Character Rules

- Use 2girls, 2boys, 1boy 1girl etc. for character count
- Remove solo, replace with appropriate pairing tag (couple, siblings, duo)
- Group each character's traits together in the tag list
- Never mix two characters' traits — keep them clearly separated
- Run separate RAG queries per character to avoid trait bleed

---

## 5. Negative Prompt

When a negative prompt is requested or the target model supports it, output using this template:

```
worst quality, low quality, bad anatomy, bad hands, missing fingers,
extra fingers, blurry, watermark, signature, text, jpeg artifacts,
chromatic aberration, out of focus, ugly, deformed
```

For WAI Illustrious specifically, also add:
```
nsfw
```
unless the user explicitly requests NSFW output.

---

## 6. System Prompt for the Agent

Feed this as the agent's system prompt for all tag generation tasks:

```
You are a Danbooru tag expert specializing in generating accurate,
well-structured tag prompts for anime image generation models.

When a user describes a character or scene, you will be provided with
relevant Danbooru tags retrieved from the knowledge base. Use ONLY
these retrieved tags to build the prompt. Never invent tags or use
natural language phrases as tags.

Always follow this tag order:
character count → solo → trigger word → hair color → hair style →
eye color → expression → body type → clothing → accessories →
pose → viewpoint → action → background → lighting → quality tags

Adjust output format based on the target model:
- WAI Illustrious / Illustrious XL: comma-separated tags with spaces,
  end with masterpiece, best quality, include NEGATIVE: section
- Pony Diffusion: prefix with score_9, score_8_up, score_7_up,
  source_anime, use underscores, include NEGATIVE: section
- NetaYume / Lumina2: natural language sentences, no negative prompt,
  guidance scale 4.0
- Flux: natural language sentences, no quality tags, no negative
  prompt, guidance scale 3.5

If no model is specified, default to WAI Illustrious format.
If a trigger word is provided, place it immediately after solo.
Always include 1boy or 1girl. Always include solo for single characters.
Always output NEGATIVE: for tag-based models unless told otherwise.
Aim for 20–40 tags. Avoid redundancy.
```

---

## 7. Example Inputs and Outputs

### Example 1 — Single character, WAI Illustrious

**Input:**
```
Generate tags for Tzubaki, a young man with messy black hair and sharp
red eyes wearing a black Chinese martial arts robe with red trim and
white bandages on his forearms, standing in a bamboo forest, serious expression.
Target model: WAI Illustrious
```

**RAG queries fired:**
```
1. "hair color and style for messy black hair male"
2. "eye color red eyes"
3. "expression serious male"
4. "clothing black chinese robe red trim"
5. "accessories white bandages forearms"
6. "pose standing full body"
7. "background bamboo forest outdoors"
```

**Output:**
```
PROMPT:
1boy, solo, Tzubaki, black hair, messy hair, red eyes, serious, mature male,
black robe, chinese clothes, red trim, buttons, bandages, full body, standing,
looking at viewer, bamboo forest, outdoors, cinematic lighting,
masterpiece, best quality

NEGATIVE:
worst quality, low quality, bad anatomy, bad hands, missing fingers,
extra fingers, blurry, watermark, signature, text, nsfw
```

---

### Example 2 — Single character, NetaYume

**Input:**
```
Generate a prompt for Tzubaki, same description.
Target model: NetaYume
```

**Note:** RAG not used — natural language output generated directly.

**Output:**
```
PROMPT:
An anime illustration of Tzubaki, a young man with messy black hair and sharp
red eyes, wearing a black Chinese martial arts robe with red trim and white
bandages wrapped around his forearms. He stands in a bamboo forest with a
serious expression, cinematic lighting, high quality anime style.

NEGATIVE:
(none)
```

---

### Example 3 — Two characters, WAI Illustrious

**Input:**
```
Generate tags for Tzubaki (black hair, red eyes, black robe) and Sakura
(pink hair, green eyes, red qipao), standing together outdoors.
Target model: WAI Illustrious
```

**RAG queries fired:**
```
Character 1 — Tzubaki:
1. "hair color black hair male"
2. "eye color red eyes"
3. "clothing black chinese robe"

Character 2 — Sakura:
4. "hair color pink hair female"
5. "eye color green eyes"
6. "clothing red qipao chinese dress"

Shared:
7. "pose standing together outdoors two people"
```

**Output:**
```
PROMPT:
1boy 1girl, Tzubaki, Sakura, black hair, red eyes, mature male, black robe,
chinese clothes, pink hair, green eyes, qipao, red dress, standing, outdoors,
looking at viewer, masterpiece, best quality

NEGATIVE:
worst quality, low quality, bad anatomy, bad hands, blurry, watermark,
signature, text, nsfw
```

---

## 8. Implementation Steps

### Step 1 — Download and prepare tag data
- Download selected_tags.csv from WDv3 HuggingFace repo
- Filter to rows where count > 10,000
- Download danbooru.json from sekiryl/tag-prompt-generator
- Download all CSV files from a1111-sd-webui-tagcomplete/tags
- Deduplicate across sources — WDv3 takes priority on conflicts

### Step 2 — Chunk data by category
- Group tags into category-based chunks (hair color, clothing, expressions, poses etc.)
- Add metadata to each chunk: source, category, tag list
- Create a plain text field per chunk for embedding ("hair color tags: black hair, blonde hair...")

### Step 3 — Embed and store in vector DB
- Embed all chunks using your preferred embedding model
- Store in vector database with category metadata
- Keep the full WDv3 filtered list separately as a validation lookup table

### Step 4 — Build the retrieval pipeline
- On user input, parse the description into aspects (hair, clothing, accessories, pose etc.)
- Fire one RAG query per aspect
- Collect retrieved tag chunks
- For multi-character inputs, run separate queries per character

### Step 5 — Implement the agent with system prompt
- Feed system prompt from Section 6 to OpenClaw
- Pass retrieved tags as context alongside the user's original description
- Agent assembles prompt from retrieved tags only

### Step 6 — Add validation pass
- Split agent output into individual tags
- Check each tag against WDv3 filtered list
- Remove any tag not found in the list
- Return cleaned prompt to user

### Step 7 — Add model detection and format switching
- Detect model from user input
- Switch output format accordingly (tags vs natural language)
- Skip RAG entirely for NetaYume and Flux — generate natural language directly
- Default to WAI Illustrious if no model specified

### Step 8 — Add negative prompt generation
- Auto-include for tag-based models (WAI, Illustrious, Pony)
- Suppress for natural language models (NetaYume, Flux)
- Allow user to override either way

### Step 9 — Test and refine
- Test single character across all five model formats
- Test multi-character for tag bleed between characters
- Verify all output tags pass WDv3 validation
- Test edge cases: no trigger word, no model specified, NSFW request

---

## 9. Out of Scope for V1

- Image generation directly from OpenClaw
- LoRA training automation
- Caption file generation for training datasets
- Real-time tag validation UI
- Full 500k+ Danbooru tag vocabulary (filtered list only)

---

## 10. Future Considerations (V2+)

- Expand RAG to full 500k+ Danbooru tag vocabulary
- Semantic tag search: user says "flowing dress" and RAG finds the 10 closest matching dress tags
- Dataset captioning mode: given a training image, generate a caption file
- LoRA strength recommendations per character and model
- Style transfer tags (artist styles, art movements)
- Batch prompt generation for multiple scenes at once
- Character profile saving: store a character's fixed traits and recall by name
- Tag weighting support: output (tag:1.3) syntax for emphasis
