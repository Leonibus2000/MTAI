# Edit timeline (reverse-engineered from the Hikaru reference)

Reference: 576×576, 30 fps, 267 frames (8.90 s), HEVC + AAC. Music is about 110 BPM, with an accent every ~8 frames. Cuts land on accents every 16–18 frames, and the cut itself is hidden inside the peak of a motion-blur or zoom-blur transition.

Detected audio onsets (frame): 2, 20, 28, 36, 45, 53, 61, 69, 73, 94, 102, 118, 126, 135, 151, 159, 167, 176, 184, 200, 204, 216, 225, 233, 241, 249, 257, 266

| Shot | Time | Frames | Reference content | Recreation (Mrwhosetheboss / tech) | Look | Background | Overlays | Camera | Transition in |
|---|---|---|---|---|---|---|---|---|---|
| S01 | 0.00–0.70s | 0–20 | Hikaru CU glaring, tilted white frame, striped rook stickers, halftone dot bg | Close-up, intense stare straight into lens (studio intro) | poster=4, halftone=0.35 | dots | tilt_rect, striped_phones | zoom 1.18→1.05, rot -4→-1°, shake 2.0px | whip (0 out / 4 in, 60°) |
| S02 | 0.70–1.30s | 21–38 | Hikaru ECU, heavy posterize + halftone, tilted frame, pixel-stair edge graphics | Extreme close-up of face, serious / unimpressed expression | poster=5, halftone=0.6 | dots | tilt_rect2, pixel_stairs | zoom 1.0→1.1, rot 3→1°, shake 1.5px | zoom (5 out / 2 in, 0°) |
| S03 | 1.30–1.83s | 39–54 | Hikaru pointing, checkerboard bg, white outline | Medium shot, pointing a finger / gesturing at camera | halftone=0.15 | app_grid | – | zoom 1.05→1.14, rot 0→-2°, shake 2.5px | whip_flash (2 out / 2 in, 35°) |
| S04 | 1.83–2.43s | 55–72 | Hikaru with glasses, hand on chin, diagonal stripe bg | Thinking pose, hand on chin, looking off-camera | poster=4, halftone=0.25 | stripes | – | zoom 1.12→1.0, rot -2→2°, shake 2.0px | whip (3 out / 2 in, 55°) |
| S05 | 2.43–3.37s | 73–100 | Hikaru hand over mouth; 'HIKARU the GREAT' glitch text slides in; icons pop at f89 | Hand over mouth / leaning in, mid close-up | poster=4, halftone=0.3 | circuit | title_text, icons_pop | zoom 1.0→1.12, rot 0→0°, shake 2.0px | glitch (4 out / 1 in, 0°) |
| S06 | 3.37–4.40s | 101–131 | Dark bg, floating stickers (rocket, bolt, stopwatch); two hands fly in at f116 | Procedural tech stickers only (phones fly in instead of hands) | plain | dark | icon_field, phones_fly_in | zoom 1.0→1.08, rot 0→3°, shake 1.5px | zoom (2 out / 2 in, 0°) |
| S07 | 4.40–4.97s | 132–148 | Hikaru looking down, 'MUHMA' pixel badge on gem sticker, icons orbit | Close-up looking down at a phone / product in hand | poster=4, halftone=0.4 | dots | badge, icon_orbit | zoom 1.15→1.02, rot 2→-2°, shake 2.0px | zoom (3 out / 2 in, 0°) |
| S08 | 4.97–5.63s | 149–168 | Hikaru profile looking up, hand on chin, chessboard bg, inner hand outline | Profile / three-quarter, looking up, finger on chin | halftone=0.15 | circuit | – | zoom 1.0→1.1, rot -3→0°, shake 1.5px | whip (1 out / 2 in, 70°) |
| S09 | 5.63–6.07s | 169–181 | Hikaru hands clasped, repeated 'GENIUS' text wall bg | Hands clasped under chin, focused stare | halftone=0.2 | text_wall | – | zoom 1.1→1.02, rot 0→0°, shake 1.5px | whip (4 out / 2 in, 10°) |
| S10 | 6.07–6.67s | 182–199 | Torn-paper diagonal split with halftone; circular sticker zooms through at f196 | Close-up reaction, shocked / surprised face | poster=4, halftone=0.55 | dots | tear, lens_zoom | zoom 1.0→1.06, rot 0→0°, shake 1.0px | whip (2 out / 4 in, 40°) |
| S11 | 6.67–7.33s | 200–219 | Hikaru at board; camera crash-zooms into the board f213-218 | At desk with phones / unboxing, looking at a device | halftone=0.15 | phone_wall | crash_zoom | zoom 1.0→1.05, rot -2→0°, shake 2.0px | zoom (1 out / 2 in, 0°) |
| S12 | 7.33–7.93s | 220–237 | Two players at angled board, white outlines | Holding a phone up to camera / comparing two phones | halftone=0.2 | app_grid | held_phone | zoom 1.12→1.0, rot 2→-1°, shake 2.0px | whip (2 out / 1 in, 15°) |
| S13 | 7.93–8.47s | 238–253 | Hikaru big smile, LED light-bar bg, outline | Big genuine smile / laugh, close-up | halftone=0.15 | light_bars | – | zoom 1.0→1.1, rot -1→1°, shake 2.5px | whip (5 out / 1 in, 30°) |
| S14 | 8.47–8.90s | 254–266 | Hikaru holding board, chess-piece backdrop, end blur | Outro: holding a product, phone wall behind | halftone=0.2 | phone_wall | held_phone | zoom 1.0→1.08, rot 0→0°, shake 2.0px | whip (4 out / 2 in, 50°) |

