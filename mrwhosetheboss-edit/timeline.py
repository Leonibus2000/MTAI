"""Shot timeline reverse-engineered from the Hikaru reference (30 fps, 267 frames, 8.9 s).

The edit loops: it is 16 beats long and its last shot whips into the first one.

Frame numbers are reference frame indices. Cuts land on detected audio onsets
(~110 BPM, a hit every ~8 frames; cuts every ~16-18 frames). Camera numbers come from
optical-flow measurements of the reference (ana/motion.py): per-frame zoom, rotation and
translation around every cut.
"""

FPS = 30
# 16 beats at 110 BPM (4 bars): a whole number of beats, so the rhythm carries straight across the
# loop seam. The reference's 267 frames (16.3 beats) would leave a stumble of 0.17 s at every repeat.
N_FRAMES = 262
SIZE = 576

# cam: push = log-zoom per frame (0.017 ~ +1.7 %/frame), spin = deg/frame, rot0 = starting tilt,
#      pan = px/frame drift, shake = base jitter px, exposure = gain or (start, end) ramp,
#      zoom_to = push into a point of the shot and stay (frame in shot, frames, log-zoom, (x, y)),
#      jolt = a fast out-and-back camera move inside the shot (frame in shot, frames, dx, dy)
#      exposure is a tone curve: < 1 darkens midtones but keeps highlights, > 1 lifts them
# cutout: "person" (portrait matte) or "held" (person plus the devices in his hands)
SHOTS = [
    dict(id="S01", start=0, framing="cu", need="Close-up, intense stare straight into lens (studio intro)",
         ref="Hikaru CU glaring, tilted white frame, striped rook stickers, halftone dot bg",
         look=dict(poster=4, halftone=0.35), bg="dots", overlays=["tilt_rect", "striped_phones"], cutout="person",
         cam=dict(push=0.005, rot0=-3, spin=0.1, shake=1.5)),
    dict(id="S02", start=21, framing="ecu", need="Extreme close-up of face, serious / unimpressed expression",
         ref="Hikaru ECU, heavy posterize + halftone, tilted frame, pixel-stair edge graphics",
         look=dict(poster=5, halftone=0.6), bg="dots", overlays=["tilt_rect2", "pixel_stairs"], cutout="person",
         erase=[[(0, 318), (62, 328), (80, 380), (78, 470), (84, 520), (92, 576), (0, 576)]],  # phone + fingers bottom-left
         cam=dict(push=0.002, rot0=-2, spin=0.45, shake=1.5)),
    dict(id="S03", start=39, framing="ms", need="Medium shot, pointing a finger / gesturing at camera",
         ref="Hikaru pointing, checkerboard bg, white outline",
         look=dict(poster=0, halftone=0.15), bg="app_grid", overlays=[], cutout="person",
         cam=dict(push=0.010, rot0=2, spin=-0.6, shake=2.0)),
    dict(id="S04", start=55, framing="mcu", need="Thinking pose, hand on chin, looking off-camera",
         ref="Hikaru with glasses, hand on chin, diagonal stripe bg",
         look=dict(poster=4, halftone=0.25), bg="stripes", overlays=[], cutout="person",
         cam=dict(push=0.004, rot0=1, spin=-0.3, shake=1.5, exposure=(0.7, 0.5))),
    dict(id="S05", start=70, framing="mcu", need="Hand over mouth / leaning in, mid close-up",
         ref="Hikaru hand over mouth; glitch cut in, 'HIKARU the' flickers on, 'GREAT' lands f80; icons pop at f89",
         look=dict(poster=4, halftone=0.3), bg="pcb_photo", overlays=["title_text", "icons_pop"], cutout="person",
         subject_offset=(160, 0), subject_scale=0.94,  # him right of centre, the title on the left behind him
         focus=(230, 230),  # camera pivots between the title and his face, so the push-in keeps both in frame
         cam=dict(push=0.002, spin=-0.4, shake=1.5, exposure=(0.95, 1.25), zoom_to=[(8, 5, 0.15, (230, 230))],
                  jolt=[(12.6, 2, 55, -25)]),
         # title flicker copied from the reference: on/off per frame, BOSS arrives with the zoom
         title=dict(off=(1, 3), glitch={0: 0.5, 2: 0.6, 4: 1.0, 5: 0.4, 18: 0.7}, boss_at=10, boss_off=(11,)),
         icons_at=89),
    dict(id="S06", start=101, framing=None, need=None,
         ref="Dark bg, floating stickers (rocket, bolt, stopwatch); two hands fly in at f116",
         look=dict(poster=0, halftone=0.0), bg="dark", overlays=["icon_field", "phones_fly_in"],
         cam=dict(push=0.0, spin=0.12, shake=0.4, beat=1.5, exposure=1.0, jolt=[(13.6, 2, 70, -10)])),
    dict(id="S07", start=132, framing="cu", need="Close-up, side-eye at a phone / product in hand",
         ref="Hikaru looking down, 'MUHMA' pixel badge on gem sticker, icons orbit",
         look=dict(poster=0, halftone=0.2), bg="dark", overlays=["badge", "icon_orbit"], cutout="held",
         add=[[(432, 50), (450, 44), (576, 44), (576, 500), (436, 500), (422, 488), (420, 70)]],  # Fold in right hand
         cam=dict(push=0.003, spin=-0.3, shake=2.0, exposure=0.7)),
    dict(id="S08", start=149, framing="mcu", need="Profile / three-quarter, looking up, finger on chin",
         ref="Hikaru profile looking up, hand on chin, chessboard bg, inner hand outline",
         look=dict(poster=0, halftone=0.15), bg="circuit", overlays=[], cutout="person",
         cam=dict(push=0.017, rot0=-2, spin=0.3, shake=1.5, exposure=0.85)),
    dict(id="S09", start=169, framing="mcu", need="Hands clasped under chin, focused stare",
         ref="Hikaru hands clasped, repeated 'GENIUS' text wall bg",
         look=dict(poster=0, halftone=0.2), bg="text_wall", overlays=[], cutout="held",
         add=[[(512, 136), (530, 128), (576, 124), (576, 576), (420, 576), (440, 480), (471, 330), (500, 190)]],  # Vertu
         cam=dict(push=0.0, shake=1.5, exposure=(0.75, 0.95))),
    dict(id="S10", start=182, framing="cu", need="Close-up reaction, shocked / surprised face",
         ref="Torn-paper diagonal split with halftone; circular sticker zooms through at f196",
         look=dict(poster=4, halftone=0.55), bg="dots", overlays=["tear"], cutout="held",
         inpaint=dict(hue=(80, 112), sat=90, val=170, region=[(0, 470), (576, 430), (576, 576), (0, 576)]),
         cam=dict(push=0.004, spin=0.25, shake=1.5, exposure=1.5)),
    dict(id="S11", start=200, framing="ms", need="At desk with phones / unboxing, looking at a device",
         ref="Hikaru at board; camera crash-zooms into the board f213-218",
         look=dict(poster=0, halftone=0.15), bg="phone_wall", overlays=["crash_zoom"], cutout="person",
         cam=dict(push=0.008, spin=-0.1, pan=(-5, 0), shake=1.5, exposure=(1.1, 1.25))),
    dict(id="S12", start=220, framing="ms", need="Holding a phone up to camera / comparing two phones",
         ref="Two players at angled board, white outlines",
         look=dict(poster=0, halftone=0.2), bg="app_grid", overlays=["held_phone"], cutout="held",
         add=[[(0, 80), (120, 72), (150, 80), (168, 100), (176, 140), (182, 300), (186, 576), (0, 576)]],  # Pixel 9a
         erase=[[(528, 334), (576, 330), (576, 446), (540, 446)]],  # fingers of the off-frame hand
         cam=dict(push=0.015, rot0=-2, spin=0.45, pan=(-3, 0), shake=1.5, exposure=0.85)),
    dict(id="S13", start=238, framing="cu", need="Big genuine smile / laugh, close-up",
         ref="Hikaru big smile, LED light-bar bg, outline",
         look=dict(poster=0, halftone=0.15), bg="light_bars", overlays=[], cutout="person",
         cam=dict(push=0.003, spin=0.3, shake=1.5, exposure=1.2)),
    dict(id="S14", start=250, framing="ms", need="Outro: holding a product, phone wall behind",
         ref="Hikaru holding board, chess-piece backdrop, end blur",
         look=dict(poster=0, halftone=0.2), bg="phone_wall", overlays=["held_phone"], cutout="held",
         add=[[(0, 440), (576, 432), (576, 576), (0, 576)]],  # keep the table of phones he sits behind
         cam=dict(push=0.016, spin=-0.5, shake=1.5, exposure=1.15)),
]

