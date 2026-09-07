from moviepy.editor import (
    VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip,
    TextClip, ColorClip, concatenate_videoclips, concatenate_audioclips,
)
from moviepy.video.fx.all import crop, loop
import os

VIDEO_W, VIDEO_H = 1080, 1920


def _cover_resize(clip, w=VIDEO_W, h=VIDEO_H):
    """Clip ko target size (9:16) mein 'cover' fit karta hai - stretch/distort nahi, balke
    scale karke beech se crop karta hai, jaisa Instagram/YouTube Shorts editors karte hain."""
    clip_ratio = clip.w / clip.h
    target_ratio = w / h
    if clip_ratio > target_ratio:
        clip = clip.resize(height=h)
    else:
        clip = clip.resize(width=w)
    return crop(clip, width=w, height=h, x_center=clip.w / 2, y_center=clip.h / 2)


def _make_caption(text, duration, w=VIDEO_W):
    """Fallback: agar kisi scene ke liye word-timing data available na ho, to pura
    sentence ek sath dikhata hai (jaisa pehle hota tha) - taake video kabhi crash na ho."""
    txt_clip = TextClip(
        text,
        fontsize=64,
        color="white",
        font="DejaVu-Sans-Bold",
        method="caption",
        size=(w - 120, None),
        align="center",
        stroke_color="black",
        stroke_width=2,
    ).set_duration(duration)

    bg = ColorClip(
        size=(txt_clip.w + 60, txt_clip.h + 40),
        color=(0, 0, 0),
    ).set_opacity(0.45).set_duration(duration)

    caption = CompositeVideoClip([bg, txt_clip.set_position("center")])
    caption = caption.set_position(("center", 0.72), relative=True)
    return caption


_CAPTION_COLORS = ["#FFD400", "#00E0FF", "#FF4D6D", "#7CFF6B", "#FF9F45", "#C77DFF"]


def _make_word_captions(words, duration, w=VIDEO_W):
    """
    Word-by-word (karaoke/TikTok-style) captions banata hai - har word apni exact
    timing par bada, BOLD font aur ek alag bright color mein screen ke center mein
    pop hota hai. `words` empty ho to None return karta hai (caller fallback caption
    use karega).
    """
    valid_words = [wd for wd in words if wd["text"].strip()]
    if not valid_words:
        return None

    segments = []
    for i, wd in enumerate(valid_words):
        text = wd["text"].strip()
        start = max(0.0, wd["start"])
        end = valid_words[i + 1]["start"] if i + 1 < len(valid_words) else duration
        end = max(end, start + 0.05)
        seg_duration = min(end, duration) - start
        if seg_duration <= 0:
            continue

        color = _CAPTION_COLORS[i % len(_CAPTION_COLORS)]

        txt_clip = TextClip(
            text,
            fontsize=100,
            color=color,
            font="DejaVu-Sans-Bold",
            method="caption",
            size=(w - 100, None),
            align="center",
            stroke_color="black",
            stroke_width=5,
        ).set_duration(seg_duration).set_start(start)

        bg = ColorClip(
            size=(txt_clip.w + 60, txt_clip.h + 40),
            color=(0, 0, 0),
        ).set_opacity(0.4).set_duration(seg_duration).set_start(start).set_position("center")

        word_clip = CompositeVideoClip(
            [bg, txt_clip.set_position("center")],
            size=(w, txt_clip.h + 40),
        ).set_start(start).set_duration(seg_duration)
        segments.append(word_clip)

    if not segments:
        return None

    max_h = max(seg.h for seg in segments)
    caption_track = CompositeVideoClip(segments, size=(w, max_h)).set_duration(duration)
    caption_track = caption_track.set_position(("center", 0.72), relative=True)
    return caption_track


def render_short_video(scenes, scene_video_paths, scene_audio_paths, scene_word_timings=None,
                        output_file="output_short.mp4"):
    """
    Har scene ke liye: uski voiceover duration nikaal kar, uske matching video clip ko
    usi duration tak trim/loop karta hai, uske upar word-by-word caption lagata hai
    (ya word-timing na ho to poore sentence wala caption), phir sab scenes ko ek ke
    baad ek jodta hai (concatenate) taake poori video topic ke hisaab se sync ho.
    """
    if scene_word_timings is None:
        scene_word_timings = [[] for _ in scenes]

    video_segments = []
    audio_segments = []

    for scene, video_path, audio_path, words in zip(
        scenes, scene_video_paths, scene_audio_paths, scene_word_timings
    ):
        voice = AudioFileClip(audio_path)
        duration = voice.duration
        audio_segments.append(voice)

        clip = VideoFileClip(video_path)
        clip = _cover_resize(clip)

        if clip.duration < duration:
            clip = loop(clip, duration=duration)
        else:
            clip = clip.subclip(0, duration)
        clip = clip.set_duration(duration)

        caption = _make_word_captions(words, duration)
        if caption is None:
            caption = _make_caption(scene["narration"], duration)

        segment = CompositeVideoClip([clip, caption]).set_duration(duration)
        video_segments.append(segment)

    final_video = concatenate_videoclips(video_segments, method="compose")
    final_audio = concatenate_audioclips(audio_segments)
    final_video = final_video.set_audio(final_audio)

    final_video.write_videofile(
        output_file,
        fps=30,
        codec="libx264",
        audio_codec="aac",
    )

    for seg in video_segments:
        seg.close()
    for a in audio_segments:
        a.close()
