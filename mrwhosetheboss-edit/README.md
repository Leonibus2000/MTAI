# Mrwhosetheboss edit (recreation of the Hikaru Nakamura edit)

Output: 576×576, 30 fps, 8.73 s MP4 (262 frames = 16 beats) that loops: the last shot opens into the first through a Dynamic Island and the music carries across the seam, so it can play on repeat. Black-and-white posterize/halftone look, white cut-out outlines,
whip/zoom/glitch transitions on the music accents, film grain, pixel/Anton typography and
real product photos as stickers. Six of the cuts use designed tech transitions (`transitions.py`): a Dynamic Island
expand, sliding slats, an iOS app close, a dive into a phone screen, a sticker pop-in and a real-phone wipe.
`EDIT_TIMELINE.md` has the full shot-by-shot breakdown.

## Status

`mrwhosetheboss_edit.mp4` is rendered with real Mrwhosetheboss imagery: 13 official video thumbnails
from his channel, one per subject slot, listed with URLs and crops in `sources.json` and
`footage/SOURCES.log`. YouTube refused video-stream downloads from this cloud server ("Sign in to confirm
you're not a bot" / HTTP 429), so the shots are animated stills rather than moving clips. The camera
moves, shake, blur and outlines supply the motion. S06 is procedural graphics only, as in the reference.

Cutouts use BiRefNet (portrait matte, plus objects in his hands for `held` shots). Mattes are cached in
`footage/` because CPU inference takes about a minute per still and needs about 8 GB of RAM. The first
render after `fetch_footage.py stills` computes them, and later renders take about 20 s.

## Props

The phones and batteries in the title shot (2.97 s), the dark interlude (3.37–4.40 s) and the MTD shot
are real product photos under CC BY / CC0, listed in `props.json`. `python3 fetch_footage.py props`
downloads them into `props/` and writes `CREDITS.md`. CC BY requires crediting the photographers, so
publish the short credit line from `CREDITS.md` with the video. Mattes are cached like the subject's.

## Swapping in video clips

Requirements: `pip install yt-dlp rembg[cpu] onnxruntime opencv-python-headless numpy pillow` (then `python3 fetch_footage.py stills` and `python3 fetch_footage.py props`), plus ffmpeg and the
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