# Audio accents (frame numbers) from onset detection on the reference track; drive shake kicks.
ONSETS = [2, 20, 28, 36, 45, 53, 61, 69, 73, 94, 102, 118, 126, 135, 151, 159, 167, 176, 184, 200,
          204, 216, 225, 233, 241, 249, 257]

for i, s in enumerate(SHOTS):
    s["end"] = SHOTS[i + 1]["start"] if i + 1 < len(SHOTS) else N_FRAMES

# Camera move at every cut, matched to the reference's measured motion.
#   exit:   moves that accelerate (u^2) into the cut over `frames`
#   arrive: moves of the next shot that start at the cut and decelerate
#   whip angle = direction the picture travels (deg, y down), dist = px at the cut
#   zoom/pull/crash amount = log-zoom at the cut, spin deg = degrees at the cut,
#   push = arrival zoom-in that settles (amount, time constant T), pull = starts zoomed in and backs out
#   shake = jitter burst (px) fired at the cut, flash = white lift, overlap = 2-frame streaked blend
#   wipe = next shot smeared in from the right before the cut (cover fraction and smear px per frame)
#   comp = a designed transition from transitions.py instead of a camera move (pre/post frames around the cut,
#          shutter = motion-blur exposure in frames, 0.8 unless set)
#   smear_in = per-frame horizontal smear / echo / darkening of the new shot's first frames
CUTS = {
    # Where the edit departs from the reference: designed transitions (transitions.py) replace its most
    # recognisable cuts - the opening whip, the zoom-in, the spin-out, the defocus dip, the magnifier
    # zoom-through - and the remaining whips run in other directions.
    0: dict(comp=dict(type="island", pre=2, post=4), arrive=[("push", dict(amount=0.05, T=5))], shake=10),
    21: dict(comp=dict(type="strips", pre=2, post=3), arrive=[("push", dict(amount=0.06, T=5))], shake=12),
    39: dict(exit=[("pull", dict(frames=4, amount=0.30))],
             arrive=[("whip", dict(frames=2, angle=128, dist=90)), ("push", dict(amount=0.25, T=5))],
             flash=0.22, shake=14),
    55: dict(exit=[("whip", dict(frames=4, angle=36, dist=150)), ("zoom", dict(frames=3, amount=0.16))],
             arrive=[("whip", dict(frames=2, angle=36, dist=50)), ("push", dict(amount=0.14, T=6))], shake=12),
    # Reference: the next shot smears in from the right over the last 3 frames, then flickers for 4.
    70: dict(wipe=dict(cover=(0.22, 0.42, 0.64), smear=(40, 64, 90)),
             smear_in={0: dict(blur=22, echo=(40, 0.45)), 1: dict(blur=48, echo=(56, 0.4), dark=0.72),
                       2: dict(blur=14, echo=(26, 0.35))},
             arrive=[("push", dict(amount=0.03, T=4))], shake=10),
    # the title shot closes like an app into the 9V icon of the interlude, which plays the home screen
    101: dict(comp=dict(type="app_close", pre=2, post=4, icon=0, shutter=0.55), shake=6),
    # dive into the screen of the iPhone at the left edge of the interlude, where the MTD shot is playing
    132: dict(comp=dict(type="portal", pre=5, fly=0), arrive=[("push", dict(amount=0.08, T=3))], shake=8),
    149: dict(exit=[("whip", dict(frames=2, angle=40, dist=90)), ("spin", dict(frames=2, deg=-3))],
              arrive=[("whip", dict(frames=2, angle=40, dist=45))], shake=12),
    # the next Arun rises in front as a sticker while the profile shot racks out of focus; lands on the hit
    169: dict(comp=dict(type="pop_in", pre=3, post=2, shutter=0.35), shake=14),
    182: dict(exit=[("zoom", dict(frames=4, amount=0.40)), ("spin", dict(frames=4, deg=7))],
              arrive=[("push", dict(amount=0.32, T=4))], shake=14),
    200: dict(comp=dict(type="phone_wipe", pre=3, post=3, phone="phone_galaxy_s7_front", scale=1.6, lean=14),
              shake=12),
    220: dict(exit=[("crash", dict(frames=7, amount=0.70, focus=(280, 500))),
                    ("whip", dict(frames=5, angle=0, dist=200)), ("bright", dict(frames=6, amount=0.4))],
              arrive=[("whip", dict(frames=5, angle=0, dist=70))], shake=10),
    238: dict(exit=[("whip", dict(frames=5, angle=270, dist=170)), ("zoom", dict(frames=5, amount=0.30))],
              arrive=[("push", dict(amount=0.20, T=5))], shake=14),
    # Reference cut at 254; here on the onset at 249 so the last shot keeps 12 frames before the loop.
    250: dict(exit=[("pull", dict(frames=5, amount=0.38)), ("spin", dict(frames=5, deg=7)),
                    ("whip", dict(frames=2, angle=139, dist=50))],
              arrive=[("push", dict(amount=0.08, T=5))], shake=12),
    # Loop seam: the opening shot expands out of a Dynamic Island pill over the end of the outro.
    N_FRAMES: dict(),
}
# The end cut and the start cut are one splice, so both ends of the edit see its exit and arrival.
CUTS[0] = CUTS[N_FRAMES] = {**CUTS[N_FRAMES], **CUTS[0]}
