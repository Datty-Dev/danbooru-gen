#!/usr/bin/env python3
"""MangaCut — Scene-Based Video Assembler.

CLI tool that orchestrates the full pipeline:
  1. Resolve images (existing or generate via ComfyUI)
  2. Render frames (transitions + holds + text overlays)
  3. Encode to MP4 via ffmpeg
  4. Mix audio (if provided)
  5. Output final MP4

Usage:
  python mangacut.py --config scene_config.json --output video.mp4
  python mangacut.py --config scene_config.json --output video.mp4 --audio music.mp3
"""
import argparse
import json
import os
import sys
import shutil

from renderer import render_video
from audio_mixer import mix_audio
from image_bridge import resolve_scenes

VIDEO_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config(config_path):
    """Load scene config from JSON file."""
    with open(config_path) as f:
        config = json.load(f)
    
    # Validate
    if "scenes" not in config or not config["scenes"]:
        raise ValueError("Config must have at least one scene")
    
    for i, scene in enumerate(config["scenes"]):
        if "image" not in scene and "description" not in scene:
            raise ValueError(f"Scene {i+1} needs 'image' or 'description'")
        if "duration" not in scene:
            scene["duration"] = 1.5  # default
    
    return config


def run_pipeline(config, output_path, audio_path=None, music_volume=0.8,
                 fade_in=0.5, fade_out=0.5, keep_frames=False):
    """Run the full MangaCut pipeline.

    Args:
        config: scene config dict
        output_path: final MP4 output path
        audio_path: optional background music path
        music_volume: music volume (0-1)
        fade_in: music fade in seconds
        fade_out: music fade out seconds
        keep_frames: keep intermediate frames
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    
    # Step 1: Resolve images
    print("=== Step 1: Resolving images ===")
    config["scenes"] = resolve_scenes(config["scenes"])
    
    # Step 2-3: Render video (frames + encode)
    print("\n=== Step 2-3: Rendering video ===")
    raw_video = output_path.replace(".mp4", "_raw.mp4")
    render_video(config, raw_video, keep_frames=keep_frames)
    
    # Step 4: Mix audio
    if audio_path and os.path.exists(audio_path):
        print(f"\n=== Step 4: Mixing audio ===")
        mix_audio(raw_video, output_path, 
                  background_music=audio_path,
                  music_volume=music_volume,
                  fade_in=fade_in, fade_out=fade_out)
        # Cleanup raw
        os.remove(raw_video)
    else:
        # No audio — rename raw to final
        shutil.move(raw_video, output_path)
    
    # Step 5: Done
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"\n=== Done! ===")
    print(f"Output: {output_path} ({size_mb:.1f} MB)")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="MangaCut — Scene-Based Video Assembler")
    parser.add_argument("--config", "-c", required=True, help="Scene config JSON file")
    parser.add_argument("--output", "-o", default="output/video.mp4", help="Output video path")
    parser.add_argument("--audio", "-a", default=None, help="Background music file (mp3/wav)")
    parser.add_argument("--volume", "-v", type=float, default=0.8, help="Music volume (0-1)")
    parser.add_argument("--fade-in", type=float, default=0.5, help="Music fade in (seconds)")
    parser.add_argument("--fade-out", type=float, default=0.5, help="Music fade out (seconds)")
    parser.add_argument("--keep-frames", action="store_true", help="Keep intermediate frames")
    args = parser.parse_args()
    
    config = load_config(args.config)
    run_pipeline(
        config, args.output,
        audio_path=args.audio,
        music_volume=args.volume,
        fade_in=args.fade_in,
        fade_out=args.fade_out,
        keep_frames=args.keep_frames,
    )


if __name__ == "__main__":
    main()
