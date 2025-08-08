from __future__ import annotations

import argparse
from typing import Tuple, Union

from video_builder import VideoBuilder, Text, Arrow


def parse_size(size_str: str) -> Tuple[int, int]:
    try:
        w_str, h_str = size_str.lower().split("x")
        return int(w_str), int(h_str)
    except Exception:
        return 1920, 1080


def parse_position(pos_str: str) -> Union[str, Tuple[Union[str, int], Union[str, int]]]:
    # Accept forms like "center,150" or "960,540" or "center,center" or "center"
    if "," not in pos_str:
        token = pos_str.strip()
        if token == "center":
            return "center"
        try:
            return int(token), int(token)  # unlikely, but keep symmetry
        except Exception:
            return "center"

    x_str, y_str = [t.strip() for t in pos_str.split(",", 1)]

    def parse_token(tok: str) -> Union[str, int]:
        if tok == "center":
            return "center"
        try:
            return int(tok)
        except Exception:
            return "center"

    return parse_token(x_str), parse_token(y_str)


def parse_arrow(arrow_str: str) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    # Accept "x1,y1,x2,y2"
    parts = [p.strip() for p in arrow_str.split(",")]
    if len(parts) != 4:
        raise ValueError("--arrow must be in the form x1,y1,x2,y2")
    x1, y1, x2, y2 = map(int, parts)
    return (x1, y1), (x2, y2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build an instructional video with VideoBuilder")
    p.add_argument("--output", default="output.mp4", help="Output video path (mp4)")
    p.add_argument("--size", default="1920x1080", help="Canvas size as WIDTHxHEIGHT, e.g. 1920x1080")
    p.add_argument("--fps", type=int, default=30, help="Frames per second")

    # Title / text screen
    p.add_argument("--text", help="Title text for a full-screen text intro")
    p.add_argument("--title-duration", type=float, default=4.0, help="Duration for the title text screen")
    p.add_argument("--title-fontsize", type=int, default=70, help="Font size for the title text")
    p.add_argument("--title-color", default="white", help="Text color for the title")
    p.add_argument("--title-bg", default="black", help="Background color for the title screen")

    # Main clip
    p.add_argument("--clip", help="Path to a main video file to include")
    p.add_argument("--clip-start", type=float, default=0.0, help="Start time (s) for the main clip")
    p.add_argument("--clip-end", type=float, help="End time (s) for the main clip")
    p.add_argument("--fade-in", type=float, default=0.0, help="Fade in duration (s) for the main clip")
    p.add_argument("--fade-out", type=float, default=0.0, help="Fade out duration (s) for the main clip")

    # Freeze frame relative to the last timeline clip
    p.add_argument("--freeze-at", type=float, help="Freeze frame at time (s) into the previous clip")
    p.add_argument("--freeze-duration", type=float, help="Duration (s) of the freeze frame")

    # Text overlay
    p.add_argument("--overlay-text", help="Text to overlay")
    p.add_argument("--overlay-start", type=float, help="Start time (s) for overlay into the entire video")
    p.add_argument("--overlay-duration", type=float, default=4.0, help="Duration (s) for the overlay")
    p.add_argument(
        "--overlay-position",
        default="center,center",
        help="Position for overlay, e.g. 'center,150' or '960,540' or 'center,center'",
    )
    p.add_argument("--overlay-fontsize", type=int, default=50, help="Font size for overlay text")
    p.add_argument("--overlay-color", default="white", help="Color for overlay text")

    # Arrow overlay
    p.add_argument(
        "--arrow",
        help="Arrow coordinates as x1,y1,x2,y2 to overlay (requires --arrow-start)",
    )
    p.add_argument("--arrow-start", type=float, help="Start time (s) for arrow overlay")
    p.add_argument("--arrow-duration", type=float, default=4.0, help="Duration (s) for arrow overlay")
    p.add_argument("--arrow-color", default="yellow", help="Arrow color")
    p.add_argument("--arrow-width", type=int, default=5, help="Arrow stroke width")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    size = parse_size(args.size)

    editor = VideoBuilder(args.output, size=size, fps=args.fps)

    # Optional title text screen
    if args.text:
        editor.add_text_screen(
            args.text,
            duration=args.title_duration,
            fontsize=args.title_fontsize,
            color=args.title_color,
            bg_color=args.title_bg,
        )

    # Optional main clip
    if args.clip:
        editor.add_clip(
            args.clip,
            start_time=args.clip_start,
            end_time=args.clip_end,
            fade_in=args.fade_in,
            fade_out=args.fade_out,
        )

    # Optional freeze frame (only meaningful if at least one timeline clip exists)
    if args.freeze_at is not None and args.freeze_duration is not None:
        editor.add_freeze_frame(duration=args.freeze_duration, at_time=args.freeze_at)

    # Optional text overlay
    if args.overlay_text and args.overlay_start is not None:
        overlay_clip = Text(args.overlay_text, fontsize=args.overlay_fontsize, color=args.overlay_color)
        editor.add_overlay(
            overlay_clip,
            start_time=args.overlay_start,
            duration=args.overlay_duration,
            position=parse_position(args.overlay_position),
        )

    # Optional arrow overlay
    if args.arrow and args.arrow_start is not None:
        start_pt, end_pt = parse_arrow(args.arrow)
        arrow_clip = Arrow(start_pos=start_pt, end_pos=end_pt, color=args.arrow_color, stroke_width=args.arrow_width)
        editor.add_overlay(
            arrow_clip,
            start_time=args.arrow_start,
            duration=args.arrow_duration,
            position=(0, 0),  # Arrow is drawn in absolute canvas coordinates, so position is (0, 0)
        )

    # Render
    editor.render()

    print("Video generation complete!")


if __name__ == "__main__":
    main()


