import sys
import os
import math
import random
import asyncio
from functools import lru_cache
import pygame as pg

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

# -------------------------
# PYGAME INIT
# -------------------------
pg.init()

w, h = 1000, 700
screen = pg.display.set_mode((w, h))
pg.display.set_caption("Shred")

clock = pg.time.Clock()
fps = 60

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 220, 0)
LIGHT_GRAY = (180, 180, 180)
LIGHT_BLUE = (100, 200, 255)
YELLOW = (255, 255, 0)

RARITY_COLORS = {
    "common": (255, 255, 255),        # white
    "uncommon": (198, 120, 60),       # copper-ish
    "rare": (255, 220, 60),           # yellow
    "legendary": (90, 170, 255),      # blue
    "mythic": (190, 80, 255),         # purple
}
RARITY_ORDER = ["common", "uncommon", "rare", "legendary", "mythic"]

TILE = 40
MINING_RADIUS = 55
REVEAL_RADIUS = TILE * 5
REVEAL_DURATION = 300
POWERUP_DURATION = 300

POWERUP_SPAWN_CHANCE = 0.02
ORE_SPAWN_CHANCE = 0.22

SHAKE_INTENSITY = 3
EARLY_SHAKE_DURATION = 15

# === TIMERS ===
SESSION_TIME = 90          # normal mode: 1:30
CHALLENGE_TIME = 180       # challenge mode: 3:00

HELL_UNLOCK_COST = 15000
HEAVEN_UNLOCK_COST = 45000

ORE_RARITY_WEIGHTS = [
    ("common", 0.745),
    ("uncommon", 0.20),
    ("rare", 0.045),
    ("legendary", 0.009),
    ("mythic", 0.001),
]

ORE_OPTIONS_WORLD = {
    "normal": {
        "common": {"coal": 6.00, "copper": 9.00, "tin": 8.00, "stone": 5.00},
        "uncommon": {"iron": 22.00, "silver": 35.00, "lead": 18.00, "nickel": 20.00},
        "rare": {"gold": 120.00, "platinum": 180.00, "zinc": 95.00, "tungsten": 160.00},
        "legendary": {"diamond": 650.00, "emerald": 800.00, "ruby": 720.00, "sapphire": 900.00},
        "mythic": {"dragonite": 2200.00, "void_pearl": 2600.00, "starcore": 3000.00, "chrono_crystal": 2800.00},
    },
    "hell": {
        "common": {"cinderstone": 10.00, "brimstone": 14.00, "ashrock": 9.00, "charcoal": 11.00},
        "uncommon": {"helliron": 32.00, "bloodsilver": 48.00, "obsidian": 40.00, "nightlead": 30.00},
        "rare": {"demonite": 220.00, "infernium": 260.00, "soulgold": 240.00, "voidtungsten": 280.00},
        "legendary": {"hellstone_core": 900.00, "abyss_gem": 1100.00, "archdemon_ruby": 1200.00, "wyrm_diamond": 1300.00},
        "mythic": {"abyssal_heart": 3200.00, "primordial_ember": 3600.00, "stygian_crown": 4200.00, "leviathan_scale": 3900.00},
    },
    "heaven": {
        "common": {"luminite": 12.00, "cloudstone": 11.00, "sunshard": 13.00, "aether_sand": 10.00},
        "uncommon": {"angel_iron": 40.00, "moon_silver": 55.00, "starlight_nickel": 45.00, "blessed_lead": 38.00},
        "rare": {"angelite": 260.00, "seraphium": 320.00, "aurorium": 300.00, "celestungsten": 340.00},
        "legendary": {"halo_diamond": 1400.00, "eden_emerald": 1600.00, "archangel_sapphire": 1700.00, "radiant_ruby": 1550.00},
        "mythic": {"divine_relic": 4200.00, "elysium_shard": 4600.00, "seraphic_prism": 5200.00, "astral_halo": 4900.00},
    },
}

POWERUP_LIST = [
    "Reveal", "Blindness", "Bomb", "Random Explosion", "Heavy Pickaxe",
    "Money Boost", "Freeze Timer", "Confusion"
]

buffs = {"mining_speed": 1, "mine_power": 1, "fortune": 0}
active_powerups = {}
popups = []

unlocks = {"hell": False, "heaven": False}
selected_world = "normal"

SKINS = {
    "base": {"name": "Base", "color": (255, 255, 255)},
    "survivor": {"name": "Survivor (Challenge)", "color": (255, 70, 70)},      # red
    "completionist": {"name": "100% (Completion)", "color": (255, 230, 70)},          # yellow
}
skins_unlocked = {"base": True, "survivor": False, "completionist": False}
selected_skin = "base"

CHALLENGE_TARGETS = {"normal": 6000.0, "hell": 9000.0, "heaven": 12000.0}
BOOST_COSTS = {"normal": 500, "hell": 2000, "heaven": 4000}

BOOST_ORE_SPAWN_CHANCE = 0.50
BOOST_HAZARD_SPAWN_CHANCE = 0.012  # reduced hazards

BOOST_RARITY_WEIGHTS = [
    ("common", 0.22),
    ("uncommon", 0.34),
    ("rare", 0.28),
    ("legendary", 0.13),
    ("mythic", 0.03),
]

# Base challenge hazards
BASE_HAZARDS = ["lava", "bomb_trap"]

# World-unique hazards (only in challenge)
WORLD_UNIQUE_HAZARDS = {
    "normal": [],
    "hell": ["fire_vent"],
    "heaven": ["smite_node"]
}

boosted_mode = False
run_boosted_mode = False

cooldown_timer = 0
COOLDOWN_MAX = 1

# -------------------------
# ITCH.IO / PYINSTALLER PATHING
# -------------------------
def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource. Works in dev and in PyInstaller builds.
    """
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder (onefile)
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def _file_exists(name: str) -> bool:
    return os.path.exists(resource_path(name))

# -------------------------
# MUSIC SYSTEM (safe init)
# -------------------------
MUSIC_END_EVENT = pg.USEREVENT + 42
MAIN_MUSIC = [
    "assets/music/Shred.ogg",
    "assets/music/Field.ogg",
    "assets/music/Find-Change.ogg",
]
CHALLENGE_MUSIC = [
    "assets/music/Countdown.ogg",
]

MIXER_OK = False
try:
    pg.mixer.init()
    pg.mixer.music.set_endevent(MUSIC_END_EVENT)
    MIXER_OK = True
except Exception:
    MIXER_OK = False

class MusicManager:
    """
    - MAIN mode: cycles forever (menu + normal gameplay)
    - CHALLENGE mode: picks ONE random track per run and loops it
    Call music.update(events) every frame in every loop.
    """
    def __init__(self, volume=0.35, shuffle=True):
        self.volume = volume
        self.shuffle = shuffle
        self.playlist = []
        self.queue = []
        self.current = None
        self.mode = None
        if MIXER_OK:
            pg.mixer.music.set_volume(self.volume)

    def set_volume(self, v: float):
        self.volume = max(0.0, min(1.0, v))
        if MIXER_OK:
            pg.mixer.music.set_volume(self.volume)

    def set_mode(self, mode_name: str):
        if mode_name == self.mode:
            return
        self.mode = mode_name
        if mode_name == "challenge":
            self.play_one_random(CHALLENGE_MUSIC)
        else:
            self.set_playlist(MAIN_MUSIC)

    def set_playlist(self, tracks):
        if not MIXER_OK:
            return
        tracks = [t for t in (tracks or []) if isinstance(t, str) and t.strip() and _file_exists(t)]
        self.playlist = tracks[:]
        self._reset_queue()
        self._start_next(force=True)

    def play_one_random(self, tracks):
        if not MIXER_OK:
            return
        tracks = [t for t in (tracks or []) if isinstance(t, str) and t.strip() and _file_exists(t)]
        if not tracks:
            return
        pick = random.choice(tracks)
        try:
            pg.mixer.music.load(resource_path(pick))
            pg.mixer.music.play(-1)  # loop forever
            self.current = pick
            self.playlist = tracks[:]
            self.queue = []
        except Exception:
            pass

    def _reset_queue(self):
        self.queue = self.playlist[:]
        if self.shuffle:
            random.shuffle(self.queue)

    def _start_next(self, force=False):
        if not MIXER_OK:
            return
        if not self.playlist:
            return
        if not self.queue:
            self._reset_queue()

        next_track = self.queue.pop(0)
        if len(self.playlist) > 1 and next_track == self.current and self.queue:
            alt = self.queue.pop(0)
            self.queue.append(next_track)
            next_track = alt

        try:
            pg.mixer.music.load(resource_path(next_track))
            pg.mixer.music.play()
            self.current = next_track
        except Exception:
            self.current = None
            self._start_next(force=True)

    def update(self, events):
        if not MIXER_OK:
            return
        if self.mode == "challenge":
            return
        for e in events:
            if e.type == MUSIC_END_EVENT:
                self._start_next()

music = MusicManager(volume=0.35, shuffle=True)

# -------------------------
# SPRITES / ART
# -------------------------
"""
EDGE/SHAPE TILES:
We select a tile by which sides are exposed to air (mined space).
Mask bits: U=1, R=2, D=4, L=8. (0..15)

