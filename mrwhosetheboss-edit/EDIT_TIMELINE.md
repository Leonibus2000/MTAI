# Edit timeline (reverse-engineered from the Hikaru reference)

Reference: 576×576, 30 fps, 267 frames (8.90 s), HEVC + AAC. Music is about 110 BPM, with an accent every ~8 frames. Cuts land on accents every 16–18 frames.

Detected audio onsets (frame): 2, 20, 28, 36, 45, 53, 61, 69, 73, 94, 102, 118, 126, 135, 151, 159, 167, 176, 184, 200, 204, 216, 225, 233, 241, 249, 257, 266

| Shot | Time | Frames | Reference content | Recreation (Mrwhosetheboss / tech) | Look | Background | Overlays | Camera | Transition in |
|---|---|---|---|---|---|---|---|---|---|
| S01 | 0.00–0.70s | 0–20 | Hikaru CU glaring, tilted white frame, striped rook stickers, halftone dot bg | Close-up, intense stare straight into lens (studio intro) | poster=4, halftone=0.35 | dots | tilt_rect, striped_phones | zoom 1.06→1.0, rot -4→-1°, shake 2.0px | whip (0 out / 4 in, 60°) |
| S02 | 0.70–1.30s | 21–38 | Hikaru ECU, heavy posterize + halftone, tilted frame, pixel-stair edge graphics | Extreme close-up of face, serious / unimpressed expression | poster=5, halftone=0.6 | dots | tilt_rect2, pixel_stairs | zoom 1.0→1.06, rot 3→1°, shake 1.5px | zoom (5 out / 2 in, 0°) |
| S03 | 1.30–1.83s | 39–54 | Hikaru pointing, checkerboard bg, white outline | Medium shot, pointing a finger / gesturing at camera | halftone=0.15 | app_grid | – | zoom 1.05→1.14, rot 0→-2°, shake 2.5px | whip_flash (2 out / 2 in, 35°) |
| S04 | 1.83–2.43s | 55–72 | Hikaru with glasses, hand on chin, diagonal stripe bg | Thinking pose, hand on chin, looking off-camera | poster=4, halftone=0.25 | stripes | – | zoom 1.12→1.0, rot -2→2°, shake 2.0px | whip (3 out / 2 in, 55°) |
| S05 | 2.43–3.37s | 73–100 | Hikaru hand over mouth; 'HIKARU the GREAT' glitch text slides in; icons pop at f89 | Hand over mouth / leaning in, mid close-up | poster=4, halftone=0.3 | circuit | title_text, icons_pop | zoom 1.0→1.12, rot 0→0°, shake 2.0px | glitch (4 out / 1 in, 0°) |
| S06 | 3.37–4.40s | 101–131 | Dark bg, floating stickers (rocket, bolt, stopwatch); two hands fly in at f116 | Procedural tech stickers only (phones fly in instead of hands) | plain | dark | icon_field, phones_fly_in | zoom 1.0→1.08, rot 0→3°, shake 1.5px | zoom (2 out / 2 in, 0°) |
| S07 | 4.40–4.97s | 132–148 | Hikaru looking down, 'MUHMA' pixel badge on gem sticker, icons orbit | Close-up, side-eye at a phone / product in hand | halftone=0.2 | dark | badge, icon_orbit | zoom 1.15→1.02, rot 2→-2°, shake 2.0px | zoom (3 out / 2 in, 0°) |
| S08 | 4.97–5.63s | 149–168 | Hikaru profile looking up, hand on chin, chessboard bg, inner hand outline | Profile / three-quarter, looking up, finger on chin | halftone=0.15 | circuit | – | zoom 1.0→1.1, rot -3→0°, shake 1.5px | whip (1 out / 2 in, 70°) |
| S09 | 5.63–6.07s | 169–181 | Hikaru hands clasped, repeated 'GENIUS' text wall bg | Hands clasped under chin, focused stare | halftone=0.2 | text_wall | – | zoom 1.1→1.02, rot 0→0°, shake 1.5px | whip (4 out / 2 in, 10°) |
| S10 | 6.07–6.67s | 182–199 | Torn-paper diagonal split with halftone; circular sticker zooms through at f196 | Close-up reaction, shocked / surprised face | poster=4, halftone=0.55 | dots | tear, lens_zoom | zoom 1.0→1.06, rot 0→0°, shake 1.0px | whip (2 out / 4 in, 40°) |
| S11 | 6.67–7.33s | 200–219 | Hikaru at board; camera crash-zooms into the board f213-218 | At desk with phones / unboxing, looking at a device | halftone=0.15 | phone_wall | crash_zoom | zoom 1.0→1.05, rot -2→0°, shake 2.0px | lens (1 out / 2 in, 30°) |
| S12 | 7.33–7.93s | 220–237 | Two players at angled board, white outlines | Holding a phone up to camera / comparing two phones | halftone=0.2 | app_grid | held_phone | zoom 1.12→1.0, rot 2→-1°, shake 2.0px | whip (2 out / 1 in, 15°) |
| S13 | 7.93–8.47s | 238–253 | Hikaru big smile, LED light-bar bg, outline | Big genuine smile / laugh, close-up | halftone=0.15, subject ×0.8 | light_bars | – | zoom 1.0→1.1, rot -1→1°, shake 2.5px | whip (5 out / 1 in, 30°) |
| S14 | 8.47–8.90s | 254–266 | Hikaru holding board, chess-piece backdrop, end blur | Outro: holding a product, phone wall behind | halftone=0.2 | phone_wall | held_phone | zoom 1.0→1.08, rot 0→0°, shake 2.0px | whip (4 out / 2 in, 50°) |

