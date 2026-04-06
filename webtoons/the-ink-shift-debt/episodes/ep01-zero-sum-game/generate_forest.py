#!/usr/bin/env python3
"""Generate the forest scene panels via ComfyUI."""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'video'))
from image_bridge import resolve_scenes

SCENE_PATH = os.path.join(os.path.dirname(__file__), 'forest-scene.json')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'images')

os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(SCENE_PATH) as f:
    config = json.load(f)

scenes = config['scenes']
print(f'Generating {len(scenes)} forest scene panels...')
print()

resolved = resolve_scenes(scenes)

# Copy images to episode images folder
import shutil
for s in resolved:
    if 'image' in s and os.path.exists(s['image']):
        dest = os.path.join(OUTPUT_DIR, f"panel_{s['id']:02d}.png")
        shutil.copy2(s['image'], dest)
        print(f"  Copied panel {s['id']} → {dest}")

print()
print('=== ALL PANELS GENERATED ===')
for s in resolved:
    print(f"  Panel {s['id']}: {s.get('image', 'N/A')}")

# Save resolved config
resolved_path = os.path.join(os.path.dirname(__file__), 'forest-scene-resolved.json')
with open(resolved_path, 'w') as f:
    json.dump({"title": config["title"], "scenes": resolved}, f, indent=2, default=str)
print(f"\nResolved config saved to {resolved_path}")
