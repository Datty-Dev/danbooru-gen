#!/usr/bin/env python3
"""Transition Engine — 14 transition effects for MangaCut.

Each transition: (img_a, img_b, progress, params) → PIL Image
progress: 0.0 to 1.0
"""
import math
import random
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageEnhance


def lerp(a, b, t):
    return a + (b - a) * t


def ease_in_out(t):
    return t * t * (3 - 2 * t)


def ease_out(t):
    return 1 - (1 - t) ** 2


def hard_cut(img_a, img_b, progress, params=None):
    """Instant switch at progress=0.5."""
    return img_b if progress >= 0.5 else img_a


def whip_pan(img_a, img_b, progress, params=None):
    """Horizontal smear + motion blur + scale punch + white flash."""
    p = params or {}
    width, height = img_a.size
    direction = p.get("direction", 1)  # 1=right, -1=left
    blur_intensity = p.get("blur_intensity", 20)
    scale_punch = p.get("scale_punch", 1.08)

    t = ease_out(progress)

    if progress < 0.15:
        # White flash
        flash_opacity = 0.7 * (1 - progress / 0.15)
        frame = img_b.copy()
        overlay = Image.new("RGBA", (width, height), (255, 255, 255, int(255 * flash_opacity)))
        frame = frame.convert("RGBA")
        frame = Image.alpha_composite(frame, overlay).convert("RGB")
    elif progress < 0.5:
        # Motion blur settling
        blur = int(blur_intensity * (1 - (progress - 0.15) / 0.35))
        frame = img_b.filter(ImageFilter.GaussianBlur(radius=max(blur, 0)))
    else:
        # Scale punch settling
        scale = lerp(scale_punch, 1.0, (progress - 0.5) / 0.5)
        new_w = int(width * scale)
        new_h = int(height * scale)
        scaled = img_b.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - width) // 2
        top = (new_h - height) // 2
        frame = scaled.crop((left, top, left + width, top + height))

    # Slide prev out during early phase
    if progress < 0.3:
        slide = int(direction * width * 0.5 * (progress / 0.3))
        prev_frame = img_a.copy()
        canvas = Image.new("RGB", (width, height), "black")
        canvas.paste(prev_frame, (slide, 0))
        if progress < 0.2:
            frame = Image.blend(canvas, frame, progress / 0.2)

    return frame


def fade_black(img_a, img_b, progress, params=None):
    """Current fades to black, then black fades to next."""
    if progress < 0.5:
        # Fade to black
        opacity = 1 - (progress / 0.5)
        black = Image.new("RGB", img_a.size, "black")
        return Image.blend(black, img_a, opacity)
    else:
        # Fade from black
        opacity = (progress - 0.5) / 0.5
        black = Image.new("RGB", img_b.size, "black")
        return Image.blend(black, img_b, opacity)


def cross_dissolve(img_a, img_b, progress, params=None):
    """Blend from A to B."""
    return Image.blend(img_a, img_b, progress)


def zoom_in(img_a, img_b, progress, params=None):
    """Zoom into current scene, hard cut to next."""
    p = params or {}
    zoom_factor = p.get("zoom_factor", 2.0)
    blur = p.get("blur", 10)

    if progress < 0.7:
        # Zoom into img_a
        t = progress / 0.7
        scale = lerp(1.0, zoom_factor, t)
        w, h = img_a.size
        new_w = int(w * scale)
        new_h = int(h * scale)
        scaled = img_a.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        frame = scaled.crop((left, top, left + w, top + h))
        # Add blur
        blur_amount = int(blur * t)
        if blur_amount > 0:
            frame = frame.filter(ImageFilter.GaussianBlur(radius=blur_amount))
        return frame
    else:
        # Flash to img_b
        t = (progress - 0.7) / 0.3
        if t < 0.3:
            # White flash
            frame = img_b.copy()
            overlay = Image.new("RGBA", frame.size, (255, 255, 255, int(255 * 0.5 * (1 - t / 0.3))))
            frame = frame.convert("RGBA")
            frame = Image.alpha_composite(frame, overlay).convert("RGB")
            return frame
        return img_b


