# PRD: Scene Creation Pipeline Skill

## Summary
A standardized workflow that converts a natural language scene description into a finished manga-style video, using the Danbooru tag generation pipeline + ComfyUI image generation + MangaCut video assembly. This PRD defines the flow so it can be converted into an OpenClaw skill later.

## Problem
Creating manga-style videos from text descriptions requires multiple coordinated steps: tag assembly, image generation, bubble placement, transition selection, and video rendering. Currently this is done ad-hoc with manual config writing. We need a repeatable, skill-driven flow.

## User Persona
Datty (or any user) describes what they want in natural language. Arbalest handles everything else.

## Trigger
User says any of: "let's make a new scene", "new scene", "create a scene", "make a manga"

## The Interview
When triggered, Arbalest asks these questions in order:

1. **What's the scene about?** — Brief story/summary of what happens
2. **Which characters?** — Name existing characters or describe new ones (appearance, outfit, personality)
3. **How many panels?** — Number of panels/shots (default: 3)
4. **Any dialogue?** — Speech bubbles, narration, subtitles per panel (or "none")
5. **Mood/vibe?** — Action, emotional, dramatic, comedic, calm (affects transitions + pacing)
6. **Orientation?** — Vertical (default) or horizontal

Arbalest may ask follow-up questions if answers are ambiguous (e.g., "what's Tzubaki wearing in this scene?").

After the interview, Arbalest summarizes the plan for confirmation before proceeding.

## Folder Structure
Each scene project gets its own folder:

```
danbooru/scenes/<scene-name>/
├── scene.json          # Full config (interview answers + generated tags + transitions)
├── images/             # Generated images (upscaled)
│   ├── panel_01.png
│   ├── panel_02.png
│   └── panel_03.png
├── video/              # Rendered outputs
│   ├── raw.mp4         # Video without audio
│   └── final.mp4       # Video with audio (when audio added)
├── audio/              # BGM + SFX (optional)
│   ├── bgm.mp3
│   └── sfx/
└── notes.md            # Arbalest's notes (continuity refs, tag decisions, etc.)
```

Scene name is auto-generated from the description (e.g., `tzubaki-bamboo-training`).

## Scene Index
A lightweight JSON manifest (`scenes/scenes_index.json`) tracks all scenes — kept locally even after cloud upload.

```json
{
  "name": "tzubaki-bamboo-training",
  "created": "2026-04-05",
  "description": "Tzubaki training in bamboo forest...",
  "characters": ["Tzubaki"],
  "panels": 3,
  "mood": "action",
  "cloud_path": "gdrive:danbooru-scenes/tzubaki-bamboo-training",
  "cloud_uploaded": "2026-04-05",
  "local_exists": false,
  "tags_used": { ... }
}
```

This lets us:
- Delete local files to save space
- Still know what scenes exist and where to find them
- Re-download from cloud if needed (`rclone copy gdrive:danbooru-scenes/<name> scenes/<name>`)
- Browse/search scenes without cloud access

## Cloud Storage
- After rendering, upload scene folder to Google Drive via `rclone`
- Update `scenes_index.json`: set `cloud_uploaded` date, `local_exists` to false after cleanup
- Config: set Google Drive remote name in TOOLS.md
- Local cache in `danbooru/video/.cache/generated/` for re-use across scenes

## The Flow

### Phase 1: Scene Breakdown
**Input:** Interview answers
**Output:** Array of scene objects with descriptions

Steps:
1. Parse interview answers into discrete scenes (panels/shots)
2. Identify character(s), their consistent features, outfit, setting
3. Determine scene order and logical progression
4. Decide per-scene: action, emotion, camera angle, background
5. Map mood to transition types and pacing

Example:
```
Interview: "Tzubaki crying on a cliff at sunset, then screaming at the sky, then walking away along a river"
           Mood: emotional | Panels: 3 | Dialogue: "Why did you leave me..." / "CHURROOOO!!!" / narration

→ Panel 1: Tzubaki, sad, crying, standing on cliff edge, sunset, close-up
→ Panel 2: Tzubaki, screaming, mouth open, arms raised, cliff edge, sunset, wide shot
→ Panel 3: Tzubaki, back to viewer, walking along riverbank, dusk, full body
```

**Continuity rules:**
- Extract character tags ONCE, repeat in every scene prompt
- Character tags: gender, hair color, hair style, eye color, body type, outfit
- Setting tags: repeat shared background elements (outdoors, time of day, etc.)
- Only change: expression, pose, action, camera angle, scene-specific details

### Phase 2: Tag Assembly
**Input:** Scene descriptions from Phase 1
**Output:** Validated Danbooru tag prompts per scene

Steps:
1. For each scene, run RAG retrieval to find relevant Danbooru tags
   - `python3 rag_pipeline.py "<natural language description>"`
   - Returns categorized tags: hair_color, hair_style, eyes, expression, clothing, pose, etc.
2. Arbalest selects the right tags from RAG results based on:
   - Scene description intent
   - Character continuity (must match Phase 1 character tags)
   - Tag order convention (see below)
3. Add quality/trigger tags:
   - Model-specific quality tags (e.g., `masterpiece, best quality, absurdres` for WAI)
   - Character trigger word (e.g., `Tzubaki`)
   - LoRA activation if applicable
