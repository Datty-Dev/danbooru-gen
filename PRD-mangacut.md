# Product Requirements Document
## MangaCut — Scene-Based Video Assembler

**Version:** 1.0  
**Status:** Draft

---

## 1. Overview

### 1.1 What We Are Building

A video assembly tool that takes natural language scene descriptions + images and produces manga-style videos with configurable transitions, text overlays, and audio. The tool is operated through Arbalest (AI agent) in Discord — the user describes what they want in plain English, and Arbalest interprets, assembles, and returns the video.

### 1.2 Problem Statement

We can generate individual anime panels via ComfyUI but have no way to stitch them into compelling video sequences. Manga and webtoon storytelling relies on rhythm — the "beat beat beat" of panels hitting in sequence with the right transitions. Currently this is a manual ffmpeg/Pillow process that requires technical input. The user should just describe scenes naturally and get a video back.

### 1.3 Goals

- Accept natural language scene descriptions + images
- Support multiple transition types selectable per scene
- Optional text overlays (speech bubbles, subtitles, title cards)
- Optional audio (user-provided or ComfyUI-generated)
- Output vertical (default) or horizontal video
- Return video in Discord, with cloud upload as future option
- Be extensible for new transitions, effects, and output formats

---

## 2. Input Format

### 2.1 Natural Language Interface

The user describes scenes in plain English. Examples:

> "Make a video with these 3 images. Close-up of Tzubaki crying for 2 seconds, then whip-pan to him screaming at the moon, hold for 3 seconds, then slow fade to the wide cliff shot."

> "Here are 4 panels. Hard cut between each, 1.5 seconds per panel. Add a speech bubble on panel 2 saying 'No!' and put this audio track over the whole thing."

> "Vertical video, 6 scenes, cross-dissolve between all of them, 2 seconds each, title card at the start saying 'Chapter 1'"

### 2.2 What Arbalest Parses From NL

From each natural language request, Arbalest extracts:
- **Scene list** — ordered list of images with duration per scene
- **Transition type** — between each pair of scenes (defaults to hard cut if not specified)
- **Text overlays** — speech bubbles, subtitles, title cards with position and content
- **Audio** — background music, per-scene sound effects
- **Orientation** — vertical (default) or horizontal
- **Global settings** — fps, total duration, letterbox bars, etc.

---

## 3. Transitions

### 3.1 Transition Library

| Transition | Description | Use Case |
|---|---|---|
| **hard_cut** | Instant switch, no effect | Default, fast-paced action |
| **whip_pan** | Horizontal smear + motion blur + scale punch + white flash | Dynamic action, manga "beat" rhythm |
| **fade_black** | Fade current scene to black, then fade in next | Emotional pauses, scene changes |
| **cross_dissolve** | Gradual blend from one scene to the next | Dreamy, passage of time |
| **zoom_in** | Zoom into current scene, cut to next | Focus on detail, intensity |
| **zoom_out** | Zoom out from current scene, cut to next | Revealing context |
| **slide_left** | Slide current scene left, next slides in from right | Sequential storytelling |
| **slide_right** | Slide current scene right, next slides in from left | Reverse direction |
| **slide_up** | Slide current up, next slides in from bottom | Vertical webtoon scroll feel |
| **slide_down** | Slide current down, next from top | Reverse scroll |
| **screen_shake** | Shake + flash on impact, then reveal next scene | Impact, explosions, dramatic reveals |
| **glitch** | Digital glitch effect (color split, offset, noise) | Cyberpunk, tech, malfunction |
| **whip_tilt** | Vertical whip-pan (smear up/down) | Vertical emphasis |
| **page_turn** | Simulated page curl/turn | Comic book feel |

### 3.2 Transition Parameters

Each transition has configurable parameters:
- **duration** — how long the transition takes (frames or seconds, default varies per type)
- **intensity** — blur amount, shake strength, zoom level (per transition type)
- **easing** — linear, ease-in, ease-out, ease-in-out

### 3.3 Per-Scene Transition Assignment

The user specifies transitions in natural language between scenes:
- "whip-pan to next" → whip_pan between scene N and N+1
- "slow fade" → fade_black with longer duration
- "just cut" → hard_cut
- Arbalest infers sensible defaults if not specified (e.g. action scenes default to whip_pan, emotional scenes default to fade_black)

---

## 4. Text Overlays

### 4.1 Speech Bubbles

- White rounded rectangle with black border
- Small tail/triangle pointing toward the speaking character
- Position: top-left, top-right, top-center, bottom-left, bottom-right, bottom-center
- Font: bold sans-serif, configurable size
- Added as a post-processing overlay on the scene image

### 4.2 Subtitles

