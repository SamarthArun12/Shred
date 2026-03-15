import sys
import os
import math
import random
import asyncio
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

    title_font = pg.font.SysFont(None, 88)
    big = pg.font.SysFont(None, 44)
    small = pg.font.SysFont(None, 30)
    tiny = pg.font.SysFont(None, 24)

    while True:
        events = pg.event.get()
        music.update(events)

        for e in events:
            if e.type == pg.QUIT:
                pg.quit()
                raise SystemExit
            if e.type == pg.KEYDOWN and e.key == pg.K_ESCAPE:
                pg.mouse.set_visible(True)
                return

        screen.fill((10, 10, 14))

        t = title_font.render(title_text, True, RED if "GAME" in title_text else YELLOW)
        screen.blit(t, (w // 2 - t.get_width() // 2, 70))

        line1 = big.render(f"World: {world_name.upper()}   |   Mode: {mode_name}", True, YELLOW)
        screen.blit(line1, (w // 2 - line1.get_width() // 2, 190))

        rsn = big.render(reason, True, WHITE)
        screen.blit(rsn, (w // 2 - rsn.get_width() // 2, 245))

        e1 = big.render(f"Earnings: ${earned:.2f}", True, WHITE)
        screen.blit(e1, (w // 2 - e1.get_width() // 2, 320))

        e2 = big.render(f"Payout ({int(payout_mult*100)}%): ${payout:.2f}", True, YELLOW)
        screen.blit(e2, (w // 2 - e2.get_width() // 2, 370))

        yy = 420
        rarity_font = pg.font.SysFont(None, 28)
        for rarity in RARITY_ORDER:
            count = rarity_counts.get(rarity, 0)
            txt = rarity_font.render(f"{rarity.title()}: {count}", True, RARITY_COLORS.get(rarity, WHITE))
            screen.blit(txt, (w // 2 - txt.get_width() // 2, yy))
            yy += 26

        stats = [
            f"Time left: {max(0, int(time_left_s))}s",
            f"Blocks mined: {mined_count}",
        ]
        if show_lives:
            stats.insert(1, f"Lives left: {lives_left}")

        yy += 14
        for s in stats:
            st = tiny.render(s, True, LIGHT_BLUE)
            screen.blit(st, (w // 2 - st.get_width() // 2, yy))
            yy += 26

        tip = small.render("Press ESC to return to main menu", True, LIGHT_BLUE)
        screen.blit(tip, (w // 2 - tip.get_width() // 2, 640))

        pg.display.flip()
        clock.tick(fps)
        await frame_yield()

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

    duration_seconds = CHALLENGE_TIME if run_boosted_mode else SESSION_TIME
    session_frames = duration_seconds * fps

    session_money = 0.0
    blocks_mined = 0
    rarity_counts = {r: 0 for r in RARITY_ORDER}

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
                            del ground.ore_tiles[b]

                        elif btype2 == "powerup" and b in ground.ore_tiles:
                            p_name = ground.ore_tiles[b]
                            active_powerups[p_name] = [REVEAL_DURATION if p_name == "Reveal" else POWERUP_DURATION, {}]
                            popups.append(Popup(f"POWERUP: {p_name}!", size=54, lifetime=160, color=GREEN))
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

# -------------------------
# ASYNC MAIN (pygbag-friendly)
# -------------------------
async def main():
    total_money = 500
    while True:
        total_money = await shop_menu(total_money)
        total_money = await game_session(total_money)

if __name__ == "__main__":
    asyncio.run(main())