4. Validate all tags against WDv3:
   - `python3 generate.py "x" --validate "<comma separated tags>"`
   - Remove or replace any INVALID tags
   - Whitelisted tags bypass validation (masterpiece, best quality, etc.)
5. Assemble final prompt in tag order:

**Tag Order (mandatory):**
```
character count → solo → trigger → hair color → hair style → eye color → 
expression → body type → clothing → accessories → pose → viewpoint → 
action → background → lighting → quality
```

Example assembled prompt:
```
1boy, solo, Tzubaki, black hair, messy hair, red eyes, sharp eyes, 
determined, chinese clothes, black robe, 5 buttons, sword, holding weapon, 
katana, jumping, full body, bamboo forest, outdoors, sunset, golden hour, 
motion lines, masterpiece, best quality, absurdres
```

### Phase 3: Image Generation
**Input:** Validated tag prompts from Phase 2
**Output:** Generated images (upscaled) per scene

Steps:
1. Check ComfyUI is running (`curl http://192.168.0.176:8188/system_stats`)
2. For each scene, generate image via ComfyUI:
   - Image cached in `video/.cache/generated/` (hash of prompt)
   - Same prompt = same image (no regeneration)
   - Copy final upscaled image to `scenes/<name>/images/panel_XX.png`
3. Confirm all images generated before proceeding

**ComfyUI workflow notes:**
- Workflow: `workflows/tzubaki-wai-upscale.json`
- Always use upscaled output (node 20:18)
- LoRA: Tzubaki at 0.9 strength
- Resolution: 1080×1920 (vertical) or 1920×1080 (horizontal)
- Negative prompt: model-specific (stored in generate.py configs)

### Phase 4: Bubble & Overlay Placement
**Input:** Generated images + dialogue from interview
**Output:** Text overlay configs with coordinates

Steps:
1. For each panel with dialogue:
   a. Load the generated image
   b. Use image analysis model to detect mouth position:
      ```
      image(model, image_path, "Where is the character's mouth? Give x,y pixel coords. Image is {width}x{height}.")
      ```
   c. Calculate bubble position: offset from mouth (+150px horizontal, -50px vertical)
   d. Choose tail direction based on bubble position relative to face
   e. If detection fails → fall back to named positions or ask user for coords
2. For narration/subtitles: always bottom-center
3. Save overlay config to scene.json

### Phase 5: Video Assembly
**Input:** scene.json with images + transitions + overlays
**Output:** Final MP4 video

Steps:
1. Assemble MangaCut config from scene.json
2. Choose transitions based on mood:
   - **Action**: whip_pan, screen_shake, glitch (fast: 1.0-1.5s per panel)
   - **Emotional**: cross_dissolve, fade_black (slower: 2.0-3.0s)
   - **Dramatic**: fade_black, flash (varied pacing)
   - **Comedic**: hard_cut, slide (snappy: 1.0-2.0s)
   - **Calm**: cross_dissolve (slow: 2.5-4.0s)
3. Run MangaCut:
   ```bash
   python3 video/mangacut.py --config scene.json --output video/raw.mp4
   ```
4. Send video to user for review
5. Save to `scenes/<name>/video/raw.mp4`

### Phase 6: Audio (Future)
**Input:** Video + optional audio config
**Output:** Video with mixed audio

- SFX auto-selected based on transitions
- BGM user-provided or generated
- Mix via audio_mixer.py

### Phase 7: Cloud Upload
**Input:** Completed scene folder
**Output:** Uploaded to Google Drive

Steps:
1. Run `rclone copy scenes/<name> gdrive:danbooru-scenes/<name>`
2. Confirm upload
3. Optionally clean local copy (keep cached images only)

## Configuration Reference

### Supported Models
| Model | Quality Tags | Notes |
|-------|-------------|-------|
| WAI Illustrious | masterpiece, best quality, absurdres | Default, best for anime |
| Pony Diffusion | score_9, score_8_up, score_7_up, source_anime | Different quality scale |
| NetaYume/Lumina2 | highres | Simpler tags |
| Flux | (TBD) | Newer model |

### Supported Transitions
hard_cut, cross_dissolve, fade_black, fade_white, whip_pan, slide_left, slide_right, slide_up, slide_down, zoom_in, zoom_out, screen_shake, flash, glitch

### Orientation
- `vertical` (default): 1080×1920 — TikTok/Reels/webtoon
- `horizontal`: 1920×1080 — YouTube/widescreen

## Error Handling
- **ComfyUI down**: Alert user, ask them to restart
- **Invalid tags**: Remove invalid, replace with closest valid alternative
- **Face detection fails**: Fall back to named positions
- **Image generation timeout**: Retry once, then alert user
- **Cache hit**: Skip generation, use cached image

## Success Criteria
- [ ] "New scene" triggers the interview
- [ ] Interview collects all needed info
- [ ] Scene folder created with proper structure
- [ ] Character consistency across all panels
- [ ] All tags validated before generation
- [ ] Speech bubbles near character mouths
- [ ] Transitions match mood
- [ ] No manual config editing required by user
- [ ] Video delivered to user
- [ ] Cloud upload works
- [ ] Works as a repeatable skill
