#!/usr/bin/env python3
"""Image Generation Bridge — ComfyUI communication + caching.

Tag assembly is Arbalest's job. This module just:
- Sends pre-built prompts to ComfyUI
- Downloads and caches generated images
- Resolves scenes (existing images stay as-is)
"""
import json
import os
import random
import urllib.request
import time
import hashlib
import shutil

COMFYUI_URL = "http://192.168.0.176:8188"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "generated")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cache_key(positive_prompt, seed=None):
    """Generate a cache key from the positive prompt."""
    raw = f"{positive_prompt}|{seed}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _check_cache(key):
    """Check if a cached image exists."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.png")
    return path if os.path.exists(path) else None


def queue_prompt(workflow):
    """Send workflow to ComfyUI."""
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
    """Wait for ComfyUI to finish."""
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


def download_image(filename, subfolder="", dest_dir=None):
    """Download image from ComfyUI."""
    url = f"{COMFYUI_URL}/view?filename={filename}"
    if subfolder:
        url += f"&subfolder={subfolder}"
    
    if dest_dir is None:
        dest_dir = CACHE_DIR
    os.makedirs(dest_dir, exist_ok=True)
    
    path = os.path.join(dest_dir, filename)
    urllib.request.urlretrieve(url, path)
    return path



def _upload_image(image_path):
    """Upload an image to ComfyUI's input folder via multipart."""
    import io
    filename = os.path.basename(image_path)
    with open(image_path, 'rb') as f:
        data = f.read()
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode())
    body.write(f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode())
    body.write(b"Content-Type: image/png\r\n\r\n")
    body.write(data)
    body.write(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        f"{COMFYUI_URL}/upload/image",
        data=body.getvalue(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read())
    return result.get("name", filename)

def generate_image(positive_prompt, negative_prompt=None, seed=None, workflow_path=None, reference_image=None, denoise=0.70):
    """Generate an image from a pre-built prompt string.

    IMPORTANT: Tag assembly is Arbalest's job. Pass the final tag string here.
    
    Args:
        positive_prompt: comma-separated Danbooru tags or natural language
        negative_prompt: negative prompt (default: standard negative)
        seed: random seed (None = random)
        workflow_path: path to base ComfyUI workflow JSON

    Returns:
        reference_image: path to reference image for img2img consistency
        denoise: denoise strength (0.3-0.9, lower = closer to reference)

    Returns:
        Path to generated image
    """
    if negative_prompt is None:
        negative_prompt = "worst quality, low quality, bad anatomy, bad hands, missing fingers, extra fingers, blurry, watermark, signature, text, nsfw"
    
    if seed is None:
        seed = random.randint(0, 2**32)
    
    # Check cache
    key = _cache_key(positive_prompt, seed)
    cached = _check_cache(key)
    if cached:
        print(f"  Cache hit: {key}")
        return cached
    
    # Load workflow
    if reference_image:
        workflow_path = workflow_path or os.path.join(PROJECT_ROOT, "workflows", "tzubaki-wai-upscale-img2img.json")
    else:
        workflow_path = workflow_path or os.path.join(PROJECT_ROOT, "workflows", "tzubaki-wai-upscale.json")
    
    with open(workflow_path) as f:
        wf = json.load(f)
    
    # Update workflow
    wf["2"]["inputs"]["text"] = positive_prompt
    wf["3"]["inputs"]["text"] = negative_prompt
    wf["5"]["inputs"]["seed"] = seed
    if "20:16" in wf:
        wf["20:16"]["inputs"]["seed"] = random.randint(0, 2**32)
    
    # img2img: upload reference and set denoise
    if reference_image and "24" in wf:
        uploaded_name = _upload_image(reference_image)
        wf["24"]["inputs"]["image"] = uploaded_name
        wf["5"]["inputs"]["denoise"] = denoise
    
    # Queue
    print(f"  Queuing to ComfyUI: {positive_prompt[:60]}...")
    prompt_id = queue_prompt(wf)
    result = wait_for_completion(prompt_id)
    
    # Get output image from SaveImageKJ (node 23) or fallback
    output_nodes = ["23", "20:18", "7"]  # priority order
    for target_nid in output_nodes:
        for nid, nout in result.get("outputs", {}).items():
            if nid == target_nid:
                for img in nout.get("images", []):
                    path = download_image(img["filename"], img.get("subfolder", ""))
                    cached_path = os.path.join(CACHE_DIR, f"{key}.png")
                    os.rename(path, cached_path)
                    print(f"  Generated: {cached_path}")
                    return cached_path
    
    # Ultimate fallback: any image node
    for nid, nout in result.get("outputs", {}).items():
        for img in nout.get("images", []):
            path = download_image(img["filename"], img.get("subfolder", ""))
            cached_path = os.path.join(CACHE_DIR, f"{key}.png")
            os.rename(path, cached_path)
            print(f"  Generated: {cached_path}")
            return cached_path
    
    raise RuntimeError("No image generated")


def resolve_scenes(scenes):
    """Resolve all scenes to image paths.

    For scenes with 'image': use the provided path (pass through).
    For scenes with 'prompt': generate via ComfyUI.
    
    img2img consistency: set "reference_panel": 0 (0-indexed) on a scene to use
    a previously generated panel as the reference image. The first panel is always
    txt2img; subsequent panels with reference_panel use img2img for consistency.
    
    Args:
        scenes: list of scene dicts
    
    Returns:
        list of scene dicts with 'image' key populated
    """
    resolved = []
    for i, scene in enumerate(scenes):
        if "image" in scene:
            if not os.path.exists(scene["image"]):
                raise FileNotFoundError(f"Image not found: {scene['image']}")
            resolved.append(scene)
            print(f"  Scene {i+1}: using existing image")
        elif "prompt" in scene:
            # Check for img2img reference
            ref_image = None
            denoise = scene.get("denoise", 0.70)
            ref_panel = scene.get("reference_panel")
            if ref_panel is not None and ref_panel < len(resolved):
                ref_image = resolved[ref_panel].get("image")
                if ref_image:
                    print(f"  Scene {i+1}: using panel {ref_panel+1} as img2img reference")
            
            image_path = generate_image(
                scene["prompt"],
                negative_prompt=scene.get("negative_prompt"),
                seed=scene.get("seed"),
                workflow_path=scene.get("workflow_path"),
                reference_image=ref_image,
                denoise=denoise,
            )
            scene_copy = dict(scene)
            scene_copy["image"] = image_path
            resolved.append(scene_copy)
            print(f"  Scene {i+1}: generated from prompt")
        elif "description" in scene:
            raise ValueError(
                f"Scene {i+1} has 'description' but no 'prompt'. "
                f"Arbalest must run the Danbooru pipeline and set 'prompt' before calling MangaCut. "
                f"Description: {scene['description'][:60]}"
            )
        else:
            raise ValueError(f"Scene {i+1} has neither 'image' nor 'prompt'")
    
    return resolved


if __name__ == "__main__":
    print("Image Generation Bridge ready")
    print(f"ComfyUI: {COMFYUI_URL}")
    print(f"Cache: {CACHE_DIR}")
    print(f"Project root: {PROJECT_ROOT}")
    print()
    print("NOTE: Tag assembly is Arbalest's job.")
    print("Pass 'prompt' (not 'description') for auto-generation.")