You can use either:
A) Individual files normal_tile_mask_0..15, etc
B) A 4x4 sprite sheet per world by setting *_tile_sheet = "path.png"
"""

# --- Optional: use a 4x4 tilesheet for masks (leave "" if not using) ---
normal_tile_sheet = ""   # e.g. "assets/sprites/normal_masks_sheet.png" (4x4)
hell_tile_sheet = ""     # e.g. "assets/sprites/hell_masks_sheet.png"   (4x4)
heaven_tile_sheet = ""   # e.g. "assets/sprites/heaven_masks_sheet.png" (4x4)

# --- Individual mask files (your existing setup) ---
normal_tile_mask_0  = "assets/sprites/0_s.png"
normal_tile_mask_1  = "assets/sprites/1_s.png"
normal_tile_mask_2  = "assets/sprites/2_s.png"
normal_tile_mask_3  = "assets/sprites/3_s.png"
normal_tile_mask_4  = "assets/sprites/4_s.png"
normal_tile_mask_5  = "assets/sprites/5_s.png"
normal_tile_mask_6  = "assets/sprites/6_s.png"
normal_tile_mask_7  = "assets/sprites/7_s.png"
normal_tile_mask_8  = "assets/sprites/8_s.png"
normal_tile_mask_9  = "assets/sprites/9_s.png"
normal_tile_mask_10 = "assets/sprites/10_s.png"
normal_tile_mask_11 = "assets/sprites/11_s.png"
normal_tile_mask_12 = "assets/sprites/12_s.png"
normal_tile_mask_13 = "assets/sprites/13_s.png"
normal_tile_mask_14 = "assets/sprites/14_s.png"
normal_tile_mask_15 = "assets/sprites/15_s.png"

hell_tile_mask_0  = ""
hell_tile_mask_1  = ""
hell_tile_mask_2  = ""
hell_tile_mask_3  = ""
hell_tile_mask_4  = ""
hell_tile_mask_5  = ""
hell_tile_mask_6  = ""
hell_tile_mask_7  = ""
hell_tile_mask_8  = ""
hell_tile_mask_9  = ""
hell_tile_mask_10 = ""
hell_tile_mask_11 = ""
hell_tile_mask_12 = ""
hell_tile_mask_13 = ""
hell_tile_mask_14 = ""
hell_tile_mask_15 = ""

heaven_tile_mask_0  = ""
heaven_tile_mask_1  = ""
heaven_tile_mask_2  = ""
heaven_tile_mask_3  = ""
heaven_tile_mask_4  = ""
heaven_tile_mask_5  = ""
heaven_tile_mask_6  = ""
heaven_tile_mask_7  = ""
heaven_tile_mask_8  = ""
heaven_tile_mask_9  = ""
heaven_tile_mask_10 = ""
heaven_tile_mask_11 = ""
heaven_tile_mask_12 = ""
heaven_tile_mask_13 = ""
heaven_tile_mask_14 = ""
heaven_tile_mask_15 = ""

# FX
ore_sparkle_yellow  = "assets/sprites/Yellow_Sparkle.gif"  # your glow gif
power_sparkle_green = ""                                   # if blank, we auto-tint yellow->green
lava_tile_anim      = ""                                   # optional

def _scale_to_tile(surf: pg.Surface) -> pg.Surface:
    return pg.transform.smoothscale(surf.convert_alpha(), (TILE, TILE))

def load_image_scaled(filename: str):
    if not filename:
        return None
    path = resource_path(filename)
    if not os.path.exists(path):
        return None
    try:
        surf = pg.image.load(path).convert_alpha()
        return _scale_to_tile(surf)
    except Exception:
        return None

def load_sheet_4x4_scaled(filename: str):
    """
    Load a 4x4 sheet and return dict mask->Surface scaled to TILE.
    Order: row-major, mask = y*4 + x
    """
    if not filename:
        return None
    path = resource_path(filename)
    if not os.path.exists(path):
        return None
    try:
        sheet = pg.image.load(path).convert_alpha()
        sw, sh = sheet.get_size()
        cw, ch = sw // 4, sh // 4
        out = {}
        for y in range(4):
            for x in range(4):
                m = y * 4 + x
                sub = pg.Surface((cw, ch), pg.SRCALPHA)
                sub.blit(sheet, (0, 0), (x * cw, y * ch, cw, ch))
                out[m] = _scale_to_tile(sub)
        return out
    except Exception:
        return None

def load_animation(filename_or_pattern: str, anim_fps: int = 10):
    if not filename_or_pattern:
        return None

    # glob pattern for frames
    if "*" in filename_or_pattern:
        import glob
        pattern = resource_path(filename_or_pattern)
        files = sorted(glob.glob(pattern))
        frames = []
        for f in files:
            try:
                surf = pg.image.load(f).convert_alpha()
                frames.append(_scale_to_tile(surf))
            except Exception:
                pass
        if frames:
            return {"frames": frames, "fps": anim_fps}
        return None

    # gif
    if filename_or_pattern.lower().endswith(".gif") and PIL_AVAILABLE:
        path = resource_path(filename_or_pattern)
        if not os.path.exists(path):
            return None
        try:
            im = Image.open(path)
            frames = []
            for frame_i in range(getattr(im, "n_frames", 1)):
                im.seek(frame_i)
                rgba = im.convert("RGBA")
                surf = pg.image.fromstring(rgba.tobytes(), rgba.size, rgba.mode).convert_alpha()
                frames.append(_scale_to_tile(surf))
            if frames:
                return {"frames": frames, "fps": anim_fps}
        except Exception:
            pass

    # still image
    surf = load_image_scaled(filename_or_pattern)
    if surf is not None:
        return {"frames": [surf], "fps": anim_fps}
    return None
# -------------------------
# UI BACKGROUND (SHOP)
# -------------------------
SHOP_UI_BG = "assets/sprites/BTSUI.png"   # <-- put your UI image here
SHOP_BG_SURF = None

def load_ui_bg():
    global SHOP_BG_SURF
    path = resource_path(SHOP_UI_BG)
    if os.path.exists(path):
        try:
            SHOP_BG_SURF = pg.image.load(path).convert()
            SHOP_BG_SURF = pg.transform.smoothscale(SHOP_BG_SURF, (w, h))
        except Exception:
            SHOP_BG_SURF = None

load_ui_bg()

# Anchor points tuned for 1000x700 like your screenshot.
# If your template changes, adjust these once and everything lines up.
SHOP_ANCHORS = {
    "title": (-10000, -10000),

    # Top labels above bars
    "label_1": (180, 245),   # Mine Cooldown
    "label_2": (500, 245),   # Mine Power
    "label_3": (820, 245),   # Mine Fortune

    # Bars (x,y,w,h) — should sit under the label
    "bar_1": (80, 275, 200, 12),
    "bar_2": (400, 275, 200, 12),
    "bar_3": (720, 275, 200, 12),

    # LVL text / number positions (center-ish in each panel)
    "lvl_1": (-1000, -1000),
    "lvl_2": (-1000, -1000),
    "lvl_3": (-1000, -1000),

    # Hotkey + cost (bottom of each panel)
    "cost_1": (210, 585),
    "cost_2": (500, 585),
    "cost_3": (790, 585),

    # Money box
    "money": (w//2, 640),

    # Skins button area (top-left corner area)
    "skins_btn": pg.Rect(0, 45, 160, 52),
    "tutorial_btn": pg.Rect(0, 105, 160, 44),

    # World line
    "world": (w-140, 50),

    # Challenge toggle center
    "challenge_center": (w-120, 90),
}
# -------------------------
# TINT CACHE (tiles + FX)
# -------------------------
_TINT_CACHE = {}

def tint_surface(src: pg.Surface, tint_rgb):
    """
    Multiply RGB by tint_rgb (0..255) while preserving alpha.
    Cached by (id(src), tint_rgb).
    """
    if src is None:
        return None
    key = (id(src), int(tint_rgb[0]), int(tint_rgb[1]), int(tint_rgb[2]))
    got = _TINT_CACHE.get(key)
    if got is not None:
        return got
    s = src.copy()
    mult = pg.Surface(s.get_size(), pg.SRCALPHA)
    mult.fill((tint_rgb[0], tint_rgb[1], tint_rgb[2], 255))
    s.blit(mult, (0, 0), special_flags=pg.BLEND_RGBA_MULT)
    _TINT_CACHE[key] = s
    return s

def tint_anim(anim, tint_rgb):
    if not anim:
        return None
    frames = anim.get("frames", [])
    if not frames:
        return None
    tinted_frames = [tint_surface(f, tint_rgb) for f in frames]
    return {"frames": tinted_frames, "fps": anim.get("fps", 10)}

class AnimPlayer:
    def __init__(self, anim, phase_seed=0.0):
        self.anim = anim
        self.t = phase_seed  # de-sync starters

    def frame(self, dt_sec: float):
        if not self.anim:
            return None
        frames = self.anim["frames"]
        if not frames:
            return None
        self.t += dt_sec
        fps_local = max(1, int(self.anim.get("fps", 10)))
        idx = int(self.t * fps_local) % len(frames)
        return frames[idx]

# -------------------------
# Build tilesets
# -------------------------
def build_tileset(prefix: str):
    out = {}
    for m in range(16):
        varname = f"{prefix}_tile_mask_{m}"
        filename = globals().get(varname, "")
        if filename:
            out[m] = filename
    return out

# Load normal from sheet if provided
TILESET_SURF = {"normal": {}, "hell": {}, "heaven": {}}

normal_from_sheet = load_sheet_4x4_scaled(normal_tile_sheet)
hell_from_sheet   = load_sheet_4x4_scaled(hell_tile_sheet)
heav_from_sheet   = load_sheet_4x4_scaled(heaven_tile_sheet)

if normal_from_sheet:
    TILESET_SURF["normal"] = normal_from_sheet
else:
    for m, fname in build_tileset("normal").items():
        TILESET_SURF["normal"][m] = load_image_scaled(fname)

if hell_from_sheet:
    TILESET_SURF["hell"] = hell_from_sheet
else:
    for m, fname in build_tileset("hell").items():
        TILESET_SURF["hell"][m] = load_image_scaled(fname)

if heav_from_sheet:
    TILESET_SURF["heaven"] = heav_from_sheet
else:
    for m, fname in build_tileset("heaven").items():
        TILESET_SURF["heaven"][m] = load_image_scaled(fname)

# If hell/heaven masks are missing, auto-tint the NORMAL masks (this is what you asked for)
HELL_TINT   = (210, 80, 80)    # red-ish stone
HEAVEN_TINT = (255, 255, 0)  # white-ish stone

for m in range(16):
    if TILESET_SURF["hell"].get(m) is None:
        TILESET_SURF["hell"][m] = tint_surface(TILESET_SURF["normal"].get(m), HELL_TINT)
    if TILESET_SURF["heaven"].get(m) is None:
        TILESET_SURF["heaven"][m] = tint_surface(TILESET_SURF["normal"].get(m), HEAVEN_TINT)

# FX animations
ORE_SPARKLE_ANIM = load_animation(ore_sparkle_yellow, anim_fps=10)
POWER_SPARKLE_ANIM = load_animation(power_sparkle_green, anim_fps=10)

# If no green sparkle provided, auto-tint the yellow sparkle to green
if POWER_SPARKLE_ANIM is None and ORE_SPARKLE_ANIM is not None:
    POWER_SPARKLE_ANIM = tint_anim(ORE_SPARKLE_ANIM, (120, 255, 140))

LAVA_ANIM = load_animation(lava_tile_anim, anim_fps=10)

# Players start with different phases so they don't look synced
ore_sparkle_player = AnimPlayer(ORE_SPARKLE_ANIM, phase_seed=random.random() * 10.0)
power_sparkle_player = AnimPlayer(POWER_SPARKLE_ANIM, phase_seed=random.random() * 10.0)
lava_player = AnimPlayer(LAVA_ANIM, phase_seed=random.random() * 10.0)

# -------------------------
# Glow scheduling (NO placeholder glow if GIF exists)
# -------------------------
def tile_seed(bx, by):
    # stable deterministic pseudo-random per tile
    return ((bx * 73856093) ^ (by * 19349663)) & 0xFFFFFFFF

def pulse_for_tile(bx, by, t_seconds, cycle=1.8, duty=0.22):
    """
    Returns 0..1 pulse. Each tile has its own phase offset.
    cycle: seconds per cycle
    duty: fraction of cycle where pulse is active
    """
    phase = (tile_seed(bx, by) % 10000) / 10000.0
    x = (t_seconds / cycle + phase) % 1.0
    if x > duty:
        return 0.0
    # ease in/out within the duty window
    u = x / max(1e-6, duty)  # 0..1
    # smoothstep
    return u * u * (3 - 2 * u)

def blit_with_alpha(dest, surf, pos, alpha_0_255):
    if surf is None:
        return
    a = max(0, min(255, int(alpha_0_255)))
    if a <= 0:
        return
    tmp = surf.copy()
    tmp.set_alpha(a)
    dest.blit(tmp, pos)

def draw_tile_glow_fallback(sx, sy, color, strength=110):
    # Used ONLY when you DON'T have a sparkle animation
    glow = pg.Surface((TILE, TILE), pg.SRCALPHA)
    r, g, b = color
    glow.fill((r, g, b, int(strength * 0.26)))
    pg.draw.rect(glow, (255, 255, 255, int(strength * 0.12)), (5, 5, TILE - 10, TILE - 10), border_radius=6)
    screen.blit(glow, (sx, sy))

def draw_reveal_rarity_outline(sx, sy, rarity):
    c = RARITY_COLORS.get(rarity, WHITE)
    pg.draw.rect(screen, c, (sx + 2, sy + 2, TILE - 4, TILE - 4), 3)
    pg.draw.rect(screen, WHITE, (sx + 6, sy + 6, TILE - 12, TILE - 12), 1)

# -------------------------
# Helpers
# -------------------------
def get_active_world():
    return selected_world

def weighted_choice(weighted_items):
    r = random.random() * sum(w for _, w in weighted_items)
    upto = 0.0
    for item, weight in weighted_items:
        upto += weight
        if r <= upto:
            return item
    return weighted_items[-1][0]

def sign(v):
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0

def facing_step(from_x, from_y, to_x, to_y):
    dx = to_x - from_x
    dy = to_y - from_y
    sx = sign(dx)
    sy = sign(dy)
    if sx == 0 and sy == 0:
        return (0, 1)
    return (sx, sy)

def blocks_for_mine_power(level, player_x, player_y, block):
    bx, by = block
    cx, cy = bx + TILE / 2, by + TILE / 2
    fx, fy = facing_step(player_x, player_y, cx, cy)
    lx, ly = (-fy, fx)
    rx, ry = (fy, -fx)

    out = [block]

    if level >= 2:
        out.append((bx + (fx + lx) * TILE, by + (fy + ly) * TILE))
        out.append((bx + (fx + rx) * TILE, by + (fy + ry) * TILE))

    if level >= 3:
        out.append((bx + fx * TILE, by + fy * TILE))
        out.append((bx + (2 * fx + 2 * lx) * TILE, by + (2 * fy + 2 * ly) * TILE))
        out.append((bx + (2 * fx + 1 * lx) * TILE, by + (2 * fy + 1 * ly) * TILE))
        out.append((bx + (2 * fx) * TILE, by + (2 * fy) * TILE))
        out.append((bx + (2 * fx + 1 * rx) * TILE, by + (2 * fy + 1 * ry) * TILE))
        out.append((bx + (2 * fx + 2 * rx) * TILE, by + (2 * fy + 2 * ry) * TILE))

    seen = set()
    uniq = []
    for b in out:
        if b not in seen:
            seen.add(b)
            uniq.append(b)
    return uniq

def is_100_percent():
    return (
        unlocks.get("hell", False)
        and unlocks.get("heaven", False)
        and buffs["mining_speed"] >= 10
        and buffs["mine_power"] >= 3
        and buffs["fortune"] >= 10
    )

def wrap_lines(font, text, max_w, max_lines=None):
    words = text.split()
    lines = []
    cur = ""

    def break_long_word(word):
        parts = []
        chunk = ""
        for ch in word:
            test = chunk + ch
            if font.size(test)[0] <= max_w:
                chunk = test
            else:
                if chunk:
                    parts.append(chunk)
                chunk = ch
        if chunk:
            parts.append(chunk)
        return parts

    expanded = []
    for word in words:
        if font.size(word)[0] <= max_w:
            expanded.append(word)
        else:
            expanded.extend(break_long_word(word))

    for word in expanded:
        test = (cur + " " + word).strip()
        if font.size(test)[0] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
        if max_lines is not None and len(lines) >= max_lines:
            cur = ""
            break

    if cur and (max_lines is None or len(lines) < max_lines):
        lines.append(cur)

    return lines

# -------------------------------------------------------
# IMPORTANT: asyncio yield helper
# -------------------------------------------------------
async def frame_yield():
    await asyncio.sleep(0)

# -------------------------
# UI helpers (revamped shop/main menu)
# -------------------------
def draw_bevel_panel(rect: pg.Rect, base=(45, 48, 54), border=(0, 0, 0)):
    # outer border
    pg.draw.rect(screen, border, rect, border_radius=10)
    inner = rect.inflate(-8, -8)
    pg.draw.rect(screen, base, inner, border_radius=10)

    # subtle top highlight / bottom shade
    top = inner.copy()
    top.height = max(1, inner.height // 3)
    shade = inner.copy()
    shade.y = inner.y + inner.height - top.height
    pg.draw.rect(screen, (70, 74, 82), top, border_radius=10)
    pg.draw.rect(screen, (32, 34, 38), shade, border_radius=10)

    # inner stroke
    pg.draw.rect(screen, (20, 20, 22), inner, 2, border_radius=10)

def draw_torch_icon(cx, cy, scale=1.0):
    # simple pixel-ish torch
    s = int(20 * scale)
    # handle
    pg.draw.rect(screen, (25, 25, 28), (cx - s//4, cy, s//2, int(s*1.2)), border_radius=4)
    pg.draw.rect(screen, (0, 0, 0), (cx - s//4, cy, s//2, int(s*1.2)), 2, border_radius=4)
    # cup
    pg.draw.rect(screen, (60, 60, 66), (cx - s//2, cy - int(s*0.15), s, int(s*0.35)), border_radius=6)
    pg.draw.rect(screen, (0, 0, 0), (cx - s//2, cy - int(s*0.15), s, int(s*0.35)), 2, border_radius=6)
    # flame (stacked circles)
    pg.draw.circle(screen, (255, 170, 30), (cx, cy - int(s*0.6)), int(s*0.55))
    pg.draw.circle(screen, (255, 235, 120), (cx, cy - int(s*0.65)), int(s*0.35))
    pg.draw.circle(screen, (0, 0, 0), (cx, cy - int(s*0.6)), int(s*0.55), 2)

def draw_shop_header():
    screen.fill((24, 26, 30))
    # vignette-ish bands
    pg.draw.rect(screen, (18, 18, 20), (0, 0, w, 120))
    pg.draw.rect(screen, (18, 18, 20), (0, h - 120, w, 120))

    title_font = pg.font.SysFont(None, 96)
    t = title_font.render("SHRED", True, (210, 210, 210))
    screen.blit(t, (w // 2 - t.get_width() // 2, 26))
    pg.draw.rect(screen, (0, 0, 0), (0, 120, w, 8))
    pg.draw.rect(screen, (0, 0, 0), (0, h - 128, w, 8))

def draw_upgrade_card(x, y, card_w, card_h, name, level, max_level, cost, can_buy, key_label):
    rect = pg.Rect(x, y, card_w, card_h)
    draw_bevel_panel(rect, base=(52, 56, 62), border=(0, 0, 0))

    label_font = pg.font.SysFont(None, 38)
    small_font = pg.font.SysFont(None, 26)

    name_s = label_font.render(name.upper(), True, (210, 210, 210))
    screen.blit(name_s, (rect.centerx - name_s.get_width() // 2, rect.y + 22))

    # bar
    bar_w = int(card_w * 0.72)
    bar_x = rect.centerx - bar_w // 2
    bar_y = rect.y + 64
    pg.draw.rect(screen, (0, 0, 0), (bar_x - 3, bar_y - 3, bar_w + 6, 16))
    pg.draw.rect(screen, (110, 110, 110), (bar_x, bar_y, bar_w, 10))
    frac = 0 if max_level <= 0 else max(0.0, min(1.0, level / float(max_level)))
    pg.draw.rect(screen, (200, 200, 200) if can_buy else (140, 140, 140), (bar_x, bar_y, int(bar_w * frac), 10))

    lvl = small_font.render("LVL", True, (220, 220, 220))
    screen.blit(lvl, (rect.centerx - lvl.get_width() // 2, rect.y + 86))

    # torch / icon
    draw_torch_icon(rect.centerx, rect.centery - 10, scale=1.15)

    # cost + hint
    cost_color = (255, 230, 70) if can_buy else (150, 150, 150)
    cost_s = small_font.render(f"[{key_label}]  ${cost}", True, cost_color)
    screen.blit(cost_s, (rect.centerx - cost_s.get_width() // 2, rect.bottom - 42))

def draw_money_bar(total_money):
    bar = pg.Rect(w//2 - 170, h - 92, 340, 54)
    pg.draw.rect(screen, (0, 0, 0), bar, border_radius=8)
    inner = bar.inflate(-10, -10)
    pg.draw.rect(screen, (70, 74, 82), inner, border_radius=8)
    pg.draw.rect(screen, (20, 20, 22), inner, 2, border_radius=8)
    font = pg.font.SysFont(None, 44)
    txt = font.render(f"MONEY: ${total_money:.2f}", True, (230, 230, 230))
    screen.blit(txt, (bar.centerx - txt.get_width()//2, bar.centery - txt.get_height()//2))

# -------------------------------------------------------
# Summary screen / popup / player
# -------------------------------------------------------
async def run_summary_screen(
    title_text,
    world_name,
    mode_name,
    earned,
    payout,
    payout_mult,
    reason,
    time_left_s,
    lives_left,
    mined_count,
    rarity_counts,
    show_lives,
):
    pg.mouse.set_visible(True)
    pg.event.set_grab(False)
    title_color = RED if 'GAME' in title_text else YELLOW
    accent = WORLD_DATA.get(world_name, WORLD_DATA['normal']).get('tile_tint', (120, 180, 255))
    while True:
        events = pg.event.get()
        music.update(events)
        for e in events:
            if e.type == pg.QUIT:
                pg.quit(); raise SystemExit
            if e.type == pg.KEYDOWN and e.key in (pg.K_ESCAPE, pg.K_RETURN, pg.K_SPACE):
                return

        screen.fill((8, 10, 16))
        card = pg.Rect(88, 34, 824, 622)
        draw_ui_panel(card, border=(88, 190, 255), fill=(8, 12, 20, 236), radius=28, glow=True)

        deco = pg.Surface((card.w, card.h), pg.SRCALPHA)
        pg.draw.circle(deco, (*accent, 28), (120, 92), 88)
        pg.draw.circle(deco, (255, 220, 70, 20), (card.w - 120, 88), 92)
        for i in range(6):
            x = 120 + i * 110
            pg.draw.line(deco, (110, 150, 210, 22), (x, 146), (x + 44, 188), 2)
        screen.blit(deco, card.topleft)

        draw_text_in_rect(title_text, pg.Rect(card.x + 32, card.y + 22, card.w - 64, 58), 60, title_color, bold=True)
        draw_text_in_rect('Run results', pg.Rect(card.x + 32, card.y + 80, card.w - 64, 18), 18, LIGHT_BLUE)

        badge_y = card.y + 104
        badge_h = 42
        badge_gap = 14
        badge_w1 = 228
        badge_w2 = 160
        badge_w3 = 154
        total_badge_w = badge_w1 + badge_w2 + badge_w3 + badge_gap * 2
        badge_x = card.centerx - total_badge_w // 2
        draw_badge(pg.Rect(badge_x, badge_y, badge_w1, badge_h), f'WORLD {world_name.upper()}', fg=YELLOW, border=(110, 200, 255), size=22)
        draw_badge(pg.Rect(badge_x + badge_w1 + badge_gap, badge_y, badge_w2, badge_h), mode_name.upper(), fg=WHITE, border=(110, 200, 255), size=22)
        draw_badge(pg.Rect(badge_x + badge_w1 + badge_gap + badge_w2 + badge_gap, badge_y, badge_w3, badge_h), f'RATE {int(payout_mult*100)}%', fg=LIGHT_BLUE, border=(110, 200, 255), size=22)

        draw_text_in_rect(reason, pg.Rect(card.x + 120, card.y + 160, card.w - 240, 26), 24, WHITE)

        stat_top = card.y + 196
        stat_gap = 16
        stat_h = 106
        stat_w = 176
        stats_total = stat_w * 4 + stat_gap * 3
        stat_left = card.centerx - stats_total // 2
        stat_specs = [
            ('RUN VALUE', f'${earned:.2f}', 'Money earned before exit rate.', WHITE),
            ('BANKED', f'${payout:.2f}', 'Money kept after the payout rate.', YELLOW),
            ('TIME LEFT' if not show_lives else 'LIVES LEFT', f'{max(0, int(time_left_s))}s' if not show_lives else str(lives_left), 'How much safety you had left.' if show_lives else 'Time remaining when the run ended.', LIGHT_BLUE if not show_lives else (GREEN if lives_left > 0 else RED)),
            ('BLOCKS MINED', str(mined_count), 'Solid blocks you broke this run.', WHITE),
        ]
        for idx, (label, value, desc, col) in enumerate(stat_specs):
            rect = pg.Rect(stat_left + idx * (stat_w + stat_gap), stat_top, stat_w, stat_h)
            draw_ui_panel(rect, border=(62, 78, 108), fill=(17, 22, 34, 228), radius=20)
            top_strip = pg.Rect(rect.x + 10, rect.y + 10, rect.w - 20, 6)
            pg.draw.rect(screen, (*col[:3], 120) if isinstance(col, tuple) else (120, 190, 255, 120), top_strip, border_radius=4)
            draw_text_in_rect(label, pg.Rect(rect.x + 14, rect.y + 20, rect.w - 28, 18), 15, LIGHT_BLUE, align='left', bold=True)
            draw_text_in_rect(value, pg.Rect(rect.x + 12, rect.y + 38, rect.w - 24, 34), 30, col, bold=True)
            draw_text_in_rect(desc, pg.Rect(rect.x + 14, rect.y + 74, rect.w - 28, 20), 13, LIGHT_GRAY, align='left')

        summary_rect = pg.Rect(card.x + 50, stat_top + stat_h + 18, card.w - 100, 98)
        draw_ui_panel(summary_rect, border=(58, 70, 96), fill=(13, 17, 27, 228), radius=18)
        draw_text_in_rect('WHAT THIS RUN MEANS', pg.Rect(summary_rect.x + 18, summary_rect.y + 10, summary_rect.w - 36, 18), 18, LIGHT_BLUE, align='left', bold=True)
        summary_line = f'You mined {mined_count} block' + ('s' if mined_count != 1 else '') + f' and kept {int(payout_mult * 100)}% of your run value.'
        if show_lives:
            summary_line += f' You finished with {lives_left} live' + ('s.' if lives_left != 1 else '.')
        else:
            summary_line += f' You exited with {max(0, int(time_left_s))}s left on the timer.'
        draw_text_in_rect(summary_line, pg.Rect(summary_rect.x + 18, summary_rect.y + 34, summary_rect.w - 36, 46), 22, WHITE, align='left')

        rarity_card = pg.Rect(card.x + 50, summary_rect.bottom + 18, card.w - 100, 142)
        draw_ui_panel(rarity_card, border=(56, 66, 90), fill=(18, 22, 32, 225), radius=20)
        draw_text_in_rect('ORE RARITY FOUND', pg.Rect(rarity_card.x + 18, rarity_card.y + 10, rarity_card.w - 36, 18), 18, LIGHT_BLUE, align='left', bold=True)
        draw_text_in_rect('How many ore blocks you mined from each rarity tier.', pg.Rect(rarity_card.x + 18, rarity_card.y + 30, rarity_card.w - 36, 16), 14, LIGHT_GRAY, align='left')
        inner_gap = 10
        inner_margin = 18
        box_top = rarity_card.y + 54
        box_h = 70
        box_w = (rarity_card.w - inner_margin * 2 - inner_gap * 4) // 5
        for idx, rarity in enumerate(RARITY_ORDER):
            rrect = pg.Rect(rarity_card.x + inner_margin + idx * (box_w + inner_gap), box_top, box_w, box_h)
            fill_col = RARITY_COLORS.get(rarity, WHITE)
            draw_ui_panel(rrect, border=(42, 50, 68), fill=(10, 13, 22, 214), radius=14)
            gem = pg.Surface((22, 22), pg.SRCALPHA)
            pg.draw.polygon(gem, (*fill_col, 220), [(11, 1), (20, 11), (11, 21), (2, 11)])
            screen.blit(gem, (rrect.x + 10, rrect.y + 10))
            draw_text_in_rect(rarity.title(), pg.Rect(rrect.x + 34, rrect.y + 10, rrect.w - 42, 16), 14, fill_col, align='left', bold=True)
            draw_text_in_rect(str(rarity_counts.get(rarity, 0)), pg.Rect(rrect.x + 8, rrect.y + 26, rrect.w - 16, 24), 22, WHITE, bold=True)
            draw_text_in_rect('ores mined', pg.Rect(rrect.x + 8, rrect.y + 48, rrect.w - 16, 14), 12, LIGHT_GRAY)

        draw_text_in_rect('Press Enter, Space, or Esc to return', pg.Rect(card.x + 120, card.bottom - 28, card.w - 240, 18), 18, LIGHT_BLUE)
        pg.display.flip(); clock.tick(fps); await frame_yield()

class Popup:
    def __init__(self, text, lifetime=120, size=30, color=WHITE, y=None):
        self.text = text
        self.lifetime = lifetime
        self.age = 0
        self.size = size
        self.color = color
        self.y = y

    def draw(self, y_offset):
        font = pg.font.SysFont(None, self.size)
        alpha = max(0, 255 - int((self.age / self.lifetime) * 255))
        text_surf = font.render(self.text, True, self.color)
        text_surf.set_alpha(alpha)
        if self.y is None:
            screen.blit(text_surf, (w // 2 - text_surf.get_width() // 2, h - 60 - y_offset))
        else:
            screen.blit(text_surf, (w // 2 - text_surf.get_width() // 2, self.y))

    def update(self):
        self.age += 1
        return self.age < self.lifetime

class Player:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.size = 15
        self.vel_x = 0
        self.vel_y = 0
        self.max_speed = 5

    def move(self, ground):
        next_x, next_y = self.x + self.vel_x, self.y + self.vel_y
        rect = pg.Rect(next_x - self.size, next_y - self.size, self.size * 2, self.size * 2)
        for bx, by in ground.get_nearby_blocks(next_x, next_y):
            if rect.colliderect(pg.Rect(bx, by, TILE, TILE)):
                return
        self.x, self.y = next_x, next_y

    def draw(self, camera_x, camera_y, invuln=0):
        if invuln > 0 and (pg.time.get_ticks() // 90) % 2 == 0:
            return

        sx = int(self.x - camera_x)
        sy = int(self.y - camera_y)

        # Base body
        color = SKINS[selected_skin]["color"]
        pg.draw.circle(screen, color, (sx, sy), self.size)
        pg.draw.circle(screen, BLACK, (sx, sy), self.size, 2)

        # Sword cosmetic for second skin (survivor)
        if selected_skin == "survivor":
            # angle based on movement; defaults to down-right
            dx = self.vel_x
            dy = self.vel_y
            ang = math.atan2(dy if (dx or dy) else 1, dx if (dx or dy) else 1)

            # sword geometry
            handle_len = 10
            blade_len = 26

            # start near right side of player
            ox = int(math.cos(ang) * (self.size - 2))
            oy = int(math.sin(ang) * (self.size - 2))

            x0 = sx + ox
            y0 = sy + oy
            x1 = x0 + int(math.cos(ang) * blade_len)
            y1 = y0 + int(math.sin(ang) * blade_len)

            # blade
            pg.draw.line(screen, (220, 220, 230), (x0, y0), (x1, y1), 4)
            pg.draw.line(screen, (255, 255, 255), (x0, y0), (x1, y1), 2)

            # hilt (perpendicular)
            px = int(-math.sin(ang) * 8)
            py = int(math.cos(ang) * 8)
            pg.draw.line(screen, (70, 70, 80), (x0 - px, y0 - py), (x0 + px, y0 + py), 4)
            pg.draw.line(screen, BLACK, (x0 - px, y0 - py), (x0 + px, y0 + py), 2)

            # handle
            hx = x0 - int(math.cos(ang) * handle_len)
            hy = y0 - int(math.sin(ang) * handle_len)
            pg.draw.line(screen, (35, 35, 40), (hx, hy), (x0, y0), 5)
            pg.draw.line(screen, BLACK, (hx, hy), (x0, y0), 2)

# -------------------------------------------------------
# Ground (tile masks fixed, glow fixed + desynced)
# -------------------------------------------------------
class Ground:
    def __init__(self):
        self.mined_blocks = set()
        self.ore_tiles = {}
        self.block_types = {}
        self.reveal_active = False
        self.reveal_time = 0
        self.early_shake_timer = 0

        self.hazard_tiles = {}

        self.lava_pools = set()
        self.lava_sources = set()
        self.lava_spread_cd = 0

        self.fire_vents = set()
        self.fire_vent_cd = {}

        self.smite_nodes = set()
        self.smite_cd = {}

        # Challenge-mode bomb traps are queued here before exploding.
        # Some reverted versions of the file reference this list later in
        # game_session(), so it must always exist on Ground.
        self.primed_bombs = []

    def generate_block(self, bx, by):
        if (bx, by) in self.block_types:
            return self.block_types[(bx, by)]

        if run_boosted_mode and random.random() < BOOST_HAZARD_SPAWN_CHANCE:
            world = get_active_world()
            pool = BASE_HAZARDS + WORLD_UNIQUE_HAZARDS.get(world, [])
            hz = random.choice(pool) if pool else "lava"
            self.hazard_tiles[(bx, by)] = hz
            self.block_types[(bx, by)] = "hazard"
            return "hazard"

        if random.random() < POWERUP_SPAWN_CHANCE:
            self.ore_tiles[(bx, by)] = random.choice(POWERUP_LIST)
            self.block_types[(bx, by)] = "powerup"
            return "powerup"

        ore_chance = BOOST_ORE_SPAWN_CHANCE if run_boosted_mode else ORE_SPAWN_CHANCE
        if random.random() < ore_chance:
            weights = BOOST_RARITY_WEIGHTS if run_boosted_mode else ORE_RARITY_WEIGHTS
            self.ore_tiles[(bx, by)] = weighted_choice(weights)
            self.block_types[(bx, by)] = "ore"
            return "ore"

        self.block_types[(bx, by)] = "regular"
        return "regular"

    def get_nearby_blocks(self, px, py):
        start_x = int((px - w // 2) // TILE) - 1
        end_x = int((px + w // 2) // TILE) + 2
        start_y = int((py - h // 2) // TILE) - 1
        end_y = int((py + h // 2) // TILE) + 2
        blocks = []
        for tx in range(start_x, end_x):
            for ty in range(start_y, end_y):
                bx, by = tx * TILE, ty * TILE
                if (bx, by) not in self.mined_blocks:
                    blocks.append((bx, by))
        return blocks

    def neighbors4(self, b):
        bx, by = b
        return [(bx + TILE, by), (bx - TILE, by), (bx, by + TILE), (bx, by - TILE)]

    def update_lava_flow(self):
        if self.lava_spread_cd > 0:
            self.lava_spread_cd -= 1
            return
        self.lava_spread_cd = 18

        new_lava = set()
        for (bx, by) in list(self.lava_sources):
            candidates = [(bx + TILE, by), (bx - TILE, by), (bx, by + TILE), (bx, by - TILE)]
            random.shuffle(candidates)

            for (nx, ny) in candidates[:1]:
                if (nx, ny) in self.lava_pools:
                    continue

                if (nx, ny) not in self.mined_blocks:
                    self.mined_blocks.add((nx, ny))
                    self.ore_tiles.pop((nx, ny), None)
                    self.hazard_tiles.pop((nx, ny), None)
                    self.block_types[(nx, ny)] = "regular"

                new_lava.add((nx, ny))

        self.lava_pools |= new_lava

    def expose_adjacent_hazards(self, mined_block):
        for nb in self.neighbors4(mined_block):
            hz = self.hazard_tiles.get(nb)
            if not hz:
                continue

            self.mined_blocks.add(nb)
            self.block_types[nb] = "regular"
            self.ore_tiles.pop(nb, None)
            self.hazard_tiles.pop(nb, None)

            if hz == "lava":
                self.lava_pools.add(nb)
                self.lava_sources.add(nb)

            elif hz == "fire_vent":
                self.fire_vents.add(nb)
                self.fire_vent_cd[nb] = random.randint(int(2.4 * fps), int(3.6 * fps))

            elif hz == "smite_node":
                self.smite_nodes.add(nb)
                self.smite_cd[nb] = random.randint(int(2.6 * fps), int(4.2 * fps))

    def exposure_mask(self, bx, by):
        """
        IMPORTANT FIX:
        Mask is about which SIDES of THIS BLOCK are exposed to air (mined space).
        That means: neighbor mined => that side is exposed.
        """
        m = 0
        if (bx, by - TILE) in self.mined_blocks:  # up neighbor is air
            m |= 1
        if (bx + TILE, by) in self.mined_blocks:  # right neighbor is air
            m |= 2
        if (bx, by + TILE) in self.mined_blocks:  # down neighbor is air
            m |= 4
        if (bx - TILE, by) in self.mined_blocks:  # left neighbor is air
            m |= 8
        return m

    def draw_block_tile(self, world, bx, by, sx, sy):
        mask = self.exposure_mask(bx, by)

        surf = TILESET_SURF.get(world, {}).get(mask)
        # If a mask tile is missing for some reason, fall back to mask 0 (fully enclosed).
        if surf is None:
            surf = TILESET_SURF.get(world, {}).get(0)

        if surf is not None:
            screen.blit(surf, (sx, sy))
            return

        # final fallback: flat color
        if world == "hell":
            color = (130, 55, 55)
        elif world == "heaven":
            color = (235, 235, 235)
        else:
            color = (100, 100, 100)
        pg.draw.rect(screen, color, (sx, sy, TILE, TILE))

    def draw(self, camera_x, camera_y, player_x, player_y, cursor_world_pos, cursor_screen_pos, dt_sec):
        cursor_wx, cursor_wy = cursor_world_pos
        world = get_active_world()

        ptx = int(player_x // TILE)
        pty = int(player_y // TILE)

        ore_overlay = ore_sparkle_player.frame(dt_sec)
        pwr_overlay = power_sparkle_player.frame(dt_sec)
        lava_frame = lava_player.frame(dt_sec)

        # global time (seconds) for desync pulses
        t_seconds = pg.time.get_ticks() / 1000.0

        for bx, by in self.get_nearby_blocks(player_x, player_y):
            sx, sy = bx - camera_x, by - camera_y

            if (bx, by) in self.mined_blocks:
                pg.draw.rect(screen, BLACK, (sx, sy, TILE, TILE))
                continue

            btype = self.generate_block(bx, by)
            self.draw_block_tile(world, bx, by, sx, sy)

            # --- ORE ---
            if btype == "ore":
                # NO placeholder glow when gif exists.
                if ore_overlay is not None:
                    p = pulse_for_tile(bx, by, t_seconds, cycle=1.9, duty=0.18)
                    if p > 0:
                        blit_with_alpha(screen, ore_overlay, (sx, sy), 255 * p)
                else:
                    # fallback glow only if no overlay exists
                    draw_tile_glow_fallback(sx, sy, (255, 220, 60), strength=120)

                if self.reveal_active and math.hypot(bx - cursor_wx, by - cursor_wy) <= REVEAL_RADIUS:
                    rarity = self.ore_tiles.get((bx, by), "common")
                    draw_reveal_rarity_outline(sx, sy, rarity)

            # --- POWERUP ---
            if btype == "powerup":
                # Green glow uses green-tinted version of yellow gif (via tint-cache)
                if pwr_overlay is not None:
                    p = pulse_for_tile(bx, by, t_seconds, cycle=2.15, duty=0.16)
                    if p > 0:
                        blit_with_alpha(screen, pwr_overlay, (sx, sy), 255 * p)
                else:
                    draw_tile_glow_fallback(sx, sy, (80, 255, 120), strength=120)

            # --- HAZARD indicator ---
            if btype == "hazard":
                hz = self.hazard_tiles.get((bx, by), "lava")
                if hz == "bomb_trap":
                    btx = int(bx // TILE)
                    bty = int(by // TILE)
                    near = max(abs(btx - ptx), abs(bty - pty)) <= 2
                    if near:
                        pg.draw.circle(screen, (30, 30, 30), (int(sx + TILE / 2), int(sy + TILE / 2)), 7)
                        pg.draw.circle(screen, (220, 40, 40), (int(sx + TILE / 2), int(sy + TILE / 2)), 7, 2)

        # lava pools drawn on top
        px, py = player_x, player_y
        min_tx = int((px - w // 2) // TILE) - 2
        max_tx = int((px + w // 2) // TILE) + 3
        min_ty = int((py - h // 2) // TILE) - 2
        max_ty = int((py + h // 2) // TILE) + 3

        for tx in range(min_tx, max_tx):
            for ty in range(min_ty, max_ty):
                bx, by = tx * TILE, ty * TILE
                if (bx, by) in self.lava_pools:
                    sx, sy = bx - camera_x, by - camera_y
                    if lava_frame is not None:
                        screen.blit(lava_frame, (sx, sy))
                    else:
                        pg.draw.rect(screen, (255, 120, 30), (sx, sy, TILE, TILE))
                        pg.draw.rect(screen, (255, 200, 80), (sx + 6, sy + 6, TILE - 12, TILE - 12), 2)

        # Blindness mask
        if "Blindness" in active_powerups:
            cursor_sx, cursor_sy = cursor_screen_pos
            mask = pg.Surface((w, h), pg.SRCALPHA)
            mask.fill((0, 0, 0, 220))
            pg.draw.circle(mask, (0, 0, 0, 0), (cursor_sx, cursor_sy), 70)
            screen.blit(mask, (0, 0))

        # cooldown bar at cursor
        if cooldown_timer < COOLDOWN_MAX or self.early_shake_timer > 0:
            bar_w, bar_h = 34, 7
            x = (cursor_wx - camera_x) - bar_w // 2
            y = (cursor_wy - camera_y) - 28
            progress = cooldown_timer / COOLDOWN_MAX if COOLDOWN_MAX > 0 else 0
            bar_color = RED if self.early_shake_timer > 0 else LIGHT_BLUE
            ox = oy = 0
            if self.early_shake_timer > 0:
                ox = random.randint(-SHAKE_INTENSITY, SHAKE_INTENSITY)
                oy = random.randint(-SHAKE_INTENSITY, SHAKE_INTENSITY)
            pg.draw.rect(screen, LIGHT_GRAY, (x + ox, y + oy, bar_w, bar_h))
            pg.draw.rect(screen, bar_color, (x + ox, y + oy, int(bar_w * progress), bar_h))

    def mine_block(self, player, camera_x, camera_y):
        mouse_x, mouse_y = pg.mouse.get_pos()
        world_x, world_y = camera_x + mouse_x, camera_y + mouse_y
        block_x, block_y = (int(world_x) // TILE) * TILE, (int(world_y) // TILE) * TILE
        block = (block_x, block_y)
        cx = block_x + TILE / 2
        cy = block_y + TILE / 2
        dist = math.hypot(player.x - cx, player.y - cy)
        if dist <= MINING_RADIUS:
            btype = self.generate_block(block_x, block_y)
            return block, btype
        return block, None

# -------------------------------------------------------
# Crosshair + misc
# -------------------------------------------------------
def draw_crosshair(surface, color, cx, cy, size, thickness, player_pos=None, reveal_time=None):
    if player_pos:
        px, py = player_pos
        dx, dy = cx - px, cy - py
        dist = math.hypot(dx, dy)
        angle = math.atan2(dy, dx)
        for i in range(0, int(dist), 15):
            sx = px + i * math.cos(angle)
            sy = py + i * math.sin(angle)
            ex = px + min(i + 10, dist) * math.cos(angle)
            ey = py + min(i + 10, dist) * math.sin(angle)
            pg.draw.line(surface, color, (int(sx), int(sy)), (int(ex), int(ey)), thickness)

    pg.draw.line(surface, color, (cx - size, cy), (cx + size, cy), thickness)
    pg.draw.line(surface, color, (cx, cy - size), (cx, cy + size), thickness)
    pg.draw.circle(surface, color, (cx, cy), 12, thickness)

    if reveal_time:
        font = pg.font.SysFont(None, 30)
        txt = font.render(f"Reveal: {reveal_time/60:.1f}s", True, LIGHT_BLUE)
        surface.blit(txt, (cx - txt.get_width() // 2, cy + 20))

def draw_beam_fade(surface, axis, value_screen, alpha, thickness=10, color=(255, 80, 80)):
    beam = pg.Surface((w, h), pg.SRCALPHA)
    a = max(0, min(255, int(alpha)))
    r, g, b = color

    if axis == "h":
        y = int(value_screen)
        pg.draw.rect(beam, (r, g, b, a), (0, y - thickness // 2, w, thickness))
        pg.draw.rect(beam, (255, 255, 255, min(255, a)), (0, y - 2, w, 4))
    else:
        x = int(value_screen)
        pg.draw.rect(beam, (r, g, b, a), (x - thickness // 2, 0, thickness, h))
        pg.draw.rect(beam, (255, 255, 255, min(255, a)), (x - 2, 0, 4, h))

    surface.blit(beam, (0, 0))

def tile_center(bx, by):
    return (bx + TILE / 2, by + TILE / 2)

def player_tile_center(player):
    return (int(player.x // TILE) * TILE + TILE / 2, int(player.y // TILE) * TILE + TILE / 2)

def line_of_sight_air(ground: Ground, from_pos, to_pos):
    fx, fy = from_pos
    tx, ty = to_pos
    fx_t = int(fx // TILE) * TILE
    fy_t = int(fy // TILE) * TILE
    tx_t = int(tx // TILE) * TILE
    ty_t = int(ty // TILE) * TILE

    if fx_t == tx_t:
        step = TILE if ty_t > fy_t else -TILE
        y = fy_t + step
        while y != ty_t:
            if (fx_t, y) not in ground.mined_blocks:
                return False
            y += step
        return True

    if fy_t == ty_t:
        step = TILE if tx_t > fx_t else -TILE
        x = fx_t + step
        while x != tx_t:
            if (x, fy_t) not in ground.mined_blocks:
                return False
            x += step
        return True

    return False

# -------------------------------------------------------
# Skins menu (kept, but uses same background style)
# -------------------------------------------------------
async def skins_menu():
    global selected_skin

    pg.mouse.set_visible(True)
    pg.event.set_grab(False)

    font = pg.font.SysFont(None, 56)
    small = pg.font.SysFont(None, 28)
    tiny = pg.font.SysFont(None, 20)

    order = ["base", "survivor", "completionist"]

    while True:
        events = pg.event.get()
        music.update(events)

        screen.fill((20, 20, 25))
        title = font.render("Skins", True, LIGHT_BLUE)
        screen.blit(title, (w // 2 - title.get_width() // 2, 30))

        hint = small.render("Click a skin to equip. ESC to go back.", True, YELLOW)
        screen.blit(hint, (w // 2 - hint.get_width() // 2, 90))

        card_w, card_h = 260, 185
        spacing = 40
        total_width = card_w * 3 + spacing * 2
        start_x = (w - total_width) // 2
        y = 190

        clicked = False
        click_pos = None
        for e in events:
            if e.type == pg.QUIT:
                pg.quit()
                raise SystemExit
            if e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
                pg.mouse.set_visible(True)
                return
            if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                clicked = True
                click_pos = e.pos

        for i, key in enumerate(order):
            x = start_x + i * (card_w + spacing)
            rect = pg.Rect(x, y, card_w, card_h)

            unlocked = skins_unlocked.get(key, False)
            base_col = (50, 50, 60) if unlocked else (35, 35, 40)
            border = LIGHT_BLUE if key == selected_skin else (110, 110, 130)
            pg.draw.rect(screen, base_col, rect, border_radius=18)
            pg.draw.rect(screen, border, rect, 3, border_radius=18)

            col = SKINS[key]["color"]
            cx, cy = x + 48, y + 58
            pg.draw.circle(screen, col if unlocked else (80, 80, 80), (cx, cy), 18)
            pg.draw.circle(screen, BLACK, (cx, cy), 18, 2)

            name_font = pg.font.SysFont(None, 22 if key in ("survivor", "completionist") else 28)
            name_txt = name_font.render(SKINS[key]["name"], True, WHITE if unlocked else (140, 140, 140))
            screen.blit(name_txt, (x + 86, y + 22))

            if not unlocked:
                if key == "survivor":
                    lock_txt = "Unlock: Survive full timer in Heaven Challenge AND hit the money target."
                elif key == "completionist":
                    lock_txt = "Unlock: 100% the game (all worlds + max upgrades)."
                else:
                    lock_txt = "Locked."
                lock_color = (170, 170, 170)
            else:
                lock_txt = "Unlocked!"
                lock_color = YELLOW

            text_x = x + 86
            text_y = y + 60
            max_w = (x + card_w - 14) - text_x
            max_h = (y + card_h - 14) - text_y
            line_h = 18
            max_lines = max(1, max_h // line_h)
            lines = wrap_lines(tiny, lock_txt, max_w, max_lines=max_lines)

            ty = text_y
            for ln in lines:
                s = tiny.render(ln, True, lock_color)
                screen.blit(s, (text_x, ty))
                ty += line_h

            if clicked and click_pos and rect.collidepoint(click_pos):
                if unlocked:
                    selected_skin = key
                    popups.append(Popup(f"Skin equipped: {SKINS[key]['name']}", size=44, lifetime=160, color=GREEN))
                else:
                    popups.append(Popup("Skin locked!", size=44, lifetime=150, color=RED))

        for i, popup in enumerate(popups[:] ):
            popup.draw(i * 30)
            if not popup.update():
                popups.remove(popup)

        pg.display.flip()
        clock.tick(fps)
        await frame_yield()

# -------------------------------------------------------
# SHOP MENU (revamped to match your screenshot vibe)
# -------------------------------------------------------
async def shop_menu(total_money):
    global selected_world, boosted_mode

    pg.mouse.set_visible(True)
    pg.event.set_grab(False)
    music.set_mode("main")

    # Fonts styled to match pixel UI vibe (use SysFont but smaller + bold-ish sizes)
    title_font = pg.font.SysFont(None, 104)
    label_font = pg.font.SysFont(None, 34)
    small_font = pg.font.SysFont(None, 28)
    tiny_font  = pg.font.SysFont(None, 22)
    money_font = pg.font.SysFont(None, 54)

    options = [
        {"name": "MINE COOLDOWN", "key": "mining_speed", "max": 10, "cost_base": 250, "hotkey": "1"},
        {"name": "MINE POWER",    "key": "mine_power",   "max": 3,  "cost_tiers": {1: 8000, 2: 22000, 3: 55000}, "hotkey": "2"},
        {"name": "MINE FORTUNE",  "key": "fortune",      "max": 10, "cost_base": 200, "hotkey": "3"},
    ]

    while True:
        if is_100_percent() and not skins_unlocked["completionist"]:
            skins_unlocked["completionist"] = True
            popups.append(Popup("Unlocked skin: 100% (Yellow)!", size=52, lifetime=170, color=YELLOW))

        # --- Background template ---
        if SHOP_BG_SURF is not None:
            screen.blit(SHOP_BG_SURF, (0, 0))
        else:
            # fallback if template missing
            screen.fill((24, 26, 30))

        # --- Title ---
        tx, ty = SHOP_ANCHORS["title"]
        title = title_font.render("SHRED", True, (220, 220, 220))
        screen.blit(title, (tx - title.get_width()//2, ty - title.get_height()//2))

        # --- Skins button (clickable region matches template) ---
        skins_btn = SHOP_ANCHORS["skins_btn"]
        # (If your image already has a skins button drawn, don’t draw anything here—just keep it clickable.)
        # Optional small indicator dot:
        pg.draw.circle(screen, SKINS[selected_skin]["color"], (skins_btn.right + 24, skins_btn.centery), 10)
        pg.draw.circle(screen, BLACK, (skins_btn.right + 24, skins_btn.centery), 10, 2)

        # --- World text ---
        wx, wy = SHOP_ANCHORS["world"]
        world_txt = tiny_font.render(f"WORLD: {selected_world.upper()}  (N/H/J)", True, (255, 230, 70))
        screen.blit(world_txt, (wx - world_txt.get_width()//2, wy - world_txt.get_height()//2))

        # --- Challenge toggle ---
        cx, cy = SHOP_ANCHORS["challenge_center"]
        r = 22
        pg.draw.circle(screen, (0, 0, 0), (cx, cy), r + 6)
        pg.draw.circle(screen, (0, 180, 0) if boosted_mode else (120, 120, 120), (cx, cy), r)
        pg.draw.circle(screen, WHITE, (cx + (10 if boosted_mode else -10), cy), 9)

        cost = BOOST_COSTS[selected_world]
        c_label = tiny_font.render(f"CHALLENGE ${cost}", True, (255, 230, 70))
        screen.blit(c_label, (cx - c_label.get_width()//2, cy + 30))
        if boosted_mode:
            tgt = CHALLENGE_TARGETS[selected_world]
            tgt_txt = tiny_font.render(f"TARGET: ${tgt:.0f}", True, (255, 230, 70))
            screen.blit(tgt_txt, (cx - tgt_txt.get_width()//2, cy + 52))

        # --- Three upgrade panels (text aligned to template) ---
        for i, opt in enumerate(options, start=1):
            level = buffs[opt["key"]]
            if opt["key"] == "mine_power":
                costv = opt["cost_tiers"].get(level, 0) if level < opt["max"] else 0
            else:
                costv = opt["cost_base"] * level if level < opt["max"] else 0

            can_buy = (level < opt["max"] and total_money >= costv)

            # Label
            lx, ly = SHOP_ANCHORS[f"label_{i}"]
            lab = label_font.render(opt["name"], True, (220, 220, 220) if can_buy else (140, 140, 140))
            screen.blit(lab, (lx - lab.get_width()//2, ly - lab.get_height()//2))

            # Bar
            bx, by, bw, bh = SHOP_ANCHORS[f"bar_{i}"]
            pg.draw.rect(screen, (0, 0, 0), (bx-3, by-3, bw+6, bh+6))
            pg.draw.rect(screen, (110, 110, 110), (bx, by, bw, bh))
            frac = 0 if opt["max"] <= 0 else max(0.0, min(1.0, level / float(opt["max"])))
            pg.draw.rect(screen, (220, 220, 220) if can_buy else (160, 160, 160), (bx, by, int(bw * frac), bh))

            # LVL
            lvx, lvy = SHOP_ANCHORS[f"lvl_{i}"]
            lvl_s = small_font.render("LVL", True, (220, 220, 220))
            screen.blit(lvl_s, (lvx - lvl_s.get_width()//2, lvy - 28))
            num_s = small_font.render(str(level), True, (255, 230, 70))
            screen.blit(num_s, (lvx - num_s.get_width()//2, lvy))

            # Cost line
            cx2, cy2 = SHOP_ANCHORS[f"cost_{i}"]
            cost_color = (255, 230, 70) if can_buy else (150, 150, 150)
            ctext = tiny_font.render(f"[{opt['hotkey']}]  ${costv}", True, cost_color)
            screen.blit(ctext, (cx2 - ctext.get_width()//2, cy2 - ctext.get_height()//2))

        # --- Money (bottom box text aligned to template) ---
        mx, my = SHOP_ANCHORS["money"]
        mtxt = money_font.render(f"MONEY: ${total_money:.2f}", True, (230, 230, 230))
        screen.blit(mtxt, (mx - mtxt.get_width()//2, my - mtxt.get_height()//2))

        # Popups
        for i, popup in enumerate(popups[:] ):
            popup.draw(i * 30)
            if not popup.update():
                popups.remove(popup)

        pg.display.flip()

        events = pg.event.get()
        music.update(events)

        for e in events:
            if e.type == pg.QUIT:
                pg.quit()
                raise SystemExit

            if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                mxp, myp = pg.mouse.get_pos()
                if skins_btn.collidepoint(mxp, myp):
                    await skins_menu()
                    break

                # challenge toggle click
                if (mxp - cx) ** 2 + (myp - cy) ** 2 <= (r + 8) ** 2:
                    boosted_mode = not boosted_mode
                    popups.append(Popup(
                        "Challenge ON" if boosted_mode else "Challenge OFF",
                        size=44, lifetime=220, color=YELLOW, y=120
                    ))

            if e.type == pg.KEYDOWN:
                if e.key == pg.K_RETURN:
                    if boosted_mode:
                        cost_need = BOOST_COSTS[selected_world]
                        if total_money < cost_need:
                            popups.append(Popup(f"Need ${cost_need} for Challenge!", size=40, lifetime=190, color=YELLOW, y=120))
                            continue
                        total_money -= cost_need

                    pg.mouse.set_visible(False)
                    pg.event.set_grab(True)
                    return total_money

                if e.key in (pg.K_1, pg.K_2, pg.K_3):
                    idx = e.key - pg.K_1
                    opt = options[idx]
                    level = buffs[opt["key"]]
                    if level < opt["max"]:
                        if opt["key"] == "mine_power":
                            costv = opt["cost_tiers"].get(level, 0)
                        else:
                            costv = opt["cost_base"] * level
                        if total_money >= costv:
                            buffs[opt["key"]] += 1
                            total_money -= costv
                            popups.append(Popup(f"{opt['name']} upgraded!", size=40, lifetime=170, color=LIGHT_BLUE))

                if e.key == pg.K_n:
                    selected_world = "normal"

                if e.key == pg.K_h:
                    if not unlocks["hell"]:
                        if total_money >= HELL_UNLOCK_COST:
                            total_money -= HELL_UNLOCK_COST
                            unlocks["hell"] = True
                            popups.append(Popup("Hell unlocked!", size=42, lifetime=190, color=YELLOW))
                    if unlocks["hell"]:
                        selected_world = "hell"

                if e.key == pg.K_j:
                    if not unlocks["heaven"]:
                        if unlocks["hell"] and total_money >= HEAVEN_UNLOCK_COST:
                            total_money -= HEAVEN_UNLOCK_COST
                            unlocks["heaven"] = True
                            popups.append(Popup("Heaven unlocked!", size=42, lifetime=190, color=YELLOW))
                    if unlocks["heaven"]:
                        selected_world = "heaven"

        clock.tick(fps)
        await frame_yield()

# -------------------------------------------------------
# GAME SESSION (unchanged except uses updated tile drawing)
# -------------------------------------------------------
async def game_session(total_money):
    global cooldown_timer, COOLDOWN_MAX
    global run_boosted_mode

    run_boosted_mode = boosted_mode
    music.set_mode("challenge" if run_boosted_mode else "main")

    player = Player(0, 0)
    ground = Ground()

    lives = 3
    invuln = 0
    pending_damage = False

    # spawn clearance shifted up-left
    clear_tiles = [(-TILE, -TILE), (0, -TILE), (-TILE, 0), (0, 0)]
    for bx, by in clear_tiles:
        ground.block_types[(bx, by)] = "regular"
        ground.mined_blocks.add((bx, by))
        ground.ore_tiles.pop((bx, by), None)
        ground.hazard_tiles.pop((bx, by), None)

    def get_cooldown(level):
        base = 72
        t = base * (0.18 + 0.82 * ((10 - level) / 9) ** 2)
        return max(6, int(t))

    cooldown_timer = get_cooldown(buffs["mining_speed"])
    COOLDOWN_MAX = cooldown_timer
    popups.clear()
    if not run_boosted_mode:
        popups.append(Popup("STARTER RUSH: quick quests for bonus cash", size=40, lifetime=150, color=LIGHT_BLUE))

    duration_seconds = CHALLENGE_TIME if run_boosted_mode else SESSION_TIME
    session_frames = duration_seconds * fps

    session_money = 0.0
    blocks_mined = 0
    rarity_counts = {r: 0 for r in RARITY_ORDER}

    starter_quests = [
        {"title": "Warm-up", "desc": "Break 10 blocks", "kind": "blocks", "target": 10, "reward": 140},
        {"title": "Treasure ping", "desc": "Mine 3 ore blocks", "kind": "ore", "target": 3, "reward": 260},
        {"title": "Mystery block", "desc": "Break 1 powerup block", "kind": "powerup", "target": 1, "reward": 0},
    ]
    starter_counts = {"blocks": 0, "ore": 0, "powerup": 0}
    starter_quest_index = 0

    def register_starter_progress(kind):
        nonlocal starter_quest_index, session_money
        if run_boosted_mode or starter_quest_index >= len(starter_quests):
            return
        quest = starter_quests[starter_quest_index]
        starter_counts[kind] = starter_counts.get(kind, 0) + 1
        if kind != quest["kind"]:
            return
        if starter_counts[kind] < quest["target"]:
            return
        reward = quest.get("reward", 0)
        if reward:
            session_money += reward
            popups.append(Popup(f"QUEST COMPLETE +${reward}", size=48, lifetime=130, color=YELLOW))
        else:
            popups.append(Popup("QUEST COMPLETE", size=48, lifetime=130, color=YELLOW))
        if quest["kind"] == "powerup":
            active_powerups["Money Boost"] = [18 * fps, {}]
            active_powerups["Reveal"] = [10 * fps, {}]
            popups.append(Popup("BONUS: Money Boost + Reveal", size=42, lifetime=140, color=GREEN))
        starter_quest_index += 1
        if starter_quest_index < len(starter_quests):
            nxt = starter_quests[starter_quest_index]
            popups.append(Popup(f"NEW QUEST: {nxt['desc']}", size=38, lifetime=120, color=LIGHT_BLUE))

    elapsed_frames = 0

    blaster_cd = 5 * fps
    blaster_warn = 0
    blaster_fire = 0
    blaster_axis = None
    blaster_value = None
    blaster_dir = 1
    blaster_fire_total = 1

    lingering_beams = []
    vent_beams = []
    pending_smites = []

    ended_by_timer = False
    aborted_early = False
    died = False
    death_reason = "You died."

    running = True
    while running:
        dt_sec = clock.get_time() / 1000.0
        elapsed_frames += 1

        events = pg.event.get()
        music.update(events)

        for e in events:
            if e.type == pg.QUIT:
                pg.quit()
                raise SystemExit
            elif e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
                aborted_early = True
                running = False

        expired = []
        for p_name in list(active_powerups.keys()):
            active_powerups[p_name][0] -= 1
            if active_powerups[p_name][0] <= 0:
                expired.append(p_name)
        for p_name in expired:
            del active_powerups[p_name]

        confusion_multiplier = -1 if "Confusion" in active_powerups else 1

        if "Reveal" in active_powerups:
            ground.reveal_active = True
            ground.reveal_time = active_powerups["Reveal"][0]
        else:
            ground.reveal_active = False
            ground.reveal_time = 0

        if "Freeze Timer" not in active_powerups:
            session_frames -= 1

        money_multiplier = 2.0 if "Money Boost" in active_powerups else 1.0

        keys = pg.key.get_pressed()
        player.vel_x = player.vel_y = 0
        if keys[pg.K_a]:
            player.vel_x = -player.max_speed * confusion_multiplier
        if keys[pg.K_d]:
            player.vel_x = player.max_speed * confusion_multiplier
        if keys[pg.K_w]:
            player.vel_y = -player.max_speed * confusion_multiplier
        if keys[pg.K_s]:
            player.vel_y = player.max_speed * confusion_multiplier
        player.move(ground)

        if run_boosted_mode:
            ground.update_lava_flow()
            tx = int(player.x // TILE) * TILE
            ty = int(player.y // TILE) * TILE
            if (tx, ty) in ground.lava_pools and invuln == 0:
                pending_damage = True
                death_reason = "You fell into lava."

        world_now = get_active_world()

        if run_boosted_mode:
            t = min(1.0, elapsed_frames / float(duration_seconds * fps))
            interval = int((6.0 - 2.2 * t) * fps)
            warn_time = int((1.05 - 0.35 * t) * fps)
            fire_time = int((0.20 - 0.05 * t) * fps)

            interval = max(int(3.2 * fps), interval)
            warn_time = max(int(0.55 * fps), warn_time)
            fire_time = max(int(0.12 * fps), fire_time)

            blaster_cd -= 1
            if blaster_cd <= 0 and blaster_warn == 0 and blaster_fire == 0:
                px_tile, py_tile = player_tile_center(player)
                blaster_axis = random.choice(["h", "v"])
                blaster_value = py_tile if blaster_axis == "h" else px_tile
                blaster_dir = random.choice([1, -1])

                blaster_warn = warn_time
                blaster_fire_total = fire_time
                blaster_cd = interval

            if blaster_warn > 0:
                blaster_warn -= 1
                if blaster_warn == 0:
                    blaster_fire = blaster_fire_total

            if blaster_fire > 0:
                blaster_fire -= 1

                px_tile, py_tile = player_tile_center(player)
                hit = (py_tile == blaster_value) if blaster_axis == "h" else (px_tile == blaster_value)
                if hit and invuln == 0:
                    pending_damage = True
                    death_reason = "You got hit by a blaster."

                if blaster_fire == 0:
                    linger_frames = int(1.3 * fps)
                    lingering_beams.append({
                        "axis": blaster_axis,
                        "value_world": blaster_value,
                        "timer": linger_frames,
                        "max": linger_frames,
                        "color": (255, 80, 80),
                    })

        if run_boosted_mode and world_now == "hell":
            for pos in list(ground.fire_vent_cd.keys()):
                ground.fire_vent_cd[pos] -= 1
                if ground.fire_vent_cd[pos] <= 0:
                    ground.fire_vent_cd[pos] = random.randint(int(2.4 * fps), int(3.6 * fps))
                    vx, vy = tile_center(*pos)
                    px_tile, py_tile = player_tile_center(player)

                    if line_of_sight_air(ground, (vx, vy), (px_tile, py_tile)) and invuln == 0:
                        pending_damage = True
                        death_reason = "You were burned by a fire vent."

                    bx, by = pos
                    if (bx + TILE, by) in ground.mined_blocks or (bx - TILE, by) in ground.mined_blocks:
                        vent_beams.append({
                            "axis": "h",
                            "value_world": vy,
                            "timer": int(0.8 * fps),
                            "max": int(0.8 * fps),
                            "color": (255, 140, 60),
                        })
                    if (bx, by + TILE) in ground.mined_blocks or (bx, by - TILE) in ground.mined_blocks:
                        vent_beams.append({
                            "axis": "v",
                            "value_world": vx,
                            "timer": int(0.8 * fps),
                            "max": int(0.8 * fps),
                            "color": (255, 140, 60),
                        })

        for b in vent_beams[:]:
            b["timer"] -= 1
            if b["timer"] <= 0:
                vent_beams.remove(b)

        if run_boosted_mode and world_now == "heaven":
            for pos in list(ground.smite_cd.keys()):
                ground.smite_cd[pos] -= 1
                if ground.smite_cd[pos] <= 0:
                    ground.smite_cd[pos] = random.randint(int(2.6 * fps), int(4.2 * fps))
                    tx = int(player.x // TILE) * TILE
                    ty = int(player.y // TILE) * TILE
                    pending_smites.append({
                        "target_tile": (tx, ty),
                        "warn": int(0.85 * fps),
                        "strike": int(0.12 * fps),
                    })

        for sm in pending_smites[:]:
            if sm["warn"] > 0:
                sm["warn"] -= 1
            else:
                sm["strike"] -= 1
                if sm["strike"] <= 0:
                    tx, ty = sm["target_tile"]
                    px_t = int(player.x // TILE) * TILE
                    py_t = int(player.y // TILE) * TILE
                    if (px_t, py_t) == (tx, ty) and invuln == 0:
                        pending_damage = True
                        death_reason = "You were smitten."

                    cx, cy = tx + TILE/2, ty + TILE/2
                    lingering_beams.append({
                        "axis": "h",
                        "value_world": cy,
                        "timer": int(0.7 * fps),
                        "max": int(0.7 * fps),
                        "color": (140, 200, 255),
                    })
                    lingering_beams.append({
                        "axis": "v",
                        "value_world": cx,
                        "timer": int(0.7 * fps),
                        "max": int(0.7 * fps),
                        "color": (140, 200, 255),
                    })
                    pending_smites.remove(sm)

        for b in lingering_beams[:]:
            b["timer"] -= 1
            if b["timer"] <= 0:
                lingering_beams.remove(b)

        mouse_pressed = pg.mouse.get_pressed()
        if mouse_pressed[0]:
            if cooldown_timer >= COOLDOWN_MAX:
                camera_x0, camera_y0 = player.x - w // 2, player.y - h // 2
                block, btype = ground.mine_block(player, camera_x0, camera_y0)
                if btype:
                    blocks_to_mine = blocks_for_mine_power(buffs["mine_power"], player.x, player.y, block)
                    mine_power = buffs["mine_power"]

                    if "Heavy Pickaxe" in active_powerups:
                        heavy_r = 1 + (mine_power - 1)
                        extra = []
                        for bb in blocks_to_mine:
                            bx, by = bb
                            for dx in range(-heavy_r, heavy_r + 1):
                                for dy in range(-heavy_r, heavy_r + 1):
                                    extra.append((bx + dx * TILE, by + dy * TILE))
                        blocks_to_mine.extend(extra)

                    if "Bomb" in active_powerups:
                        px, py = player.x, player.y
                        bomb_r = TILE * (2.2 + 1.2 * (mine_power - 1))
                        for bx, by in ground.get_nearby_blocks(px, py):
                            if math.hypot((bx + TILE / 2) - px, (by + TILE / 2) - py) <= bomb_r:
                                blocks_to_mine.append((bx, by))
                        del active_powerups["Bomb"]

                    if "Random Explosion" in active_powerups:
                        count = 22 + 18 * (mine_power - 1)
                        spread = 3 + 2 * (mine_power - 1)
                        for _ in range(count):
                            rx = block[0] + random.randint(-spread, spread) * TILE
                            ry = block[1] + random.randint(-spread, spread) * TILE
                            blocks_to_mine.append((rx, ry))
                        del active_powerups["Random Explosion"]

                    seen = set()
                    uniq = []
                    for bb in blocks_to_mine:
                        if bb not in seen:
                            seen.add(bb)
                            uniq.append(bb)
                    blocks_to_mine = uniq

                    i = 0
                    while i < len(blocks_to_mine):
                        b = blocks_to_mine[i]
                        i += 1
                        if b in ground.mined_blocks:
                            continue

                        btype2 = ground.generate_block(b[0], b[1])
                        ground.mined_blocks.add(b)
                        blocks_mined += 1
                        register_starter_progress("blocks")

                        if run_boosted_mode:
                            ground.expose_adjacent_hazards(b)

                        if btype2 == "hazard":
                            hz = ground.hazard_tiles.get(b, "lava")
                            if hz == "bomb_trap":
                                popups.append(Popup("BOMB!", size=52, lifetime=120, color=RED))
                                bx, by = b
                                bomb_cx, bomb_cy = bx + TILE / 2, by + TILE / 2
                                blast_r = TILE * 2.0
                                if math.hypot(player.x - bomb_cx, player.y - bomb_cy) <= blast_r and invuln == 0:
                                    pending_damage = True
                                    death_reason = "You got caught in a bomb blast."
                                for ex in range(-2, 3):
                                    for ey in range(-2, 3):
                                        nbx = bx + ex * TILE
                                        nby = by + ey * TILE
                                        if (nbx, nby) in ground.mined_blocks:
                                            continue
                                        if math.hypot((nbx + TILE / 2) - bomb_cx, (nby + TILE / 2) - bomb_cy) <= blast_r:
                                            blocks_to_mine.append((nbx, nby))

                            ground.hazard_tiles.pop(b, None)
                            continue

                        if btype2 == "ore" and b in ground.ore_tiles:
                            rarity2 = ground.ore_tiles[b]
                            rarity_counts[rarity2] = rarity_counts.get(rarity2, 0) + 1

                            world = get_active_world()
                            pool = ORE_OPTIONS_WORLD[world][rarity2]
                            ore_name, ore_value = random.choice(list(pool.items()))
                            ore_value *= (1 + buffs["fortune"] * 0.05) * money_multiplier
                            session_money += ore_value
                            ore_color = RARITY_COLORS.get(rarity2, WHITE)
                            popups.append(Popup(f"+{ore_name} (${ore_value:.2f})", size=44, lifetime=140, color=ore_color))
                            register_starter_progress("ore")
                            del ground.ore_tiles[b]

                        elif btype2 == "powerup" and b in ground.ore_tiles:
                            p_name = ground.ore_tiles[b]
                            active_powerups[p_name] = [REVEAL_DURATION if p_name == "Reveal" else POWERUP_DURATION, {}]
                            popups.append(Popup(f"POWERUP: {p_name}!", size=54, lifetime=160, color=GREEN))
                            register_starter_progress("powerup")
                            del ground.ore_tiles[b]

                    cooldown_timer = 0
                    ground.early_shake_timer = 0
            else:
                ground.early_shake_timer = EARLY_SHAKE_DURATION

        if cooldown_timer < COOLDOWN_MAX:
            cooldown_timer += 1
        if ground.early_shake_timer > 0:
            ground.early_shake_timer -= 1

        if run_boosted_mode:
            if invuln > 0:
                invuln -= 1
            if pending_damage and invuln == 0:
                pending_damage = False
                lives -= 1
                invuln = int(1.1 * fps)
                if lives <= 0:
                    died = True
                    running = False
        else:
            pending_damage = False

        screen.fill(BLACK)
        camera_x, camera_y = player.x - w // 2, player.y - h // 2
        cursor_screen_pos = pg.mouse.get_pos()
        cursor_world_pos = (camera_x + cursor_screen_pos[0], camera_y + cursor_screen_pos[1])

        ground.draw(camera_x, camera_y, player.x, player.y, cursor_world_pos, cursor_screen_pos, dt_sec)

        if run_boosted_mode and blaster_axis is not None:
            if blaster_warn > 0:
                pulse = 0.5 + 0.5 * math.sin(pg.time.get_ticks() * 0.02)
                thick = 2 + int(2 * pulse)
                if blaster_axis == "h":
                    yv = blaster_value - camera_y
                    pg.draw.line(screen, YELLOW, (0, int(yv)), (w, int(yv)), thick)
                else:
                    xv = blaster_value - camera_x
                    pg.draw.line(screen, YELLOW, (int(xv), 0), (int(xv), h), thick)

            if blaster_fire > 0:
                progress = 1.0 - (blaster_fire / float(max(1, blaster_fire_total)))
                beam_thick = 10
                if blaster_axis == "h":
                    yv = int(blaster_value - camera_y)
                    if blaster_dir > 0:
                        x0, x1 = 0, int(w * progress)
                    else:
                        x0, x1 = int(w * (1.0 - progress)), w
                    pg.draw.rect(screen, (255, 80, 80), (x0, yv - beam_thick // 2, max(1, x1 - x0), beam_thick))
                    pg.draw.rect(screen, (255, 180, 180), (x0, yv - 2, max(1, x1 - x0), 4))
                else:
                    xv = int(blaster_value - camera_x)
                    if blaster_dir > 0:
                        y0, y1 = 0, int(h * progress)
                    else:
                        y0, y1 = int(h * (1.0 - progress)), h
                    pg.draw.rect(screen, (255, 80, 80), (xv - beam_thick // 2, y0, beam_thick, max(1, y1 - y0)))
                    pg.draw.rect(screen, (255, 180, 180), (xv - 2, y0, 4, max(1, y1 - y0)))

        if run_boosted_mode:
            for b in lingering_beams:
                frac = b["timer"] / float(max(1, b["max"]))
                alpha = 210 * frac
                axis = b["axis"]
                value_world = b["value_world"]
                value_screen = (value_world - camera_y) if axis == "h" else (value_world - camera_x)
                draw_beam_fade(screen, axis, value_screen, alpha, thickness=10, color=b.get("color", (255, 80, 80)))

            for b in vent_beams:
                frac = b["timer"] / float(max(1, b["max"]))
                alpha = 200 * frac
                axis = b["axis"]
                value_world = b["value_world"]
                value_screen = (value_world - camera_y) if axis == "h" else (value_world - camera_x)
                draw_beam_fade(screen, axis, value_screen, alpha, thickness=10, color=b.get("color", (255, 140, 60)))

            for sm in pending_smites:
                if sm["warn"] > 0:
                    tx, ty = sm["target_tile"]
                    sx, sy = tx - camera_x, ty - camera_y
                    pg.draw.rect(screen, (140, 200, 255), (sx + 4, sy + 4, TILE - 8, TILE - 8), 3)

        draw_crosshair(
            screen, RED, cursor_screen_pos[0], cursor_screen_pos[1], 15, 2,
            player_pos=(player.x - camera_x, player.y - camera_y),
            reveal_time=ground.reveal_time if ground.reveal_active else None
        )

        font = pg.font.SysFont(None, 32)
        world_txt = font.render(f"World: {get_active_world().upper()}", True, YELLOW)
        screen.blit(world_txt, (w - world_txt.get_width() - 20, 60))

        timer_text = pg.font.SysFont(None, 40).render(f"Time: {max(0, session_frames // fps)}", True, YELLOW)
        screen.blit(timer_text, (w - 200, 15))

        if run_boosted_mode:
            mode_txt = pg.font.SysFont(None, 28).render("Challenge: ON", True, YELLOW)
            screen.blit(mode_txt, (w - mode_txt.get_width() - 20, 95))
            lives_txt = pg.font.SysFont(None, 36).render(f"Lives: {lives}", True, YELLOW)
            screen.blit(lives_txt, (w - lives_txt.get_width() - 20, 130))

        if not run_boosted_mode and starter_quest_index < len(starter_quests):
            quest = starter_quests[starter_quest_index]
            qsurf = pg.Surface((300, 78), pg.SRCALPHA)
            qsurf.fill((8, 10, 16, 190))
            screen.blit(qsurf, (18, 16))
            pg.draw.rect(screen, LIGHT_BLUE, (18, 16, 300, 78), 2, border_radius=10)
            draw_text("Starter Rush", 28, YELLOW, 32, 24)
            draw_text(quest["desc"], 26, WHITE, 32, 50)
            draw_text(f"{min(starter_counts[quest['kind']], quest['target'])}/{quest['target']}", 28, GREEN, 278, 50, center=True)

        for i, popup in enumerate(popups[:] ):
            popup.draw(i * 30)
            if not popup.update():
                popups.remove(popup)

        player.draw(camera_x, camera_y, invuln=(invuln if run_boosted_mode else 0))
        pg.display.flip()
        clock.tick(fps)
        await frame_yield()

        if session_frames <= 0:
            ended_by_timer = True
            running = False

    earned = session_money
    if ended_by_timer:
        payout_mult = 1.0
    else:
        payout_mult = 0.25 if run_boosted_mode else 0.75
    payout = earned * payout_mult

    if run_boosted_mode and ended_by_timer and get_active_world() == "heaven":
        target = CHALLENGE_TARGETS["heaven"]
        if session_money >= target and not skins_unlocked["survivor"]:
            skins_unlocked["survivor"] = True

    if is_100_percent() and not skins_unlocked["completionist"]:
        skins_unlocked["completionist"] = True

    title = "GAME OVER" if died else ("RUN COMPLETE" if ended_by_timer else "RUN ENDED")
    mode_name = "Challenge" if run_boosted_mode else "Normal"
    time_left_s = session_frames / fps
    lives_left = max(0, lives)
    reason = death_reason if died else ("Timer finished!" if ended_by_timer else "You left early.")

    await run_summary_screen(
        title_text=title,
        world_name=get_active_world(),
        mode_name=mode_name,
        earned=earned,
        payout=payout,
        payout_mult=payout_mult,
        reason=reason,
        time_left_s=time_left_s,
        lives_left=lives_left,
        mined_count=blocks_mined,
        rarity_counts=rarity_counts,
        show_lives=run_boosted_mode,
    )

    return total_money + payout



# =======================================================
# PATCHED OVERRIDES: tutorial, better caves, darker world
# background, menu layout editing + saving, secret combo
# =======================================================
import json
from pathlib import Path as _Path

_ORIG_SYSFONT = pg.font.SysFont
_UI_FONT_CACHE = {}
_FONT_SIZE_SCALE = 0.78
_UI_FONT_STACK = ["arial", "verdana", "dejavusans", "liberationsans"]
_TITLE_FONT_STACK = ["arial", "verdana", "dejavusans", "liberationsans"]

def _best_font_name(size):
    stack = _TITLE_FONT_STACK if size >= 56 else _UI_FONT_STACK
    for candidate in stack:
        if pg.font.match_font(candidate):
            return candidate
    return None

def _scaled_font_size(size):
    return max(12, int(round(float(size) * _FONT_SIZE_SCALE)))

def _patched_sysfont(name, size, bold=False, italic=False):
    real_size = _scaled_font_size(size)
    key = (name, int(real_size), bool(bold), bool(italic))
    if key in _UI_FONT_CACHE:
        return _UI_FONT_CACHE[key]
    chosen = name if name else _best_font_name(real_size)
    try:
        if chosen and pg.font.match_font(chosen):
            font = _ORIG_SYSFONT(chosen, int(real_size), bold=bold, italic=italic)
        else:
            font = _ORIG_SYSFONT(None, int(real_size), bold=bold, italic=italic)
    except TypeError:
        font = _ORIG_SYSFONT(chosen, int(real_size), bold, italic)
    _UI_FONT_CACHE[key] = font
    return font

pg.font.SysFont = _patched_sysfont

def fit_font_to_width(text, base_size, max_width, min_size=14, bold=False):
    size = int(base_size)
    while size >= min_size:
        font = pg.font.SysFont(None, size, bold=bold)
        if font.size(str(text))[0] <= max_width:
            return font
        size -= 1
    return pg.font.SysFont(None, max(min_size, 12), bold=bold)


def _ellipsis_text(font, text, max_width):
    msg = str(text)
    if font.size(msg)[0] <= max_width:
        return msg
    dots = '...'
    while msg and font.size(msg + dots)[0] > max_width:
        msg = msg[:-1]
    return (msg + dots) if msg else dots


def _wrap_fit_lines(text, base_size, width, height, bold=False, min_size=12):
    msg = str(text)
    size = int(base_size)
    while size >= min_size:
        font = pg.font.SysFont(None, size, bold=bold)
        line_h = font.get_linesize()
        max_lines = max(1, height // max(1, line_h)) if height else 1
        lines = wrap_lines(font, msg, width, max_lines=max_lines)
        if len(lines) <= max_lines:
            if max_lines > 0 and lines:
                last = _ellipsis_text(font, lines[-1], width)
                lines = lines[:-1] + [last]
            return font, lines
        size -= 1
    font = pg.font.SysFont(None, max(min_size, 12), bold=bold)
    line_h = font.get_linesize()
    max_lines = max(1, height // max(1, line_h)) if height else 1
    lines = wrap_lines(font, msg, width, max_lines=max_lines)
    if lines:
        lines[-1] = _ellipsis_text(font, lines[-1], width)
    return font, lines


def draw_text(text, size, color, x, y, center=False, max_width=None, shadow=True, bold=False):
    msg = str(text)
    if max_width:
        font = fit_font_to_width(msg, size, max_width, min_size=max(11, int(size * 0.55)), bold=bold)
        msg = _ellipsis_text(font, msg, max_width)
    else:
        font = pg.font.SysFont(None, size, bold=bold)
    surf = font.render(msg, True, color)
    px = int(x - surf.get_width() // 2) if center else int(x)
    py = int(y - surf.get_height() // 2) if center else int(y)
    if shadow:
        shadow_surf = font.render(msg, True, (0, 0, 0))
        shadow_surf.set_alpha(110)
        screen.blit(shadow_surf, (px + 1, py + 2))
    screen.blit(surf, (px, py))
    return surf


def draw_text_in_rect(text, rect, size, color, align='center', valign='center', padding=8, shadow=True, bold=False):
    if not isinstance(rect, pg.Rect):
        rect = pg.Rect(rect)
    inner = rect.inflate(-padding * 2, -padding * 2)
    if inner.w <= 4 or inner.h <= 4:
        return None
    font, lines = _wrap_fit_lines(str(text), size, inner.w, inner.h, bold=bold, min_size=max(11, int(size * 0.52)))
    if not lines:
        return None
    line_h = font.get_linesize()
    total_h = line_h * len(lines)
    if valign == 'top':
        y = inner.y
    elif valign == 'bottom':
        y = inner.bottom - total_h
    else:
        y = inner.centery - total_h // 2
    clip_prev = screen.get_clip()
    screen.set_clip(rect)
    for line in lines:
        surf = font.render(line, True, color)
        if align == 'left':
            x = inner.x
        elif align == 'right':
            x = inner.right - surf.get_width()
        else:
            x = inner.centerx - surf.get_width() // 2
        if shadow:
            sh = font.render(line, True, (0, 0, 0))
            sh.set_alpha(110)
            screen.blit(sh, (x + 1, y + 2))
        screen.blit(surf, (x, y))
        y += line_h
    screen.set_clip(clip_prev)
    return True


def draw_ui_panel(rect, border=(95, 195, 255), fill=(11, 14, 22, 218), radius=18, glow=False):
    if not isinstance(rect, pg.Rect):
        rect = pg.Rect(rect)
    panel = pg.Surface(rect.size, pg.SRCALPHA)
    pg.draw.rect(panel, fill, panel.get_rect(), border_radius=radius)
    if glow:
        pg.draw.rect(panel, (*border, 55), panel.get_rect(), 4, border_radius=radius)
    screen.blit(panel, rect.topleft)
    pg.draw.rect(screen, border, rect, 2, border_radius=radius)


def draw_badge(rect, text, fg=WHITE, bg=(40, 46, 62), border=(95, 195, 255), size=20):
    draw_ui_panel(rect, border=border, fill=(*bg, 220), radius=12)
    draw_text_in_rect(text, rect, size, fg, padding=6, bold=True)
# ---------- first boot tutorial ----------
TUTORIAL_FLAG = resource_path("tutorial_seen_v2.flag")

def tutorial_seen():
    return os.path.exists(TUTORIAL_FLAG)

def mark_tutorial_seen():
    try:
        with open(TUTORIAL_FLAG, "w", encoding="utf-8") as f:
            f.write("seen")
    except Exception:
        pass

async def tutorial_menu():
    pages = [
        {"title": "Welcome to Shred", "body": "Shred is built around fast mining runs. Break through caves, grab ore for money, pick up powerup blocks, and head back to the menu to buy upgrades for your next run."},
        {"title": "Movement and Mining", "body": "Move with WASD and aim with the mouse. Clicking mines the closest block in the direction you aim. It only works within 2 blocks, so you need to get close and move with intention."},
        {"title": "Ore and Economy", "body": "Ore blocks are your money makers. Common ore keeps runs steady, while rarer ore can spike your payout fast. The shop upgrades your cooldown, mine power, and fortune so every run gets stronger."},
        {"title": "Powerup Blocks", "body": "Powerup blocks can help or hurt. Reveal and Money Boost are great for profit. Heavy Pickaxe can blow open a path. Blindness and Confusion are risky. They make runs feel less predictable."},
        {"title": "Modifiers and Challenge", "body": "Every run uses a modifier. Classic is steady. Challenge adds hazards, more lives, a target payout, and bigger pressure. Later modifiers like Ore Surge and Powerup Storm unlock through progression."},
        {"title": "Questlines and Bounties", "body": "Questlines are your long-term progression and gate the next world. Run Bounties are short goals inside a single run. They pay bonus cash and rewards fast, so even short sessions feel exciting."},
    ]
    page = 0
    while True:
        events = pg.event.get()
        music.update(events)
        clicked = None
        for e in events:
            if e.type == pg.QUIT:
                pg.quit(); raise SystemExit
            if e.type == pg.KEYDOWN:
                if e.key in (pg.K_RIGHT, pg.K_d, pg.K_RETURN, pg.K_SPACE):
                    if page < len(pages) - 1:
                        page += 1
                    else:
                        mark_tutorial_seen(); return
                elif e.key in (pg.K_LEFT, pg.K_a, pg.K_BACKSPACE):
                    if page > 0:
                        page -= 1
                elif e.key == pg.K_ESCAPE:
                    mark_tutorial_seen(); return
            if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                clicked = e.pos
        screen.fill((9, 12, 18))
        card = pg.Rect(86, 54, 828, 592)
        draw_ui_panel(card, border=(88, 190, 255), fill=(9, 14, 22, 235), radius=28, glow=True)
        head = pg.Rect(card.x+32, card.y+24, card.w-64, 66)
        draw_text_in_rect('HOW TO PLAY', head, 58, LIGHT_BLUE, bold=True)
        draw_badge(pg.Rect(card.right-118, card.y+28, 76, 38), f'{page+1}/{len(pages)}', fg=WHITE, border=(88, 190, 255), size=20)
        title_rect = pg.Rect(card.x+68, card.y+120, card.w-136, 54)
        draw_text_in_rect(pages[page]['title'], title_rect, 40, WHITE, bold=True)
        body_rect = pg.Rect(card.x+78, card.y+202, card.w-156, 216)
        draw_ui_panel(body_rect, border=(44, 54, 74), fill=(15, 20, 32, 220), radius=20)
        draw_text_in_rect(pages[page]['body'], pg.Rect(body_rect.x+20, body_rect.y+18, body_rect.w-40, body_rect.h-36), 30, (232, 236, 244), align='left', valign='top', padding=2)
        tips_rect = pg.Rect(card.x+78, card.y+444, card.w-156, 78)
        draw_ui_panel(tips_rect, border=(44, 54, 74), fill=(15, 20, 32, 210), radius=18)
        draw_text_in_rect('A/D or Left/Right to move pages. Enter/Space continues. Esc skips.', pg.Rect(tips_rect.x+16, tips_rect.y+14, tips_rect.w-32, 22), 22, LIGHT_BLUE)
        draw_text_in_rect('You can reopen this tutorial from the main menu any time.', pg.Rect(tips_rect.x+16, tips_rect.y+42, tips_rect.w-32, 18), 20, YELLOW)
        back_btn = pg.Rect(card.x+90, card.bottom-74, 180, 46)
        next_btn = pg.Rect(card.right-270, card.bottom-74, 180, 46)
        done_btn = pg.Rect(card.centerx-90, card.bottom-74, 180, 46)
        if page > 0:
            draw_ui_panel(back_btn, border=(88, 190, 255), fill=(26, 36, 58, 235), radius=16)
            draw_text_in_rect('BACK', back_btn, 24, WHITE, bold=True)
        if page < len(pages) - 1:
            draw_ui_panel(next_btn, border=(88, 190, 255), fill=(26, 36, 58, 235), radius=16)
            draw_text_in_rect('NEXT', next_btn, 24, WHITE, bold=True)
        else:
            draw_ui_panel(done_btn, border=(125, 235, 125), fill=(24, 52, 32, 235), radius=16)
            draw_text_in_rect('START PLAYING', done_btn, 24, WHITE, bold=True)
        if clicked:
            if page > 0 and back_btn.collidepoint(clicked):
                page -= 1
            elif page < len(pages) - 1 and next_btn.collidepoint(clicked):
                page += 1
            elif page == len(pages) - 1 and done_btn.collidepoint(clicked):
                mark_tutorial_seen(); return
        pg.display.flip(); clock.tick(fps); await frame_yield()

# ---------- layout editor + secret combo ----------
SECRET_COMBO = [
    pg.K_UP, pg.K_DOWN, pg.K_LEFT, pg.K_RIGHT,
    pg.K_UP, pg.K_UP, pg.K_DOWN, pg.K_DOWN
]
_secret_progress = []
layout_edit_mode = False
cheat_mode = False

SHOP_ANCHOR_START = "# -- SHOP_ANCHORS START --"
SHOP_ANCHOR_END = "# -- SHOP_ANCHORS END --"
SHOP_LAYOUT_JSON = resource_path("shop_layout.json")

def _rect_to_tuple(v):
    if isinstance(v, pg.Rect):
        return {"__rect__": True, "x": v.x, "y": v.y, "w": v.w, "h": v.h}
    return v

def _tuple_to_rect(v):
    if isinstance(v, dict) and v.get("__rect__"):
        return pg.Rect(v["x"], v["y"], v["w"], v["h"])
    return v

def export_shop_anchors():
    return {k: _rect_to_tuple(v) for k, v in SHOP_ANCHORS.items()}

def apply_shop_anchors(data):
    for k, v in data.items():
        SHOP_ANCHORS[k] = _tuple_to_rect(v)

def save_shop_layout_json():
    try:
        with open(SHOP_LAYOUT_JSON, "w", encoding="utf-8") as f:
            json.dump(export_shop_anchors(), f, indent=4)
    except Exception:
        pass

def load_shop_layout_json():
    try:
        if os.path.exists(SHOP_LAYOUT_JSON):
            with open(SHOP_LAYOUT_JSON, "r", encoding="utf-8") as f:
                apply_shop_anchors(json.load(f))
    except Exception:
        pass

def _anchor_repr():
    lines = ["SHOP_ANCHORS = {"]
    for k, v in SHOP_ANCHORS.items():
        if isinstance(v, pg.Rect):
            lines.append(f'    "{k}": pg.Rect({v.x}, {v.y}, {v.w}, {v.h}),')
        else:
            lines.append(f'    "{k}": {repr(v)},')
    lines.append("}")
    return "\n".join(lines)

def save_shop_anchors_to_source():
    save_shop_layout_json()
    try:
        src_path = _Path(__file__)
        text = src_path.read_text(encoding="utf-8")
        start = text.find(SHOP_ANCHOR_START)
        end = text.find(SHOP_ANCHOR_END)
        block = SHOP_ANCHOR_START + "\n" + _anchor_repr() + "\n" + SHOP_ANCHOR_END
        if start != -1 and end != -1 and end > start:
            end += len(SHOP_ANCHOR_END)
            new_text = text[:start] + block + text[end:]
        else:
            import re
            pattern = r'SHOP_ANCHORS\s*=\s*\{.*?\n\}'
            new_text, count = re.subn(pattern, _anchor_repr(), text, count=1, flags=re.S)
            if count == 0:
                return False
        src_path.write_text(new_text, encoding="utf-8")
        return True
    except Exception:
        return False

def handle_secret_combo(event):
    global layout_edit_mode, cheat_mode
    if event.type != pg.KEYDOWN:
        return False
    _secret_progress.append(event.key)
    if len(_secret_progress) > len(SECRET_COMBO):
        del _secret_progress[0]
    if _secret_progress == SECRET_COMBO:
        layout_edit_mode = not layout_edit_mode
        cheat_mode = not cheat_mode
        if not layout_edit_mode:
            save_shop_anchors_to_source()
        popups.append(Popup(
            f"SECRET: layout {'ON' if layout_edit_mode else 'OFF'} | cheats {'ON' if cheat_mode else 'OFF'}",
            size=38, lifetime=220, color=YELLOW, y=120
        ))
        _secret_progress.clear()
        return True
    return False

load_shop_layout_json()

WORLD_BASE_COLORS = {
    "normal": (90, 90, 100),
    "hell": (125, 62, 62),
    "heaven": (210, 210, 210),
}

WORLD_DATA = {
    name: {"tile_tint": color}
    for name, color in WORLD_BASE_COLORS.items()
}

def darker_world_color(world=None):
    world = world or get_active_world()
    base = WORLD_BASE_COLORS.get(world, (80, 80, 85))
    return tuple(max(8, int(c * 0.28)) for c in base)

# ---------- Better cave generation ----------
def _chunk_seed(cx, cy, salt=0):
    return ((cx * 92837111) ^ (cy * 689287499) ^ (salt * 19349663) ^ 0xA2C79) & 0xFFFFFFFF

def _segment_distance(px, py, ax, ay, bx, by):
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / denom))
    cx, cy = ax + abx * t, ay + aby * t
    return math.hypot(px - cx, py - cy)

CAVE_REGION_W = 18
CAVE_REGION_H = 18

@lru_cache(maxsize=None)
def _curve_region(rx, ry):
    rng = random.Random(_chunk_seed(rx, ry, 71))
    worms = []
    caverns = []

    worm_count = 2 + rng.randint(0, 2)
    if (rx, ry) == (0, 0):
        worm_count += 1

    for _ in range(worm_count):
        x = rx * CAVE_REGION_W + rng.uniform(3.0, CAVE_REGION_W - 3.0)
        y = ry * CAVE_REGION_H + rng.uniform(3.0, CAVE_REGION_H - 3.0)
        ang = rng.uniform(0.0, math.tau)
        width = rng.uniform(1.4, 2.6)
        steps = rng.randint(10, 24)
        pts = [(x, y)]
        for _step in range(steps):
            ang += rng.uniform(-0.62, 0.62)
            if rng.random() < 0.18:
                ang += rng.uniform(-0.85, 0.85)
            step_len = rng.uniform(0.9, 1.8)
            x += math.cos(ang) * step_len
            y += math.sin(ang) * step_len
            pts.append((x, y))
            if rng.random() < 0.12:
                caverns.append((x, y, rng.uniform(1.8, 3.4), rng.uniform(1.4, 2.8)))
        worms.append((tuple(pts), width))

    cavern_count = 1 + rng.randint(0, 1)
    if (rx, ry) == (0, 0):
        cavern_count += 1
    for _ in range(cavern_count):
        caverns.append((
            rx * CAVE_REGION_W + rng.uniform(3.0, CAVE_REGION_W - 3.0),
            ry * CAVE_REGION_H + rng.uniform(3.0, CAVE_REGION_H - 3.0),
            rng.uniform(2.2, 4.6),
            rng.uniform(1.8, 3.7),
        ))

    return {"worms": worms, "caverns": tuple(caverns)}

def _tile_in_curve_region(tx, ty, region):
    for cx, cy, rx, ry in region["caverns"]:
        dx = (tx - cx) / max(0.001, rx)
        dy = (ty - cy) / max(0.001, ry)
        if dx * dx + dy * dy <= 1.0:
            return True
    for pts, width in region["worms"]:
        for i in range(len(pts) - 1):
            ax, ay = pts[i]
            bx, by = pts[i + 1]
            if _segment_distance(tx, ty, ax, ay, bx, by) <= width:
                return True
    return False

@lru_cache(maxsize=None)
def _is_natural_air_cached(tx, ty):
    if max(abs(tx), abs(ty)) <= 1:
        return True

    # Bigger connected spawn cave so early game starts fast.
    if (tx * tx) / 20.0 + (ty * ty) / 12.0 <= 1.0:
        return True

    rx = math.floor(tx / CAVE_REGION_W)
    ry = math.floor(ty / CAVE_REGION_H)
    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            if _tile_in_curve_region(tx, ty, _curve_region(rx + ox, ry + oy)):
                return True

    # Small chance of side pockets close to curvy tunnels so caves feel more organic.
    pocket_rng = random.Random(_chunk_seed(tx, ty, 103))
    if pocket_rng.random() < 0.015:
        return True
    return False

class Ground(Ground):
    def is_natural_air(self, bx, by):
        return _is_natural_air_cached(int(bx // TILE), int(by // TILE))

    def is_solid_tile(self, bx, by):
        return (bx, by) not in self.mined_blocks and not self.is_natural_air(bx, by)

    def get_nearby_blocks(self, px, py):
        start_x = int((px - w // 2) // TILE) - 1
        end_x = int((px + w // 2) // TILE) + 2
        start_y = int((py - h // 2) // TILE) - 1
        end_y = int((py + h // 2) // TILE) + 2
        blocks = []
        for tx in range(start_x, end_x):
            for ty in range(start_y, end_y):
                bx, by = tx * TILE, ty * TILE
                if self.is_solid_tile(bx, by):
                    blocks.append((bx, by))
        return blocks

    def exposure_mask(self, bx, by):
        m = 0
        if not self.is_solid_tile(bx, by - TILE): m |= 1
        if not self.is_solid_tile(bx + TILE, by): m |= 2
        if not self.is_solid_tile(bx, by + TILE): m |= 4
        if not self.is_solid_tile(bx - TILE, by): m |= 8
        return m

    def mine_block(self, player, camera_x, camera_y):
        mouse_x, mouse_y = pg.mouse.get_pos()
        world_x, world_y = camera_x + mouse_x, camera_y + mouse_y
        dx = world_x - player.x
        dy = world_y - player.y
        dist = math.hypot(dx, dy)
        if dist <= 1e-6:
            return None, None
        ux, uy = dx / dist, dy / dist
        best = None
        best_proj = 10**9
        for step in range(1, 3):
            sx = player.x + ux * (step * TILE)
            sy = player.y + uy * (step * TILE)
            bx, by = int(sx // TILE) * TILE, int(sy // TILE) * TILE
            if not self.is_solid_tile(bx, by):
                continue
            cx = bx + TILE / 2
            cy = by + TILE / 2
            vx, vy = cx - player.x, cy - player.y
            proj = vx * ux + vy * uy
            perp = abs(vx * uy - vy * ux)
            if proj < 10 or proj > TILE * 2.45 or perp > TILE * 0.6:
                continue
            if proj < best_proj:
                best_proj = proj
                best = (bx, by)
        if best is None:
            return None, None
        return best, self.generate_block(*best)

    def draw(self, camera_x, camera_y, player_x, player_y, cursor_world_pos, cursor_screen_pos, dt_sec):
        screen.fill(darker_world_color(get_active_world()))
        world = get_active_world()
        bg = darker_world_color(world)
        alt = tuple(min(255, c + 10) for c in bg)
        px, py = player_x, player_y
        min_tx = int((px - w // 2) // TILE) - 2
        max_tx = int((px + w // 2) // TILE) + 3
        min_ty = int((py - h // 2) // TILE) - 2
        max_ty = int((py + h // 2) // TILE) + 3
        t = pg.time.get_ticks() * 0.001
        for tx in range(min_tx, max_tx):
            for ty in range(min_ty, max_ty):
                bx, by = tx * TILE, ty * TILE
                if self.is_solid_tile(bx, by):
                    continue
                sx, sy = bx - camera_x, by - camera_y
                col = alt if ((tx + ty) & 1) == 0 else bg
                pg.draw.rect(screen, col, (sx, sy, TILE, TILE))
                if (tx + ty) % 7 == 0:
                    a = 14 + int(10 * (0.5 + 0.5 * math.sin(t + tx * 0.3 + ty * 0.17)))
                    fog = pg.Surface((TILE, TILE), pg.SRCALPHA)
                    fog.fill((0, 0, 0, a))
                    screen.blit(fog, (sx, sy))
        super().draw(camera_x, camera_y, player_x, player_y, cursor_world_pos, cursor_screen_pos, dt_sec)

    def generate_block(self, bx, by):
        if (bx, by) in self.block_types:
            return self.block_types[(bx, by)]
        spawn_dist = math.hypot(bx / TILE, by / TILE)
        ore_bonus = 0.08 if spawn_dist < 10 else 0.0
        pwr_bonus = 0.012 if spawn_dist < 8 else 0.0
        if run_boosted_mode and random.random() < BOOST_HAZARD_SPAWN_CHANCE:
            world = get_active_world()
            pool = BASE_HAZARDS + WORLD_UNIQUE_HAZARDS.get(world, [])
            hz = random.choice(pool) if pool else "lava"
            self.hazard_tiles[(bx, by)] = hz
            self.block_types[(bx, by)] = "hazard"
            return "hazard"
        if random.random() < POWERUP_SPAWN_CHANCE + pwr_bonus:
            self.ore_tiles[(bx, by)] = random.choice(POWERUP_LIST)
            self.block_types[(bx, by)] = "powerup"
            return "powerup"
        ore_chance = (BOOST_ORE_SPAWN_CHANCE if run_boosted_mode else ORE_SPAWN_CHANCE) + ore_bonus
        if random.random() < ore_chance:
            weights = BOOST_RARITY_WEIGHTS if run_boosted_mode else ORE_RARITY_WEIGHTS
            self.ore_tiles[(bx, by)] = weighted_choice(weights)
            self.block_types[(bx, by)] = "ore"
            return "ore"
        self.block_types[(bx, by)] = "regular"
        return "regular"

HELL_UNLOCK_COST = 9000
HEAVEN_UNLOCK_COST = 26000
BOOST_COSTS = {"normal": 400, "hell": 1800, "heaven": 3800}
CHALLENGE_TARGETS = {"normal": 5500.0, "hell": 9000.0, "heaven": 12000.0}

# -- SHOP_ANCHORS START --
SHOP_ANCHORS = {
    "title": (-10000, -10000),
    "label_1": (180, 245),
    "label_2": (500, 245),
    "label_3": (820, 245),
    "bar_1": (80, 275, 200, 12),
    "bar_2": (400, 275, 200, 12),
    "bar_3": (720, 275, 200, 12),
    "lvl_1": (-1000, -1000),
    "lvl_2": (-1000, -1000),
    "lvl_3": (-1000, -1000),
    "cost_1": (210, 585),
    "cost_2": (500, 585),
    "cost_3": (790, 585),
    "money": (500, 640),
    "skins_btn": pg.Rect(0, 45, 160, 52),
    "tutorial_btn": pg.Rect(0, 105, 160, 44),
    "world": (860, 50),
    "challenge_center": (880, 90),
}
# -- SHOP_ANCHORS END --

async def worlds_menu(total_money):
    global selected_world
    while True:
        events = pg.event.get()
        music.update(events)
        clicked = None
        for e in events:
            if e.type == pg.QUIT:
                pg.quit()
                raise SystemExit
            if e.type == pg.KEYDOWN:
                handle_secret_combo(e)
                if e.key == pg.K_ESCAPE:
                    return
            if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                clicked = e.pos

        screen.fill((20, 20, 25))
        draw_text("Worlds", 72, LIGHT_BLUE, w // 2, 70, center=True)
        draw_text("Click a world to switch or unlock it.", 28, YELLOW, w // 2, 120, center=True)

        worlds = [
            ("normal", "Overworld", True, 0),
            ("hell", "Hell", unlocks["hell"], HELL_UNLOCK_COST),
            ("heaven", "Heaven", unlocks["heaven"], HEAVEN_UNLOCK_COST),
        ]
        for i, (key, name, unlocked, cost) in enumerate(worlds):
            rect = pg.Rect(130 + i * 250, 210, 190, 220)
            pg.draw.rect(screen, (48, 52, 60), rect, border_radius=18)
            pg.draw.rect(screen, LIGHT_BLUE if key == selected_world else (100, 110, 130), rect, 3, border_radius=18)
            pg.draw.circle(screen, WORLD_BASE_COLORS[key], (rect.centerx, rect.y + 55), 26)
            draw_text(name, 36, WHITE, rect.centerx, rect.y + 110, center=True)
            if unlocked or key == "normal":
                draw_text("Unlocked", 28, YELLOW, rect.centerx, rect.y + 150, center=True)
            else:
                draw_text(f"Unlock: ${cost}", 26, YELLOW, rect.centerx, rect.y + 150, center=True)
                if key == "heaven" and not unlocks["hell"]:
                    draw_text("Need Hell first", 24, LIGHT_GRAY, rect.centerx, rect.y + 180, center=True)
                else:
                    draw_text("Locked", 24, LIGHT_GRAY, rect.centerx, rect.y + 180, center=True)
            if clicked and rect.collidepoint(clicked):
                if key == "normal":
                    selected_world = key
                    return
                if unlocked:
                    selected_world = key
                    return
                if key == "hell" and total_money >= cost:
                    total_money -= cost
                    unlocks["hell"] = True
                    selected_world = key
                    popups.append(Popup("Hell unlocked!", size=42, lifetime=180, color=YELLOW))
                    return
                if key == "heaven" and unlocks["hell"] and total_money >= cost:
                    total_money -= cost
                    unlocks["heaven"] = True
                    selected_world = key
                    popups.append(Popup("Heaven unlocked!", size=42, lifetime=180, color=YELLOW))
                    return

        draw_text("ESC to return", 28, LIGHT_BLUE, w // 2, 625, center=True)
        pg.display.flip()
        clock.tick(fps)
        await frame_yield()

async def shop_menu(total_money):
    global selected_world, boosted_mode, layout_edit_mode

    pg.mouse.set_visible(True)
    pg.event.set_grab(False)
    music.set_mode("main")

    title_font = pg.font.SysFont(None, 104)
    label_font = pg.font.SysFont(None, 34)
    tiny_font  = pg.font.SysFont(None, 22)
    money_font = pg.font.SysFont(None, 54)

    options = [
        {"name": "MINE COOLDOWN", "key": "mining_speed", "max": 10, "cost_base": 180},
        {"name": "MINE POWER",    "key": "mine_power",   "max": 3,  "cost_tiers": {1: 1200, 2: 4200, 3: 9500}},
        {"name": "MINE FORTUNE",  "key": "fortune",      "max": 10, "cost_base": 160},
    ]
    editable_keys = ["label_1","label_2","label_3","bar_1","bar_2","bar_3","cost_1","cost_2","cost_3","money","skins_btn","tutorial_btn","world","challenge_center"]
    edit_idx = 0

    while True:
        if SHOP_BG_SURF is not None:
            screen.blit(SHOP_BG_SURF, (0, 0))
        else:
            screen.fill((24, 26, 30))

        tx, ty = SHOP_ANCHORS["title"]
        title = title_font.render("SHRED", True, (220, 220, 220))
        if tx > -9999:
            screen.blit(title, (tx - title.get_width()//2, ty - title.get_height()//2))

        skins_btn = SHOP_ANCHORS["skins_btn"]
        pg.draw.circle(screen, SKINS[selected_skin]["color"], (skins_btn.right + 24, skins_btn.centery), 10)
        pg.draw.circle(screen, BLACK, (skins_btn.right + 24, skins_btn.centery), 10, 2)

        wx, wy = SHOP_ANCHORS["world"]
        world_txt = tiny_font.render(f"WORLD: {selected_world.upper()}", True, (255, 230, 70))
        screen.blit(world_txt, (wx - world_txt.get_width()//2, wy - world_txt.get_height()//2))
        world_hint = tiny_font.render("click for worlds", True, (220, 220, 220))
        screen.blit(world_hint, (wx - world_hint.get_width()//2, wy + 16))

        cx, cy = SHOP_ANCHORS["challenge_center"]
        r = 22
        pg.draw.circle(screen, (0, 0, 0), (cx, cy), r + 6)
        pg.draw.circle(screen, (0, 180, 0) if boosted_mode else (120, 120, 120), (cx, cy), r)
        pg.draw.circle(screen, WHITE, (cx + (10 if boosted_mode else -10), cy), 9)
        cost = 0 if cheat_mode else BOOST_COSTS[selected_world]
        c_label = tiny_font.render(f"CHALLENGE ${cost}", True, (255, 230, 70))
        screen.blit(c_label, (cx - c_label.get_width()//2, cy + 30))
        if boosted_mode:
            tgt = CHALLENGE_TARGETS[selected_world]
            tgt_txt = tiny_font.render(f"TARGET: ${tgt:.0f}", True, (255, 230, 70))
            screen.blit(tgt_txt, (cx - tgt_txt.get_width()//2, cy + 52))

        buy_button_rects = []
        for i, opt in enumerate(options, start=1):
            level = buffs[opt["key"]]
            if opt["key"] == "mine_power":
                costv = opt["cost_tiers"].get(level, 0) if level < opt["max"] else 0
            else:
                costv = opt["cost_base"] * level if level < opt["max"] else 0
            if cheat_mode and level < opt["max"]:
                costv = 0
            can_buy = level < opt["max"] and (total_money >= costv or cheat_mode)

            lx, ly = SHOP_ANCHORS[f"label_{i}"]
            lab = label_font.render(opt["name"], True, (220, 220, 220) if can_buy else (140, 140, 140))
            screen.blit(lab, (lx - lab.get_width()//2, ly - lab.get_height()//2))

            bx, by, bw, bh = SHOP_ANCHORS[f"bar_{i}"]
            pg.draw.rect(screen, (0, 0, 0), (bx-3, by-3, bw+6, bh+6))
            pg.draw.rect(screen, (110, 110, 110), (bx, by, bw, bh))
            frac = 0 if opt["max"] <= 0 else max(0.0, min(1.0, level / float(opt["max"])))
            pg.draw.rect(screen, (220, 220, 220) if can_buy else (160, 160, 160), (bx, by, int(bw * frac), bh))

            cx2, cy2 = SHOP_ANCHORS[f"cost_{i}"]
            btn = pg.Rect(cx2 - 82, cy2 - 20, 164, 42)
            buy_button_rects.append((btn, opt, costv))
            base_col = (110, 110, 110) if can_buy else (70, 70, 70)
            pg.draw.rect(screen, (0, 0, 0), btn, border_radius=10)
            pg.draw.rect(screen, base_col, btn.inflate(-4, -4), border_radius=10)
            txt = "MAX" if level >= opt["max"] else f"BUY ${costv}"
            draw_text_in_rect(txt, btn, 18, YELLOW if can_buy else LIGHT_GRAY, align='center', valign='center', padding=6, bold=True)

        mx, my = SHOP_ANCHORS["money"]
        mtxt = money_font.render(f"MONEY: ${total_money:.2f}", True, (230, 230, 230))
        screen.blit(mtxt, (mx - mtxt.get_width()//2, my - mtxt.get_height()//2))

        if layout_edit_mode:
            key = editable_keys[edit_idx]
            value = SHOP_ANCHORS[key]
            if isinstance(value, pg.Rect):
                high_rect = value.inflate(10, 10)
            elif isinstance(value, tuple) and len(value) == 2:
                high_rect = pg.Rect(value[0] - 12, value[1] - 12, 24, 24)
            else:
                bx, by, bw, bh = value
                high_rect = pg.Rect(bx - 6, by - 6, bw + 12, bh + 12)
            pg.draw.rect(screen, RED, high_rect, 3, border_radius=8)
            draw_text(f"LAYOUT EDIT: {key}", 28, YELLOW, w // 2, 24, center=True)
            draw_text("Tab next • Arrows move • Shift faster • Ctrl+S save • F8 exit", 24, WHITE, w // 2, 50, center=True)

        for i, popup in enumerate(popups[:] ):
            popup.draw(i * 30)
            if not popup.update():
                popups.remove(popup)

        pg.display.flip()

        events = pg.event.get()
        music.update(events)
        clicked_pos = None
        for e in events:
            if e.type == pg.QUIT:
                pg.quit()
                raise SystemExit
            if e.type == pg.KEYDOWN:
                handle_secret_combo(e)
                if e.key == pg.K_F8:
                    layout_edit_mode = not layout_edit_mode
                    if not layout_edit_mode:
                        ok = save_shop_anchors_to_source()
                        popups.append(Popup("Layout saved." if ok else "Layout save failed.", size=38, lifetime=160, color=LIGHT_BLUE if ok else RED, y=120))
                    else:
                        popups.append(Popup("Layout edit ON", size=38, lifetime=160, color=YELLOW, y=120))
                if layout_edit_mode:
                    step = 10 if (pg.key.get_mods() & pg.KMOD_SHIFT) else 1
                    current = editable_keys[edit_idx]
                    val = SHOP_ANCHORS[current]
                    if e.key == pg.K_TAB:
                        edit_idx = (edit_idx + 1) % len(editable_keys)
                    elif e.key == pg.K_LEFT:
                        if isinstance(val, pg.Rect): val.x -= step
                        elif len(val) == 2: SHOP_ANCHORS[current] = (val[0] - step, val[1])
                        else: SHOP_ANCHORS[current] = (val[0] - step, val[1], val[2], val[3])
                    elif e.key == pg.K_RIGHT:
                        if isinstance(val, pg.Rect): val.x += step
                        elif len(val) == 2: SHOP_ANCHORS[current] = (val[0] + step, val[1])
                        else: SHOP_ANCHORS[current] = (val[0] + step, val[1], val[2], val[3])
                    elif e.key == pg.K_UP:
                        if isinstance(val, pg.Rect): val.y -= step
                        elif len(val) == 2: SHOP_ANCHORS[current] = (val[0], val[1] - step)
                        else: SHOP_ANCHORS[current] = (val[0], val[1] - step, val[2], val[3])
                    elif e.key == pg.K_DOWN:
                        if isinstance(val, pg.Rect): val.y += step
                        elif len(val) == 2: SHOP_ANCHORS[current] = (val[0], val[1] + step)
                        else: SHOP_ANCHORS[current] = (val[0], val[1] + step, val[2], val[3])
                    elif e.key == pg.K_s and (pg.key.get_mods() & pg.KMOD_CTRL):
                        ok = save_shop_anchors_to_source()
                        popups.append(Popup("Saved to main.py" if ok else "Save failed", size=36, lifetime=150, color=LIGHT_BLUE if ok else RED, y=120))
                    continue
            if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                clicked_pos = e.pos

        if clicked_pos and skins_btn.collidepoint(clicked_pos):
            await skins_menu()
            clock.tick(fps)
            await frame_yield()
            continue

        if clicked_pos:
            mxp, myp = clicked_pos
            if (mxp - cx) ** 2 + (myp - cy) ** 2 <= (r + 8) ** 2:
                boosted_mode = not boosted_mode
                popups.append(Popup("Challenge ON" if boosted_mode else "Challenge OFF", size=44, lifetime=180, color=YELLOW, y=120))
            world_click = pg.Rect(wx - 110, wy - 20, 220, 54)
            if world_click.collidepoint(clicked_pos):
                await worlds_menu(total_money)
                clock.tick(fps)
                await frame_yield()
                continue
            for btn, opt, costv in buy_button_rects:
                if btn.collidepoint(clicked_pos):
                    level = buffs[opt["key"]]
                    if level >= opt["max"]:
                        popups.append(Popup("Already maxed", size=34, lifetime=120, color=LIGHT_BLUE))
                    elif total_money >= costv or cheat_mode:
                        buffs[opt["key"]] += 1
                        if not cheat_mode:
                            total_money -= costv
                        popups.append(Popup(f"{opt['name']} upgraded!", size=40, lifetime=170, color=LIGHT_BLUE))
                    else:
                        popups.append(Popup("Not enough money", size=36, lifetime=150, color=RED))
                    break

        keys = pg.key.get_pressed()
        if keys[pg.K_RETURN]:
            if boosted_mode:
                cost_need = 0 if cheat_mode else BOOST_COSTS[selected_world]
                if total_money < cost_need:
                    popups.append(Popup(f"Need ${cost_need} for Challenge!", size=40, lifetime=190, color=YELLOW, y=120))
                else:
                    if not cheat_mode:
                        total_money -= cost_need
                    pg.mouse.set_visible(False)
                    pg.event.set_grab(True)
                    return total_money
            else:
                pg.mouse.set_visible(False)
                pg.event.set_grab(True)
                return total_money

        clock.tick(fps)
        await frame_yield()



# -------------------------
# PERFORMANCE PATCH
# -------------------------
_old_ground_init = Ground.__init__


def _ground_init_perf(self, *args, **kwargs):
    _old_ground_init(self, *args, **kwargs)
    self._air_cache = {}
    self._fog_cache = {}
    self._bg_surface_cache = {}


Ground.__init__ = _ground_init_perf


def _is_natural_air_perf(self, bx, by):
    key = (bx, by)
    got = self._air_cache.get(key)
    if got is not None:
        return got
    got = _is_natural_air_cached(int(bx // TILE), int(by // TILE))
    self._air_cache[key] = got
    return got


Ground.is_natural_air = _is_natural_air_perf


def _get_nearby_blocks_perf(self, px, py):
    start_x = int((px - w // 2) // TILE) - 1
    end_x = int((px + w // 2) // TILE) + 2
    start_y = int((py - h // 2) // TILE) - 1
    end_y = int((py + h // 2) // TILE) + 2
    blocks = []
    append = blocks.append
    for tx in range(start_x, end_x):
        bx = tx * TILE
        for ty in range(start_y, end_y):
            by = ty * TILE
            if (bx, by) not in self.mined_blocks and not self.is_natural_air(bx, by):
                append((bx, by))
    return blocks


Ground.get_nearby_blocks = _get_nearby_blocks_perf


def _get_bg_surface(self, world):
    surf = self._bg_surface_cache.get(world)
    if surf is not None:
        return surf
    bg = darker_world_color(world)
    alt = tuple(min(255, c + 8) for c in bg)
    surf = pg.Surface((TILE * 2, TILE * 2)).convert()
    for tx in range(2):
        for ty in range(2):
            col = alt if ((tx + ty) & 1) == 0 else bg
            pg.draw.rect(surf, col, (tx * TILE, ty * TILE, TILE, TILE))
    self._bg_surface_cache[world] = surf
    return surf


def _draw_perf(self, camera_x, camera_y, player_x, player_y, cursor_world_pos, cursor_screen_pos, dt_sec):
    world = get_active_world()
    screen.fill(darker_world_color(world))

    bg_tile = _get_bg_surface(self, world)
    px, py = player_x, player_y
    min_tx = int((px - w // 2) // TILE) - 2
    max_tx = int((px + w // 2) // TILE) + 3
    min_ty = int((py - h // 2) // TILE) - 2
    max_ty = int((py + h // 2) // TILE) + 3

    start_px = (min_tx * TILE) - camera_x
    start_py = (min_ty * TILE) - camera_y
    for sx in range(start_px - (start_px % (TILE * 2)) - TILE * 2, w + TILE * 2, TILE * 2):
        for sy in range(start_py - (start_py % (TILE * 2)) - TILE * 2, h + TILE * 2, TILE * 2):
            screen.blit(bg_tile, (sx, sy))

    # subtle vignette once per frame instead of per-tile fog surfaces
    vignette_alpha = 36
    vig = self._fog_cache.get(vignette_alpha)
    if vig is None:
        vig = pg.Surface((w, h), pg.SRCALPHA)
        pg.draw.rect(vig, (0, 0, 0, vignette_alpha), (0, 0, w, h), border_radius=0)
        self._fog_cache[vignette_alpha] = vig
    screen.blit(vig, (0, 0))

    super(Ground, self).draw(camera_x, camera_y, player_x, player_y, cursor_world_pos, cursor_screen_pos, dt_sec)


Ground.draw = _draw_perf


# =======================================================
# FINAL PROGRESSION / MODIFIER / CURVY CAVE PATCH
# =======================================================
selected_modifiers = {"classic"}
MODIFIER_UNLOCKS = {"classic": True, "challenge": True, "ore_surge": False, "powerup_storm": False, "bounty_hunter": False}
MODIFIER_INFO = {
    "classic": {"name": "Classic", "desc": "Normal run. Clean mining and steady progression."},
    "challenge": {"name": "Challenge", "desc": "3 lives, hazards, longer timer, target payout."},
    "ore_surge": {"name": "Ore Surge", "desc": "+Ore rate, richer caves, shorter run."},
    "powerup_storm": {"name": "Powerup Storm", "desc": "More powerups, more chaos, fast rewards."},
    "bounty_hunter": {"name": "Bounty Hunter", "desc": "Clearer, richer bounty rewards and easier bounty rolls."},
}
WORLD_SEQUENCE = ["normal", "hell", "heaven"]
QUESTLINE_DATA = {
    "normal": [
        {"key": "blocks", "label": "Break 70 blocks", "target": 70},
        {"key": "ore", "label": "Mine 18 ore blocks", "target": 18},
        {"key": "money", "label": "Earn $1800 total in Overworld", "target": 1800},
    ],
    "hell": [
        {"key": "blocks", "label": "Break 95 blocks", "target": 95},
        {"key": "ore", "label": "Mine 22 ore blocks", "target": 22},
        {"key": "money", "label": "Earn $6500 total in Hell", "target": 6500},
    ],
    "heaven": [
        {"key": "blocks", "label": "Break 120 blocks", "target": 120},
        {"key": "ore", "label": "Mine 26 ore blocks", "target": 26},
        {"key": "money", "label": "Earn $12000 total in Heaven", "target": 12000},
    ],
}
quest_progress = {w: {q["key"]: 0 for q in qs} for w, qs in QUESTLINE_DATA.items()}
questline_complete = {w: False for w in QUESTLINE_DATA}
challenge_target_cleared = {"normal": False, "hell": False, "heaven": False}

SKINS["quest walker"] = {"name": "Quest walker", "color": (120, 255, 170)}
skins_unlocked.setdefault("quest walker", False)

RUN_EVENT = {"name": None, "timer": 0, "ping_block": None}
BOUNTY_BANNER = {"timer": 0, "text": "", "subtext": "", "cash": 0.0}

BOUNTY_POOL = [
    {"key": "ore", "label": "Mine 5 ore blocks", "target": 5, "reward_cash": 180, "reward_buff": None},
    {"key": "powerup", "label": "Break 1 powerup block", "target": 1, "reward_cash": 160, "reward_buff": ("Reveal", int(5 * fps))},
    {"key": "combo", "label": "Reach combo x1.40", "target": 5, "reward_cash": 220, "reward_buff": ("Money Boost", int(5 * fps))},
    {"key": "money", "label": "Earn $350 in one run", "target": 350, "reward_cash": 240, "reward_buff": None},
    {"key": "rare", "label": "Mine 1 rare+ ore", "target": 1, "reward_cash": 280, "reward_buff": ("Reveal", int(7 * fps))},
]


def get_core_modifier():
    return 'challenge' if 'challenge' in selected_modifiers else 'classic'


def has_modifier(name):
    return name in selected_modifiers


def active_modifier_names():
    order = ['classic', 'challenge', 'ore_surge', 'powerup_storm', 'bounty_hunter']
    return [MODIFIER_INFO[k]['name'] for k in order if k in selected_modifiers and not (k == 'classic' and 'challenge' in selected_modifiers)]


def toggle_modifier(key):
    if key not in MODIFIER_UNLOCKS or not MODIFIER_UNLOCKS[key]:
        return
    if key in ('classic', 'challenge'):
        selected_modifiers.discard('classic')
        selected_modifiers.discard('challenge')
        selected_modifiers.add(key)
    else:
        if key in selected_modifiers:
            selected_modifiers.remove(key)
        else:
            selected_modifiers.add(key)
    if not ({'classic', 'challenge'} & selected_modifiers):
        selected_modifiers.add('classic')

# smaller, tighter cave network
@lru_cache(maxsize=None)
def _curve_region(rx, ry):
    rng = random.Random(_chunk_seed(rx, ry, 71))
    worms = []
    caverns = []
    worm_count = 1
    if rng.random() < 0.35:
        worm_count += 1
    for _ in range(worm_count):
        x = rx * CAVE_REGION_W + rng.uniform(4.0, CAVE_REGION_W - 4.0)
        y = ry * CAVE_REGION_H + rng.uniform(4.0, CAVE_REGION_H - 4.0)
        ang = rng.uniform(0.0, math.tau)
        width = rng.uniform(0.62, 1.02)
        steps = rng.randint(6, 11)
        pts = [(x, y)]
        for _step in range(steps):
            ang += rng.uniform(-0.45, 0.45)
            step_len = rng.uniform(0.8, 1.45)
            x += math.cos(ang) * step_len
            y += math.sin(ang) * step_len
            pts.append((x, y))
            if rng.random() < 0.035:
                caverns.append((x, y, rng.uniform(0.95, 1.55), rng.uniform(0.9, 1.45)))
        worms.append((tuple(pts), width))
    if rng.random() < 0.22 or (rx, ry) == (0, 0):
        caverns.append((
            rx * CAVE_REGION_W + rng.uniform(6.0, CAVE_REGION_W - 6.0),
            ry * CAVE_REGION_H + rng.uniform(6.0, CAVE_REGION_H - 6.0),
            rng.uniform(1.2, 1.9),
            rng.uniform(1.0, 1.6),
        ))
    return {"worms": worms, "caverns": tuple(caverns)}

@lru_cache(maxsize=None)
def _is_natural_air_cached(tx, ty):
    if max(abs(tx), abs(ty)) <= 1:
        return True
    # smaller spawn pocket
    if (tx * tx) / 7.0 + (ty * ty) / 5.5 <= 1.0:
        return True
    rx = math.floor(tx / CAVE_REGION_W)
    ry = math.floor(ty / CAVE_REGION_H)
    hits = 0
    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            if _tile_in_curve_region(tx, ty, _curve_region(rx + ox, ry + oy)):
                hits += 1
                if hits >= 1:
                    return True
    pocket_rng = random.Random(_chunk_seed(tx, ty, 103))
    return pocket_rng.random() < 0.0013

_old_ground_init_patch2 = Ground.__init__
def _ground_init_patch2(self, *args, **kwargs):
    _old_ground_init_patch2(self, *args, **kwargs)
Ground.__init__ = _ground_init_patch2

_old_generate_block_patch2 = Ground.generate_block
def _generate_block_patch2(self, bx, by):
    if (bx, by) in getattr(self, 'block_types', {}):
        return self.block_types[(bx, by)]
    spawn_dist = math.hypot(bx / TILE, by / TILE)
    ore_bonus = 0.0
    pwr_bonus = 0.0
    if has_modifier('ore_surge') or RUN_EVENT["name"] == 'Ore Surge':
        ore_bonus += 0.14
    if has_modifier('powerup_storm') or RUN_EVENT["name"] == 'Powerup Storm':
        pwr_bonus += 0.08
    if spawn_dist < 8:
        ore_bonus += 0.04
        pwr_bonus += 0.008
    if has_modifier('challenge') and random.random() < BOOST_HAZARD_SPAWN_CHANCE:
        world = get_active_world()
        pool = BASE_HAZARDS + WORLD_UNIQUE_HAZARDS.get(world, [])
        hz = random.choice(pool) if pool else 'lava'
        self.hazard_tiles[(bx, by)] = hz
        self.block_types[(bx, by)] = 'hazard'
        return 'hazard'
    if random.random() < POWERUP_SPAWN_CHANCE + pwr_bonus:
        self.ore_tiles[(bx, by)] = random.choice(POWERUP_LIST)
        self.block_types[(bx, by)] = 'powerup'
        return 'powerup'
    ore_chance = ORE_SPAWN_CHANCE + ore_bonus
    if has_modifier('challenge'):
        ore_chance = BOOST_ORE_SPAWN_CHANCE + ore_bonus
    if random.random() < ore_chance:
        weights = BOOST_RARITY_WEIGHTS if has_modifier('challenge') else ORE_RARITY_WEIGHTS
        self.ore_tiles[(bx, by)] = weighted_choice(weights)
        self.block_types[(bx, by)] = 'ore'
        return 'ore'
    self.block_types[(bx, by)] = 'regular'
    return 'regular'
Ground.generate_block = _generate_block_patch2


def current_world_quest_index(world):
    qs = QUESTLINE_DATA[world]
    prog = quest_progress[world]
    for i, q in enumerate(qs):
        if prog[q['key']] < q['target']:
            return i
    return len(qs)


def update_world_unlocks():
    unlocks['hell'] = questline_complete['normal']
    unlocks['heaven'] = questline_complete['hell']
    MODIFIER_UNLOCKS['ore_surge'] = unlocks['hell']
    MODIFIER_UNLOCKS['powerup_storm'] = unlocks['heaven']
    MODIFIER_UNLOCKS['bounty_hunter'] = all(questline_complete.values())
    if all(questline_complete.values()):
        skins_unlocked['quest walker'] = True
    if all(challenge_target_cleared.values()):
        skins_unlocked['completionist'] = True


def add_quest_progress(world, key, amount=1):
    if world not in quest_progress:
        return []
    prog = quest_progress[world]
    before_idx = current_world_quest_index(world)
    if key in prog:
        prog[key] += amount
    qs = QUESTLINE_DATA[world]
    unlocked_msgs = []
    after_idx = current_world_quest_index(world)
    if before_idx < len(qs) and after_idx > before_idx:
        unlocked_msgs.append(f"Quest complete: {qs[before_idx]['label']}")
    if after_idx >= len(qs) and not questline_complete[world]:
        questline_complete[world] = True
        unlocked_msgs.append(f"{world.title()} questline complete!")
        seq = WORLD_SEQUENCE.index(world)
        if seq + 1 < len(WORLD_SEQUENCE):
            nxt = WORLD_SEQUENCE[seq + 1]
            unlocks[nxt] = True
            unlocked_msgs.append(f"{nxt.title()} unlocked")
    update_world_unlocks()
    return unlocked_msgs


def get_current_quest_line(world):
    idx = current_world_quest_index(world)
    if idx >= len(QUESTLINE_DATA[world]):
        return None
    q = QUESTLINE_DATA[world][idx]
    prog = quest_progress[world][q['key']]
    return q, prog


def pick_run_bounty(world_name, modifier_name):
    pool = list(BOUNTY_POOL)
    if ('Challenge' in modifier_name) if isinstance(modifier_name, list) else (modifier_name == 'challenge'):
        pool.append({"key": "survive", "label": "Survive 45s in Challenge", "target": 45, "reward_cash": 340, "reward_buff": None})
    if ('Bounty Hunter' in modifier_name) if isinstance(modifier_name, list) else (modifier_name == 'bounty_hunter'):
        pool = [
            {"key": "ore", "label": "Mine 4 ore blocks", "target": 4, "reward_cash": 260, "reward_buff": ("Reveal", int(6 * fps))},
            {"key": "powerup", "label": "Break 1 powerup block", "target": 1, "reward_cash": 240, "reward_buff": ("Money Boost", int(6 * fps))},
            {"key": "combo", "label": "Reach combo x1.40", "target": 5, "reward_cash": 320, "reward_buff": ("Money Boost", int(6 * fps))},
            {"key": "money", "label": "Earn $300 in one run", "target": 300, "reward_cash": 300, "reward_buff": ("Reveal", int(7 * fps))},
            {"key": "rare", "label": "Mine 1 rare+ ore", "target": 1, "reward_cash": 360, "reward_buff": ("Money Boost", int(7 * fps))},
        ]
    return dict(random.choice(pool))

def apply_bounty_progress(bounty, amount=0, current_money=0, combo_level=0, rarity=None, elapsed_seconds=0):
    if not bounty or bounty.get('complete'):
        return False
    key = bounty['key']
    old = bounty.get('progress', 0)
    new = old
    if key in ('ore', 'powerup'):
        new = old + amount
    elif key == 'combo':
        new = max(old, combo_level)
    elif key == 'money':
        new = max(old, int(current_money))
    elif key == 'rare':
        if rarity in ('rare', 'legendary', 'mythic'):
            new = old + amount
    elif key == 'survive':
        new = max(old, int(elapsed_seconds))
    bounty['progress'] = new
    if old < bounty['target'] <= new:
        bounty['complete'] = True
        return True
    return False

def grant_bounty_reward(bounty):
    cash = float(bounty.get('reward_cash', 0))
    buff = bounty.get('reward_buff')
    if buff:
        active_powerups[buff[0]] = [buff[1], {}]
    BOUNTY_BANNER['timer'] = int(2.7 * fps)
    BOUNTY_BANNER['text'] = 'BOUNTY COMPLETE!'
    if buff:
        BOUNTY_BANNER['subtext'] = f"+${cash:.0f} and {buff[0]}"
    else:
        BOUNTY_BANNER['subtext'] = f"+${cash:.0f}"
    BOUNTY_BANNER['cash'] = cash
    popups.append(Popup(BOUNTY_BANNER['subtext'], size=48, lifetime=170, color=GREEN, y=170))
    return cash, buff


def draw_bounty_banner():
    if BOUNTY_BANNER['timer'] <= 0:
        return
    frac = BOUNTY_BANNER['timer'] / float(int(2.7 * fps))
    alpha = min(220, int(255 * min(1.0, 1.35 - frac)))
    overlay = pg.Surface((w, h), pg.SRCALPHA)
    overlay.fill((255, 220, 40, min(45, alpha // 5)))
    screen.blit(overlay, (0, 0))
    rect = pg.Rect(w // 2 - 260, 22, 520, 98)
    draw_ui_panel(rect, border=(255, 235, 90), fill=(24, 56, 28, 235), radius=20, glow=True)
    draw_text_in_rect(BOUNTY_BANNER['text'], pg.Rect(rect.x+18, rect.y+12, rect.w-36, 26), 34, WHITE, bold=True)
    draw_text_in_rect(BOUNTY_BANNER['subtext'], pg.Rect(rect.x+22, rect.y+46, rect.w-44, 28), 24, YELLOW)
    BOUNTY_BANNER['timer'] -= 1


async def modifiers_menu():
    order = ['classic', 'challenge', 'ore_surge', 'powerup_storm', 'bounty_hunter']
    while True:
        events = pg.event.get()
        music.update(events)
        clicked = None
        for e in events:
            if e.type == pg.QUIT:
                pg.quit(); raise SystemExit
            if e.type == pg.KEYDOWN:
                handle_secret_combo(e)
                if e.key == pg.K_ESCAPE:
                    return
            if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                clicked = e.pos
        screen.fill((9, 12, 18))
        shell = pg.Rect(52, 26, 896, 648)
        draw_ui_panel(shell, border=(88, 190, 255), fill=(8, 13, 22, 235), radius=28, glow=True)
        draw_text_in_rect('RUN MODIFIERS', pg.Rect(shell.x+40, shell.y+16, shell.w-80, 68), 58, LIGHT_BLUE, bold=True)
        draw_text_in_rect('Pick any combination. Challenge can stack with other unlocked modifiers.', pg.Rect(shell.x+74, shell.y+92, shell.w-148, 30), 26, YELLOW)
        draw_text_in_rect('Choose Classic or Challenge as the base, then toggle bonus modifiers below.', pg.Rect(shell.x+74, shell.y+122, shell.w-148, 26), 22, WHITE)
        draw_text_in_rect('Active: ' + ', '.join(active_modifier_names()), pg.Rect(shell.x+74, shell.y+148, shell.w-148, 24), 22, LIGHT_BLUE)

        for i, key in enumerate(order):
            rect = pg.Rect(shell.x + 48, shell.y + 182 + i * 88, shell.w - 96, 70)
            unlocked = MODIFIER_UNLOCKS.get(key, False)
            active = has_modifier(key)
            hovered = rect.collidepoint(pg.mouse.get_pos())
            fill = (22, 26, 36, 230)
            border = (95, 105, 125)
            if unlocked:
                border = (88, 190, 255)
                if hovered and not active:
                    fill = (28, 34, 48, 235)
            if active:
                border = (255, 215, 110) if key == 'challenge' else (120, 245, 150)
                fill = (84, 64, 18, 235) if key == 'challenge' else (20, 62, 34, 235)
            if not unlocked:
                fill = (24, 24, 28, 220)
            draw_ui_panel(rect, border=border, fill=fill, radius=20, glow=active)
            draw_text_in_rect(MODIFIER_INFO[key]['name'], pg.Rect(rect.x+22, rect.y+10, rect.w-180, 24), 30, WHITE if unlocked else LIGHT_GRAY, align='left', valign='top', padding=0, bold=True)
            draw_text_in_rect(MODIFIER_INFO[key]['desc'], pg.Rect(rect.x+22, rect.y+38, rect.w-180, 20), 20, YELLOW if active else LIGHT_GRAY, align='left', valign='top', padding=0)
            if unlocked:
                badge = 'ON' if active else ('READY' if key in ('classic','challenge') else 'OFF')
                bg = (92, 70, 18) if (active and key == 'challenge') else ((20, 70, 34) if active else (22, 36, 60))
                br = (255, 225, 110) if (active and key == 'challenge') else ((120, 245, 150) if active else (88, 190, 255))
                draw_badge(pg.Rect(rect.right-120, rect.y+16, 92, 36), badge, fg=WHITE, bg=bg, border=br, size=18)
            else:
                draw_badge(pg.Rect(rect.right-120, rect.y+16, 92, 36), 'LOCKED', fg=WHITE, bg=(60, 18, 18), border=(255, 90, 90), size=18)
            if clicked and rect.collidepoint(clicked) and unlocked:
                toggle_modifier(key)

        draw_text_in_rect('Esc to return', pg.Rect(shell.x+40, shell.bottom-34, shell.w-80, 22), 20, LIGHT_BLUE)
        pg.display.flip(); clock.tick(fps); await frame_yield()

async def worlds_menu(total_money):
    global selected_world
    while True:
        events = pg.event.get()
        music.update(events)
        clicked = None
        for e in events:
            if e.type == pg.QUIT:
                pg.quit(); raise SystemExit
            if e.type == pg.KEYDOWN:
                handle_secret_combo(e)
                if e.key == pg.K_ESCAPE:
                    return
            if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                clicked = e.pos
        screen.fill((9, 12, 18))
        shell = pg.Rect(74, 44, 852, 610)
        draw_ui_panel(shell, border=(88, 190, 255), fill=(8, 13, 22, 235), radius=28, glow=True)
        draw_text_in_rect('WORLDS', pg.Rect(shell.x+40, shell.y+18, shell.w-80, 60), 58, LIGHT_BLUE, bold=True)
        draw_text_in_rect('Finish each world questline to unlock the next one.', pg.Rect(shell.x+80, shell.y+86, shell.w-160, 28), 26, YELLOW)
        for i, key in enumerate(WORLD_SEQUENCE):
            rect = pg.Rect(shell.x + 40 + i * 255, shell.y + 150, 230, 310)
            unlocked = (key == 'normal') or unlocks.get(key, False)
            active = selected_world == key
            draw_ui_panel(rect, border=(125, 235, 125) if active else (88, 190, 255), fill=(20, 28, 42, 228), radius=20)
            orb = pg.Rect(rect.x+78, rect.y+24, 74, 74)
            pg.draw.circle(screen, WORLD_BASE_COLORS[key], orb.center, 30)
            pg.draw.circle(screen, WHITE, orb.center, 30, 2)
            draw_text_in_rect(key.upper(), pg.Rect(rect.x+18, rect.y+108, rect.w-36, 30), 34, WHITE, bold=True)
            q = get_current_quest_line(key)
            status_rect = pg.Rect(rect.x+18, rect.y+152, rect.w-36, 92)
            draw_ui_panel(status_rect, border=(46, 58, 78), fill=(12, 16, 26, 214), radius=16)
            if q is None:
                draw_text_in_rect('QUESTLINE COMPLETE', pg.Rect(status_rect.x+10, status_rect.y+12, status_rect.w-20, 22), 22, GREEN, bold=True)
                draw_text_in_rect('This world is fully cleared.', pg.Rect(status_rect.x+10, status_rect.y+40, status_rect.w-20, 18), 18, WHITE)
            else:
                quest, prog = q
                draw_text_in_rect(quest['label'], pg.Rect(status_rect.x+10, status_rect.y+10, status_rect.w-20, 40), 20, YELLOW, align='left', valign='top', bold=True)
                draw_text_in_rect(f'Progress {min(prog, quest["target"])}/{quest["target"]}', pg.Rect(status_rect.x+10, status_rect.y+58, status_rect.w-20, 18), 18, WHITE, align='left', valign='top')
            badge = 'SELECTED' if active else ('UNLOCKED' if unlocked else 'LOCKED')
            bcol = (125, 235, 125) if unlocked else (255, 90, 90)
            draw_badge(pg.Rect(rect.x+44, rect.bottom-60, rect.w-88, 38), badge, fg=WHITE, bg=(30, 38, 52), border=bcol, size=18)
            if clicked and rect.collidepoint(clicked) and unlocked:
                selected_world = key
                return
        info = pg.Rect(shell.x+58, shell.bottom-126, shell.w-116, 58)
        draw_ui_panel(info, border=(46, 58, 78), fill=(12, 16, 26, 214), radius=18)
        draw_text_in_rect('Challenge skin: beat every world challenge target.  Quest skin: finish every questline.', pg.Rect(info.x+16, info.y+16, info.w-32, 24), 20, WHITE)
        draw_text_in_rect('Esc to return', pg.Rect(shell.x+260, shell.bottom-40, shell.w-520, 22), 22, LIGHT_BLUE)
        pg.display.flip(); clock.tick(fps); await frame_yield()

async def skins_menu():
    global selected_skin
    order = ['base', 'survivor', 'completionist', 'quest walker']
    while True:
        events = pg.event.get(); music.update(events)
        clicked = None
        for e in events:
            if e.type == pg.QUIT:
                pg.quit(); raise SystemExit
            if e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
                return
            if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                clicked = e.pos
        screen.fill((9, 12, 18))
        shell = pg.Rect(74, 44, 852, 610)
        draw_ui_panel(shell, border=(88, 190, 255), fill=(8, 13, 22, 235), radius=28, glow=True)
        draw_text_in_rect('SKINS', pg.Rect(shell.x+40, shell.y+18, shell.w-80, 60), 58, LIGHT_BLUE, bold=True)
        draw_text_in_rect('Choose your look. Unlocks come from challenge clears and questlines.', pg.Rect(shell.x+90, shell.y+88, shell.w-180, 28), 24, YELLOW)
        for i, key in enumerate(order):
            rect = pg.Rect(shell.x + 28 + i * 202, shell.y + 172, 190, 300)
            unlocked = skins_unlocked.get(key, False)
            active = selected_skin == key
            draw_ui_panel(rect, border=(125, 235, 125) if active else (88, 190, 255), fill=(20, 28, 42, 228), radius=20)
            pg.draw.circle(screen, SKINS[key]['color'] if unlocked else (100, 100, 105), (rect.centerx, rect.y + 64), 34)
            pg.draw.circle(screen, WHITE, (rect.centerx, rect.y + 64), 34, 2)
            draw_text_in_rect(SKINS[key]['name'], pg.Rect(rect.x+14, rect.y+118, rect.w-28, 52), 26, WHITE if unlocked else LIGHT_GRAY, bold=True)
            desc = 'Always available.' if key == 'base' else ('Beat every world challenge target.' if key == 'completionist' else ('Clear Heaven challenge target.' if key == 'survivor' else 'Finish every world questline.'))
            info_rect = pg.Rect(rect.x+14, rect.y+178, rect.w-28, 72)
            draw_ui_panel(info_rect, border=(46, 58, 78), fill=(12, 16, 26, 214), radius=16)
            draw_text_in_rect(desc, pg.Rect(info_rect.x+10, info_rect.y+10, info_rect.w-20, info_rect.h-20), 18, YELLOW if unlocked else LIGHT_GRAY, align='left', valign='top')
            badge = 'EQUIPPED' if active else ('UNLOCKED' if unlocked else 'LOCKED')
            bcol = (125, 235, 125) if unlocked else (255, 90, 90)
            draw_badge(pg.Rect(rect.x+28, rect.bottom-50, rect.w-56, 34), badge, fg=WHITE, bg=(30, 38, 52), border=bcol, size=16)
            if clicked and rect.collidepoint(clicked) and unlocked:
                selected_skin = key
        draw_text_in_rect('Esc to return', pg.Rect(shell.x+260, shell.bottom-40, shell.w-520, 22), 22, LIGHT_BLUE)
        pg.display.flip(); clock.tick(fps); await frame_yield()

async def shop_menu(total_money):
    global layout_edit_mode
    pg.mouse.set_visible(True)
    pg.event.set_grab(False)
    music.set_mode('main')
    title_font = pg.font.SysFont(None, 104)
    label_font = pg.font.SysFont(None, 34)
    tiny_font = pg.font.SysFont(None, 22)
    money_font = pg.font.SysFont(None, 52)
    options = [
        {"name": "MINE COOLDOWN", "key": "mining_speed", "max": 10, "cost_base": 180},
        {"name": "MINE POWER", "key": "mine_power", "max": 3, "cost_tiers": {1: 1200, 2: 4200, 3: 9500}},
        {"name": "MINE FORTUNE", "key": "fortune", "max": 10, "cost_base": 160},
    ]
    editable_keys = ["label_1","label_2","label_3","bar_1","bar_2","bar_3","cost_1","cost_2","cost_3","money","skins_btn","tutorial_btn","world","challenge_center"]
    edit_idx = 0
    while True:
        if SHOP_BG_SURF is not None:
            screen.blit(SHOP_BG_SURF, (0, 0))
        else:
            screen.fill((24, 26, 30))
        tx, ty = SHOP_ANCHORS['title']
        title = title_font.render('SHRED', True, (220, 220, 220))
        if tx > -9999:
            screen.blit(title, (tx - title.get_width()//2, ty - title.get_height()//2))
        skins_btn = SHOP_ANCHORS['skins_btn']
        tutorial_btn = SHOP_ANCHORS['tutorial_btn']
        pg.draw.circle(screen, SKINS[selected_skin]['color'], (skins_btn.right + 24, skins_btn.centery), 10)
        pg.draw.circle(screen, BLACK, (skins_btn.right + 24, skins_btn.centery), 10, 2)
        pg.draw.rect(screen, (0,0,0), tutorial_btn, border_radius=10)
        pg.draw.rect(screen, (80, 95, 118), tutorial_btn.inflate(-4, -4), border_radius=10)
        draw_text_in_rect('TUTORIAL', tutorial_btn, 18, WHITE, align='center', valign='center', padding=6, bold=True)
        wx, wy = SHOP_ANCHORS['world']
        draw_text(f"WORLD: {selected_world.upper()}", 22, YELLOW, wx, wy, center=True)
        draw_text("click for worlds", 20, WHITE, wx, wy + 18, center=True)
        mx2, my2 = SHOP_ANCHORS['challenge_center']
        draw_text(f"MODIFIER: {' + '.join(active_modifier_names()) if active_modifier_names() else MODIFIER_INFO[get_core_modifier()]['name'].upper()}", 22, YELLOW, mx2, my2, center=True)
        draw_text("click for modifiers", 20, WHITE, mx2, my2 + 18, center=True)
        q = get_current_quest_line(selected_world)
        if q is None:
            draw_text(f"{selected_world.title()} questline done", 24, GREEN, w // 2, 130, center=True)
        else:
            quest, prog = q
            draw_text(f"Questline: {quest['label']}", 26, LIGHT_BLUE, w // 2, 126, center=True)
            draw_text(f"{min(prog, quest['target'])}/{quest['target']}", 24, GREEN, w // 2, 152, center=True)
        buy_button_rects = []
        for i, opt in enumerate(options, start=1):
            level = buffs[opt['key']]
            if opt['key'] == 'mine_power':
                costv = opt['cost_tiers'].get(level, 0) if level < opt['max'] else 0
            else:
                costv = opt['cost_base'] * level if level < opt['max'] else 0
            if cheat_mode and level < opt['max']:
                costv = 0
            can_buy = level < opt['max'] and (total_money >= costv or cheat_mode)
            lx, ly = SHOP_ANCHORS[f'label_{i}']
            lab = label_font.render(opt['name'], True, (220,220,220) if can_buy else (140,140,140))
            screen.blit(lab, (lx - lab.get_width()//2, ly - lab.get_height()//2))
            bx, by, bw, bh = SHOP_ANCHORS[f'bar_{i}']
            pg.draw.rect(screen, (0,0,0), (bx-3, by-3, bw+6, bh+6))
            pg.draw.rect(screen, (110,110,110), (bx,by,bw,bh))
            frac = max(0.0, min(1.0, level / float(opt['max'])))
            pg.draw.rect(screen, (220,220,220) if can_buy else (160,160,160), (bx,by,int(bw*frac),bh))
            cx2, cy2 = SHOP_ANCHORS[f'cost_{i}']
            btn = pg.Rect(cx2 - 82, cy2 - 20, 164, 42)
            buy_button_rects.append((btn, opt, costv))
            pg.draw.rect(screen, (0,0,0), btn, border_radius=10)
            pg.draw.rect(screen, (110,110,110) if can_buy else (70,70,70), btn.inflate(-4,-4), border_radius=10)
            txt = 'MAX' if level >= opt['max'] else f'BUY ${costv}'
            draw_text_in_rect(txt, btn, 18, YELLOW if can_buy else LIGHT_GRAY, align='center', valign='center', padding=6, bold=True)
        mx, my = SHOP_ANCHORS['money']
        draw_text(f"MONEY: ${total_money:.2f}", 50, (230,230,230), mx, my, center=True, max_width=360, bold=True)
        if layout_edit_mode:
            key = editable_keys[edit_idx]
            value = SHOP_ANCHORS[key]
            if isinstance(value, pg.Rect):
                high_rect = value.inflate(10, 10)
            elif isinstance(value, tuple) and len(value) == 2:
                high_rect = pg.Rect(value[0]-12, value[1]-12, 24, 24)
            else:
                bx, by, bw, bh = value
                high_rect = pg.Rect(bx-6, by-6, bw+12, bh+12)
            pg.draw.rect(screen, RED, high_rect, 3, border_radius=8)
            draw_text(f"LAYOUT EDIT: {key}", 28, YELLOW, w//2, 24, center=True)
        for i, popup in enumerate(popups[:]):
            popup.draw(i*30)
            if not popup.update():
                popups.remove(popup)
        pg.display.flip()
        events = pg.event.get(); music.update(events)
        clicked_pos = None
        for e in events:
            if e.type == pg.QUIT:
                pg.quit(); raise SystemExit
            if e.type == pg.KEYDOWN:
                handle_secret_combo(e)
                if e.key == pg.K_F8:
                    layout_edit_mode = not layout_edit_mode
                    if not layout_edit_mode:
                        ok = save_shop_anchors_to_source()
                        popups.append(Popup("Layout saved." if ok else "Layout save failed.", size=34, lifetime=140, color=LIGHT_BLUE if ok else RED, y=120))
                if layout_edit_mode:
                    step = 10 if (pg.key.get_mods() & pg.KMOD_SHIFT) else 1
                    current = editable_keys[edit_idx]
                    val = SHOP_ANCHORS[current]
                    if e.key == pg.K_TAB:
                        edit_idx = (edit_idx + 1) % len(editable_keys)
                    elif e.key == pg.K_LEFT:
                        if isinstance(val, pg.Rect): val.x -= step
                        elif len(val) == 2: SHOP_ANCHORS[current] = (val[0]-step, val[1])
                        else: SHOP_ANCHORS[current] = (val[0]-step, val[1], val[2], val[3])
                    elif e.key == pg.K_RIGHT:
                        if isinstance(val, pg.Rect): val.x += step
                        elif len(val) == 2: SHOP_ANCHORS[current] = (val[0]+step, val[1])
                        else: SHOP_ANCHORS[current] = (val[0]+step, val[1], val[2], val[3])
                    elif e.key == pg.K_UP:
                        if isinstance(val, pg.Rect): val.y -= step
                        elif len(val) == 2: SHOP_ANCHORS[current] = (val[0], val[1]-step)
                        else: SHOP_ANCHORS[current] = (val[0], val[1]-step, val[2], val[3])
                    elif e.key == pg.K_DOWN:
                        if isinstance(val, pg.Rect): val.y += step
                        elif len(val) == 2: SHOP_ANCHORS[current] = (val[0], val[1]+step)
                        else: SHOP_ANCHORS[current] = (val[0], val[1]+step, val[2], val[3])
                    elif e.key == pg.K_s and (pg.key.get_mods() & pg.KMOD_CTRL):
                        save_shop_anchors_to_source()
            if e.type == pg.MOUSEBUTTONDOWN and e.button == 1:
                clicked_pos = e.pos
        if clicked_pos and skins_btn.collidepoint(clicked_pos):
            await skins_menu(); clock.tick(fps); await frame_yield(); continue
        if clicked_pos and tutorial_btn.collidepoint(clicked_pos):
            await tutorial_menu(); clock.tick(fps); await frame_yield(); continue
        if clicked_pos:
            if pg.Rect(wx - 110, wy - 20, 220, 54).collidepoint(clicked_pos):
                await worlds_menu(total_money); clock.tick(fps); await frame_yield(); continue
            if pg.Rect(mx2 - 120, my2 - 20, 240, 58).collidepoint(clicked_pos):
                await modifiers_menu(); clock.tick(fps); await frame_yield(); continue
            for btn, opt, costv in buy_button_rects:
                if btn.collidepoint(clicked_pos):
                    lvl = buffs[opt['key']]
                    if lvl >= opt['max']:
                        popups.append(Popup('Already maxed', size=34, lifetime=120, color=LIGHT_BLUE))
                    elif total_money >= costv or cheat_mode:
                        buffs[opt['key']] += 1
                        if not cheat_mode:
                            total_money -= costv
                        popups.append(Popup(f"{opt['name']} upgraded!", size=38, lifetime=150, color=GREEN))
                    else:
                        popups.append(Popup('Not enough money', size=34, lifetime=120, color=RED))
        keys = pg.key.get_pressed()
        if keys[pg.K_RETURN]:
            pg.mouse.set_visible(False); pg.event.set_grab(True); return total_money
        clock.tick(fps); await frame_yield()


async def game_session(total_money):
    global cooldown_timer, COOLDOWN_MAX, run_boosted_mode
    run_boosted_mode = (has_modifier('challenge'))
    music.set_mode('challenge' if run_boosted_mode else 'main')
    player = Player(0, 0)
    ground = Ground()
    lives = 3
    invuln = 0
    pending_damage = False
    clear_tiles = [(-TILE, -TILE), (0, -TILE), (-TILE, 0), (0, 0)]
    for bx, by in clear_tiles:
        ground.block_types[(bx, by)] = 'regular'
        ground.mined_blocks.add((bx, by))
        ground.ore_tiles.pop((bx, by), None)
        ground.hazard_tiles.pop((bx, by), None)
    def get_cooldown(level):
        base = 72
        t = base * (0.18 + 0.82 * ((10 - level) / 9) ** 2)
        return max(6, int(t))
    cooldown_timer = get_cooldown(buffs['mining_speed'])
    COOLDOWN_MAX = cooldown_timer
    popups.clear()
    if not run_boosted_mode:
        popups.append(Popup('Questline + combo + bounty active', size=38, lifetime=150, color=LIGHT_BLUE))
    else:
        popups.append(Popup('Challenge modifier active', size=38, lifetime=150, color=YELLOW))
    duration_seconds = CHALLENGE_TIME if run_boosted_mode else SESSION_TIME
    if (has_modifier('ore_surge') or has_modifier('powerup_storm')):
        duration_seconds = 75
    if has_modifier('bounty_hunter'):
        duration_seconds = 80
    session_frames = duration_seconds * fps
    session_money = 0.0
    blocks_mined = 0
    rarity_counts = {r: 0 for r in RARITY_ORDER}
    elapsed_frames = 0
    combo = 0
    combo_timer = 0
    combo_max = int(2.6 * fps)
    run_bounty = pick_run_bounty(get_active_world(), active_modifier_names())
    run_bounty['progress'] = 0
    run_bounty['complete'] = False
    event_cd = random.randint(11 * fps, 17 * fps)
    RUN_EVENT['name'] = None
    RUN_EVENT['timer'] = 0
    RUN_EVENT['ping_block'] = None
    blaster_cd = 5 * fps
    blaster_warn = 0
    blaster_fire = 0
    blaster_axis = None
    blaster_value = None
    blaster_dir = 1
    blaster_fire_total = 1
    lingering_beams = []
    vent_beams = []
    pending_smites = []
    ended_by_timer = False
    aborted_early = False
    died = False
    death_reason = 'You died.'

    def combo_mult():
        return min(2.0, 1.0 + combo * 0.08)

    def trigger_run_event():
        RUN_EVENT['name'] = random.choice(['Ore Surge', 'Powerup Storm', 'Bounty Rush'])
        RUN_EVENT['timer'] = 18 * fps
        if RUN_EVENT['name'] == 'Bounty Rush':
            RUN_EVENT['ping_block'] = None
        popups.append(Popup(RUN_EVENT['name'] + '!', size=46, lifetime=130, color=YELLOW))

    def push_combo(kind='ore'):
        nonlocal combo, combo_timer, session_money
        combo += 1
        combo_timer = combo_max
        if combo in (4, 8, 12):
            popups.append(Popup(f'COMBO x{combo_mult():.2f}', size=36, lifetime=100, color=LIGHT_BLUE))
        if apply_bounty_progress(run_bounty, combo_level=combo, current_money=session_money):
            reward_cash, reward_buff = grant_bounty_reward(run_bounty)
            session_money += reward_cash
            if reward_buff:
                popups.append(Popup(f"BOUNTY COMPLETE +${reward_cash:.0f} + {reward_buff[0]}", size=40, lifetime=145, color=GREEN))
            else:
                popups.append(Popup(f"BOUNTY COMPLETE +${reward_cash:.0f}", size=40, lifetime=145, color=GREEN))

    running = True
    while running:
        dt_sec = clock.get_time() / 1000.0
        elapsed_frames += 1
        events = pg.event.get(); music.update(events)
        for e in events:
            if e.type == pg.QUIT:
                pg.quit(); raise SystemExit
            elif e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
                aborted_early = True; running = False
        expired = []
        for p_name in list(active_powerups.keys()):
            active_powerups[p_name][0] -= 1
            if active_powerups[p_name][0] <= 0:
                expired.append(p_name)
        for p_name in expired:
            del active_powerups[p_name]
        ground.reveal_active = 'Reveal' in active_powerups
        ground.reveal_time = active_powerups['Reveal'][0] if 'Reveal' in active_powerups else 0
        if 'Freeze Timer' not in active_powerups:
            session_frames -= 1
        money_multiplier = 2.0 if 'Money Boost' in active_powerups else 1.0
        if RUN_EVENT['timer'] > 0:
            RUN_EVENT['timer'] -= 1
            if RUN_EVENT['timer'] <= 0:
                RUN_EVENT['name'] = None
                RUN_EVENT['ping_block'] = None
        else:
            event_cd -= 1
            if event_cd <= 0:
                trigger_run_event()
                event_cd = random.randint(13 * fps, 20 * fps)
        if combo_timer > 0:
            combo_timer -= 1
        elif combo > 0:
            combo = 0
        confusion_multiplier = -1 if 'Confusion' in active_powerups else 1
        keys = pg.key.get_pressed()
        player.vel_x = player.vel_y = 0
        if keys[pg.K_a]: player.vel_x = -player.max_speed * confusion_multiplier
        if keys[pg.K_d]: player.vel_x = player.max_speed * confusion_multiplier
        if keys[pg.K_w]: player.vel_y = -player.max_speed * confusion_multiplier
        if keys[pg.K_s]: player.vel_y = player.max_speed * confusion_multiplier
        player.move(ground)
        if run_boosted_mode:
            ground.update_lava_flow()
            tx = int(player.x // TILE) * TILE; ty = int(player.y // TILE) * TILE
            if (tx, ty) in ground.lava_pools and invuln == 0 and not cheat_mode:
                pending_damage = True; death_reason = 'You fell into lava.'
        world_now = get_active_world()
        if apply_bounty_progress(run_bounty, elapsed_seconds=elapsed_frames // fps):
            reward_cash, reward_buff = grant_bounty_reward(run_bounty)
            session_money += reward_cash
            if reward_buff:
                popups.append(Popup(f"BOUNTY COMPLETE +${reward_cash:.0f} + {reward_buff[0]}", size=40, lifetime=145, color=GREEN))
            else:
                popups.append(Popup(f"BOUNTY COMPLETE +${reward_cash:.0f}", size=40, lifetime=145, color=GREEN))
        if run_boosted_mode:
            t = min(1.0, elapsed_frames / float(duration_seconds * fps))
            interval = max(int(3.2 * fps), int((6.0 - 2.2 * t) * fps))
            warn_time = max(int(0.55 * fps), int((1.05 - 0.35 * t) * fps))
            fire_time = max(int(0.12 * fps), int((0.20 - 0.05 * t) * fps))
            blaster_cd -= 1
            if blaster_cd <= 0 and blaster_warn == 0 and blaster_fire == 0:
                px_tile, py_tile = player_tile_center(player)
                blaster_axis = random.choice(['h', 'v'])
                blaster_value = py_tile if blaster_axis == 'h' else px_tile
                blaster_dir = random.choice([1, -1])
                blaster_warn = warn_time
                blaster_fire_total = fire_time
                blaster_cd = interval
            if blaster_warn > 0:
                blaster_warn -= 1
                if blaster_warn == 0:
                    blaster_fire = blaster_fire_total
            if blaster_fire > 0:
                blaster_fire -= 1
                px_tile, py_tile = player_tile_center(player)
                hit = (py_tile == blaster_value) if blaster_axis == 'h' else (px_tile == blaster_value)
                if hit and invuln == 0 and not cheat_mode:
                    pending_damage = True; death_reason = 'You got hit by a blaster.'
                if blaster_fire == 0:
                    linger_frames = int(1.3 * fps)
                    lingering_beams.append({'axis': blaster_axis, 'value_world': blaster_value, 'timer': linger_frames, 'max': linger_frames, 'color': (255, 80, 80)})
        if run_boosted_mode and world_now == 'hell':
            for pos in list(ground.fire_vent_cd.keys()):
                ground.fire_vent_cd[pos] -= 1
                if ground.fire_vent_cd[pos] <= 0:
                    ground.fire_vent_cd[pos] = random.randint(int(2.4 * fps), int(3.6 * fps))
                    vx, vy = tile_center(*pos)
                    px_tile, py_tile = player_tile_center(player)
                    if line_of_sight_air(ground, (vx, vy), (px_tile, py_tile)) and invuln == 0 and not cheat_mode:
                        pending_damage = True; death_reason = 'You were burned by a fire vent.'
                    bx, by = pos
                    if (bx + TILE, by) in ground.mined_blocks or (bx - TILE, by) in ground.mined_blocks:
                        vent_beams.append({'axis': 'h', 'value_world': vy, 'timer': int(0.8 * fps), 'max': int(0.8 * fps), 'color': (255, 140, 60)})
                    if (bx, by + TILE) in ground.mined_blocks or (bx, by - TILE) in ground.mined_blocks:
                        vent_beams.append({'axis': 'v', 'value_world': vx, 'timer': int(0.8 * fps), 'max': int(0.8 * fps), 'color': (255, 140, 60)})
        for b in vent_beams[:]:
            b['timer'] -= 1
            if b['timer'] <= 0: vent_beams.remove(b)
        if run_boosted_mode and world_now == 'heaven':
            for pos in list(ground.smite_cd.keys()):
                ground.smite_cd[pos] -= 1
                if ground.smite_cd[pos] <= 0:
                    ground.smite_cd[pos] = random.randint(int(2.6 * fps), int(4.2 * fps))
                    tx = int(player.x // TILE) * TILE; ty = int(player.y // TILE) * TILE
                    pending_smites.append({'target_tile': (tx, ty), 'warn': int(0.85 * fps), 'strike': int(0.12 * fps)})
        for sm in pending_smites[:]:
            if sm['warn'] > 0:
                sm['warn'] -= 1
            else:
                sm['strike'] -= 1
                if sm['strike'] <= 0:
                    tx, ty = sm['target_tile']
                    px_t = int(player.x // TILE) * TILE; py_t = int(player.y // TILE) * TILE
                    if (px_t, py_t) == (tx, ty) and invuln == 0 and not cheat_mode:
                        pending_damage = True; death_reason = 'You were smitten.'
                    lingering_beams.append({'axis': 'h', 'value_world': ty + TILE/2, 'timer': int(0.6 * fps), 'max': int(0.6 * fps), 'color': (160, 210, 255)})
                    lingering_beams.append({'axis': 'v', 'value_world': tx + TILE/2, 'timer': int(0.6 * fps), 'max': int(0.6 * fps), 'color': (160, 210, 255)})
                    pending_smites.remove(sm)
        for b in lingering_beams[:]:
            b['timer'] -= 1
            if b['timer'] <= 0: lingering_beams.remove(b)
        if pg.mouse.get_pressed()[0]:
            camera_x = player.x - w // 2; camera_y = player.y - h // 2
            block, btype = ground.mine_block(player, camera_x, camera_y)
            if block and cooldown_timer >= COOLDOWN_MAX:
                direction = (block[0] + TILE / 2 - player.x, block[1] + TILE / 2 - player.y)
                blocks_to_mine = blocks_for_mine_power(buffs['mine_power'], player.x, player.y, block)
                if 'Heavy Pickaxe' in active_powerups:
                    bx, by = block
                    for ex in range(-1, 2):
                        for ey in range(-1, 2):
                            blocks_to_mine.append((bx + ex * TILE, by + ey * TILE))
                    del active_powerups['Heavy Pickaxe']
                if 'Bomb' in active_powerups:
                    bx, by = block
                    for ex in range(-2, 3):
                        for ey in range(-2, 3):
                            blocks_to_mine.append((bx + ex * TILE, by + ey * TILE))
                    del active_powerups['Bomb']
                seen = set(); uniq = []
                for b in blocks_to_mine:
                    if b not in seen: seen.add(b); uniq.append(b)
                for b in uniq:
                    if b in ground.mined_blocks: continue
                    bx, by = b
                    btype2 = ground.generate_block(bx, by)
                    ground.mined_blocks.add(b)
                    blocks_mined += 1
                    for msg in add_quest_progress(world_now, 'blocks', 1):
                        popups.append(Popup(msg, size=36, lifetime=120, color=YELLOW))
                    if has_modifier('challenge'):
                        ground.expose_adjacent_hazards(b)
                    if btype2 == 'hazard':
                        hz = ground.hazard_tiles.get(b, 'lava')
                        if hz == 'bomb_trap':
                            popups.append(Popup('BOMB!', size=52, lifetime=120, color=RED))
                            primed = {'block': b, 'ticks': 0, 'delay': int(2.0 * fps), 'flash_interval': max(1, int((2.0 * fps) / 6))}
                            ground.primed_bombs.append(primed)
                        ground.hazard_tiles.pop(b, None)
                        continue
                    if btype2 == 'ore' and b in ground.ore_tiles:
                        rarity2 = ground.ore_tiles[b]
                        rarity_counts[rarity2] = rarity_counts.get(rarity2, 0) + 1
                        pool = ORE_OPTIONS_WORLD[world_now][rarity2]
                        ore_name, ore_value = random.choice(list(pool.items()))
                        ore_value *= (1 + buffs['fortune'] * 0.05) * money_multiplier * combo_mult()
                        session_money += ore_value
                        push_combo('ore')
                        if apply_bounty_progress(run_bounty, amount=1, current_money=session_money, combo_level=combo, rarity=rarity2):
                            reward_cash, reward_buff = grant_bounty_reward(run_bounty)
                            session_money += reward_cash
                            if reward_buff:
                                popups.append(Popup(f"BOUNTY COMPLETE +${reward_cash:.0f} + {reward_buff[0]}", size=40, lifetime=145, color=GREEN))
                            else:
                                popups.append(Popup(f"BOUNTY COMPLETE +${reward_cash:.0f}", size=40, lifetime=145, color=GREEN))
                        for msg in add_quest_progress(world_now, 'ore', 1):
                            popups.append(Popup(msg, size=36, lifetime=120, color=YELLOW))
                        popups.append(Popup(f'+{ore_name} (${ore_value:.2f})', size=42, lifetime=120, color=RARITY_COLORS.get(rarity2, WHITE)))
                        del ground.ore_tiles[b]
                    elif btype2 == 'powerup' and b in ground.ore_tiles:
                        p_name = ground.ore_tiles[b]
                        active_powerups[p_name] = [REVEAL_DURATION if p_name == 'Reveal' else POWERUP_DURATION, {}]
                        push_combo('powerup')
                        if apply_bounty_progress(run_bounty, amount=1, current_money=session_money, combo_level=combo):
                            reward_cash, reward_buff = grant_bounty_reward(run_bounty)
                            session_money += reward_cash
                            if reward_buff:
                                popups.append(Popup(f"BOUNTY COMPLETE +${reward_cash:.0f} + {reward_buff[0]}", size=40, lifetime=145, color=GREEN))
                            else:
                                popups.append(Popup(f"BOUNTY COMPLETE +${reward_cash:.0f}", size=40, lifetime=145, color=GREEN))
                        popups.append(Popup(f'POWERUP: {p_name}!', size=50, lifetime=140, color=GREEN))
                        del ground.ore_tiles[b]
                    for msg in add_quest_progress(world_now, 'money', 0):
                        popups.append(Popup(msg, size=36, lifetime=120, color=YELLOW))
                if apply_bounty_progress(run_bounty, current_money=session_money):
                    reward_cash, reward_buff = grant_bounty_reward(run_bounty)
                    session_money += reward_cash
                    if reward_buff:
                        popups.append(Popup(f"BOUNTY COMPLETE +${reward_cash:.0f} + {reward_buff[0]}", size=40, lifetime=145, color=GREEN))
                    else:
                        popups.append(Popup(f"BOUNTY COMPLETE +${reward_cash:.0f}", size=40, lifetime=145, color=GREEN))
                current_money_prog = quest_progress[world_now].get('money', 0)
                if session_money > current_money_prog:
                    for msg in add_quest_progress(world_now, 'money', session_money - current_money_prog):
                        popups.append(Popup(msg, size=36, lifetime=120, color=YELLOW))
                cooldown_timer = 0
                ground.early_shake_timer = 0
            else:
                ground.early_shake_timer = EARLY_SHAKE_DURATION
        if cooldown_timer < COOLDOWN_MAX: cooldown_timer += 1
        if ground.early_shake_timer > 0: ground.early_shake_timer -= 1
        if run_boosted_mode:
            # bomb flashing then 5x5 explosion
            for bomb in ground.primed_bombs[:]:
                bomb['ticks'] += 1
                if bomb['ticks'] >= bomb['delay']:
                    bx, by = bomb['block']
                    bomb_cx, bomb_cy = bx + TILE / 2, by + TILE / 2
                    for ex in range(-2, 3):
                        for ey in range(-2, 3):
                            nb = (bx + ex * TILE, by + ey * TILE)
                            if nb not in ground.mined_blocks:
                                ground.generate_block(*nb)
                                ground.mined_blocks.add(nb)
                    if math.hypot(player.x - bomb_cx, player.y - bomb_cy) <= TILE * 2.6 and invuln == 0 and not cheat_mode:
                        pending_damage = True; death_reason = 'You got caught in a bomb blast.'
                    ground.primed_bombs.remove(bomb)
            if invuln > 0: invuln -= 1
            if pending_damage and invuln == 0:
                pending_damage = False
                lives -= 1
                invuln = int(1.1 * fps)
                if lives <= 0:
                    died = True; running = False
        else:
            pending_damage = False
        screen.fill(BLACK)
        camera_x, camera_y = player.x - w // 2, player.y - h // 2
        cursor_screen_pos = pg.mouse.get_pos()
        cursor_world_pos = (camera_x + cursor_screen_pos[0], camera_y + cursor_screen_pos[1])
        ground.draw(camera_x, camera_y, player.x, player.y, cursor_world_pos, cursor_screen_pos, dt_sec)
        if RUN_EVENT['name'] == 'Bounty Rush' and RUN_EVENT['ping_block']:
            pbx, pby = RUN_EVENT['ping_block']
            sx, sy = pbx - camera_x + TILE // 2, pby - camera_y + TILE // 2
            if -40 <= sx <= w + 40 and -40 <= sy <= h + 40:
                pg.draw.circle(screen, YELLOW, (int(sx), int(sy)), 20, 2)
                pg.draw.circle(screen, LIGHT_BLUE, (int(sx), int(sy)), 28, 1)
        if run_boosted_mode and blaster_axis is not None:
            if blaster_warn > 0:
                pulse = 0.5 + 0.5 * math.sin(pg.time.get_ticks() * 0.02)
                thick = 2 + int(2 * pulse)
                if blaster_axis == 'h':
                    yv = blaster_value - camera_y; pg.draw.line(screen, YELLOW, (0, int(yv)), (w, int(yv)), thick)
                else:
                    xv = blaster_value - camera_x; pg.draw.line(screen, YELLOW, (int(xv), 0), (int(xv), h), thick)
            if blaster_fire > 0:
                progress = 1.0 - (blaster_fire / float(max(1, blaster_fire_total)))
                beam_thick = 10
                if blaster_axis == 'h':
                    yv = int(blaster_value - camera_y)
                    x0, x1 = (0, int(w * progress)) if blaster_dir > 0 else (int(w * (1.0 - progress)), w)
                    pg.draw.rect(screen, (255,80,80), (x0, yv - beam_thick//2, max(1, x1 - x0), beam_thick))
                    pg.draw.rect(screen, (255,180,180), (x0, yv - 2, max(1, x1 - x0), 4))
                else:
                    xv = int(blaster_value - camera_x)
                    y0, y1 = (0, int(h * progress)) if blaster_dir > 0 else (int(h * (1.0 - progress)), h)
                    pg.draw.rect(screen, (255,80,80), (xv - beam_thick//2, y0, beam_thick, max(1, y1 - y0)))
                    pg.draw.rect(screen, (255,180,180), (xv - 2, y0, 4, max(1, y1 - y0)))
        for b in lingering_beams:
            frac = b['timer'] / float(max(1, b['max']))
            alpha = 210 * frac
            axis = b['axis']; value_world = b['value_world']
            value_screen = (value_world - camera_y) if axis == 'h' else (value_world - camera_x)
            draw_beam_fade(screen, axis, value_screen, alpha, thickness=10, color=b.get('color', (255,80,80)))
        for b in vent_beams:
            frac = b['timer'] / float(max(1, b['max']))
            alpha = 200 * frac
            axis = b['axis']; value_world = b['value_world']
            value_screen = (value_world - camera_y) if axis == 'h' else (value_world - camera_x)
            draw_beam_fade(screen, axis, value_screen, alpha, thickness=10, color=b.get('color', (255,140,60)))
        for sm in pending_smites:
            if sm['warn'] > 0:
                tx, ty = sm['target_tile']; sx, sy = tx - camera_x, ty - camera_y
                pg.draw.rect(screen, (140, 200, 255), (sx + 4, sy + 4, TILE - 8, TILE - 8), 3)
        draw_crosshair(screen, RED, cursor_screen_pos[0], cursor_screen_pos[1], 15, 2, player_pos=(player.x - camera_x, player.y - camera_y), reveal_time=ground.reveal_time if ground.reveal_active else None)
        top_right = pg.Rect(w - 218, 12, 198, 100 if not run_boosted_mode else 122)
        draw_ui_panel(top_right, border=(88, 190, 255), fill=(8, 12, 20, 214), radius=16)
        draw_text_in_rect(f"{max(0, session_frames // fps)}", pg.Rect(top_right.x+14, top_right.y+8, top_right.w-28, 28), 36, YELLOW, bold=True)
        draw_text_in_rect(f"WORLD {world_now.upper()}", pg.Rect(top_right.x+14, top_right.y+42, top_right.w-28, 22), 22, YELLOW, bold=True)
        mod_text = ' + '.join(active_modifier_names()).upper() if active_modifier_names() else MODIFIER_INFO[get_core_modifier()]['name'].upper()
        draw_text_in_rect(mod_text, pg.Rect(top_right.x+14, top_right.y+68, top_right.w-28, 18), 15, LIGHT_BLUE, valign='top')
        if run_boosted_mode:
            draw_text_in_rect(f"LIVES {lives}", pg.Rect(top_right.x+14, top_right.y+88, top_right.w-28, 18), 16, WHITE, bold=True)

        draw_bounty_banner()
        left_top_y = 14
        q = get_current_quest_line(world_now)
        if q is not None:
            quest, prog = q
            quest_rect = pg.Rect(14, left_top_y, 350, 76)
            draw_ui_panel(quest_rect, border=(125, 210, 255), fill=(8, 12, 20, 214), radius=14)
            draw_text_in_rect(world_now.upper() + ' QUESTLINE', pg.Rect(quest_rect.x+14, quest_rect.y+10, quest_rect.w-110, 18), 18, YELLOW, align='left', valign='top', bold=True)
            draw_badge(pg.Rect(quest_rect.right-84, quest_rect.y+10, 68, 24), f"{min(int(prog), quest['target'])}/{quest['target']}", fg=GREEN, bg=(20, 34, 24), border=(120, 235, 120), size=13)
            draw_text_in_rect(quest['label'], pg.Rect(quest_rect.x+14, quest_rect.y+34, quest_rect.w-28, 28), 15, WHITE, align='left', valign='top')
            left_top_y += 84

        bounty_rect = pg.Rect(14, left_top_y, 350, 86)
        draw_ui_panel(bounty_rect, border=GREEN if run_bounty.get('complete') else YELLOW, fill=(8, 12, 20, 214), radius=14, glow=bool(run_bounty.get('complete')))
        draw_text_in_rect('RUN BOUNTY', pg.Rect(bounty_rect.x+14, bounty_rect.y+10, bounty_rect.w-110, 18), 18, YELLOW, align='left', valign='top', bold=True)
        draw_badge(pg.Rect(bounty_rect.right-84, bounty_rect.y+10, 68, 24), f"{min(int(run_bounty.get('progress',0)), run_bounty['target'])}/{run_bounty['target']}", fg=GREEN, bg=(20, 34, 24), border=(120, 235, 120), size=13)
        draw_text_in_rect(run_bounty['label'], pg.Rect(bounty_rect.x+14, bounty_rect.y+34, bounty_rect.w-28, 22), 15, WHITE, align='left', valign='top')
        reward_line = f"Reward +${int(run_bounty.get('reward_cash',0))}"
        if run_bounty.get('reward_buff'):
            reward_line += f" + {run_bounty['reward_buff'][0]}"
        draw_text_in_rect(reward_line, pg.Rect(bounty_rect.x+14, bounty_rect.y+58, bounty_rect.w-28, 16), 13, LIGHT_BLUE, align='left', valign='top')
        left_top_y += 94

        if RUN_EVENT['name']:
            event_rect = pg.Rect(14, left_top_y, 256, 34)
            draw_ui_panel(event_rect, border=(88, 190, 255), fill=(14, 20, 34, 208), radius=12)
            draw_text_in_rect(f"EVENT {RUN_EVENT['name']} {max(0, RUN_EVENT['timer']//fps)}s", event_rect, 14, LIGHT_BLUE, padding=8, bold=True)
            left_top_y += 40
        if combo > 0:
            combo_rect = pg.Rect(14, left_top_y, 180, 30)
            draw_ui_panel(combo_rect, border=(120, 235, 120), fill=(14, 34, 18, 208), radius=12)
            draw_text_in_rect(f"COMBO x{combo_mult():.2f}", combo_rect, 14, GREEN, bold=True)
        for i, popup in enumerate(popups[:]):
            popup.draw(i*30)
            if not popup.update(): popups.remove(popup)
        player.draw(camera_x, camera_y, invuln=(invuln if run_boosted_mode else 0))
        pg.display.flip(); clock.tick(fps); await frame_yield()
        if session_frames <= 0:
            ended_by_timer = True; running = False
    earned = session_money
    payout_mult = 1.0 if ended_by_timer else (0.25 if run_boosted_mode else 0.75)
    payout = earned * payout_mult
    if run_boosted_mode and ended_by_timer:
        challenge_target_cleared[world_now] = challenge_target_cleared[world_now] or (session_money >= CHALLENGE_TARGETS[world_now])
        if world_now == 'heaven' and not skins_unlocked['survivor']:
            skins_unlocked['survivor'] = True
    if all(challenge_target_cleared.values()):
        skins_unlocked['completionist'] = True
    if all(questline_complete.values()):
        skins_unlocked['quest walker'] = True
    update_world_unlocks()
    title = 'GAME OVER' if died else ('RUN COMPLETE' if ended_by_timer else 'RUN ENDED')
    mode_name = ' + '.join(active_modifier_names()) if active_modifier_names() else MODIFIER_INFO[get_core_modifier()]['name']
    reason = death_reason if died else ('Timer finished!' if ended_by_timer else 'You left early.')
    await run_summary_screen(title_text=title, world_name=world_now, mode_name=mode_name, earned=earned, payout=payout, payout_mult=payout_mult, reason=reason, time_left_s=session_frames / fps, lives_left=max(0, lives), mined_count=blocks_mined, rarity_counts=rarity_counts, show_lives=run_boosted_mode)
    return total_money + payout


async def main():
    update_world_unlocks()
    total_money = 1200
    if not tutorial_seen():
        await tutorial_menu()
    while True:
        total_money = await shop_menu(total_money)
        total_money = await game_session(total_money)

if __name__ == '__main__':
    asyncio.run(main())
