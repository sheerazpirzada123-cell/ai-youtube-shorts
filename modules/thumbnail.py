"""
Curiosity thumbnail maker (PIL only).

- Takes a raw stock-footage frame (no captions on it), boosts colour/contrast,
  darkens top+bottom, and writes a BIG 2-4 word curiosity text with a thick
  black stroke. The last word is yellow, a red "?" badge adds the click-bait pull.
- Every video gets its own text (script["thumb_text"]), so 3 videos/day = 3 different thumbnails.
- Output is a portrait 1080x1920 JPEG under 2MB (YouTube limit).
"""
import io
import os
import random
import re
import subprocess
import time
import urllib.parse

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from modules.captions import ensure_fonts, _fallback_font

W, H = 1080, 1920
YELLOW = (255, 221, 0)
WHITE = (255, 255, 255)
RED = (235, 30, 40)


POLL_URL = "https://image.pollinations.ai/prompt/"
STYLE = (
    "ultra detailed, cinematic lighting, dramatic, vibrant saturated colors, sharp focus, "
    "high contrast, professional YouTube thumbnail, vertical 9:16, subject big in the center, "
    "no text, no letters, no watermark, no logo"
)
_ai_cache = {}


def _ai_background(prompt, tries=3):
    """Free AI image from Pollinations (flux). Returns a PIL image or None."""
    if not prompt:
        return None
    if prompt in _ai_cache:
        return _ai_cache[prompt].copy()
    try:
        import requests
    except Exception:
        return None

    full = f"{prompt.strip().rstrip('.')}, {STYLE}"
    headers = {"User-Agent": "Mozilla/5.0"}
    key = os.environ.get("POLLINATIONS_API_KEY")
    if key:
        headers["Authorization"] = "Bearer " + key

    for attempt in range(tries):
        seed = random.randint(1, 10_000_000)
        model = "flux" if attempt < 2 else "turbo"
        url = (
            POLL_URL + urllib.parse.quote(full)
            + f"?width=864&height=1536&seed={seed}&model={model}&nologo=true&enhance=false"
        )
        try:
            r = requests.get(url, headers=headers, timeout=120)
            ctype = r.headers.get("content-type", "")
            if r.status_code == 200 and ctype.startswith("image") and len(r.content) > 20_000:
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                _ai_cache[prompt] = img
                print(f"Pollinations thumbnail OK (model={model}, seed={seed})")
                return img.copy()
            print(f"Pollinations try {attempt + 1} failed: HTTP {r.status_code} {ctype}")
        except Exception as e:
            print(f"Pollinations try {attempt + 1} error: {e}")
        time.sleep(4 * (attempt + 1))
    return None


def _extract_frame(video_path, out_path, at=1.0):
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(at), "-i", video_path, "-frames:v", "1", "-q:v", "2", out_path],
        capture_output=True,
    )
    return os.path.exists(out_path)


def _cover(img, w, h):
    s = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * s) + 1, int(img.height * s) + 1), Image.LANCZOS)
    x = (img.width - w) // 2
    y = (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def _gradient(size, top_alpha, bottom_alpha):
    w, h = size
    g = Image.new("L", (1, h))
    for y in range(h):
        t = y / (h - 1)
        edge = max(0.0, 1 - t / 0.35) * top_alpha + max(0.0, (t - 0.6) / 0.4) * bottom_alpha
        g.putpixel((0, y), int(min(255, edge * 255)))
    return g.resize((w, h))


def _clean_text(text):
    text = re.sub(r"[^\w\s?!'-]", "", text or "", flags=re.ASCII)
    text = " ".join(text.split()).upper()
    words = text.split()[:5]
    return " ".join(words)


def _wrap(words, draw, font_path, size, max_w):
    font = ImageFont.truetype(font_path, size)
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        if cur and draw.textlength(trial, font=font) > max_w:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(cur)
    return lines, font


def make_thumbnail(video_path, output_path, text, title_fallback="Amazing Fact", image_prompt=None):
    """Return output_path on success, None on failure (never raises)."""
    try:
        if not image_prompt and not os.path.exists(video_path):
            return None

        img = _ai_background(image_prompt)
        if img is None:
            print("AI image nahi mili, video frame use ho raha hai.")
            frame_path = output_path + ".frame.jpg"
            if not _extract_frame(video_path, frame_path, 1.0) and not _extract_frame(video_path, frame_path, 0):
                print("Thumbnail frame extract nahi ho paya.")
                return None
            img = Image.open(frame_path).convert("RGB")
            os.remove(frame_path)

        img = _cover(img, W, H)
        img = ImageEnhance.Color(img).enhance(1.25)
        img = ImageEnhance.Contrast(img).enhance(1.12)

        shade = _gradient((W, H), 0.55, 0.75)
        img = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), img, shade)

        words = _clean_text(text).split() or _clean_text(title_fallback).split()[:4]
        fonts = ensure_fonts()
        font_path = fonts.get("anton") or fonts.get("bangers") or _fallback_font()

        draw = ImageDraw.Draw(img)
        # shrink until it fits in <= 3 lines and within the safe width
        max_w = W - 140
        size = 260
        while True:
            lines, font = _wrap(words, draw, font_path, size, max_w)
            if len(lines) <= 3 or size <= 110:
                break
            size -= 12
        line_h = int(size * 1.12)
        block_h = line_h * len(lines)
        y = int(H * 0.42) - block_h // 2  # upper-middle: clear of Shorts UI at the bottom

        last_word = words[-1]
        for li, line in enumerate(lines):
            line_text = " ".join(line)
            lw = draw.textlength(line_text, font=font)
            x = (W - lw) / 2
            for w in line:
                is_last = (li == len(lines) - 1) and (w is line[-1])
                color = YELLOW if is_last else WHITE
                draw.text((x + 6, y + 8), w, font=font, fill=(0, 0, 0))
                draw.text((x, y), w, font=font, fill=color, stroke_width=12, stroke_fill=(0, 0, 0))
                x += draw.textlength(w + " ", font=font)
            y += line_h

        # red "?" badge, top-right: pure curiosity trigger
        r = 130
        cx, cy = W - 190, 230
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=RED, outline=WHITE, width=10)
        qfont = ImageFont.truetype(font_path, 220)
        draw.text((cx, cy + 8), "?", font=qfont, fill=WHITE, anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0))

        q = 90
        while True:
            img.save(output_path, "JPEG", quality=q, optimize=True)
            if os.path.getsize(output_path) < 1_900_000 or q <= 60:
                break
            q -= 10
        return output_path
    except Exception as e:
        print(f"Thumbnail generate nahi hua: {e}")
        return None
