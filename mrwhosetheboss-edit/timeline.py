"""Shot timeline reverse-engineered from the Hikaru reference (30 fps, 267 frames, 8.9 s).

Frame numbers are reference frame indices. Cuts land on detected audio onsets
(~110 BPM, a hit every ~8 frames; cuts every ~16-18 frames).
"""

FPS = 30
N_FRAMES = 267
SIZE = 576

# start frame, footage slot description, framing, look, background, overlays, camera
SHOTS = [
    dict(id="S01", start=0, framing="cu", need="Close-up, intense stare straight into lens (studio intro)",
         ref="Hikaru CU glaring, tilted white frame, striped rook stickers, halftone dot bg",
         look=dict(poster=4, halftone=0.35), bg="dots", overlays=["tilt_rect", "striped_phones"],
         cam=dict(z=(1.06, 1.0), rot=(-4, -1), shake=2.0)),
    dict(id="S02", start=21, framing="ecu", need="Extreme close-up of face, serious / unimpressed expression",
         ref="Hikaru ECU, heavy posterize + halftone, tilted frame, pixel-stair edge graphics",
         look=dict(poster=5, halftone=0.6), bg="dots", overlays=["tilt_rect2", "pixel_stairs"],
         cam=dict(z=(1.0, 1.06), rot=(3, 1), shake=1.5)),
    dict(id="S03", start=39, framing="ms", need="Medium shot, pointing a finger / gesturing at camera",
         ref="Hikaru pointing, checkerboard bg, white outline",
         look=dict(poster=0, halftone=0.15), bg="app_grid", overlays=[],
         cam=dict(z=(1.05, 1.14), rot=(0, -2), shake=2.5)),
    dict(id="S04", start=55, framing="mcu", need="Thinking pose, hand on chin, looking off-camera",
         ref="Hikaru with glasses, hand on chin, diagonal stripe bg",
         look=dict(poster=4, halftone=0.25), bg="stripes", overlays=[],
         cam=dict(z=(1.12, 1.0), rot=(-2, 2), shake=2.0)),
    dict(id="S05", start=73, framing="mcu", need="Hand over mouth / leaning in, mid close-up",
         ref="Hikaru hand over mouth; 'HIKARU the GREAT' glitch text slides in; icons pop at f89",
         look=dict(poster=4, halftone=0.3), bg="circuit", overlays=["title_text", "icons_pop"],
         cam=dict(z=(1.0, 1.12), rot=(0, 0), shake=2.0)),
    dict(id="S06", start=101, framing=None, need=None,
         ref="Dark bg, floating stickers (rocket, bolt, stopwatch); two hands fly in at f116",
         look=dict(poster=0, halftone=0.0), bg="dark", overlays=["icon_field", "phones_fly_in"],
         cam=dict(z=(1.0, 1.08), rot=(0, 3), shake=1.5)),
    dict(id="S07", start=132, framing="cu", need="Close-up, side-eye at a phone / product in hand",
         ref="Hikaru looking down, 'MUHMA' pixel badge on gem sticker, icons orbit",
         look=dict(poster=0, halftone=0.2), bg="dark", overlays=["badge", "icon_orbit"],
         cam=dict(z=(1.15, 1.02), rot=(2, -2), shake=2.0)),
    dict(id="S08", start=149, framing="mcu", need="Profile / three-quarter, looking up, finger on chin",
         ref="Hikaru profile looking up, hand on chin, chessboard bg, inner hand outline",
         look=dict(poster=0, halftone=0.15), bg="circuit", overlays=[],
         cam=dict(z=(1.0, 1.1), rot=(-3, 0), shake=1.5)),
    dict(id="S09", start=169, framing="mcu", need="Hands clasped under chin, focused stare",
         ref="Hikaru hands clasped, repeated 'GENIUS' text wall bg",
         look=dict(poster=0, halftone=0.2), bg="text_wall", overlays=[],
         cam=dict(z=(1.1, 1.02), rot=(0, 0), shake=1.5)),
    dict(id="S10", start=182, framing="cu", need="Close-up reaction, shocked / surprised face",
         ref="Torn-paper diagonal split with halftone; circular sticker zooms through at f196",
         look=dict(poster=4, halftone=0.55), bg="dots", overlays=["tear", "lens_zoom"],
         cam=dict(z=(1.0, 1.06), rot=(0, 0), shake=1.0)),
    dict(id="S11", start=200, framing="ms", need="At desk with phones / unboxing, looking at a device",
         ref="Hikaru at board; camera crash-zooms into the board f213-218",
         look=dict(poster=0, halftone=0.15), bg="phone_wall", overlays=["crash_zoom"],
         cam=dict(z=(1.0, 1.05), rot=(-2, 0), shake=2.0)),
    dict(id="S12", start=220, framing="ms", need="Holding a phone up to camera / comparing two phones",
         ref="Two players at angled board, white outlines",
         look=dict(poster=0, halftone=0.2), bg="app_grid", overlays=["held_phone"],
         cam=dict(z=(1.12, 1.0), rot=(2, -1), shake=2.0)),
    dict(id="S13", start=238, framing="cu", subject_scale=0.8, need="Big genuine smile / laugh, close-up",
         ref="Hikaru big smile, LED light-bar bg, outline",
         look=dict(poster=0, halftone=0.15), bg="light_bars", overlays=[],
         cam=dict(z=(1.0, 1.1), rot=(-1, 1), shake=2.5)),
    dict(id="S14", start=254, framing="ms", need="Outro: holding a product, phone wall behind",
         ref="Hikaru holding board, chess-piece backdrop, end blur",
         look=dict(poster=0, halftone=0.2), bg="phone_wall", overlays=["held_phone"],
         cam=dict(z=(1.0, 1.08), rot=(0, 0), shake=2.0)),
]

# Audio accents (frame numbers) from onset detection on the reference track; drive shake kicks.
ONSETS = [2, 20, 28, 36, 45, 53, 61, 69, 73, 94, 102, 118, 126, 135, 151, 159, 167, 176, 184, 200,
          204, 216, 225, 233, 241, 249, 257, 266]

for i, s in enumerate(SHOTS):
    s["end"] = SHOTS[i + 1]["start"] if i + 1 < len(SHOTS) else N_FRAMES

# Transitions at each cut: (cut frame, kind, frames before cut, frames after, blur angle deg)
TRANSITIONS = [
    (0, "whip", 0, 4, 60),
    (21, "zoom", 5, 2, 0),
    (39, "whip_flash", 2, 2, 35),
    (55, "whip", 3, 2, 55),
    (73, "glitch", 4, 1, 0),
    (101, "zoom", 2, 2, 0),
    (132, "zoom", 3, 2, 0),
    (149, "whip", 1, 2, 70),
    (169, "whip", 4, 2, 10),
    (182, "whip", 2, 4, 40),
    (200, "lens", 1, 2, 30),
    (220, "whip", 2, 1, 15),
    (238, "whip", 5, 1, 30),
    (254, "whip", 4, 2, 50),
    (267, "whip", 2, 0, 20),
]
