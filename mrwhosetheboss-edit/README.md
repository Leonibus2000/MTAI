# Mrwhosetheboss edit (recreation of the Hikaru Nakamura edit)

Output: 576×576, 30 fps, 8.73 s MP4 (262 frames = 16 beats) that loops: the last shot whips into the first and the music carries across the seam, so it can play on repeat. Black-and-white posterize/halftone look, white cut-out outlines,
whip/zoom/glitch transitions on the music accents, film grain, Anton/Silkscreen typography and
procedural tech stickers. `EDIT_TIMELINE.md` has the full shot-by-shot breakdown.

## Status

`mrwhosetheboss_edit.mp4` is rendered with real Mrwhosetheboss imagery: 13 official video thumbnails
from his channel, one per subject slot, listed with URLs and crops in `sources.json` and
`footage/SOURCES.log`. YouTube refused video-stream downloads from this cloud server ("Sign in to confirm
you're not a bot" / HTTP 429), so the shots are animated stills rather than moving clips. The camera
moves, shake, blur and outlines supply the motion. S06 is procedural graphics only, as in the reference.

Cutouts use BiRefNet (portrait matte, plus objects in his hands for `held` shots). Mattes are cached in
`footage/` because CPU inference takes about a minute per still and needs about 8 GB of RAM. The first
render after `fetch_footage.py stills` computes them, and later renders take about 20 s.

## Swapping in video clips

Requirements: `pip install yt-dlp rembg[cpu] onnxruntime opencv-python-headless numpy pillow`, plus ffmpeg and the
fonts in `fonts/` (Anton, Silkscreen, Bungee from @fontsource, OFL-licensed).

0. `python3 fetch_footage.py stills` re-downloads and crops the thumbnails used now.
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
