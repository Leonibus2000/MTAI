# Mrwhosetheboss edit (recreation of the Hikaru Nakamura edit)

Output: 576×576, 30 fps, 8.9 s MP4. Black-and-white posterize/halftone look, white cut-out outlines,
whip/zoom/glitch transitions on the music accents, film grain, Anton/Silkscreen typography and
procedural tech stickers. `EDIT_TIMELINE.md` has the full shot-by-shot breakdown.

## Status

No Mrwhosetheboss footage is included. This session's network policy blocks youtube.com and the
other video hosts, so every subject slot renders as a labelled PLACEHOLDER mannequin.
Everything else is final: timing, effects, graphics, text and music sync.

## Finishing it

Requirements: `pip install yt-dlp rembg[cpu] opencv-python-headless numpy pillow`, plus ffmpeg and the
fonts in `fonts/` (Anton, Silkscreen, Bungee from @fontsource, OFL-licensed).

1. Scout a video and pick a moment for each slot:
   `python3 fetch_footage.py scout <video-url>` writes a contact sheet with timestamps.
2. Fill `url` and `start` (seconds) for each slot in `sources.json`.
   The `need` field describes the moment each slot wants.
3. Run `python3 fetch_footage.py fetch` to download only those sections into `footage/`, logged
   with URLs and timestamps in `footage/SOURCES.log`.
4. Render with `python3 render.py --out mrwhosetheboss_edit.mp4 --audio <reference edit .mp4>`.
   Any slot that has a `footage/<slot>.mp4` uses it. The person is auto-framed from the
   segmentation mask, cut out with the white outline, and placed on the tech background.
   Slots without footage stay as placeholders.
