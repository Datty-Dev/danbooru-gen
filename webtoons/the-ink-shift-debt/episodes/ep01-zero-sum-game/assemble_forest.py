#!/usr/bin/env python3
"""Assemble the forest scene into a video."""
import sys
import os
import json

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', 'video'))

from mangacut import load_config, run_pipeline

CONFIG = os.path.join(os.path.dirname(__file__), 'forest-scene-resolved.json')
OUTPUT = os.path.join(os.path.dirname(__file__), 'video', 'forest-scene.mp4')

print("Loading resolved config...", flush=True)
config = load_config(CONFIG)
print(f"Loaded {len(config['scenes'])} scenes", flush=True)

print("Running MangaCut pipeline...", flush=True)
run_pipeline(config, OUTPUT)

print(f"\nDone! Video at: {OUTPUT}", flush=True)
