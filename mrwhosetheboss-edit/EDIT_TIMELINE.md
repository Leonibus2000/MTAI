# Edit timeline (reverse-engineered from the Hikaru reference)

Reference: 576×576, 30 fps, 267 frames (8.90 s), HEVC + AAC. Music is about 110 BPM, with an accent every ~8 frames. Cuts land on accents every 16–18 frames.

**This edit loops.** It is 262 frames (8.73 s), exactly 16 beats, and its last shot whips into its first. See *Loop* below.

Detected audio onsets (frame): 2, 20, 28, 36, 45, 53, 61, 69, 73, 94, 102, 118, 126, 135, 151, 159, 167, 176, 184, 200, 204, 216, 225, 233, 241, 249, 257, 266

Camera numbers come from optical flow on the reference (`analyze_motion.py`): per-frame zoom, rotation and translation around every cut.

| Shot | Time | Frames | Reference content | Recreation (Mrwhosetheboss / tech) | Cutout | Camera in shot | Cut into this shot |
|---|---|---|---|---|---|---|---|
| S01 | 0.00–0.70s | 0–20 | Hikaru CU glaring, tilted white frame, striped rook stickers, halftone dot bg | Close-up, intense stare straight into lens (studio intro) | person | push +0.5%/f, spin +0.10°/f, tilt -3° | loop seam from S14: **Dynamic Island expand** (2 frames before / 4 after); in: push 0.05; shake 10px |
| S02 | 0.70–1.30s | 21–38 | Hikaru ECU, heavy posterize + halftone, tilted frame, pixel-stair edge graphics | Extreme close-up of face, serious / unimpressed expression | person (erase) | push +0.2%/f, spin +0.45°/f, tilt -2° | **sliding slats** (2 frames before / 3 after); in: push 0.06; shake 12px |
| S03 | 1.30–1.83s | 39–54 | Hikaru pointing, checkerboard bg, white outline | Medium shot, pointing a finger / gesturing at camera | person | push +1.0%/f, spin -0.60°/f, tilt 2° | out: pull 0.3/4f; in: whip 90 @128°/2f; in: push 0.25; flash 0.22; shake 14px; 2-frame overlap |
| S04 | 1.83–2.33s | 55–69 | Hikaru with glasses, hand on chin, diagonal stripe bg | Thinking pose, hand on chin, looking off-camera | person | push +0.4%/f, spin -0.30°/f, tilt 1°, exposure (0.7, 0.5) | out: whip 150 @36°/4f; out: zoom 0.16/3f; in: whip 50 @36°/2f; in: push 0.14; shake 12px; 2-frame overlap |
| S05 | 2.33–3.37s | 70–100 | Hikaru hand over mouth; glitch cut in, 'HIKARU the' flickers on, 'GREAT' lands f80; icons pop at f89 | Hand over mouth / leaning in, mid close-up | person | push +0.4%/f, spin -0.40°/f, exposure (0.7, 0.9), zoom-in to (20, 150) at f78–83 and hold | out: next shot smears in from the right over the last 3f; in: push 0.03; in: 3-frame smear/echo flicker; shake 10px |
| S06 | 3.37–4.40s | 101–131 | Dark bg, floating stickers (rocket, bolt, stopwatch); two hands fly in at f116 | Real photos of batteries drifting; two real phones whip in from the sides instead of hands | – | push +0.0%/f, spin +0.12°/f, exposure 0.75 | **iOS app close** (2 frames before / 4 after); shake 6px |
| S07 | 4.40–4.97s | 132–148 | Hikaru looking down, 'MUHMA' pixel badge on gem sticker, icons orbit | Close-up, side-eye at a phone / product in hand | held (add) | push +0.3%/f, spin -0.30°/f, exposure 0.7 | **dive into the phone screen** (5 frames before / 0 after); in: push 0.08; shake 8px |
| S08 | 4.97–5.63s | 149–168 | Hikaru profile looking up, hand on chin, chessboard bg, inner hand outline | Profile / three-quarter, looking up, finger on chin | person | push +1.7%/f, spin +0.30°/f, tilt -2°, exposure 0.85 | out: whip 90 @40°/2f; out: spin -3/2f; in: whip 45 @40°/2f; shake 12px; 2-frame overlap |
| S09 | 5.63–6.07s | 169–181 | Hikaru hands clasped, repeated 'GENIUS' text wall bg | Hands clasped under chin, focused stare | held (add) | push +0.0%/f, spin +0.00°/f, exposure (0.75, 0.95) | **sticker pop-in** (3 frames before / 2 after); shake 14px |
| S10 | 6.07–6.67s | 182–199 | Torn-paper diagonal split with halftone; circular sticker zooms through at f196 | Close-up reaction, shocked / surprised face | held (inpaint) | push +0.4%/f, spin +0.25°/f, exposure 1.5 | out: zoom 0.4/4f; out: spin 7/4f; in: push 0.32; shake 14px; 2-frame overlap |
| S11 | 6.67–7.33s | 200–219 | Hikaru at board; camera crash-zooms into the board f213-218 | At desk with phones / unboxing, looking at a device | person | push +0.8%/f, spin -0.10°/f, exposure (1.1, 1.25) | **real-phone wipe** (3 frames before / 3 after); shake 12px |
| S12 | 7.33–7.93s | 220–237 | Two players at angled board, white outlines | Holding a phone up to camera / comparing two phones | held (add, erase) | push +1.5%/f, spin +0.45°/f, tilt -2°, exposure 0.85 | out: crash 0.7/7f; out: whip 200 @0°/5f; out: bright 0.4/6f; in: whip 70 @0°/5f; shake 10px; 2-frame overlap |
| S13 | 7.93–8.33s | 238–249 | Hikaru big smile, LED light-bar bg, outline | Big genuine smile / laugh, close-up | person | push +0.3%/f, spin +0.30°/f, exposure 1.2 | out: whip 170 @270°/5f; out: zoom 0.3/5f; in: push 0.2; shake 14px; 2-frame overlap |
| S14 | 8.33–8.73s | 250–261 | Hikaru holding board, chess-piece backdrop, end blur | Outro: holding a product, phone wall behind | held (add) | push +1.6%/f, spin -0.50°/f, exposure 1.15 | out: pull 0.38/5f; out: spin 7/5f; out: whip 50 @139°/2f; in: push 0.08; shake 12px; 2-frame overlap |

