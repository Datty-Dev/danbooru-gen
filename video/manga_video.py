#!/usr/bin/env python3
"""Manga-style video generator with whip-pan transitions.

Uses ffmpeg + moviepy. No browser needed.
Hard cuts with motion blur, white flash, and letterbox bars.
"""
import os
import sys
import random
import subprocess
from PIL import Image, ImageDraw, ImageFilter

VIDEO_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(VIDEO_DIR, "output")

FPS = 30
PANEL_DURATION = 1.5  # seconds per panel
TRANSITION_DURATION = 0.27  # ~8 frames at 30fps
FLASH_DURATION = 0.1  # ~3 frames
WIDTH = 1080
HEIGHT = 1920
BAR_HEIGHT = int(HEIGHT * 0.08)  # letterbox


def add_letterbox(img):
    """Add cinematic black bars top and bottom."""
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, WIDTH, BAR_HEIGHT], fill="black")
    draw.rectangle([0, HEIGHT - BAR_HEIGHT, WIDTH, HEIGHT], fill="black")
    return img


def create_motion_blur_frame(img, direction="left", intensity=20):
    """Create a motion-blurred version of an image."""
    blurred = img.filter(ImageFilter.GaussianBlur(radius=intensity))
    return blurred


def create_flash_frame(img, opacity=0.7):
    """Create a white flash overlay."""
    flash = img.copy()
    draw = ImageDraw.Draw(flash)
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=(255, 255, 255, int(255 * opacity)))
    return flash


def generate_frames(panels, output_dir):
    """Generate all frames for the video."""
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    frames_per_panel = int(FPS * PANEL_DURATION)
    transition_frames = int(FPS * TRANSITION_DURATION)
    flash_frames = int(FPS * FLASH_DURATION)
    total_frames = len(panels) * frames_per_panel

    # Load and resize all panel images
    images = []
    for panel_path in panels:
        img = Image.open(panel_path)
        img = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
        img = add_letterbox(img)
        images.append(img)

    frame_num = 0
    for panel_idx in range(len(panels)):
        panel_start = panel_idx * frames_per_panel
        img = images[panel_idx]

        for f in range(frames_per_panel):
            # Transition: first few frames of each panel (except first)
            if f < transition_frames and panel_idx > 0:
                prev_img = images[panel_idx - 1]
                progress = f / transition_frames

                if f < flash_frames:
                    # White flash
                    flash_opacity = 0.7 * (1 - f / flash_frames)
                    frame = img.copy()
                    draw = ImageDraw.Draw(frame)
                    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (255, 255, 255, int(255 * flash_opacity)))
                    frame = frame.convert("RGBA")
                    frame = Image.alpha_composite(frame, overlay)
                    frame = frame.convert("RGB")
                elif f < flash_frames + 3:
                    # Motion blur
                    blur_amount = int(20 * (1 - progress))
                    frame = img.filter(ImageFilter.GaussianBlur(radius=blur_amount))
                else:
                    # Scale punch: slight zoom that settles
                    scale = 1.08 - 0.08 * progress
                    new_w = int(WIDTH * scale)
                    new_h = int(HEIGHT * scale)
                    scaled = img.resize((new_w, new_h), Image.LANCZOS)
                    left = (new_w - WIDTH) // 2
                    top = (new_h - HEIGHT) // 2
                    frame = scaled.crop((left, top, left + WIDTH, top + HEIGHT))
                    # Add letterbox back
                    frame = add_letterbox(frame)
            else:
                frame = img.copy()

            frame_path = os.path.join(frames_dir, f"frame_{frame_num:05d}.png")
            frame.save(frame_path)
            frame_num += 1

        print(f"  Panel {panel_idx + 1}/{len(panels)}: {frames_per_panel} frames")

    print(f"Total frames: {frame_num}")
    return frames_dir, frame_num


def render_video(frames_dir, total_frames, output_path):
    """Render frames to MP4 using ffmpeg."""
    print("Rendering video with ffmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%05d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "slow",
        "-vf", f"scale={WIDTH}:{HEIGHT}",
        output_path,
    ]
    subprocess.run(cmd, check=True)
    print(f"Video saved: {output_path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Manga-style video generator")
    parser.add_argument("--panels", nargs="+", required=True, help="Panel image paths")
    parser.add_argument("--output", "-o", default="manga.mp4", help="Output video file")
    parser.add_argument("--keep-frames", action="store_true", help="Keep frame images")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, args.output)

    print(f"Generating manga video: {len(args.panels)} panels")
    print(f"Resolution: {WIDTH}x{HEIGHT}, FPS: {FPS}, Duration: {len(args.panels) * PANEL_DURATION}s")

    frames_dir, total_frames = generate_frames(args.panels, OUTPUT_DIR)
    render_video(frames_dir, total_frames, output_path)

    # Cleanup
    if not args.keep_frames:
        import shutil
        shutil.rmtree(frames_dir, ignore_errors=True)
        print("Cleaned up frames")

    print("Done!")


if __name__ == "__main__":
    main()
