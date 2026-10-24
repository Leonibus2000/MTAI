# Edit timeline (reverse-engineered from the Hikaru reference)

Reference: 576×576, 30 fps, 267 frames (8.90 s), HEVC + AAC. Music is about 110 BPM, with an accent every ~8 frames. Cuts land on accents every 16–18 frames.

Detected audio onsets (frame): 2, 20, 28, 36, 45, 53, 61, 69, 73, 94, 102, 118, 126, 135, 151, 159, 167, 176, 184, 200, 204, 216, 225, 233, 241, 249, 257, 266

Camera numbers come from optical flow on the reference (`ana/motion.py`): per-frame zoom, rotation and translation around every cut.

| Shot | Time | Frames | Reference content | Recreation (Mrwhosetheboss / tech) | Cutout | Camera in shot | Cut into this shot |
|---|---|---|---|---|---|---|---|
| S01 | 0.00–0.70s | 0–20 | Hikaru CU glaring, tilted white frame, striped rook stickers, halftone dot bg | Close-up, intense stare straight into lens (studio intro) | person | push +0.5%/f, spin +0.10°/f, tilt -3° | in: whip 150/4f; in: push 0.03; shake 14px |
| S02 | 0.70–1.30s | 21–38 | Hikaru ECU, heavy posterize + halftone, tilted frame, pixel-stair edge graphics | Extreme close-up of face, serious / unimpressed expression | person (erase) | push +0.2%/f, spin +0.45°/f, tilt -2° | out: zoom 0.55/5f; in: push 0.06; shake 12px; 2-frame overlap |
| S03 | 1.30–1.83s | 39–54 | Hikaru pointing, checkerboard bg, white outline | Medium shot, pointing a finger / gesturing at camera | person | push +1.0%/f, spin -0.60°/f, tilt 2° | out: pull 0.3/4f; in: whip 90/2f; in: push 0.25; flash 0.22; shake 14px; 2-frame overlap |
| S04 | 1.83–2.43s | 55–72 | Hikaru with glasses, hand on chin, diagonal stripe bg | Thinking pose, hand on chin, looking off-camera | person | push +0.4%/f, spin -0.30°/f, tilt 1°, exposure (0.8, 0.62) | out: whip 150/4f; out: zoom 0.16/3f; in: whip 50/2f; in: push 0.14; shake 12px; 2-frame overlap |
| S05 | 2.43–3.37s | 73–100 | Hikaru hand over mouth; 'HIKARU the GREAT' glitch text slides in; icons pop at f89 | Hand over mouth / leaning in, mid close-up | person | push +0.6%/f, spin -0.50°/f, exposure (0.62, 1.1) | out: glitch/4f; out: dip 0.3/4f; in: push 0.06; shake 10px; 2-frame overlap |
| S06 | 3.37–4.40s | 101–131 | Dark bg, floating stickers (rocket, bolt, stopwatch); two hands fly in at f116 | Procedural tech stickers only (phones fly in instead of hands) | – | push +0.0%/f, spin +0.12°/f, exposure 0.75 | out: pull 0.06/2f; in: defocus 7/5f |
| S07 | 4.40–4.97s | 132–148 | Hikaru looking down, 'MUHMA' pixel badge on gem sticker, icons orbit | Close-up, side-eye at a phone / product in hand | held (add) | push +0.3%/f, spin -0.30°/f, exposure 0.85 | out: defocus 10/3f; out: dip 0.4/3f; in: defocus 8/3f; in: pull 0.1; shake 6px |
| S08 | 4.97–5.63s | 149–168 | Hikaru profile looking up, hand on chin, chessboard bg, inner hand outline | Profile / three-quarter, looking up, finger on chin | person | push +1.7%/f, spin +0.30°/f, tilt -2°, exposure 0.85 | out: whip 90/2f; out: spin 3/2f; in: whip 45/2f; shake 12px; 2-frame overlap |
| S09 | 5.63–6.07s | 169–181 | Hikaru hands clasped, repeated 'GENIUS' text wall bg | Hands clasped under chin, focused stare | held (add) | push +0.0%/f, spin +0.00°/f, exposure (0.75, 0.95) | out: spin -32/4f; out: zoom 0.25/4f; out: whip 80/4f; in: pull 0.3; in: spin -5/5f; shake 10px; 2-frame overlap |
| S10 | 6.07–6.67s | 182–199 | Torn-paper diagonal split with halftone; circular sticker zooms through at f196 | Close-up reaction, shocked / surprised face | held (inpaint) | push +0.4%/f, spin +0.25°/f, exposure 1.3 | out: zoom 0.4/4f; out: spin 7/4f; in: push 0.32; shake 14px; 2-frame overlap |
| S11 | 6.67–7.33s | 200–219 | Hikaru at board; camera crash-zooms into the board f213-218 | At desk with phones / unboxing, looking at a device | person | push +0.8%/f, spin -0.10°/f, exposure (1.0, 1.12) | out: zoom 0.1/3f; out: whip 40/2f; in: lens /2f; in: whip 30/2f; flash 0.15; shake 10px; 2-frame overlap |
| S12 | 7.33–7.93s | 220–237 | Two players at angled board, white outlines | Holding a phone up to camera / comparing two phones | held (add, erase) | push +1.5%/f, spin +0.45°/f, tilt -2°, exposure 0.95 | out: crash 0.7/7f; out: whip 200/5f; out: bright 0.4/6f; in: whip 70/5f; shake 10px; 2-frame overlap |
| S13 | 7.93–8.47s | 238–253 | Hikaru big smile, LED light-bar bg, outline | Big genuine smile / laugh, close-up | person | push +0.3%/f, spin +0.30°/f, exposure 1.1 | out: whip 170/5f; out: zoom 0.3/5f; in: push 0.2; shake 14px; 2-frame overlap |
| S14 | 8.47–8.90s | 254–266 | Hikaru holding board, chess-piece backdrop, end blur | Outro: holding a product, phone wall behind | held (add) | push +1.6%/f, spin -0.50°/f, exposure 1.15 | out: pull 0.38/5f; out: spin 7/5f; out: whip 50/2f; in: push 0.08; shake 12px; 2-frame overlap |

