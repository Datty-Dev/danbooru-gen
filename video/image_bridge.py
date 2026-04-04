#!/usr/bin/env python3
"""Image Generation Bridge — uses Danbooru RAG pipeline + ComfyUI API.

For scenes with 'description' instead of 'image', generates images automatically.
"""
import json
import os
import random
import urllib.request
import time
import hashlib

COMFYUI_URL = "http://192.168.0.176:8188"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache", "generated")

# Path to the danbooru project root (parent of video/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cache_key(description, trigger=None, model="wai"):
    """Generate a cache key for a scene description."""
    raw = f"{description}|{trigger}|{model}"
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


def generate_image(description, trigger=None, model="wai", seed=None, workflow_path=None):
    """Generate an image from a text description using the full pipeline.

    Args:
        description: character/scene description
        trigger: LoRA trigger word (e.g. "Tzubaki")
        model: target model format (wai, pony, netayume, flux)
        seed: random seed (None = random)
        workflow_path: path to base ComfyUI workflow JSON

    Returns:
        Path to generated image
    """
    # Check cache
    key = _cache_key(description, trigger, model)
    cached = _check_cache(key)
    if cached:
        print(f"  Cache hit: {key}")
        return cached
    
    # Run RAG pipeline to get tags
    print(f"  Running RAG for: {description[:60]}...")
    rag = run_rag_pipeline(description, model)
    
    # Assemble tags
    tags = assemble_tags(rag, description, trigger, model)
    
    # Load workflow
    if workflow_path is None:
        workflow_path = os.path.join(PROJECT_ROOT, "workflows", "tzubaki-wai-upscale.json")
    
    with open(workflow_path) as f:
        wf = json.load(f)
    
    # Update workflow
    positive, negative = build_prompts(tags, model)
    wf["2"]["inputs"]["text"] = positive
    wf["3"]["inputs"]["text"] = negative
    
    if seed is None:
        seed = random.randint(0, 2**32)
    wf["5"]["inputs"]["seed"] = seed
    wf["20:16"]["inputs"]["seed"] = random.randint(0, 2**32)
    
    # Queue
    print(f"  Queuing to ComfyUI...")
    prompt_id = queue_prompt(wf)
    result = wait_for_completion(prompt_id)
    
    # Get base image (node 7)
    for nid, nout in result.get("outputs", {}).items():
        for img in nout.get("images", []):
            path = download_image(img["filename"], img.get("subfolder", ""))
            # Rename to cache key
            cached_path = os.path.join(CACHE_DIR, f"{key}.png")
            os.rename(path, cached_path)
            print(f"  Generated: {cached_path}")
            return cached_path
    
    raise RuntimeError("No image generated")


def run_rag_pipeline(description, model="wai"):
    """Run the RAG pipeline to get relevant tags."""
    sys_path = os.path.join(PROJECT_ROOT)
    if sys_path not in os.sys.path:
        os.sys.path.insert(0, sys_path)
    
    from rag_pipeline import RAGPipeline
    
    pipeline = RAGPipeline()
    
    # Skip RAG for natural language models
    if model in ("netayume", "flux"):
        return {"tags": {}, "description": description}
    
    return pipeline.retrieve(description)


def assemble_tags(rag_result, description, trigger=None, model="wai"):
    """Assemble final tag list from RAG results and description.
    
    This is where Arbalest's tag assembly logic goes.
    In production, Arbalest does this. For auto-generation, we do a simplified version.
    """
    if model in ("netayume", "flux"):
        return description  # Return raw description for NL models
    
    # Collect top tags from each subcategory
    tags = []
    for subcat, tag_list in rag_result.get("tags", {}).items():
        # Take first few tags from each category
        tags.extend(tag_list[:5])
    
    return tags


def build_prompts(tags, model="wai"):
    """Build positive and negative prompts from tags."""
    if isinstance(tags, str):
        # Natural language model
        return tags, ""
    
    positive = ", ".join(tags)
    negative = "worst quality, low quality, bad anatomy, bad hands, missing fingers, extra fingers, blurry, watermark, signature, text, nsfw"
    return positive, negative


def resolve_scenes(scenes):
    """Resolve all scenes to image paths.

    For scenes with 'image': use the provided path.
    For scenes with 'description': generate via ComfyUI.
    
    Args:
        scenes: list of scene dicts with either 'image' or 'description' key
    
    Returns:
        list of scene dicts with 'image' key populated
    """
    resolved = []
    for i, scene in enumerate(scenes):
        if "image" in scene:
            # Use existing image
            if not os.path.exists(scene["image"]):
                raise FileNotFoundError(f"Image not found: {scene['image']}")
            resolved.append(scene)
            print(f"  Scene {i+1}: using existing image")
        elif "description" in scene:
            # Generate image
            trigger = scene.get("trigger")
            model = scene.get("model", "wai")
            image_path = generate_image(
                scene["description"],
                trigger=trigger,
                model=model,
            )
            scene_copy = dict(scene)
            scene_copy["image"] = image_path
            resolved.append(scene_copy)
            print(f"  Scene {i+1}: generated image")
        else:
            raise ValueError(f"Scene {i+1} has neither 'image' nor 'description'")
    
    return resolved


if __name__ == "__main__":
    print("Image Generation Bridge ready")
    print(f"ComfyUI: {COMFYUI_URL}")
    print(f"Cache: {CACHE_DIR}")
    print(f"Project root: {PROJECT_ROOT}")