## Transitions (how the reference hides its cuts)

- **Accelerate out:** the outgoing shot's displacement ramps up (u²) over the 1–5 frames before the cut.
- **Overlap the cut:** the last frame before the cut is 72% outgoing and 28% incoming, both already streaking. The first frame after it is 74% incoming and 26% outgoing.
- **Snap in:** the incoming shot decelerates over 1–4 frames (v^2.2), so it is nearly sharp by the second frame. Each shot also lands with a +7% punch-in that decays over about 2 frames.
- **whip:** up to 150 px of travel along the angle, plus 3° of rotation and a ≤62 px line blur. The blur keeps structure readable instead of turning the frame to mush. *whip_flash* adds a +0.22 white lift.
- **zoom:** scale up to 1.45× (out) or 1.35× (in), with an 8-tap radial blur of ≤0.2.
- **glitch:** horizontal slice offsets up to 90 px with a light horizontal blur.
- **lens (6.67 s):** the camera-lens sticker grows to cover the frame on the last 4 frames of S10. It then flies off toward the top-right over the first 2 frames of S11, with only a light camera move underneath.
- **Shake:** smooth low-passed noise whose amplitude kicks ×3 on every detected music onset and decays over about 2 frames. This replaces random per-frame jitter.

## Global treatment (every frame)

- Grayscale with contrast ×1.3. Posterize (bilateral filter, then 4–5 levels mixed 60/40 with the smooth image) on the 'graphic' shots.
- Halftone: a 45° dot screen applied mostly in the subject's midtones, plus a dot-grid pattern in the `dots` backgrounds.
- White subject outline: person mask (rembg `u2net_human_seg`) dilated 6 px, edge jittered every 3 frames so it reads as a hand-cut sticker.
- Vignette, then per-frame blurred film grain (σ≈0.05), then gamma 1.05.

## Typography

- S05 title: 'ARUN / the / BOSS' in Anton (replaces 'HIKARU the GREAT'). It slides in from the left over 14 frames, clipped at the frame edge, with glitch-sliced rows while moving.
- S07 editor watermark: **MTD** (replaces the reference's 'MUHMA' tag). Tall VT323 pixel lettering at 1.45× height, white with a black keyline and inner black hairlines, on a white die-cut badge. It pops in over frames 0–2 (0.55 → 1.12 → 1.0), holds, then breaks up into random vertical strips on frames 11–15, the same timing as the reference.
- S09 wall: repeated 'TECH' in Anton, scrolling (replaces 'GENIUS').
- Not reproduced: the reference's faint one-frame serif text flash ('…LOVES MO…') across the face at f36.

## Chess → tech substitutions

| Reference | Recreation |
|---|---|
| Striped rook graphics | Striped phone silhouettes |
| Rocket / bolt / stopwatch stickers | Phone-back, lightning bolt, AI chip, battery, Wi-Fi stickers |
| Hands flying in | Two phones flying in |
| Checkerboard backgrounds | Rounded app-icon grid |
| Chessboard / chess-piece walls | Wall of phone backs, PCB circuit traces |
| Magnifier sticker zoom-through | Camera-lens sticker zoom-through |
| Crash zoom into chessboard | Crash zoom into the watches on the desk |
