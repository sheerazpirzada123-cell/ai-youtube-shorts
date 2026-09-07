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
    """Bottom ke thoda upar ek readable caption banata hai - semi-transparent background box
    ke sath, taake kisi bhi background video par text saaf padha ja sake."""
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


def render_short_video(scenes, scene_video_paths, scene_audio_paths, output_file="output_short.mp4"):
    """
    Har scene ke liye: uski voiceover duration nikaal kar, uske matching video clip ko
    usi duration tak trim/loop karta hai, uske upar caption lagata hai, phir sab scenes ko
    ek ke baad ek jodta hai (concatenate) taake poori video topic ke hisaab se sync ho.
    """
    video_segments = []
    audio_segments = []

    for scene, video_path, audio_path in zip(scenes, scene_video_paths, scene_audio_paths):
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
