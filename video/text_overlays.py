#!/usr/bin/env python3
"""Text Overlay Engine — speech bubbles, subtitles, title cards for MangaCut.

Bubble shapes: speech (rounded), thought (cloud), shout (jagged), whisper (dashed)
Position: named presets OR custom x,y coords
"""
import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import cv2
import numpy as np


FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONT_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
FONT_REGULAR = os.path.join(FONT_DIR, "DejaVuSans.ttf")

_cascade = None

def detect_face(img):
    """Detect face position in image. Returns (x, y, w, h) or None."""
    global _cascade
    if _cascade is None:
        _cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    img_array = np.array(img)
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    faces = _cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
    if len(faces) > 0:
        areas = [w*h for (x,y,w,h) in faces]
        best = faces[areas.index(max(areas))]
        result = tuple(int(v) for v in best)
        print(f"    [face] detected at {result}")
        return result
    else:
        print("    [face] no face detected, using fallback position")
        return None


def load_font(size, bold=True):
    """Load bundled font."""
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()




def _wrap_text(text, font, max_width, draw):
    """Wrap text to fit within max_width pixels. Returns list of lines."""
    words = text.split()
    if not words:
        return [text]
    lines = []
    current_line = words[0]
    for word in words[1:]:
        test_line = current_line + ' ' + word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return lines
def _jagged_rect(draw, x1, y1, x2, y2, spikes=16, spike_size=8, **kwargs):
    """Draw a jagged/spiky rectangle (for shout bubbles)."""
    points = []
    # Top edge
    for i in range(spikes + 1):
        px = x1 + (x2 - x1) * i / spikes
        py = y1 - spike_size if i % 2 == 1 else y1
        points.append((px, py))
    # Right edge
    for i in range(1, spikes + 1):
        px = x2 + spike_size if i % 2 == 1 else x2
        py = y1 + (y2 - y1) * i / spikes
        points.append((px, py))
    # Bottom edge (reverse)
    for i in range(spikes + 1):
        px = x2 - (x2 - x1) * i / spikes
        py = y2 + spike_size if i % 2 == 1 else y2
        points.append((px, py))
    # Left edge (reverse)
    for i in range(1, spikes + 1):
        px = x1 - spike_size if i % 2 == 1 else x1
        py = y2 - (y2 - y1) * i / spikes
        points.append((px, py))

    draw.polygon(points, **kwargs)


