"""
VideoBuilder: A simple, declarative API for composing instructional videos.

Core ideas:
- Build a main timeline of clips (intro text screens, trimmed clips, freeze frames)
- Add overlays (text, arrows, etc.) positioned and timed relative to the full timeline
- Render once at the end

Notes:
- Text and graphics rendering use Pillow, avoiding ImageMagick requirements.
- All timeline clips are resized with letterboxing to a consistent canvas size to ensure overlays align reliably.
"""

from __future__ import annotations

from typing import Optional, Tuple, Union
import math

import numpy as np
import moviepy.editor as mp
import moviepy.video.fx.all as vfx
from PIL import Image, ImageDraw, ImageFont


Size = Tuple[int, int]
Point = Tuple[int, int]
Position = Union[str, Tuple[Union[str, int], Union[str, int]]]


def _load_font(fontsize: int) -> ImageFont.ImageFont:
    """Best-effort load of a TTF font, falling back to PIL's default.

    On Windows, Arial is commonly available; if not, we fall back gracefully.
    """
    try:
        return ImageFont.truetype("arial.ttf", fontsize)
    except Exception:
        return ImageFont.load_default()


def _pil_rgba_to_imageclip(img: Image.Image, duration: float) -> mp.ImageClip:
    """Convert a PIL RGBA image to a MoviePy ImageClip with alpha preserved."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    arr = np.array(img).astype("uint8")
    rgb = arr[..., :3]
    alpha = (arr[..., 3] / 255.0).astype("float32")

    base = mp.ImageClip(rgb).set_duration(duration)
    mask = mp.ImageClip(alpha, ismask=True).set_duration(duration)
    return base.set_mask(mask)


def _draw_centered_text_image(
    canvas_size: Size,
    text: str,
    fontsize: int,
    text_color: Union[str, Tuple[int, int, int]] = "white",
    bg_color: Union[str, Tuple[int, int, int]] = "black",
) -> Image.Image:
    """Create a full-size RGBA image with centered text on a solid background."""
    width, height = canvas_size
    img = Image.new("RGBA", (width, height), color=bg_color if isinstance(bg_color, tuple) else bg_color)
    draw = ImageDraw.Draw(img)
    font = _load_font(fontsize)

    # Compute multi-line text box and center it
    # Use multiline_textbbox for accurate size (Pillow >= 8.0)
    bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (width - text_w) // 2
    y = (height - text_h) // 2
    draw.multiline_text((x, y), text, font=font, fill=text_color, align="center")
    return img


def _draw_text_image_tight(
    text: str,
    fontsize: int,
    text_color: Union[str, Tuple[int, int, int]] = "white",
    padding: int = 8,
    bg_rgba: Tuple[int, int, int, int] = (0, 0, 0, 0),
) -> Image.Image:
    """Create a tight RGBA image around the rendered text (useful for overlays)."""
    font = _load_font(fontsize)
    # Measure text box
    dummy_img = Image.new("RGBA", (2, 2), (0, 0, 0, 0))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.multiline_textbbox((0, 0), text, font=font, align="left")
    text_w = max(1, bbox[2] - bbox[0])
    text_h = max(1, bbox[3] - bbox[1])

    img = Image.new("RGBA", (text_w + 2 * padding, text_h + 2 * padding), bg_rgba)
    draw = ImageDraw.Draw(img)
    draw.multiline_text((padding, padding), text, font=font, fill=text_color, align="left")
    return img


def _resize_and_letterbox(
    clip: mp.VideoClip,
    target_size: Size,
    bg_color: Tuple[int, int, int] = (0, 0, 0),
) -> mp.VideoClip:
    """Resize clip to fit within target_size, preserving aspect ratio, letterboxed.

    Audio is preserved from the original clip.
    """
    target_w, target_h = target_size
    cw, ch = clip.size

    scale = min(target_w / cw, target_h / ch)
    new_w = int(round(cw * scale))
    new_h = int(round(ch * scale))

    resized = clip.resize(newsize=(new_w, new_h))
    if (new_w, new_h) == (target_w, target_h):
        return resized

    bg = mp.ColorClip(size=target_size, color=bg_color, duration=clip.duration)
    composed = mp.CompositeVideoClip([bg, resized.set_position("center")], size=target_size)
    # Preserve audio track
    if clip.audio is not None:
        composed = composed.set_audio(clip.audio)
    return composed


# --- Annotation Helper Classes ---


class Arrow:
    """A helper class to create an arrow image as an overlay."""

    def __init__(
        self,
        start_pos: Point,
        end_pos: Point,
        color: Union[str, Tuple[int, int, int]] = "yellow",
        stroke_width: int = 5,
        head_length: int = 24,
        head_angle_deg: float = 30.0,
    ) -> None:
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.color = color
        self.stroke_width = stroke_width
        self.head_length = head_length
        self.head_angle_deg = head_angle_deg

    def as_clip(self, duration: float, video_size: Size) -> mp.ImageClip:
        # Create transparent canvas
        img = Image.new("RGBA", video_size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(img)

        # Draw main shaft
        draw.line([self.start_pos, self.end_pos], fill=self.color, width=self.stroke_width)

        # Draw arrowhead oriented to the line direction
        dx = self.end_pos[0] - self.start_pos[0]
        dy = self.end_pos[1] - self.start_pos[1]
        angle = math.atan2(dy, dx)
        theta = math.radians(self.head_angle_deg)

        left_angle = angle + math.pi - theta
        right_angle = angle + math.pi + theta

        left_point = (
            int(self.end_pos[0] + self.head_length * math.cos(left_angle)),
            int(self.end_pos[1] + self.head_length * math.sin(left_angle)),
        )
        right_point = (
            int(self.end_pos[0] + self.head_length * math.cos(right_angle)),
            int(self.end_pos[1] + self.head_length * math.sin(right_angle)),
        )
        draw.polygon([self.end_pos, left_point, right_point], fill=self.color)

        return _pil_rgba_to_imageclip(img, duration)


class Text:
    """A helper class for creating text overlays as clips using Pillow."""

    def __init__(
        self,
        text: str,
        fontsize: int = 50,
        color: Union[str, Tuple[int, int, int]] = "white",
        padding: int = 8,
    ) -> None:
        self.text = text
        self.fontsize = fontsize
        self.color = color
        self.padding = padding

    def as_clip(self, duration: float) -> mp.ImageClip:
        img = _draw_text_image_tight(self.text, self.fontsize, self.color, padding=self.padding)
        return _pil_rgba_to_imageclip(img, duration)


# --- The Main Builder Class ---


class VideoBuilder:
    def __init__(self, output_path: str, size: Size = (1920, 1080), fps: int = 30) -> None:
        self.output_path = output_path
        self.size: Size = size
        self.fps: int = fps
        self.timeline_clips: list[mp.VideoClip] = []  # Main sequential clips
        self.overlay_clips: list[mp.VideoClip] = []   # Timed overlays

    # --- Timeline methods ---
    def add_text_screen(
        self,
        text: str,
        duration: float,
        fontsize: int = 70,
        color: Union[str, Tuple[int, int, int]] = "white",
        bg_color: Union[str, Tuple[int, int, int]] = "black",
    ) -> None:
        """Adds a full screen of text on a solid background."""
        img = _draw_centered_text_image(self.size, text, fontsize=fontsize, text_color=color, bg_color=bg_color)
        clip = _pil_rgba_to_imageclip(img, duration).set_fps(self.fps)
        self.timeline_clips.append(clip)

    def add_clip(
        self,
        filepath: str,
        start_time: float = 0,
        end_time: Optional[float] = None,
        fade_in: float = 0,
        fade_out: float = 0,
        letterbox_bg: Tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        """Adds a video clip from a file, with optional trimming, fades, and letterboxing to canvas size."""
        base_clip = mp.VideoFileClip(filepath)
        if end_time is not None:
            clip = base_clip.subclip(start_time, end_time)
        else:
            clip = base_clip.subclip(start_time)

        # Conform clip to builder canvas with letterboxing (preserve aspect ratio)
        clip = _resize_and_letterbox(clip, self.size, bg_color=letterbox_bg)

        if fade_in and fade_in > 0:
            clip = vfx.fadein(clip, fade_in)
        if fade_out and fade_out > 0:
            clip = vfx.fadeout(clip, fade_out)

        self.timeline_clips.append(clip)

    def add_freeze_frame(self, duration: float, at_time: float) -> None:
        """Adds a freeze frame taken from the previous clip at the given time (in seconds).

        The time is relative to the previous timeline clip.
        """
        if not self.timeline_clips:
            raise ValueError("You must add a video clip before adding a freeze frame.")

        previous_clip = self.timeline_clips[-1]
        sample_t = max(0.0, min(at_time, max(0.0, previous_clip.duration - 1e-3)))
        frame = previous_clip.get_frame(sample_t)

        freeze_clip = mp.ImageClip(frame).set_duration(duration).set_fps(self.fps)
        # Conform to canvas to align with overlays/timeline
        freeze_clip = _resize_and_letterbox(freeze_clip, self.size)
        self.timeline_clips.append(freeze_clip)

    # --- Overlays ---
    def add_overlay(
        self,
        overlay_obj: Union[Arrow, Text],
        start_time: float,
        duration: float,
        position: Position = ("center", "center"),
    ) -> None:
        """Adds an overlay (e.g., Text or Arrow) onto the timeline at the given absolute start time.

        position can be a string (e.g., 'center') or a tuple, e.g., ("center", 150) or (x, y)
        """
        if isinstance(overlay_obj, Arrow):
            clip = overlay_obj.as_clip(duration, self.size)
        elif isinstance(overlay_obj, Text):
            clip = overlay_obj.as_clip(duration)
        else:
            raise TypeError("Unsupported overlay object type.")

        clip = clip.set_start(start_time).set_position(position)
        self.overlay_clips.append(clip)

    # --- Render ---
    def render(self) -> None:
        """Concatenates timeline clips, composites overlays, and writes the final video file."""
        if not self.timeline_clips:
            print("Timeline is empty. Nothing to render.")
            return

        final_timeline = mp.concatenate_videoclips(self.timeline_clips, method="compose")

        # Add all overlays on top of the main timeline
        composed_layers = [final_timeline] + self.overlay_clips
        final_video = mp.CompositeVideoClip(composed_layers, size=self.size)

        # Ensure audio from timeline is preserved if present
        if final_timeline.audio is not None:
            final_video = final_video.set_audio(final_timeline.audio)

        # Write output
        final_video.write_videofile(
            self.output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
            threads=4,
            preset="medium",
        )


