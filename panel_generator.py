#!/usr/bin/env python3
"""Webtoon panel generator.

Generates multiple panels via ComfyUI and stitches them into a vertical strip.
"""
import json
import os
import random
import urllib.request
import time
from PIL import Image, ImageDraw, ImageFont

COMFYUI_URL = "http://192.168.0.176:8188"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
WORKFLOW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflows")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

PANEL_WIDTH = 640
PANEL_HEIGHT = 832
BORDER_SIZE = 4
FONT_SIZE = 28
BUBBLE_PADDING = 12


def load_base_workflow():
    with open(os.path.join(WORKFLOW_DIR, "tzubaki-wai-upscale.json")) as f:
        return json.load(f)


def queue_prompt(workflow):
    payload = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())["prompt_id"]


def wait_for_completion(prompt_id, timeout=180):
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = urllib.request.urlopen(
                urllib.request.Request(f"{COMFYUI_URL}/history/{prompt_id}")
            )
            data = json.loads(resp.read())
            if prompt_id in data:
                status = data[prompt_id].get("status", {})
                if status.get("completed", False):
                    return data[prompt_id]
                if status.get("status_str") == "error":
                    raise RuntimeError(f"ComfyUI error: {data}")
        except urllib.error.URLError:
            pass
        time.sleep(3)
    raise TimeoutError(f"Timed out after {timeout}s")


def get_base_image(result):
    """Get the base (non-upscaled) image from result."""
    for nid, nout in result.get("outputs", {}).items():
        for img in nout.get("images", []):
            # Prefer base image (node 7) over upscaled (node 20:18)
            if nid == "7":
                return img
    # Fallback to any image
    for nid, nout in result.get("outputs", {}).items():
        for img in nout.get("images", []):
            return img
    return None


def download_image(filename, subfolder=""):
    url = f"{COMFYUI_URL}/view?filename={filename}"
    if subfolder:
        url += f"&subfolder={subfolder}"
    path = os.path.join(OUTPUT_DIR, filename)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    urllib.request.urlretrieve(url, path)
    return path


def generate_panel(base_wf, positive, negative=None, seed=None):
    if negative is None:
        negative = "worst quality, low quality, bad anatomy, bad hands, missing fingers, extra fingers, blurry, watermark, signature, text, nsfw"

    wf = json.loads(json.dumps(base_wf))
    wf["2"]["inputs"]["text"] = positive
    wf["3"]["inputs"]["text"] = negative
    wf["4"]["inputs"]["width"] = PANEL_WIDTH
    wf["4"]["inputs"]["height"] = PANEL_HEIGHT

    if seed is None:
        seed = random.randint(0, 2**32)
    wf["5"]["inputs"]["seed"] = seed
    wf["20:16"]["inputs"]["seed"] = random.randint(0, 2**32)

    print(f"  Queuing: {positive[:60]}...")
    prompt_id = queue_prompt(wf)
    print(f"  ID: {prompt_id}")
    result = wait_for_completion(prompt_id)

    img_info = get_base_image(result)
    if not img_info:
        raise RuntimeError("No image generated")
    return download_image(img_info["filename"], img_info.get("subfolder", ""))


def add_speech_bubble(img, text, position="top-right"):
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", FONT_SIZE)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    bubble_w = text_w + BUBBLE_PADDING * 2
    bubble_h = text_h + BUBBLE_PADDING * 2

    margin = 15
    positions = {
        "top-right": (img.width - bubble_w - margin, margin),
        "top-left": (margin, margin),
        "top-center": ((img.width - bubble_w) // 2, margin),
        "bottom-right": (img.width - bubble_w - margin, img.height - bubble_h - margin),
        "bottom-left": (margin, img.height - bubble_h - margin),
    }
    x, y = positions.get(position, positions["top-right"])

    # Bubble
    draw.rounded_rectangle([x, y, x + bubble_w, y + bubble_h], radius=12, fill="white", outline="black", width=2)

    # Tail
    tail_x = x + bubble_w // 2
    tail_y = y + bubble_h
    draw.polygon([(tail_x - 8, tail_y), (tail_x + 8, tail_y), (tail_x, tail_y + 12)], fill="white", outline="black")

    # Text
    draw.text((x + BUBBLE_PADDING, y + BUBBLE_PADDING - bbox[1]), text, fill="black", font=font)
    return img


def stitch_panels(panel_paths, output_path):
    panels = [Image.open(p) for p in panel_paths]
    width = max(p.width for p in panels)
    total_h = sum(p.height for p in panels) + BORDER_SIZE * (len(panels) - 1)

    strip = Image.new("RGB", (width, total_h), "black")
    y = 0
    for i, panel in enumerate(panels):
        if panel.width != width:
            panel = panel.resize((width, int(width * panel.height / panel.width)), Image.LANCZOS)
        strip.paste(panel, (0, y))
        y += panel.height
        if i < len(panels) - 1:
            y += BORDER_SIZE

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    strip.save(output_path, quality=95)
    print(f"Saved: {output_path} ({width}x{total_h})")
    return output_path


def generate_strip(panels_config, output_name="webtoon_strip.png"):
    """
    Generate a webtoon strip from panel configs.
    
    panels_config: list of dicts:
        - prompt: positive prompt tags
        - dialogue: speech bubble text (optional)
        - bubble_position: top-right|top-left|top-center|bottom-right|bottom-left
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base_wf = load_base_workflow()

    panel_paths = []
    for i, cfg in enumerate(panels_config):
        print(f"\n=== Panel {i+1}/{len(panels_config)} ===")
        path = generate_panel(base_wf, cfg["prompt"])

        if cfg.get("dialogue"):
            img = Image.open(path)
            img = add_speech_bubble(img, cfg["dialogue"], cfg.get("bubble_position", "top-right"))
            path = os.path.join(OUTPUT_DIR, f"panel_{i}_bubble.png")
            img.save(path)

        panel_paths.append(path)

    output_path = os.path.join(OUTPUT_DIR, output_name)
    return stitch_panels(panel_paths, output_path)


if __name__ == "__main__":
    panels = [
        {
            "prompt": "1boy, solo, Tzubaki, black hair, messy hair, red eyes, serious, chinese clothes, black robe, standing, full body, looking at viewer, forest, outdoors, masterpiece, best quality",
            "dialogue": "I can feel it...",
            "bubble_position": "top-right",
        },
        {
            "prompt": "1boy, solo, Tzubaki, black hair, messy hair, red eyes, angry, clenched fists, upper body, close-up, dark background, masterpiece, best quality",
            "dialogue": "The power within me...",
            "bubble_position": "top-center",
        },
        {
            "prompt": "1boy, solo, Tzubaki, black hair, messy hair, red eyes, glowing eyes, aura, energy, dynamic pose, full body, motion lines, dark background, masterpiece, best quality",
            "dialogue": "is AWAKENING!",
            "bubble_position": "top-right",
        },
        {
            "prompt": "1boy, solo, Tzubaki, black hair, messy hair, red eyes, confident, smirk, chinese clothes, black robe, standing, full body, looking at viewer, sunlight, outdoors, masterpiece, best quality",
            "dialogue": None,
        },
    ]

    result = generate_strip(panels, "tzubaki_awakening_strip.png")
    print(f"\nDone! {result}")