## Camera and transitions (`camera.py`)

Every shot has one continuous camera path, and every frame is rendered by sampling that path at up to 28 instants inside an 0.8-frame shutter. Motion blur therefore follows the real motion: radial for zooms, arcs for spins, streaks for whips.

- **Exits** accelerate into the cut (u²): zoom-in, pull-back, whip, spin, crash zoom on a point, defocus, exposure dip or brightening, glitch.
- **Arrivals** decelerate out of the cut (v²): whip settle, spin settle, defocus clear, lens sticker exit, and *push*/*pull* zoom settles. The reference measures +4–8 %/frame of zoom right after most cuts, decaying over about 5 frames.
- **Splice:** moves are centred half a frame before the first new frame. On motion cuts the last old frame and the first new frame each blend 24% of the other shot, both mid-move.
- **In-shot moves:** `zoom_to` pushes into a point of the shot and holds there; `jolt` is a fast out-and-back move that streaks both ways in 2 frames.
- **Hold motion:** a steady push-in (0–1.7 %/frame) and rotation drift (up to ±0.6°/frame). Handheld jitter is a Catmull-Rom spline through random targets, so it is continuous and blurs. Its amplitude bursts on each cut and each music onset, then decays.
- **Exposure** is a tone curve. Below 1 it darkens midtones but keeps highlights, so dark sections stay contrasty instead of turning muddy grey. Above 1 it lifts midtones but keeps black.

### Transitions that depart from the reference (`transitions.py`)

Six cuts use transitions the reference doesn't have, mostly built from the real phone photos, and four
of the remaining whips run in other directions (55: up-right instead of down-left; 149: up-right with the
spin reversed; 220: right instead of left; 238: up instead of left). They still land on the same
music hits. Each one blends both shots across the cut. Fast geometry gets motion blur from averaging
up to 24 instants inside the shutter (the count adapts to how far the edges travel), so it blurs
instead of ghosting.

| Cut | Reference | This edit |
|---|---|---|
| 0.00 s (loop seam) | whip in from the top right | **Dynamic Island:** S01 plays in a pill at the top of the screen, then the pill expands into the frame over the dimming outro |
| 0.70 s | zoom into the face, hard cut | **Sliding slats:** six vertical slats; alternate ones slide the next shot in from the top and the bottom, staggered left to right, with white seams |
| 3.37 s | pull back, defocus | **iOS app close:** the title shot shrinks into a rounded card like a closing app, lifts, and flies into the 9V battery, one of the three "icons" on the dark interlude that plays the home screen, which springs back behind it |
| 4.40 s | defocus dip | **Dive into the phone screen:** the MTD shot starts playing on the screen of the iPhone at the left edge (it flashes on), then the camera dives in until the screen fills the frame |
| 5.63 s | 32° spin-out | **Sticker pop-in:** the next shot's Arun pops up from the bottom as a white-bordered cut-out sticker at 70% size, in front of the profile shot, which racks out of focus and dims behind him. On the music hit he punches in to full size as his own background slams in with a white flash and a camera jolt |
| 6.67 s | magnifier sticker zoom-through | **Real-phone wipe:** a giant Galaxy S6 Edge slams in from the right, pauses mid-frame over the cut like a product shot, then shoots out left; the next shot is revealed behind it |

### The S04 → S05 glitch cut (2.33 s)

The reference's real cut here is at frame 70, not 73 (frame-difference detection had picked the end of the glitch). Frame by frame:

| Frames | Reference | Recreation |
|---|---|---|
| 67–69 | Next shot appears as a horizontally smeared slab from the right edge, growing to ~60 % | `wipe`: S05 smeared 40→90 px, revealed from the right over 22 / 42 / 64 % behind a ragged soft seam; S04 streaks along the seam |
| 70 | New shot, smeared with a double image, title visible | 22 px smear + 40 px echo, title on (lightly glitched) |
| 71 | Darker, heavier smear, no title | 48 px smear + 56 px echo, ×0.72, title off |
| 72 | Lighter smear, title visible | 14 px smear + 26 px echo, title on |
| 73 | Crisp, title off | crisp, title off |
| 74–79 | 'HIKARU / the' with a glitch on the lettering, then static | 'ARUN / the' with sliced rows and a horizontal ghost on f74, then static |
| 80–82 | 'GREAT' appears (off on 81) as the camera pushes in | 'BOSS' pops in (off on 81) as the camera pushes in |
| 83–84 | Two heavily streaked frames | 2-frame `jolt` (55, −25 px out and back) |
| 85–100 | Tight hold on the title + face; stickers slam in at the edges on f89 | Zoom ×1.27 pivoting between the title and his face so both stay in frame; real photos of an iPhone 12 Pro, a Duracell AA and a power bank fly in at the frame edges on f89 (screen space, after the exposure curve so they stay bright like the reference's stickers) |

## Loop

- **Length:** 262 frames = 8.73 s = 16 beats (4 bars) at 110 BPM. The reference's 267 frames are 16.3 beats. Looped as-is, the gap between the last beat and the first would be 0.72 s instead of 0.55 s, a stumble at every repeat.
- **Shot timing:** the S13 → S14 cut moves from the reference's 254 onto the music hit at 250, so the outro keeps 12 frames.
- **Seam transition:** a Dynamic Island. Over the last 2 frames of S14 a small pill opens at the top of the frame with S01 playing inside it; over the first 4 frames of S01 it expands into the full frame, with a slight overshoot. S14 dims and shrinks behind it, like an app opening on iOS. The renderer wraps around for this: before S01 comes S14, one loop later in its own timeline.
- **Audio:** the first 45 ms of the file crossfade (equal power) from the music that follows the loop point into the real start. On repeat, the sound continues the uncut track across the seam (waveform correlation 0.995).
- **Audio length:** rounded down to whole AAC frames (376 × 1024 samples = 8.7307 s, 2.6 ms short of the video). A partial last frame gets zero padding that only some players trim. FFmpeg, and so most upload pipelines, does not, which would leave a 21 ms dropout and a click at every repeat. Players that loop on the audio get a sample-continuous seam. Players that loop on the video get a 2.6 ms gap, softened by 1.5 ms fades.
- **Checks:** a 3× concatenation shows no duplicated frames at the seams. The high-frequency energy at each audio seam is below the median of the surrounding music, so there is no click.

## Cutouts (`cutout.py`)

- **Person matte:** BiRefNet-portrait at 1024 px. It replaced u2net_human_seg, which fragmented on busy backgrounds.
- **Held mode:** adds BiRefNet-general components that touch him, so devices in his hands stay attached. Per-shot `add` polygons complete devices the models only half-find.
- **Cleanup:** hard threshold with smoothstep, then drop components under 5% of the largest, fill pinholes, and a 1.4 px contour smooth.
- **Per-shot fixes:** `erase` polygons (S02 phone sliver, S12 off-frame fingers) and an `inpaint` pass for the S10 neon line.
- **Mattes are cached** as `footage/<id>_person.png` / `_general.png`. About 8 GB peak, about 1 minute per image on CPU.

## Global treatment (every frame)

- Grayscale with contrast ×1.3. Posterize (bilateral filter, then 4–5 levels mixed 60/40 with the smooth image) on the 'graphic' shots.
- Halftone: a 45° dot screen applied mostly in the subject's midtones, plus a dot-grid pattern in the `dots` backgrounds.
- White subject outline: the matte dilated 6 px, with the edge jittered every 3 frames so it reads as a hand-cut sticker.
- Vignette, then per-frame blurred film grain (σ≈0.05), then gamma 1.05.

## Typography

- S05 title: 'ARUN / the' (replaces 'HIKARU the') is on screen from the cut and flickers with the glitch frames. 'BOSS' (replaces 'GREAT') lands on f80 with the zoom. As in the reference, it's bold pixel type (Pixelify Sans Bold) with an LED-dot texture and a soft glow, sitting **behind** him on a real circuit-board photo: he's moved right of centre (`subject_offset`) and covers the edge of the last letters, like Hikaru covers the 'U' of HIKARU.
- S07 editor watermark: **MTD** (replaces the reference's 'MUHMA' tag). Tall VT323 pixel lettering, white with a black keyline and inner black hairlines, on a white die-cut badge. It pops in over frames 0–2, holds, then breaks up into vertical strips on frames 11–15.
- S09 wall: repeated 'TECH' in Anton, scrolling (replaces 'GENIUS').

## Chess → tech substitutions

| Reference | Recreation |
|---|---|
| Striped rook graphics | Striped phone silhouettes |
| Rocket / bolt / stopwatch stickers | Real photos (CC BY / CC0, see CREDITS.md) of a Galaxy S6 Edge and an iPhone 12 Pro, and of batteries: Duracell AA / AAA / 9V, a 2 Ah LiPo cell and a Xiaomi power bank. All are cut out with BiRefNet as black-and-white die-cut stickers with a soft shadow (`props.py`) |
| Hands flying in | Two real phones (iPhone 12 Pro, Galaxy S21) whip in from the sides with motion blur and hold at the frame edges |
| Checkerboard backgrounds | Rounded app-icon grid |
| Chessboard / chess-piece walls | Wall of phone backs, PCB circuit traces |
| Magnifier sticker zoom-through | Dropped: a real Galaxy S6 Edge slides in and pauses mid-frame as the wipe into the desk shot |
| Crash zoom into chessboard | Crash zoom into the watches on the desk |