def zoom_out(img_a, img_b, progress, params=None):
    """Next scene starts zoomed in, zooms out to normal."""
    p = params or {}
    zoom_factor = p.get("zoom_factor", 2.0)
    blur = p.get("blur", 10)

    t = ease_out(progress)
    scale = lerp(zoom_factor, 1.0, t)
    w, h = img_b.size
    new_w = int(w * scale)
    new_h = int(h * scale)
    scaled = img_b.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    frame = scaled.crop((left, top, left + w, top + h))

    blur_amount = int(blur * (1 - t))
    if blur_amount > 0:
        frame = frame.filter(ImageFilter.GaussianBlur(radius=blur_amount))

    return frame


def _slide(img_a, img_b, progress, direction_x=1, direction_y=0, params=None):
    """Generic slide transition."""
    p = params or {}
    blur = p.get("blur", 5)
    w, h = img_a.size

    t = ease_in_out(progress)
    offset_x = int(direction_x * w * t)
    offset_y = int(direction_y * h * t)

    canvas = Image.new("RGB", (w, h), "black")

    # Slide img_a out
    a_x = -offset_x if direction_x >= 0 else offset_x
    a_y = -offset_y if direction_y >= 0 else offset_y
    canvas.paste(img_a, (a_x, a_y))

    # Slide img_b in
    b_x = w - offset_x if direction_x >= 0 else -w + offset_x
    b_y = h - offset_y if direction_y >= 0 else -h + offset_y
    canvas.paste(img_b, (b_x, b_y))

    # Motion blur during mid-transition
    mid_blur = int(blur * (1 - abs(2 * progress - 1)))
    if mid_blur > 0:
        canvas = canvas.filter(ImageFilter.GaussianBlur(radius=mid_blur))

    return canvas


def slide_left(img_a, img_b, progress, params=None):
    return _slide(img_a, img_b, progress, direction_x=1, direction_y=0, params=params)


def slide_right(img_a, img_b, progress, params=None):
    return _slide(img_a, img_b, progress, direction_x=-1, direction_y=0, params=params)


def slide_up(img_a, img_b, progress, params=None):
    return _slide(img_a, img_b, progress, direction_x=0, direction_y=1, params=params)


def slide_down(img_a, img_b, progress, params=None):
    return _slide(img_a, img_b, progress, direction_x=0, direction_y=-1, params=params)


def screen_shake(img_a, img_b, progress, params=None):
    """Violent shake + flash + hard cut."""
    p = params or {}
    intensity = p.get("shake_intensity", 20)
    flash_opacity = p.get("flash_opacity", 0.8)

    w, h = img_a.size

    if progress < 0.7:
        # Shake img_a
        shake = int(intensity * (1 - progress / 0.7))
        ox = random.randint(-shake, shake)
        oy = random.randint(-shake, shake)
        canvas = Image.new("RGB", (w, h), "black")
        canvas.paste(img_a, (ox, oy))

        # Flash on early frames
        if progress < 0.2:
            flash = Image.new("RGBA", (w, h), (255, 255, 255, int(255 * flash_opacity * (1 - progress / 0.2))))
            canvas = canvas.convert("RGBA")
            canvas = Image.alpha_composite(canvas, flash).convert("RGB")
        return canvas
    else:
        # Settle into img_b with slight shake
        t = (progress - 0.7) / 0.3
        shake = int(intensity * 0.3 * (1 - t))
        ox = random.randint(-shake, max(shake, 0))
        oy = random.randint(-shake, max(shake, 0))
        canvas = Image.new("RGB", (w, h), "black")
        canvas.paste(img_b, (ox, oy))
        return canvas


def glitch(img_a, img_b, progress, params=None):
    """RGB split + horizontal slice displacement + noise."""
    p = params or {}
    slice_count = p.get("slice_count", 8)
    offset = p.get("offset", 15)

    w, h = img_a.size

    if progress < 0.7:
        # Glitch img_a
        frame = img_a.copy()

        # RGB channel split
        r, g, b = frame.split()
        shift = int(offset * math.sin(progress * 20))
        r = ImageChops.offset(r, shift, 0)
        b = ImageChops.offset(b, -shift, 0)
        frame = Image.merge("RGB", (r, g, b))

        # Horizontal slice displacement
        draw = ImageDraw.Draw(frame)
        for i in range(slice_count):
            y = random.randint(0, h - 1)
            slice_h = random.randint(5, 30)
            x_offset = random.randint(-offset * 2, offset * 2)
            slice_img = frame.crop((0, y, w, min(y + slice_h, h)))
            frame.paste(slice_img, (x_offset, y))

        return frame
    else:
        # Quick settle into img_b with final glitch
        t = (progress - 0.7) / 0.3
        frame = img_b.copy()
        if t < 0.5:
            r, g, b = frame.split()
            shift = int(offset * (1 - t * 2))
            r = ImageChops.offset(r, shift, 0)
            frame = Image.merge("RGB", (r, g, b))
        return frame