## Global treatment (every frame)

- Grayscale with contrast ×1.3. Posterize (bilateral filter, then 4–5 levels mixed 60/40 with the smooth image) on the 'graphic' shots.
- Halftone: a 45° dot screen applied mostly in the midtones of the subject, plus a dot-grid pattern in the `dots` backgrounds.
- White subject outline: person mask (rembg `u2net_human_seg`) dilated 6 px, edge jittered every 3 frames so it reads as a hand-cut sticker.
- Constant handheld shake (1–2.5 px Gaussian per frame), an eased push-in/out and a slight rotation on every shot.
- Transitions: *whip* = translate up to 110 px along the angle plus a line blur up to ~100 px. *zoom* = scale up to 1.5× plus 10-tap radial zoom blur. *glitch* = random horizontal slice offsets. *whip_flash* adds +0.45 white.
- Vignette, then per-frame blurred film grain (σ≈0.05), then gamma 1.05.

## Typography

- S05 title: 'ARUN / the / BOSS' in Anton (replaces 'HIKARU the GREAT'). It slides in from the left over 14 frames, clipped at the frame edge, with glitch-sliced rows while moving and a stutter every 5 frames.
- S07 badge: 'WHO?' in Silkscreen pixel font, white with a black stroke, on a die-cut sticker (replaces 'MUHMA' on the gem). It pops in over 2 frames and fades out by frame 14.
- S09 wall: repeated 'TECH' in Anton, scrolling (replaces 'GENIUS').

## Chess → tech substitutions

| Reference | Recreation |
|---|---|
| Striped rook graphics | Striped phone silhouettes |
| Rocket / bolt / stopwatch stickers | Phone-back, lightning bolt, AI chip, battery, Wi-Fi stickers |
| Hands flying in | Two phones flying in |
| Checkerboard backgrounds | Rounded app-icon grid |
| Chessboard / chess-piece walls | Wall of phone backs, PCB circuit traces |
| Magnifier sticker zoom-through | Camera-lens sticker zoom-through |
| Crash zoom into chessboard | Crash zoom into a phone on the desk |