## Camera and transitions (`camera.py`)

Every shot has one continuous camera path, and every frame is rendered by sampling that path at up to 28 instants inside an 0.8-frame shutter. Motion blur therefore follows the real motion: radial for zooms, arcs for spins, streaks for whips. Before v3, blur was a fixed filter added on top.

- **Exits** accelerate into the cut (u²): zoom-in, pull-back, whip, spin, crash zoom on a point, defocus, exposure dip or brightening, glitch.
- **Arrivals** decelerate out of the cut (v²): whip settle, spin settle, defocus clear, lens sticker exit, and *push*/*pull* zoom settles with a time constant. The reference measures +4–8 %/frame of zoom right after most cuts, decaying over about 5 frames.
- **Splice:** moves are centred half a frame before the first new frame. On motion cuts the last old frame and the first new frame each blend 24% of the other shot, both mid-move, so the splice hides inside the blur.
- **Hold motion:** a steady push-in (0–1.7 %/frame) and rotation drift (up to ±0.6°/frame), matching the reference's measured holds. Handheld jitter is a Catmull-Rom spline through random targets, so it is continuous and blurs. Its amplitude bursts on each cut (10–14 px) and on each music onset (×6.5), then decays.
- **Exposure** follows the reference's brightness curve per shot: the dark S04→S05 dip, the dark S06 sticker interlude, and the bright S10–S11 section.
- **Measured result** (holds, frames more than 4 from a cut): median motion 5.3 px/frame vs the reference's 6.0, median sharpness 1702 vs 1719. Before v3 the figures were 2.4 px/frame and 2697: too steady and too crisp.

## Cutouts (`cutout.py`)

- **Person matte:** BiRefNet-portrait at 1024 px. It replaced u2net_human_seg, which fragmented on busy backgrounds: carpet chunks in S08, a missing arm and watches in S11, and a rectangular crop edge in S13.
- **Held mode:** adds BiRefNet-general components that touch him, so phones and consoles in his hands stay attached to his fingers instead of fingers floating in mid-air. Per-shot `add` polygons complete devices the models only half-find. The S07 Fold and S12 Pixel needed this.
- **Cleanup:** hard threshold with smoothstep, then drop components under 5% of the largest, fill pinholes, and a 1.4 px contour smooth.
- **Per-shot fixes:** an `erase` polygon for the cropped phone sliver in S02 and the off-frame fingers in S12. An `inpaint` pass removes the neon line baked into the S10 thumbnail.
- **Mattes are cached** as `footage/<id>_person.png` / `_general.png`. Each inference runs in its own process with onnxruntime's memory arena off (about 8 GB peak, about 1 minute per image on CPU).

## Global treatment (every frame)

- Grayscale with contrast ×1.3. Posterize (bilateral filter, then 4–5 levels mixed 60/40 with the smooth image) on the 'graphic' shots.
- Halftone: a 45° dot screen applied mostly in the subject's midtones, plus a dot-grid pattern in the `dots` backgrounds.
- White subject outline: the matte dilated 6 px, with the edge jittered every 3 frames so it reads as a hand-cut sticker.
- Vignette, then per-frame blurred film grain (σ≈0.05), then gamma 1.05.

## Typography

- S05 title: 'ARUN / the / BOSS' in Anton (replaces 'HIKARU the GREAT'). It slides in from the left over 14 frames, clipped at the frame edge, with glitch-sliced rows while moving.
- S07 editor watermark: **MTD** (replaces the reference's 'MUHMA' tag). Tall VT323 pixel lettering, white with a black keyline and inner black hairlines, on a white die-cut badge. It pops in over frames 0–2, holds, then breaks up into vertical strips on frames 11–15.
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
| Crash zoom into chessboard | Crash zoom into the watches on the desk |
