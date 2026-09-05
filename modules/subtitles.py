"""
Word-level timing for burned-in, TikTok/Reels-style dynamic captions
(1-2 words on screen at a time, synced to the voiceover).

Two ways to get timings, tried in order:
  1. faster-whisper — transcribes the actual generated audio and gives real
     word-level timestamps. This is what actually produces well-synced
     captions. Needs the `faster-whisper` package (see requirements.txt);
     first run downloads a small model (~150-500MB depending on size,
     cached after that).
  2. Even-split fallback — if faster-whisper isn't installed or fails on a
     scene, splits that scene's known audio duration evenly across the
     script's words. Captions will still appear, just not perfectly
     synced to the actual speech rhythm.
"""

import re

try:
    from faster_whisper import WhisperModel
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False

_model = None
_MODEL_SIZE = "small"  # good Hindi accuracy/speed tradeoff on CPU; use "base" for faster/less accurate


def _load_model():
    global _model
    if _model is None:
        print(f"      ⏳ Loading Whisper ({_MODEL_SIZE}) for word-level captions "
              f"(first run downloads the model, cached after)...")
        _model = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def get_word_timings(audio_path, text, duration):
    """
    Returns a list of (word, start, end) tuples spanning roughly 0..duration,
    aligned to the actual spoken audio where possible.
    """
    words = [w for w in text.split() if w.strip()]
    if not words:
        return []

    if _WHISPER_AVAILABLE:
        try:
            model = _load_model()
            segments, _ = model.transcribe(audio_path, language="hi", word_timestamps=True)
            timings = []
            for seg in segments:
                for w in (seg.words or []):
                    word_text = (w.word or "").strip()
                    if word_text:
                        start = max(0.0, w.start)
                        end = min(duration, max(w.end, start + 0.05))
                        timings.append((word_text, start, end))
            if timings:
                return timings
            print("      ⚠️ Whisper returned no words, using even-split fallback.")
        except Exception as e:
            print(f"      ⚠️ Whisper alignment failed ({e}), using even-split fallback.")
    else:
        print("      ℹ️ faster-whisper not installed — using even-split caption timing "
              "(add faster-whisper to requirements.txt for real synced captions).")

    # Fallback: evenly distribute the known scene duration across words.
    per_word = duration / len(words)
    timings = []
    for i, w in enumerate(words):
        start = i * per_word
        end = start + per_word
        timings.append((w, start, end))
    return timings


MIN_CHUNK_DURATION = 0.28  # seconds — below this, a caption flashes faster than it can be read
MAX_CHUNK_CHARS = 18       # keeps the on-screen box from overcrowding on long compound words


def group_into_chunks(word_timings, chunk_size=2):
    """
    Groups (word, start, end) tuples into (text, start, end) chunks of at
    most `chunk_size` words. Shrinks the group to 1 word if the combined
    text is too wide for a clean caption, and stretches too-short chunks up
    to MIN_CHUNK_DURATION (without overlapping the next chunk) so fast
    speech doesn't produce captions that flicker on/off unreadably.
    """
    chunks = []
    i = 0
    n = len(word_timings)
    while i < n:
        group = word_timings[i:i + chunk_size]
        text = " ".join(w for w, _, _ in group)
        if len(text) > MAX_CHUNK_CHARS and len(group) > 1:
            group = group[:1]
            text = group[0][0]
        if not group:
            i += 1
            continue

        start = group[0][1]
        end = group[-1][2]

        if end - start < MIN_CHUNK_DURATION:
            next_idx = i + len(group)
            next_start = word_timings[next_idx][1] if next_idx < n else start + MIN_CHUNK_DURATION
            end = max(end, min(start + MIN_CHUNK_DURATION, next_start))

        chunks.append((text, start, end))
        i += len(group)
    return chunks


def escape_drawtext(text):
    """
    Escapes characters that break ffmpeg's drawtext filter argument syntax
    (backslash, colon, percent) and swaps a plain apostrophe for a
    typographic one so it doesn't collide with drawtext's own quoting.
    """
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    text = text.replace("'", "\u2019")
    return text