def whip_tilt(img_a, img_b, progress, params=None):
    """Vertical whip-pan (smear up/down)."""
    p = params or {}
    blur_intensity = p.get("blur_intensity", 20)
    direction = p.get("direction", -1)  # -1=up, 1=down
    w, h = img_a.size
    t = ease_out(progress)

    if progress < 0.15:
        # White flash
        flash_opacity = 0.6 * (1 - progress / 0.15)
        frame = img_b.copy()
        overlay = Image.new("RGBA", (w, h), (255, 255, 255, int(255 * flash_opacity)))
        frame = frame.convert("RGBA")
        frame = Image.alpha_composite(frame, overlay).convert("RGB")
    elif progress < 0.5:
        blur = int(blur_intensity * (1 - (progress - 0.15) / 0.35))
        frame = img_b.filter(ImageFilter.GaussianBlur(radius=max(blur, 0)))
    else:
        scale = lerp(1.06, 1.0, (progress - 0.5) / 0.5)
        new_w = int(w * scale)
        new_h = int(h * scale)
        scaled = img_b.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        frame = scaled.crop((left, top, left + w, top + h))

    # Vertical slide prev out during early phase
    if progress < 0.3:
        slide = int(direction * h * 0.5 * (progress / 0.3))
        canvas = Image.new("RGB", (w, h), "black")
        canvas.paste(img_a, (0, slide))
        if progress < 0.2:
            frame = Image.blend(canvas, frame, progress / 0.2)

    return frame


def page_turn(img_a, img_b, progress, params=None):
    """Simulated page curl/peel revealing next scene."""
    p = params or {}
    w, h = img_a.size

    t = ease_in_out(progress)
    turn_x = int(w * t)

    # img_b is revealed from left to right
    canvas = img_b.copy()

    if turn_x < w:
        # Remaining portion of img_a (the page being turned)
        a_crop = img_a.crop((turn_x, 0, w, h))

        # Add shadow along the edge
        shadow_width = min(30, w - turn_x)
        shadow = Image.new("RGBA", (shadow_width, h), (0, 0, 0, 0))
        for x in range(shadow_width):
            alpha = int(100 * (1 - x / shadow_width))
            draw = ImageDraw.Draw(shadow)
            draw.line([(x, 0), (x, h)], fill=(0, 0, 0, alpha))

        canvas.paste(a_crop, (turn_x, 0))

        # Overlay shadow
        shadow_pos = max(turn_x - shadow_width, 0)
        canvas = canvas.convert("RGBA")
        shadow_canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        shadow_canvas.paste(shadow, (shadow_pos, 0))
        canvas = Image.alpha_composite(canvas, shadow_canvas).convert("RGB")

    return canvas


# Registry
TRANSITIONS = {
    "hard_cut": hard_cut,
    "whip_pan": whip_pan,
    "fade_black": fade_black,
    "cross_dissolve": cross_dissolve,
    "zoom_in": zoom_in,
    "zoom_out": zoom_out,
    "slide_left": slide_left,
    "slide_right": slide_right,
    "slide_up": slide_up,
    "slide_down": slide_down,
    "screen_shake": screen_shake,
    "glitch": glitch,
    "whip_tilt": whip_tilt,
    "page_turn": page_turn,
}


def get_transition(name):
    """Get transition function by name."""
    if name not in TRANSITIONS:
        raise ValueError(f"Unknown transition: {name}. Available: {list(TRANSITIONS.keys())}")
    return TRANSITIONS[name]


def render_transition(name, img_a, img_b, num_frames, params=None):
    """Render a complete transition as a list of PIL Images."""
    func = get_transition(name)
    frames = []
    for i in range(num_frames):
        progress = i / max(num_frames - 1, 1)
        frame = func(img_a, img_b, progress, params)
        frames.append(frame)
    return frames
