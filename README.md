## KinoPy VideoBuilder

A small abstraction over MoviePy to declaratively build instructional videos using a clean, readable API. Text and graphics are rendered with Pillow (no ImageMagick required).

### Install

```bash
python -m venv .venv
. .venv/Scripts/Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
```

You will need an ffmpeg binary on your PATH. The `imageio-ffmpeg` dependency arranges one for most environments automatically; if not, install ffmpeg manually.

### Usage

You can use the CLI via `main.py`:

```python
python main.py --text "My Awesome Instructional Video" \
  --clip my_video.mp4 --clip-start 10 --clip-end 25 --fade-in 1 \
  --freeze-at 3 --freeze-duration 5 \
  --overlay-text "Focus on this button" --overlay-start 12 --overlay-duration 4 --overlay-position "center,150" \
  --arrow 400,300,600,450 --arrow-start 12 --arrow-duration 4
```

Run it:

```bash
python main.py
```

### Notes

- All clips are letterboxed to a consistent canvas size so overlays align.
- Text rendering uses Pillow, so you do not need ImageMagick. The code attempts to load `arial.ttf` and falls back to Pillow's default font if unavailable.
- For custom fonts, change `_load_font` in `video_builder.py` to point to your `.ttf`.

### Programmatic API example

If you prefer Python scripting instead of the CLI:

```python
from video_builder import VideoBuilder, Text, Arrow

editor = VideoBuilder("output.mp4")
editor.add_text_screen("My Awesome Instructional Video", duration=4)
editor.add_clip("my_video.mp4", start_time=10, end_time=25, fade_in=1)
editor.add_freeze_frame(duration=5, at_time=3)
editor.add_overlay(Text("Focus on this button"), start_time=12, duration=4, position=("center", 150))
editor.add_overlay(Arrow(start_pos=(400, 300), end_pos=(600, 450)), start_time=12, duration=4)
editor.render()
```