- Centered text at bottom of frame
- Semi-transparent black background bar
- White text, configurable font size
- Can span full scene duration or specify start/end time

### 4.3 Title Cards

- Full-screen overlay, typically before first scene or between acts
- Large centered text on black or blurred background
- Configurable font, size, color, animation (fade in/out, typewriter, etc.)
- Duration specified by user or defaults to 2 seconds

### 4.4 Implementation

All text overlays rendered with Pillow (PIL):
- Font: DejaVu Sans Bold (bundled) or user-specified
- Bubble shapes drawn with ImageDraw
- Anti-aliased rendering
- All overlays are optional — scenes work without them

---

## 5. Audio

### 5.1 Audio Sources

- **User-provided** — mp3/wav files attached in Discord or referenced by path
- **ComfyUI-generated** — future: audio generation workflows
- **Per-scene** — different audio per scene, or one track for the whole video
- **Sound effects** — per-transition sounds (whoosh for whip-pan, boom for screen_shake)

### 5.2 Audio Mixing

- Background music at configurable volume (default 80%)
- Sound effects layered on top at configurable volume (default 100%)
- Fade in/out on music at start/end (default 0.5s fade)
- If audio is shorter than video, loop or pad with silence
- If audio is longer than video, truncate to video length

### 5.3 V1 Scope

V1: User provides audio file(s). Arbalest mixes them into the video. No auto-generation of audio.

---

## 6. Output

### 6.1 Video Formats

| Orientation | Resolution | Aspect | Default FPS |
|---|---|---|---|
| **vertical** (default) | 1080×1920 | 9:16 | 30 |
| **horizontal** | 1920×1080 | 16:9 | 30 |

### 6.2 Encoding

- Codec: H.264 (libx264)
- Quality: CRF 18 (high quality)
- Preset: slow (better compression)
- Pixel format: yuv420p (max compatibility)
- Container: MP4

### 6.3 Delivery

V1: Return video file in Discord channel.
Future: Upload to cloud storage (S3, R2, etc.), return link.

---

## 7. Scene Configuration Schema

Internal representation parsed from natural language:

```json
{
  "orientation": "vertical",
  "fps": 30,
  "scenes": [
    {
      "image": "path/to/panel1.png",
      "duration": 2.0,
      "transition_in": "fade_black",
      "transition_duration": 0.5,
      "text_overlays": [
        {
          "type": "speech_bubble",
          "text": "I won't forgive you!",
          "position": "top-right"
        }
      ]
    },
    {
      "image": "path/to/panel2.png",
      "duration": 1.5,
      "transition_in": "whip_pan",
      "transition_duration": 0.27,
      "text_overlays": []
    },
    {
      "image": "path/to/panel3.png",
      "duration": 3.0,
      "transition_in": "cross_dissolve",
      "transition_duration": 0.8,
      "text_overlays": [
        {
          "type": "subtitle",
          "text": "And so he disappeared into the night.",
          "start": 0.5,
          "end": 2.5
        }
      ]
    }
  ],
  "title_card": {
    "text": "Chapter 1: The Fall",
    "duration": 2.0,
    "animation": "fade"
  },
  "audio": {
    "background": "path/to/music.mp3",
    "volume": 0.8,
    "fade_in": 0.5,
    "fade_out": 0.5
  }
}
```

---

## 8. System Architecture

### 8.1 Components

1. **NL Parser (Arbalest)** — Interprets natural language into scene config JSON. This is Arbalest's brain, not code.

2. **Transition Engine** — Python module that renders transition frames between scenes using Pillow. Each transition is a function that takes (scene_a, scene_b, progress, params) → frame.

3. **Text Overlay Engine** — Python module for rendering speech bubbles, subtitles, title cards onto frames.

4. **Audio Mixer** — Uses ffmpeg to mix background audio and sound effects into the final video.

5. **Video Renderer** — Orchestrates frame generation + ffmpeg encoding into final MP4.

6. **CLI Tool (`mangacut.py`)** — Takes scene config JSON, runs the pipeline, outputs MP4.

### 8.2 Pipeline

```
Natural Language → Arbalest parses → Scene Config JSON
                                          ↓
                                    Transition Engine → Frame Sequence
                                          ↓
                                    Text Overlay Engine → Annotated Frames
                                          ↓
                                    ffmpeg → Raw MP4
                                          ↓
                                    Audio Mixer → Final MP4
                                          ↓
                                    Send in Discord
```

### 8.3 Directory Structure

```
danbooru/
  video/
    mangacut.py              # Main CLI tool
    transitions.py           # All transition effects
    text_overlays.py         # Speech bubbles, subtitles, title cards
    audio_mixer.py           # Audio mixing
    renderer.py              # Frame generation + ffmpeg encoding
    fonts/                   # Bundled fonts
    sfx/                     # Bundled transition sound effects
    output/                  # Generated videos
```

