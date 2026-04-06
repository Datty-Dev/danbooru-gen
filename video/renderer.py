#!/usr/bin/env python3
"""Video Renderer — frame generation + ffmpeg encoding for MangaCut.

Orchestrates transitions, text overlays, and ffmpeg to produce final video.
"""
import json
import os
import shutil
import subprocess
from PIL import Image, ImageDraw

from transitions import render_transition, get_transition
from text_overlays import render_speech_bubble, render_subtitle, render_title_card, render_text_overlay

DEFAULT_FPS = 30
DEFAULT_ORIENTATION = "vertical"

ORIENTATIONS = {
    "vertical": (1080, 1920),
    "horizontal": (1920, 1080),
}

DEFAULT_TRANSITION_FRAMES = {
    "hard_cut": 1,
    "whip_pan": 8,
    "fade_black": 15,
    "cross_dissolve": 15,
    "zoom_in": 12,
    "zoom_out": 12,
    "slide_left": 10,
    "slide_right": 10,
    "slide_up": 10,
    "slide_down": 10,
    "screen_shake": 8,
    "glitch": 10,
    "whip_tilt": 8,
    "page_turn": 15,
}


def get_ffmpeg():
    """Find ffmpeg."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except:
            pass
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")
    return ffmpeg


def resize_image(img, width, height):
    """Resize image to target dimensions, covering the frame."""
    img_ratio = img.width / img.height
    target_ratio = width / height
    
    if img_ratio > target_ratio:
        # Image is wider — fit height, crop width
        new_h = height
        new_w = int(height * img_ratio)
    else:
        # Image is taller — fit width, crop height
        new_w = width
        new_h = int(width / img_ratio)
    
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return resized.crop((left, top, left + width, top + height))


def add_letterbox(img, bar_pct=0.06):
    """Add cinematic black bars."""
    w, h = img.size
    bar_h = int(h * bar_pct)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, w, bar_h], fill="black")
    draw.rectangle([0, h - bar_h, w, h], fill="black")
    return img


def generate_frames(config, output_dir):
    """Generate all frames from scene config.

    Args:
        config: scene config dict (orientation, fps, scenes, title_card)
        output_dir: directory for frame images

    Returns:
        (frames_dir, total_frames)
    """
    fps = config.get("fps", DEFAULT_FPS)
    orientation = config.get("orientation", DEFAULT_ORIENTATION)
    width, height = ORIENTATIONS[orientation]
    
    scenes = config.get("scenes", [])
    title_card = config.get("title_card")
    
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)  # ensure parent exists too
    os.makedirs(output_dir, exist_ok=True)
    
    # Load and resize all scene images
    images = []
    for scene in scenes:
        img = Image.open(scene["image"])
        img = resize_image(img, width, height)
        if config.get('letterbox', False):
            img = add_letterbox(img)
        images.append(img)
    
    frame_num = 0
    
    # Title card
    if title_card:
        tc_duration = title_card.get("duration", 2.0)
        tc_frames = int(tc_duration * fps)
        tc_text = title_card.get("text", "")
        tc_animation = title_card.get("animation", "fade")
        
        for f in range(tc_frames):
            progress = f / max(tc_frames - 1, 1)
            frame = render_title_card(width, height, tc_text, 
                                     font_size=title_card.get("font_size", 72),
                                     animation=tc_animation, progress=progress)
            frame.save(os.path.join(frames_dir, f"frame_{frame_num:05d}.jpg"), "JPEG", quality=95)
            frame_num += 1
    
    # Generate scene frames
    for i, scene in enumerate(scenes):
        duration = scene.get("duration", 1.5)
        hold_frames = int(duration * fps)
        
        # Transition-in frames (except first scene)
        if i > 0:
            transition = scene.get("transition_in", "hard_cut")
            trans_dur = scene.get("transition_duration")
            if trans_dur:
                trans_frames = int(trans_dur * fps)
            else:
                trans_frames = DEFAULT_TRANSITION_FRAMES.get(transition, 8)
            
            # Get transition params
            trans_params = scene.get("transition_params", {})
            
            frames = render_transition(transition, images[i-1], images[i], 
                                      trans_frames, trans_params)
            
            for frame in frames:
                frame.save(os.path.join(frames_dir, f"frame_{frame_num:05d}.jpg"), "JPEG", quality=95)
                frame_num += 1
        
        # Hold frames (with text overlays)
        text_overlays = scene.get("text_overlays", [])
        
        for f in range(hold_frames):
            frame = images[i].copy()
            
            # Apply text overlays
            progress = f / max(hold_frames - 1, 1)
            for overlay in text_overlays:
                frame = render_text_overlay(frame, overlay, progress=progress)
            
            frame.save(os.path.join(frames_dir, f"frame_{frame_num:05d}.jpg"), "JPEG", quality=95)
            frame_num += 1
        
        print(f"  Scene {i+1}/{len(scenes)}: {hold_frames} hold + transition frames")
    
    print(f"  Total frames: {frame_num}")
    return frames_dir, frame_num


def encode_video(frames_dir, output_path, fps=30, width=1080, height=1920, crf=18):
    """Encode frames to MP4 using ffmpeg."""
    ffmpeg = get_ffmpeg()
    
    cmd = [
        ffmpeg, "-y",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "frame_%05d.jpg"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", str(crf),
        "-preset", "slow",
        "-vf", f"scale={width}:{height}",
        output_path,
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def render_video(config, output_path, keep_frames=False):
    """Full render pipeline: frames → encode.

    Args:
        config: scene config dict
        output_path: path for final MP4
        keep_frames: keep frame images after encoding

    Returns:
        Path to final MP4
    """
    fps = config.get("fps", DEFAULT_FPS)
    orientation = config.get("orientation", DEFAULT_ORIENTATION)
    width, height = ORIENTATIONS[orientation]
    
    output_dir = os.path.dirname(output_path) or "."
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Rendering video: {len(config.get('scenes', []))} scenes, {orientation} ({width}x{height})")
    
    # Generate frames
    frames_dir, total_frames = generate_frames(config, output_dir)
    
    # Encode
    print("Encoding with ffmpeg...")
    encode_video(frames_dir, output_path, fps=fps, width=width, height=height)
    
    # Cleanup
    if not keep_frames:
        shutil.rmtree(frames_dir, ignore_errors=True)
        print("Cleaned up frames")
    
    print(f"Video saved: {output_path}")
    return output_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MangaCut Video Renderer")
    parser.add_argument("--config", required=True, help="Scene config JSON file")
    parser.add_argument("--output", "-o", default="output.mp4", help="Output video path")
    parser.add_argument("--keep-frames", action="store_true", help="Keep frame images")
    args = parser.parse_args()
    
    with open(args.config) as f:
        config = json.load(f)
    
    render_video(config, args.output, keep_frames=args.keep_frames)