def _cloud_rect(draw, x1, y1, x2, y2, bumps=6, **kwargs):
    """Draw a cloud/bumpy rectangle (for thought bubbles)."""
    r = min((x2 - x1), (y2 - y1)) // (bumps * 2)
    r = max(r, 8)
    # Start with rounded rect as base
    draw.rounded_rectangle([x1, y1, x2, y2], radius=r + 4, **kwargs)
    # Add circles along edges for bumpy look
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    bw, bh = x2 - x1, y2 - y1
    # Top bumps
    for i in range(bumps):
        bx = x1 + bw * (i + 0.5) / bumps
        draw.ellipse([bx - r, y1 - r//2, bx + r, y1 + r//2], **kwargs)
    # Bottom bumps
    for i in range(bumps):
        bx = x1 + bw * (i + 0.5) / bumps
        draw.ellipse([bx - r, y2 - r//2, bx + r, y2 + r//2], **kwargs)
    # Left bumps
    for i in range(max(2, bumps // 2)):
        by = y1 + bh * (i + 0.5) / max(2, bumps // 2)
        draw.ellipse([x1 - r//2, by - r, x1 + r//2, by + r], **kwargs)
    # Right bumps
    for i in range(max(2, bumps // 2)):
        by = y1 + bh * (i + 0.5) / max(2, bumps // 2)
        draw.ellipse([x2 - r//2, by - r, x2 + r//2, by + r], **kwargs)


def _draw_bubble_shape(draw, x, y, w, h, shape="speech", fill="white", outline="black", width=2):
    """Draw the bubble body in the given shape."""
    if shape == "speech":
        draw.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=fill, outline=outline, width=width)
    elif shape == "shout":
        _jagged_rect(draw, x, y, x + w, y + h, spikes=20, spike_size=10, fill=fill, outline=outline)
        # Redraw outline on top since polygon doesn't support width
        _jagged_rect(draw, x, y, x + w, y + h, spikes=20, spike_size=10, fill=None, outline=outline, width=width)
    elif shape == "thought":
        _cloud_rect(draw, x, y, x + w, y + h, bumps=8, fill=fill, outline=outline, width=width)
    elif shape == "whisper":
        # Dashed rectangle
        draw.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=fill)
        # Draw dashed outline
        dash_len = 8
        gap_len = 4
        total = dash_len + gap_len
        for edge in [
            [(x, y), (x + w, y)],       # top
            [(x + w, y), (x + w, y + h)], # right
            [(x + w, y + h), (x, y + h)], # bottom
            [(x, y + h), (x, y)],         # left
        ]:
            sx, sy = edge[0]
            ex, ey = edge[1]
            length = math.sqrt((ex-sx)**2 + (ey-sy)**2)
            dx, dy = (ex-sx)/length, (ey-sy)/length
            pos = 0
            while pos < length:
                end_pos = min(pos + dash_len, length)
                draw.line([
                    (sx + dx*pos, sy + dy*pos),
                    (sx + dx*end_pos, sy + dy*end_pos)
                ], fill=outline, width=width)
                pos = end_pos + gap_len


def _draw_tail(draw, x, y, w, h, tail_dir, tail_size=18, shape="speech", fill="white", outline="black"):
    """Draw the bubble tail."""
    if shape == "thought":
        # Thought bubbles have small circles instead of a pointed tail
        if tail_dir in ("down", "down-left", "down-right"):
            cx = x + w // 2
            cy = y + h
            draw.ellipse([cx-5, cy+4, cx+5, cy+14], fill=fill, outline=outline)
            draw.ellipse([cx-3, cy+16, cx+3, cy+22], fill=fill, outline=outline)
        elif tail_dir in ("up", "up-left", "up-right"):
            cx = x + w // 2
            cy = y
            draw.ellipse([cx-5, cy-14, cx+5, cy-4], fill=fill, outline=outline)
            draw.ellipse([cx-3, cy-22, cx+3, cy-16], fill=fill, outline=outline)
        elif tail_dir == "left":
            cx, cy = x, y + h // 2
            draw.ellipse([cx-14, cy-5, cx-4, cy+5], fill=fill, outline=outline)
            draw.ellipse([cx-22, cy-3, cx-16, cy+3], fill=fill, outline=outline)
        elif tail_dir == "right":
            cx, cy = x + w, y + h // 2
            draw.ellipse([cx+4, cy-5, cx+14, cy+5], fill=fill, outline=outline)
            draw.ellipse([cx+16, cy-3, cx+22, cy+3], fill=fill, outline=outline)
        return

    # Standard pointed tail
    offset_x = w // 4
    if tail_dir == "down-right":
        tx, ty = x + w - offset_x, y + h
        draw.polygon([(tx-10, ty), (tx+10, ty), (tx+12, ty+tail_size)], fill=fill, outline=outline)
        draw.line([(tx-10, ty), (tx+10, ty)], fill=fill, width=4)
    elif tail_dir == "down-left":
        tx, ty = x + offset_x, y + h
        draw.polygon([(tx-10, ty), (tx+10, ty), (tx-12, ty+tail_size)], fill=fill, outline=outline)
        draw.line([(tx-10, ty), (tx+10, ty)], fill=fill, width=4)
    elif tail_dir == "down":
        tx, ty = x + w // 2, y + h
        draw.polygon([(tx-10, ty), (tx+10, ty), (tx, ty+tail_size)], fill=fill, outline=outline)
        draw.line([(tx-10, ty), (tx+10, ty)], fill=fill, width=4)
    elif tail_dir == "up-right":
        tx, ty = x + w - offset_x, y
        draw.polygon([(tx-10, ty), (tx+10, ty), (tx+12, ty-tail_size)], fill=fill, outline=outline)
        draw.line([(tx-10, ty), (tx+10, ty)], fill=fill, width=4)
    elif tail_dir == "up-left":
        tx, ty = x + offset_x, y
        draw.polygon([(tx-10, ty), (tx+10, ty), (tx-12, ty-tail_size)], fill=fill, outline=outline)
        draw.line([(tx-10, ty), (tx+10, ty)], fill=fill, width=4)
    elif tail_dir == "up":
        tx, ty = x + w // 2, y
        draw.polygon([(tx-10, ty), (tx+10, ty), (tx, ty-tail_size)], fill=fill, outline=outline)
        draw.line([(tx-10, ty), (tx+10, ty)], fill=fill, width=4)
    elif tail_dir == "left":
        tx, ty = x, y + h // 2
        draw.polygon([(tx, ty-10), (tx, ty+10), (tx-tail_size, ty)], fill=fill, outline=outline)
        draw.line([(tx, ty-10), (tx, ty+10)], fill=fill, width=4)
    elif tail_dir == "right":
        tx, ty = x + w, y + h // 2
        draw.polygon([(tx, ty-10), (tx, ty+10), (tx+tail_size, ty)], fill=fill, outline=outline)
        draw.line([(tx, ty-10), (tx, ty+10)], fill=fill, width=4)


def render_speech_bubble(img, text, position="top-right", font_size=42, padding=16,
                         shape="speech", tail_direction=None, bx=None, by=None):
    """Add a speech bubble to an image.

    Args:
        img: PIL Image
        text: bubble text
        position: top-left, top-right, top-center, bottom-left, bottom-right, bottom-center
        font_size: text font size (default 42 for 1080p vertical)
        padding: bubble padding
        shape: speech (rounded), thought (cloud), shout (jagged), whisper (dashed)
        tail_direction: override tail direction (down-left, down-right, etc.)
        bx, by: manual bubble top-left position

    Returns:
        Modified PIL Image
    """
    frame = img.copy()
    draw = ImageDraw.Draw(frame)
    font = load_font(font_size, bold=True)

    w, h = frame.size
    margin = 20

    # Wrap text to fit within 80% of frame width
    max_text_width = int(w * 0.8) - padding * 2
    lines = _wrap_text(text, font, max_text_width, draw)

    # Calculate total text size from wrapped lines
    line_heights = []
    max_line_w = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        line_heights.append((line_w, line_h))
        max_line_w = max(max_line_w, line_w)

    total_text_h = sum(lh for _, lh in line_heights) + 4 * (len(lines) - 1)  # 4px line spacing

    bubble_w = max_line_w + padding * 2
    bubble_h = total_text_h + padding * 2

    # Determine bubble position and tail direction
    if bx is not None and by is not None:
        x, y = bx, by
        tail_dir = tail_direction or "down"
        x = max(margin, min(x, w - bubble_w - margin))
        y = max(margin, min(y, h - bubble_h - margin - 30))
    else:
        # Try face detection
        face = detect_face(img)
        if face:
            fx, fy, fw, fh = face
            mouth_y = fy + int(fh * 0.8)
            x = fx + fw + 20
            y = mouth_y - bubble_h // 2
            tail_dir = "left"
            if x + bubble_w + margin > w:
                x = fx - bubble_w - 20
                tail_dir = "right"
            if y + bubble_h + margin > h:
                y = h - bubble_h - margin - 30
        else:
            positions = {
                "top-left":      {"pos": (margin, margin), "tail_dir": "down-right"},
                "top-right":     {"pos": (w - bubble_w - margin, margin), "tail_dir": "down-left"},
                "top-center":    {"pos": ((w - bubble_w) // 2, margin), "tail_dir": "down"},
                "bottom-left":   {"pos": (margin, h - bubble_h - margin - 30), "tail_dir": "up-right"},
                "bottom-right":  {"pos": (w - bubble_w - margin, h - bubble_h - margin - 30), "tail_dir": "up-left"},
                "bottom-center": {"pos": ((w - bubble_w) // 2, h - bubble_h - margin - 30), "tail_dir": "up"},
            }
            pos_config = positions.get(position, positions["top-right"])
            x, y = pos_config["pos"]
            tail_dir = tail_direction or pos_config["tail_dir"]

    # Draw bubble shape
    _draw_bubble_shape(draw, x, y, bubble_w, bubble_h, shape=shape)

    # Draw tail
    _draw_tail(draw, x, y, bubble_w, bubble_h, tail_dir, shape=shape)

    # Draw text (multi-line)
    text_y = y + padding
    for i, line in enumerate(lines):
        line_w, line_h = line_heights[i]
        # Center each line within bubble
        line_x = x + padding + (max_line_w - line_w) // 2
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text((line_x, text_y - bbox[1]), line, fill="black", font=font)
        text_y += line_h + 4

    return frame


def render_subtitle(img, text, font_size=32, bg_opacity=160, start=None, end=None, progress=None):
    """Add a subtitle bar at the bottom of the frame."""
    if progress is not None and start is not None and end is not None:
        if progress < start or progress > end:
            return img

    frame = img.copy()
    w, h = frame.size
    font = load_font(font_size, bold=True)

    draw = ImageDraw.Draw(frame)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    bar_h = text_h + 24
    bar_y = h - bar_h - 12

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bar_draw = ImageDraw.Draw(overlay)
    bar_draw.rounded_rectangle(
        [24, bar_y, w - 24, bar_y + bar_h],
        radius=10,
        fill=(0, 0, 0, bg_opacity),
    )
    frame = frame.convert("RGBA")
    frame = Image.alpha_composite(frame, overlay)

    text_draw = ImageDraw.Draw(frame)
    text_x = (w - text_w) // 2
    text_y = bar_y + 12 - bbox[1]
    text_draw.text((text_x, text_y), text, fill="white", font=font)

    return frame.convert("RGB")


def render_title_card(width, height, text, font_size=72, animation="fade", progress=0.5):
    """Generate a title card frame."""
    font = load_font(font_size, bold=True)
    frame = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(frame)
    display_text = text

    if animation == "typewriter":
        char_count = max(1, int(len(text) * progress))
        display_text = text[:char_count]

    bbox = draw.textbbox((0, 0), display_text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2
    draw.text((x, y - bbox[1]), display_text, fill="white", font=font)

    if animation == "fade":
        if progress < 0.2:
            opacity = progress / 0.2
        elif progress > 0.8:
            opacity = (1 - progress) / 0.2
        else:
            opacity = 1.0
        black = Image.new("RGB", (width, height), "black")
        frame = Image.blend(black, frame, opacity)

    return frame


def render_text_overlay(img, overlay_config, progress=None):
    """Apply a text overlay to an image based on config."""
    overlay_type = overlay_config.get("type")

    if overlay_type == "speech_bubble":
        return render_speech_bubble(
            img,
            text=overlay_config["text"],
            position=overlay_config.get("position", "top-right"),
            font_size=overlay_config.get("font_size", 42),
            shape=overlay_config.get("shape", "speech"),
            tail_direction=overlay_config.get("tail_direction"),
            bx=overlay_config.get("x"),
            by=overlay_config.get("y"),
        )
    elif overlay_type == "subtitle":
        return render_subtitle(
            img,
            text=overlay_config["text"],
            font_size=overlay_config.get("font_size", 32),
            start=overlay_config.get("start"),
            end=overlay_config.get("end"),
            progress=progress,
        )
    else:
        return img


if __name__ == "__main__":
    test = Image.new("RGB", (1080, 1920), (40, 40, 60))
    draw = ImageDraw.Draw(test)
    draw.rectangle([100, 100, 980, 1820], fill=(60, 60, 80), outline="white")

    for shape in ["speech", "thought", "shout", "whisper"]:
        bubble = render_speech_bubble(test, f"This is a {shape} bubble!", position="top-right", shape=shape)
        bubble.save(f"/tmp/test_bubble_{shape}.png")
        print(f"✓ {shape} bubble")

    sub = render_subtitle(test, "And so he disappeared into the night.", progress=0.5)
    sub.save("/tmp/test_subtitle.png")
    print("✓ Subtitle")

    title = render_title_card(1080, 1920, "Chapter 1: The Fall", animation="fade", progress=0.5)
    title.save("/tmp/test_title.png")
    print("✓ Title card")

    print("All text overlays working!")