---

## 9. Transition Effect Specifications

### 9.1 hard_cut
- **Frames:** 1
- **Effect:** Instant switch. No processing.
- **Parameters:** none

### 9.2 whip_pan
- **Frames:** 8 (configurable)
- **Effect:**
  1. Current scene slides out horizontally with increasing motion blur
  2. White flash on impact (frames 0-2, opacity 0.7→0)
  3. Next scene slams in from opposite side with scale punch (1.08→1.0)
  4. Motion blur decreases as scene settles
- **Parameters:** direction (left/right), blur_intensity (default 20), scale_punch (default 1.08)

### 9.3 fade_black
- **Frames:** 15 (configurable)
- **Effect:** Current scene fades to black (opacity 1→0), then black fades to next scene (opacity 0→1)
- **Parameters:** duration

### 9.4 cross_dissolve
- **Frames:** 15 (configurable)
- **Effect:** Both scenes visible simultaneously, current fades out while next fades in
- **Parameters:** duration

### 9.5 zoom_in
- **Frames:** 12 (configurable)
- **Effect:** Current scene zooms in 2x, slight blur increases, hard cut to next scene
- **Parameters:** zoom_factor (default 2.0), blur (default 10)

### 9.6 zoom_out
- **Frames:** 12 (configurable)
- **Effect:** Next scene starts zoomed in 2x with blur, rapidly zooms out to normal
- **Parameters:** zoom_factor (default 2.0), blur (default 10)

### 9.7 slide_left / slide_right / slide_up / slide_down
- **Frames:** 10 (configurable)
- **Effect:** Current scene slides out in direction, next slides in from opposite. Slight motion blur during movement.
- **Parameters:** direction, blur (default 5)

### 9.8 screen_shake
- **Frames:** 8 (configurable)
- **Effect:**
  1. Current scene shakes violently (random x/y offset ±20px)
  2. White flash on frame 2-3
  3. Hard cut to next scene
- **Parameters:** shake_intensity (default 20), flash_opacity (default 0.8)

### 9.9 glitch
- **Frames:** 10 (configurable)
- **Effect:**
  1. RGB channel split (offset red/blue channels)
  2. Random horizontal slice displacement
  3. Noise/static overlay
  4. Abrupt cut to next scene
- **Parameters:** slice_count (default 8), offset (default 15)

### 9.10 page_turn
- **Frames:** 15 (configurable)
- **Effect:** Current scene appears to curl/peel away revealing next scene underneath. Implemented as a wipe with a curved edge and shadow.
- **Parameters:** curl_size (default 0.3)

---

## 10. Implementation Steps

### Step 1 — Transition Engine
- Implement all 14 transitions as functions in `transitions.py`
- Each transition: (img_a, img_b, progress, params) → PIL Image
- Progress is 0.0 to 1.0
- Unit test each transition renders correctly

### Step 2 — Text Overlay Engine
- Speech bubble renderer with tail and position
- Subtitle renderer with background bar
- Title card renderer with fade animation
- Font bundling

### Step 3 — Video Renderer
- Frame generation pipeline: scenes → transition frames → hold frames → overlay frames
- ffmpeg encoding to MP4
- Support vertical and horizontal output

### Step 4 — Audio Mixer
- Mix background audio into video using ffmpeg
- Per-transition sound effects
- Volume control, fade in/out

### Step 5 — CLI Tool
- `mangacut.py` takes scene config JSON
- Orchestrates transition engine → text overlays → renderer → audio mixer
- Returns path to final MP4

### Step 6 — Integration with Arbalest
- Document tool usage in TOOLS.md
- Arbalest parses NL → generates scene config JSON → runs mangacut.py → returns video in Discord

---

## 11. Out of Scope for V1

- Auto-generating audio/music
- Cloud upload
- Real-time preview
- GUI/web interface
- Video effects beyond transitions (color grading, speed ramping)
- Animation of character poses within a scene
- Multiple audio tracks with complex mixing
- Subtitle import from SRT/ASS files

---

## 12. Future Considerations (V2+)

- Cloud upload (S3, R2, Cloudflare Stream)
- AI-generated music/sound effects via ComfyUI
- Ken Burns effect (pan + zoom within a scene)
- Scene-to-scene color grading consistency
- Batch video generation from script files
- Video templates (save transition + timing configs as presets)
- Animated text (typewriter effect, text bounce)
- Parallax layers (foreground/background separation)
- Integration with the danbooru tag pipeline for end-to-end: describe scenes → generate images → assemble video
