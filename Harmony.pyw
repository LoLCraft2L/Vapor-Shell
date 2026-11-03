"""
Harmony - skewed-carousel wallpaper picker for Windows.

Install:  pip install PySide6 Pillow
Run:      pythonw Harmony.pyw [folder]      (add --background to start hidden, e.g. at login)
Hotkey:   Alt+Shift+A shows / hides the picker (see HOTKEY_*). Launching the script again just shows it.

Keys     Up/Down = recall earlier typed texts | Left/Right/wheel browse | Enter or click centre = apply | Space or Ctrl+F or heart = favourite
         Click colour square = filter | just type to search | Esc / right click = clear, then hide
         Ctrl+B = achievements
Commands (type, then Enter)
  ;fav  ;red ;blue ;green ... ;gray   filter favourites / by colour
  ;color [name]   set the colour of the focused wallpaper by hand (e.g. ;color red). Bare ;color = list the names
  ;random      apply a random wallpaper          ;crop     pick an area of the wallpaper and apply it
  ;rename [n]  rename the focused wallpaper      ;delete   delete it (Recycle Bin)
  ;path [dir]  change wallpaper folder           ;wallpapers / ;cache / ;locate   open folders in Explorer
  ;fetch "link" [-n "name"]   download a direct image link into the wallpaper folder (-n = custom file name)
  ;sound       sound effects on / off            ;volume 1-100   sound volume (remembered)
  ;toggle      show / hide the file name
  ;help        show the command list            ;clicks   show / hide the click count on the icon (remembered)
  ;spin        icon spins while music plays (on / off)   ;resetc  reset clicks + achievements
  ;config      open the settings file (every setting is remembered between runs)
  ;quit  or  ;q   exit the background process
"""
import base64
import bisect
import ctypes
import colorsys
from ctypes import wintypes
import gc
import hashlib
import io
import json
import math
import os
import random
import sys
import threading
import time
from collections import OrderedDict
from pathlib import Path

WM_SHOW_PICKER = 0x8000 + 0x51                  # WM_APP + n: "please show yourself"
WINDOW_TITLE = "Harmony-daemon"


def _already_running() -> bool:
    """Single-instance guard. Runs before the heavy imports, so a second launch is near-instant:
    it just asks the running picker to show itself and exits."""
    try:
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        u = ctypes.WinDLL("user32", use_last_error=True)
        k.CreateMutexW(None, False, "Local\\HarmonySingleInstance")
        if ctypes.get_last_error() != 183:      # ERROR_ALREADY_EXISTS
            return False
        if "--background" not in sys.argv:
            u.FindWindowW.restype = ctypes.c_void_p
            u.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
            u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                       ctypes.c_size_t, ctypes.c_ssize_t]
            hwnd = u.FindWindowW(None, WINDOW_TITLE)
            if hwnd:
                u.PostMessageW(hwnd, WM_SHOW_PICKER, 0, 0)
        return True
    except Exception:
        return False


if __name__ == "__main__" and _already_running():
    sys.exit(0)

from PIL import Image, ImageOps
from PySide6.QtCore import (QAbstractNativeEventFilter, QEasingCurve, QEvent, QObject, QPointF, QRect, QRectF,
                            QRunnable, QSize, Qt, QThreadPool, QTimer,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QGuiApplication, QIcon,
                           QImage, QImageReader, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QPolygonF, QRadialGradient, QRegion, QTransform)
from PySide6.QtWidgets import (QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon,
                               QWidget)

# ----------------------------------------------------------------- settings
WALLPAPER_DIR = Path(r"D:\Customizations\Images\Wallpapers")
EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
_BASE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
DATA_DIR = _BASE_DIR / "Harmony"
_OLD_DATA_DIR = _BASE_DIR / "WallpaperPicker"     # pre-rename folder: favourites, colours, settings, cache
if _OLD_DATA_DIR.is_dir() and not DATA_DIR.exists():
    try:
        os.rename(_OLD_DATA_DIR, DATA_DIR)        # one-time migration, keeps everything you set up
    except OSError:
        DATA_DIR = _OLD_DATA_DIR                  # old copy still running / folder locked: keep using the old folder
CACHE_DIR = DATA_DIR / "cache"
META_FILE = DATA_DIR / "colors.json"
STATE_FILE = DATA_DIR / "state.json"
FAV_FILE = DATA_DIR / "favorites.json"
HISTORY_FILE = DATA_DIR / "history.json"         # texts typed before (Up / Down arrows)
SETTINGS_FILE = DATA_DIR / "settings.json"       # small on/off options (;toggle)
THUMB_SIZE = (1280, 720)
SKEW = 0.0           # slant of the slices (0 = straight rectangles: the cards)
CARD_H = 0.48        # centre card height, as a fraction of the screen height
SIDE_W = 0.32        # side slice width  as a fraction of the centre card width
SIDE_H = 0.82        # side slice height as a fraction of the centre card height
VIS = 9              # slices drawn on each side of the centre
Image.MAX_IMAGE_PIXELS = None
CACHE_MAX_OPEN = 24      # upper bound of thumbnails kept in RAM while open (really: on-screen ones + 4)
CACHE_KEEP_HIDDEN = 0    # thumbnails kept once the picker is hidden (0 = drop all; reopening reloads ~15 in ~0.1s)
IDLE_FREE_MS = 3000      # this long after hiding, memory is handed back to Windows
GEN_THREADS = 2          # max parallel thumbnail jobs (each may decode a huge image = lots of RAM)
_BIG_DECODE = threading.Semaphore(1)   # PNG/BMP/WebP can't be decoded at reduced size: only one such full decode at a time
ACTIVE_DIR = WALLPAPER_DIR      # updated in main() if a folder is passed on the command line
HOTKEY_MODS = 0x0001 | 0x0004   # MOD_ALT | MOD_SHIFT  (Ctrl = 0x0002, Win = 0x0008)
HOTKEY_VK = ord("A")            # the hotkey's letter
DELETE_TO_RECYCLE_BIN = True    # ;delete -> Recycle Bin (False = delete for good)
SNAPSHOT_BACKDROP = True        # True: opaque window + frozen desktop snapshot (much lighter for DWM). False: transparent window, desktop stays live
HISTORY_MAX = 100               # Up / Down arrows recall this many previously entered texts
LAYOUT = "orbit"                # "orbit": planet system | "canvas": endless wall of wallpapers, arrow keys to travel
INTRO = True                    # orbit: a ball flies in from below the screen and explodes into the solar system
INTRO_BALL = 0.30               # share of the intro spent on the ball's flight (the rest is the explosion)
INTRO_MS = 750                  # length of the opening animation (was 1700, then 1000)
GO_MS = 200                     # one carousel step (was 320)
TRANSITION_MS = (700, 1000)     # wallpaper-change animation length, random in this range (was 550-850: too few frames)
TRANSITION_EASING = "InOutSine" # gentler than InOutCubic, whose fast middle makes dropped frames obvious. try "Linear" / "OutCubic"
HI_RES_TIMER = True             # ask Windows for 1 ms timer resolution during the transition (even frame pacing)
LOG_FRAME_STATS = True          # log frames / avg / max paint time of every transition to the Harmony log
USE_GL_OVERLAY = False          # EXPERIMENT: paint the transition overlay with QOpenGLWidget (GPU). may misbehave inside Progman
PLANET_HUE = None               # black-hole colour: None = follows the applied wallpaper, or a hue 0-359 (e.g. 25 = orange)
RING_H = 0.16                   # size of the orbiting wallpapers (fraction of the screen height)
FOCUS_H = 0.34                  # height of the focused wallpaper (it opens up into a full 16:9 card)
FOCUS_ASPECT = 16 / 9           # shape of the focused card
CANVAS_COLS = 8                 # canvas: the wall wraps every N wallpapers per row (each row continues the list)
SOUND_VOLUME = 0.5              # default volume, 0.0 - 1.0 (change it live with ;volume 1-100; ;sound turns sound off)

COLORS = [("Red", "#ff4a1c"), ("Orange", "#ffa400"), ("Yellow", "#ffd60a"),
          ("Green", "#2fd04a"), ("Blue", "#1e90ff"), ("Purple", "#8a2be2"),
          ("Pink", "#ff6fb5"), ("Gray", "#b4b4b4")]

HELP = ((";fav", "show favourites only"),
        (";red  ;blue  ;green ...", "filter by colour (also ;gray)"),
        (";color [name]", "recolour the focused wallpaper by hand"),
        (";random", "apply a random wallpaper"),
        (";crop", "pick an area of the wallpaper and apply it"),
        (";rename [name]", "rename the focused wallpaper"),
        (";delete", "delete it (to the Recycle Bin)"),
        (";path [folder]", "change the wallpaper folder"),
        (";wallpapers", "open the wallpaper folder"),
        (";cache", "open the thumbnail cache folder"),
        (";locate", "show this app (.exe or script) in Explorer"),
        (';fetch "link" -n "name"', "download an image link (-n sets the name)"),
        (";sound", "sound effects on / off"),
        (";volume 1-100", "set the sound volume"),
        (";toggle", "show / hide the file name"),
        (";clicks", "show / hide the click count on the icon"),
        (";spin", "icon spins while music plays (on / off)"),
        (";resetc", "reset the icon click count + achievements"),
        (";config", "open the settings file"),
        ("Ctrl+B", "show your achievements"),
        (";help", "show this list"),
        (";quit  or  ;q", "exit the background process"))


# (clicks needed, title, joke) - Ctrl+B shows them
ACHIEVEMENTS = (
    (100, "Curious Clicker", "100 clicks. The icon is starting to enjoy this."),
    (500, "Professional Poker", "500 clicks. The icon has filed a complaint with HR."),
    (1000, "Four-Digit Finger", "1,000 clicks. Your mouse is asking for a raise."),
    (1500, "Carpal Tunnel Speedrun", "1,500 clicks. Your wrist just wrote its resignation letter."),
    (2000, "Touch Grass (Please)", "2,000 clicks. You and the icon are legally roommates now."),
)
SPIN_DPS = 85.0          # icon spin speed in degrees / second while music plays
SPIN_ACCEL = 140.0       # how fast it winds up (deg/s per second)
MUSIC_PEAK = 0.003       # speaker loudness (0-1) that counts as "something is playing"


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]


_AUDIO = {}


def _guid(text):
    import uuid
    u = uuid.UUID(text)
    return _GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))


def _vcall(obj, idx, argtypes, *args):
    """Call method number idx of a raw COM object."""
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vtbl[idx])(obj, *args)


def audio_peak() -> float:
    """How loud whatever the default speakers play is right now (0.0 - 1.0); 0.0 on any problem."""
    held = []
    try:
        if "ole" not in _AUDIO:
            ole = ctypes.WinDLL("ole32")
            ole.CoCreateInstance.argtypes = [ctypes.POINTER(_GUID), ctypes.c_void_p, ctypes.c_uint32,
                                             ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
            ole.CoCreateInstance.restype = ctypes.c_long
            _AUDIO["clsid"] = _guid("BCDE0395-E52F-467C-8E3D-C4579291692E")      # MMDeviceEnumerator
            _AUDIO["iid_enum"] = _guid("A95664D2-9614-4F35-A746-DE8DB63617E6")   # IMMDeviceEnumerator
            _AUDIO["iid_meter"] = _guid("C02216F6-8C67-4B5B-9D00-D008E73E0064")  # IAudioMeterInformation
            _AUDIO["ole"] = ole
        enum, dev, meter = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
        if _AUDIO["ole"].CoCreateInstance(ctypes.byref(_AUDIO["clsid"]), None, 0x17,
                                          ctypes.byref(_AUDIO["iid_enum"]), ctypes.byref(enum)) or not enum.value:
            return 0.0
        held.append(enum)
        P = ctypes.POINTER(ctypes.c_void_p)
        if _vcall(enum, 4, (ctypes.c_int, ctypes.c_int, P), 0, 1, ctypes.byref(dev)) or not dev.value:
            return 0.0                                                          # GetDefaultAudioEndpoint(render, multimedia)
        held.append(dev)
        if _vcall(dev, 3, (ctypes.POINTER(_GUID), ctypes.c_uint32, ctypes.c_void_p, P),
                  ctypes.byref(_AUDIO["iid_meter"]), 0x17, None, ctypes.byref(meter)) or not meter.value:
            return 0.0                                                          # Activate(IAudioMeterInformation)
        held.append(meter)
        peak = ctypes.c_float(0.0)
        if _vcall(meter, 3, (ctypes.POINTER(ctypes.c_float),), ctypes.byref(peak)):
            return 0.0                                                          # GetPeakValue
        return float(peak.value)
    except Exception:
        return 0.0
    finally:
        for ptr in reversed(held):
            try:
                _vcall(ptr, 2, ())                                              # Release
            except Exception:
                pass


# Artwork is built in: "tray" = default tray icon, "menu" = corner image in the picker (data at the bottom).
CREDIT_TEXT = "Designed by LoLCraft2"
_ART_IMGS = {}


def art_full(which: str):
    """The built-in artwork image (decoded once and cached), or None if it can't be decoded."""
    if which not in _ART_IMGS:
        im = None
        try:
            with Image.open(io.BytesIO(base64.b64decode(_ART_B64[which]))) as f:
                im = f.convert("RGBA")
            im.thumbnail((512, 512), Image.LANCZOS)      # never needed bigger; saves several MB
        except Exception as e:
            log(f"built-in artwork '{which}' could not be decoded: {e!r}")
        _ART_IMGS[which] = im
    return _ART_IMGS[which]


def art_pixmap(px: int, which: str = "tray") -> QPixmap:
    """The artwork at exactly px x px, downscaled with Lanczos (sharper than Qt's scaler).
    The 'menu' image is cut to a circle only if it is an opaque square (transparent art is kept whole)."""
    px = max(8, int(px))
    full = art_full(which)
    if full is None:
        if which == "tray":              # no file: plain placeholder dot so the tray icon still shows
            pm = QPixmap(px, px)
            pm.fill(Qt.transparent)
            qp = QPainter(pm)
            qp.setRenderHint(QPainter.Antialiasing)
            qp.setBrush(QColor("#1e90ff"))
            qp.setPen(Qt.NoPen)
            qp.drawEllipse(1, 1, px - 2, px - 2)
            qp.end()
            return pm
        return QPixmap()                 # corner image: simply not drawn
    fw, fh = full.size
    k0 = min(px / fw, px / fh)                       # fit inside px x px, keep proportions (no squashing)
    nw, nh = max(1, round(fw * k0)), max(1, round(fh * k0))
    im = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    im.paste(full.resize((nw, nh), Image.LANCZOS), ((px - nw) // 2, (px - nh) // 2))
    corners = [full.getpixel(c)[3] for c in ((0, 0), (fw - 1, 0), (0, fh - 1), (fw - 1, fh - 1))]
    if which == "menu" and min(corners) > 200:       # opaque square image -> round it; transparent art is left whole
        from PIL import ImageDraw
        k = 4
        mask = Image.new("L", (px * k, px * k), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, px * k - 1, px * k - 1), fill=255)
        im.putalpha(mask.resize((px, px), Image.LANCZOS))
    qi = QImage(im.tobytes("raw", "RGBA"), px, px, px * 4, QImage.Format_RGBA8888).copy()
    return QPixmap.fromImage(qi)


def art_icon() -> QIcon:
    """Multi-size icon so Windows picks a pre-rendered size instead of rescaling one big image."""
    icon = QIcon()
    for px in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256):
        icon.addPixmap(art_pixmap(px, "tray"))
    return icon


def oriented_size(path):
    """(width, height) of an image as it is displayed (EXIF rotation applied)."""
    with Image.open(path) as im:
        w, h = im.size
        try:
            if im.getexif().get(0x0112, 1) in (5, 6, 7, 8):
                w, h = h, w
        except Exception:
            pass
    return w, h


# ------------------------------------------------------------------ helpers
def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, indent=2 if path == SETTINGS_FILE else None)   # settings.json stays human-editable
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)                       # atomic: a crash can never leave half a file behind
    except Exception:
        pass


def save_setting(**kw):
    """Remember one or more settings (merged into settings.json)."""
    cfg = load_json(SETTINGS_FILE, {})
    cfg = cfg if isinstance(cfg, dict) else {}
    cfg.update(kw)
    save_json(SETTINGS_FILE, cfg)


def key_of(p: Path) -> str:
    st = p.stat()
    return hashlib.sha1(f"{p}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()[:20]


def thumb_path(key: str) -> Path:
    return CACHE_DIR / f"{key}_{THUMB_SIZE[0]}.jpg"


def hue_bucket(deg):
    if deg < 15 or deg >= 345:
        return 0
    if deg < 45:
        return 1
    if deg < 70:
        return 2
    if deg < 170:
        return 3
    if deg < 260:
        return 4
    if deg < 310:
        return 5
    return 6


def classify(img: Image.Image) -> str:
    """Dominant colour name of an image (or Gray if it is mostly colourless)."""
    data = img.resize((48, 27)).convert("HSV").tobytes()
    weights = [0.0] * 7
    colored = 0
    total = len(data) // 3
    for i in range(0, len(data), 3):
        h, s, v = data[i], data[i + 1], data[i + 2]
        if s > 60 and v > 45:
            colored += 1
            weights[hue_bucket(h * 360 / 255)] += (s / 255) * (v / 255)
    if total == 0 or colored / total < 0.12:
        return "Gray"
    return COLORS[max(range(7), key=lambda i: weights[i])][0]


def cleanup_junk(keys, meta):
    """Delete leftovers: thumbnails of wallpapers that no longer exist, stale converted BMPs
    (the one Windows is currently using is kept) and colour entries for removed wallpapers."""
    try:
        live = set(keys.values())
        for f in CACHE_DIR.glob("*_*.jpg"):
            if f.stem.rsplit("_", 1)[0] not in live:
                f.unlink()
        in_use = os.path.normcase(os.path.abspath(current_wallpaper() or ""))
        for f in CACHE_DIR.glob("current_wallpaper_*"):
            if os.path.normcase(os.path.abspath(f)) != in_use:
                f.unlink()
        for f in CACHE_DIR.glob("crop_tmp_*"):
            try:
                f.unlink()
            except OSError:
                pass
        stale = [k for k in meta if k not in live]
        for k in stale:
            del meta[k]
        if stale:
            save_json(META_FILE, meta)
    except Exception as e:
        log(f"cleanup_junk failed: {e!r}")


def trim_memory():
    """Give freed memory back to Windows: Python GC + shrink the process working set."""
    try:
        gc.collect()
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.GetCurrentProcess.restype = ctypes.c_void_p
        ps = ctypes.WinDLL("psapi", use_last_error=True)
        ps.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
        ps.EmptyWorkingSet(k.GetCurrentProcess())
    except Exception:
        pass


def log(msg):
    """Append a line to Harmony/error.log in LOCALAPPDATA (pythonw has no console)."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        f = DATA_DIR / "error.log"
        if f.exists() and f.stat().st_size > 100_000:
            f.unlink()
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except Exception:
        pass


def current_wallpaper() -> str:
    """What is on the desktop right now (falls back to the last one we applied)."""
    try:
        buf = ctypes.create_unicode_buffer(520)
        ctypes.windll.user32.SystemParametersInfoW(0x73, 520, buf, 0)
        if buf.value and Path(buf.value).is_file():
            return buf.value
    except Exception:
        pass
    last = load_json(STATE_FILE, {}).get("last")
    return last if last and Path(last).is_file() else ""


def prepare_wallpaper(path: Path) -> Path:
    """The slow part of changing the wallpaper (decode + crop + save a BMP). Runs *before* the
    transition starts, so it can't hog the interpreter while the animation is playing."""
    # Pre-crop to the exact screen size (same centre-crop as the transition overlay), so Windows
    # never has to scale/crop it itself and the wallpaper can't shift when the overlay goes away.
    u32 = ctypes.windll.user32
    sw, sh = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)       # primary screen, physical px
    src = CACHE_DIR / f"current_wallpaper_{time.time_ns()}.bmp"     # BMP: Windows loads it instantly
    with Image.open(path) as im0:
        im0.draft("RGB", (max(sw, sh), max(sw, sh)))   # JPEG: decode at a reduced size that is still >= the screen
        img = ImageOps.exif_transpose(im0).convert("RGB")
    fitted = ImageOps.fit(img, (sw, sh), Image.LANCZOS, centering=(0.5, 0.5))
    del img                                          # drop the (possibly huge) full-size decode before saving
    fitted.save(src)
    del fitted
    return src


def update_dynamic_theme(image_path: Path):
    """Match the shared Control Center/YASB hue to a wallpaper, unless dynamic mode is off."""
    try:
        theme_file = Path(__file__).resolve().with_name("cc_theme.json")
        try:
            state = json.loads(theme_file.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                state = {}
        except (OSError, ValueError):
            state = {}
        if not bool(state.get("dynamic_theme", True)):
            return
        if not image_path.is_file():
            return

        # Pick the strongest saturated hue family rather than averaging every hue in the image;
        # a red/blue wallpaper should not cancel itself into an arbitrary gray-ish result.
        with Image.open(image_path) as original:
            im = ImageOps.exif_transpose(original).convert("RGB")
            im.thumbnail((96, 96))
            pixels = list(im.getdata())
        bins = [0.0] * 36
        colored = []
        for r, g, b in pixels:
            h, sat, val = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if sat < 0.22 or not 0.12 <= val <= 0.98:
                continue
            weight = (sat ** 1.35) * (0.35 + 0.65 * val)
            idx = int(h * 36) % 36
            bins[idx] += weight
            colored.append((h, weight, idx))
        if colored:
            peak = max(range(36), key=lambda i: bins[i])
            # Circular mean within the winning hue bin and its two immediate neighbours.
            selected = [(h, w) for h, w, idx in colored
                        if min((idx - peak) % 36, (peak - idx) % 36) <= 1]
            sx = sum(math.cos(h * 2 * math.pi) * weight for h, weight in selected)
            sy = sum(math.sin(h * 2 * math.pi) * weight for h, weight in selected)
            target_hue = (math.atan2(sy, sx) / (2 * math.pi)) % 1.0 if (sx or sy) else (peak + 0.5) / 36
        else:
            # Mostly neutral wallpapers fall back to the established Control Center blue.
            target_hue = colorsys.rgb_to_hsv(76 / 255.0, 194 / 255.0, 255 / 255.0)[0]

        base_hue = colorsys.rgb_to_hsv(76 / 255.0, 194 / 255.0, 255 / 255.0)[0]
        hue = int(round((target_hue - base_hue) * 360)) % 360
        spec = hue or None
        old_spec = state.get("css_theme", state.get("theme"))

        # Reuse the Control Center's own CSS rewrite implementation so Synapse, YASB and popups
        # share one palette. Import it by its conventional name, or accept a renamed .pyw file.
        css_updated = False
        cc_module = None
        try:
            import importlib.machinery
            import importlib.util
            cc_path = Path(__file__).resolve().with_name("control_center.pyw")
            if not cc_path.is_file():
                matches = sorted(p for p in cc_path.parent.glob("control_center*.pyw") if p.is_file())
                if matches:
                    cc_path = matches[0]
            if cc_path.is_file():
                loader = importlib.machinery.SourceFileLoader("harmony_cc_theme", str(cc_path))
                module = importlib.util.module_from_spec(
                    importlib.util.spec_from_loader("harmony_cc_theme", loader))
                loader.exec_module(module)
                cc_module = module
                css_updated = bool(module.rewrite_css(old_spec, spec))
            else:
                log("dynamic theme: Control Center script not found; saved hue only")
        except Exception as exc:
            log(f"dynamic theme: YASB CSS update failed: {exc!r}")

        updates = {"hue": hue, "theme": spec,
                   "dynamic_theme_last_wallpaper": str(image_path)}
        if css_updated:
            updates["css_theme"] = spec
        # Let Control Center merge into the latest state on disk, preserving slider settings
        # and any unrelated fields written by Synapse while the wallpaper was being applied.
        if cc_module is not None and hasattr(cc_module, "save_theme_state"):
            cc_module.save_theme_state(**updates)
        else:
            try:
                latest = json.loads(theme_file.read_text(encoding="utf-8"))
                if not isinstance(latest, dict):
                    latest = {}
            except (OSError, ValueError):
                latest = {}
            latest.update(updates)
            theme_file.write_text(json.dumps(latest, indent=2), encoding="utf-8")
    except Exception as exc:
        try:
            log(f"dynamic theme update failed: {exc!r}")
        except Exception:
            pass


def hint_vapor(path: Path):
    """Tell Vapor (the bar) which wallpaper is coming, the moment a change starts, so the bar's
    glass theme recolours along with the transition instead of waiting for Windows to finish
    applying it. The hint goes to Vapor's own data folder under %LOCALAPPDATA%, so Harmony and
    Vapor never have to be installed in the same directory."""
    d = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "vapor"
    try:
        d.mkdir(parents=True, exist_ok=True)
        (d / "wallpaper_next.txt").write_text(str(path), encoding="utf-8")
    except Exception as e:
        log(f"vapor hint failed: {e!r}")


def set_wallpaper(path: Path):
    bmp = prepare_wallpaper(path)
    hint_vapor(bmp)      # hint the exact file Windows will show (the cropped BMP), not the original, so the bar colours from the same pixels as after a restart
    apply_wallpaper_file(bmp)
    update_dynamic_theme(path)


def apply_wallpaper_file(src: Path):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "WallpaperStyle", 0, winreg.REG_SZ, "10")  # fill
        winreg.SetValueEx(k, "TileWallpaper", 0, winreg.REG_SZ, "0")
    ctypes.windll.user32.SystemParametersInfoW(20, 0, os.path.abspath(src), 3)
    for old in CACHE_DIR.glob("current_wallpaper_*"):   # tidy up previous conversions
        if old != src:
            try:
                old.unlink()
            except OSError:
                pass


# ------------------------------------------------ native desktop-layer helpers
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE, WS_EX_TOPMOST = 0x08000000, 0x00000008
SWP_NOZORDER, SWP_NOACTIVATE, SWP_NOSIZE, SWP_NOMOVE = 0x0004, 0x0010, 0x0001, 0x0002
GW_HWNDPREV = 3
GWL_STYLE = -16
WS_POPUP, WS_CHILD, WS_CLIPSIBLINGS = 0x80000000, 0x40000000, 0x04000000
_native = None


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
                ("szDevice", wintypes.WCHAR * 32)]


def native():
    """user32 with explicit argtypes (ctypes' default int conversion overflows on window styles)."""
    global _native
    if _native is None:
        from types import SimpleNamespace
        u = ctypes.WinDLL("user32", use_last_error=True)
        H, I, UI = ctypes.c_void_p, ctypes.c_int, ctypes.c_uint
        u.FindWindowW.restype = H
        u.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        u.FindWindowExW.restype = H
        u.FindWindowExW.argtypes = [H, H, ctypes.c_wchar_p, ctypes.c_wchar_p]
        u.SendMessageTimeoutW.argtypes = [H, UI, ctypes.c_size_t, ctypes.c_ssize_t, UI, UI, H]
        u.GetParent.restype, u.GetParent.argtypes = H, [H]
        u.SetParent.restype, u.SetParent.argtypes = H, [H, H]
        u.GetAncestor.restype, u.GetAncestor.argtypes = H, [H, UI]
        u.GetDesktopWindow.restype = H
        u.GetWindow.restype, u.GetWindow.argtypes = H, [H, UI]
        u.SetWindowPos.argtypes = [H, H, I, I, I, I, UI]
        u.ClientToScreen.argtypes = [H, ctypes.POINTER(wintypes.POINT)]
        u.ScreenToClient.argtypes = [H, ctypes.POINTER(wintypes.POINT)]
        u.GetMonitorInfoW.argtypes = [H, H]
        wnd_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, H, ctypes.c_ssize_t)
        mon_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, H, H, H, ctypes.c_ssize_t)
        u.EnumWindows.argtypes = [wnd_proc, ctypes.c_ssize_t]
        u.EnumDisplayMonitors.argtypes = [H, H, mon_proc, ctypes.c_ssize_t]
        get = getattr(u, "GetWindowLongPtrW", None) or u.GetWindowLongW
        put = getattr(u, "SetWindowLongPtrW", None) or u.SetWindowLongW
        get.restype, get.argtypes = ctypes.c_ssize_t, [H, I]
        put.restype, put.argtypes = ctypes.c_ssize_t, [H, I, ctypes.c_ssize_t]
        _native = SimpleNamespace(u=u, get=get, put=put, wnd_proc=wnd_proc, mon_proc=mon_proc)
    return _native


def find_workerw():
    """Window that sits behind desktop icons and every app (None if unavailable)."""
    try:
        n = native()
        u = n.u
        progman = u.FindWindowW("Progman", None)
        if not progman:
            return None
        u.SendMessageTimeoutW(progman, 0x052C, 0xD, 0x1, 0, 1000, None)
        w = u.FindWindowExW(progman, None, "WorkerW", None)   # Windows 11 24H2+
        if w and not u.FindWindowExW(w, None, "SHELLDLL_DefView", None):
            return w
        found = []

        @n.wnd_proc
        def cb(hwnd, _):
            if u.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
                nxt = u.FindWindowExW(None, hwnd, "WorkerW", None)
                if nxt:
                    found.append(nxt)
            return True

        u.EnumWindows(cb, 0)
        return found[0] if found else None
    except Exception as e:
        log(f"find_workerw failed: {e!r}")
        return None


def screen_native_rects(screens):
    """(x, y, w, h) in *physical* pixels for each Qt screen, matched by device name."""
    mons = {}
    try:
        n = native()

        @n.mon_proc
        def cb(hmon, _hdc, _rc, _lp):
            mi = MONITORINFOEXW()
            mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
            if n.u.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcMonitor
                mons[mi.szDevice] = (r.left, r.top, r.right - r.left, r.bottom - r.top)
            return True

        n.u.EnumDisplayMonitors(None, None, cb, 0)
    except Exception as e:
        log(f"monitor enumeration failed: {e!r}")
    out = []
    for s in screens:
        r = mons.get(s.name())
        if r is None:                               # fallback: derive from Qt's logical geometry
            g, d = s.geometry(), s.devicePixelRatio()
            r = (round(g.x() * d), round(g.y() * d), round(g.width() * d), round(g.height() * d))
        out.append(r)
    return out


def desktop_anchor():
    """Desktop window the overlay is stacked directly above (keeps it below every app window)."""
    try:
        u = native().u
        w = find_workerw()
        if w:
            parent = u.GetAncestor(w, 1)                 # GA_PARENT
            return w if parent == u.GetDesktopWindow() else parent
        return u.FindWindowW("Progman", None) or None
    except Exception as e:
        log(f"desktop_anchor failed: {e!r}")
        return None


def native_prepare(hwnd, anchor, x, y, w, h):
    """While still hidden: never take focus, and sit just above the desktop in z-order."""
    n = native()
    ex = n.get(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
    n.put(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE)
    return native_stack(hwnd, anchor, x, y, w, h)


def native_stack(hwnd, anchor, x, y, w, h):
    """Position the window (physical px) directly above `anchor` and below all apps.

    Only the overlay's *own* window is ever moved. The desktop window belongs to Explorer, and
    SetWindowPos() on another process's window waits for that process to answer - while Explorer
    is busy applying the new wallpaper that froze the animation at ~40% until it had finished.
    GetWindow() only reads the z-order, so it never blocks.

    The overlay is dropped right below whatever sits directly above the desktop, which puts it
    directly on top of the desktop and under every app. If nothing but topmost windows are above
    the desktop (everything minimised), HWND_TOP puts it on top of the normal windows instead.
    """
    n = native()
    u = n.u
    ok = u.SetWindowPos(hwnd, 0, int(x), int(y), int(w), int(h), SWP_NOZORDER | SWP_NOACTIVATE)
    if not anchor:
        return bool(ok)
    prev = u.GetWindow(anchor, GW_HWNDPREV)                    # window directly above the desktop
    if prev == hwnd:
        return bool(ok)                                        # already in the right place
    if prev and not (n.get(prev, GWL_EXSTYLE) & WS_EX_TOPMOST):
        after = prev
    else:
        after = 0                                              # HWND_TOP: top of the normal windows
    u.SetWindowPos(hwnd, after, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    return bool(ok)


def desktop_icon_host(anchor):
    """Windows 11 24H2+: the desktop icons (SHELLDLL_DefView) live *inside* the Progman window.
    A top-level overlay stacked above Progman therefore covers them. Returns the DefView handle in
    that case, None on older layouts (there the icons sit in their own window above the overlay)."""
    try:
        if not anchor:
            return None
        return native().u.FindWindowExW(anchor, None, "SHELLDLL_DefView", None) or None
    except Exception as e:
        log(f"desktop_icon_host failed: {e!r}")
        return None


def native_stack_child(hwnd, parent, defview, x, y, w, h):
    """Position a child of Progman (x, y = physical screen px) directly *behind* the desktop icons."""
    u = native().u
    pt = wintypes.POINT(int(x), int(y))
    u.ScreenToClient(parent, ctypes.byref(pt))
    return bool(u.SetWindowPos(hwnd, defview, pt.x, pt.y, int(w), int(h), SWP_NOACTIVATE))


def native_adopt(hwnd, parent, defview, x, y, w, h):
    """Make our overlay a child of Progman, sitting between the wallpaper and the icons."""
    n = native()
    style = n.get(hwnd, GWL_STYLE) & 0xFFFFFFFF
    n.put(hwnd, GWL_STYLE, (style & ~WS_POPUP) | WS_CHILD | WS_CLIPSIBLINGS)   # before SetParent (per docs)
    if not n.u.SetParent(hwnd, parent):
        n.put(hwnd, GWL_STYLE, style)
        log(f"SetParent into desktop failed: {ctypes.get_last_error()}")
        return False
    return native_stack_child(hwnd, parent, defview, x, y, w, h)


def cover_pixmap_px(path, pw, ph) -> QPixmap:
    """Image scaled to cover (pw x ph) *physical* pixels, centre-cropped."""
    pw, ph = max(1, int(pw)), max(1, int(ph))
    img = QImage()
    if path and Path(path).is_file():
        rd = QImageReader(str(path))
        rd.setAutoTransform(True)
        sz = rd.size()
        if sz.isValid():
            sc = max(pw / sz.width(), ph / sz.height())
            if sc < 1:
                rd.setScaledSize(QSize(max(1, round(sz.width() * sc)),
                                       max(1, round(sz.height() * sc))))
        img = rd.read()
    if img.isNull():
        pm = QPixmap(pw, ph)
        pm.fill(Qt.black)
        return pm
    img = img.scaled(pw, ph, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x, y = (img.width() - pw) // 2, (img.height() - ph) // 2
    return QPixmap.fromImage(img.copy(x, y, pw, ph))


# ------------------------------------------------- background thumbnail jobs
class Signals(QObject):
    done = Signal(str, str)
    scanned = Signal(object, object, object)       # files, keys, folder that was scanned
    fetched = Signal(bool, str, str)               # ;fetch finished: ok, message, saved file path


class Job(QRunnable):
    def __init__(self, path, key, need_color, signals):
        super().__init__()
        self.path, self.key, self.need_color, self.signals = path, key, need_color, signals

    def run(self):
        color = ""
        try:
            thumb = thumb_path(self.key)
            if thumb.exists():
                img = Image.open(thumb)
                img.draft("RGB", (160, 90))              # JPEG decodes at 1/8 size: colour needs only 48x27
                img = img.convert("RGB")
            else:
                src = Image.open(self.path)
                is_jpeg = src.format == "JPEG"
                src.draft("RGB", (THUMB_SIZE[0] * 2, THUMB_SIZE[1] * 2))    # JPEG: decodes at 1/2, 1/4 or 1/8 size
                if not is_jpeg:
                    _BIG_DECODE.acquire()            # full-size decode: never run several at once
                try:
                    img = ImageOps.exif_transpose(src).convert("RGB")
                    src.close()
                    del src
                    img.thumbnail(THUMB_SIZE, Image.LANCZOS)    # full-size copy is released right here
                finally:
                    if not is_jpeg:
                        _BIG_DECODE.release()
                img.save(thumb, "JPEG", quality=88)
            if self.need_color:
                color = classify(img)
            del img
        except Exception:
            pass
        self.signals.done.emit(str(self.path), color)


class Scanner(QRunnable):
    """Re-scans the wallpaper folder in the background each time the picker is shown."""

    def __init__(self, folder, signals):
        super().__init__()
        self.folder, self.signals = folder, signals

    def run(self):
        try:
            files, keys = scan_files(self.folder)
        except Exception:
            files = keys = None
        self.signals.scanned.emit(files, keys, self.folder)


def app_path() -> Path:
    """The file you actually launched - the .exe when the app is compiled (whatever you renamed it to),
    otherwise this script. __file__ can't be used for a compiled app: with PyInstaller --onefile it points
    into a temporary folder that is deleted again when the app exits."""
    try:
        compiled = "__compiled__" in globals()                 # Nuitka sets this
        if getattr(sys, "frozen", False) or compiled:
            # Nuitka --onefile: sys.executable is the unpacked copy, argv[0] is the real exe.
            # PyInstaller / cx_Freeze: sys.executable is the real exe.
            for c in ((sys.argv[0], sys.executable) if compiled else (sys.executable, sys.argv[0])):
                if c and Path(c).suffix.lower() == ".exe" and Path(c).is_file():
                    return Path(c).resolve()
            return Path(sys.executable).resolve()
    except Exception as e:
        log(f"app_path failed: {e!r}")
    return Path(__file__).resolve()


SCRIPT_PATH = app_path()


def reveal_in_explorer(path):
    """Open Explorer with `path` selected (or just its folder if the file isn't there any more)."""
    try:
        import subprocess
        path = Path(path)
        if path.exists():
            subprocess.Popen(["explorer", "/select,", os.path.normpath(str(path))])
        else:
            os.startfile(str(path.parent))
    except Exception as e:
        log(f"reveal failed: {e!r}")


def open_folder(path):
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))
    except Exception as e:
        log(f"open folder failed: {e!r}")


def scan_files(folder):
    """(sorted image files, {file: cache key}) for a wallpaper folder - empty if it has none."""
    folder = Path(folder)
    files = sorted((p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in EXTS),
                   key=lambda p: p.name.lower()) if folder.is_dir() else []
    return files, {p: key_of(p) for p in files}


# ------------------------------------------------------------------ ;fetch (download an image link)
FETCH_MAX_BYTES = 200 * 1024 * 1024         # refuse anything bigger than this
FETCH_TIMEOUT = 25                          # seconds without an answer from the server
FETCH_EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "BMP": ".bmp"}     # saved as-is, no re-encoding
IMG_EXTS_SEEN = EXTS | {".gif", ".tif", ".tiff", ".jfif", ".jpe", ".avif"}      # extensions we strip from names
BAD_NAME_CHARS = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def valid_stem(stem: str) -> bool:
    return bool(stem) and not any(ch in BAD_NAME_CHARS for ch in stem) and stem.split(".")[0].upper() not in RESERVED_NAMES


def parse_fetch_args(text: str):
    """';fetch "link" -n "name"'  ->  (url, name, error).  The name is optional ('' = take it from the link).
    Quotes are optional, and an unquoted name may contain spaces (-n my sunset wall)."""
    import re
    text = text.translate({0x201C: '"', 0x201D: '"', 0x2018: "'", 0x2019: "'"})      # pasted curly quotes
    toks = [a or b or c for a, b, c in re.findall(r'"([^"]*)"|\'([^\']*)\'|(\S+)', text)]
    toks = [t for t in toks if t]
    is_url = lambda t: re.match(r"https?://", t, re.I) is not None
    url, name, extra, i = "", "", [], 0
    while i < len(toks):
        t = toks[i]
        if t.lower() in ("-n", "--name"):
            i += 1
            words = []
            while i < len(toks) and not toks[i].startswith("-") and not is_url(toks[i]):
                words.append(toks[i])
                i += 1
            name = " ".join(words)
            if not name:
                return "", "", 'Give the name after -n:  ;fetch "link" -n "name"'
            continue
        if not url and not t.startswith("-"):
            url = t
        else:
            extra.append(t)
        i += 1
    if not url:
        return "", "", 'Usage:  ;fetch "link" [-n "name"]'
    if extra:
        return "", "", 'Use -n for the name:  ;fetch "link" -n "name"'
    if url.lower().startswith("www."):
        url = "https://" + url
    return url, name, ""


def fetch_worker(url, name, folder, signals):
    """Runs in its own thread: download `url`, check that it really is an image and save it into `folder`.
    Reports back through signals.fetched (and signals.scanned, so the new file shows up in the picker)."""
    import urllib.error
    import urllib.parse
    import urllib.request
    folder = Path(folder)
    tmp = None

    def fail(msg):
        signals.fetched.emit(False, msg, "")

    try:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
            return fail("That isn't a web link - it must start with http:// or https://")
        safe = urllib.parse.urlunsplit((
            parts.scheme, parts.netloc,
            urllib.parse.quote(parts.path, safe="/%:@!$&'()*+,;=~-._"),       # spaces / unicode in the link
            urllib.parse.quote(parts.query, safe="=&%+:/?@!$'()*,;~-._"), ""))
        req = urllib.request.Request(safe, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Harmony/1.0",   # many hosts block Python's default
            "Accept": "image/*,*/*;q=0.8"})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            length = resp.headers.get("Content-Length", "")
            if length.isdigit() and int(length) > FETCH_MAX_BYTES:
                return fail("That file is too big (over 200 MB).")
            data = resp.read(FETCH_MAX_BYTES + 1)
        if len(data) > FETCH_MAX_BYTES:
            return fail("That file is too big (over 200 MB).")
        try:
            im = Image.open(io.BytesIO(data))
            fmt = im.format
        except Exception:
            return fail("That link isn't a direct image - open the picture on its own and copy that address.")

        explicit = bool(name)
        if explicit:
            stem = name.strip()
            if os.path.splitext(stem)[1].lower() in IMG_EXTS_SEEN:
                stem = os.path.splitext(stem)[0]                    # "-n sunset.jpg" -> "sunset" (extension comes from the image)
            stem = stem.rstrip(". ")
            if not valid_stem(stem):
                return fail("That isn't a valid file name.")
        else:
            base = urllib.parse.unquote(parts.path.rsplit("/", 1)[-1])
            root, ext = os.path.splitext(base)
            stem = root if ext.lower() in IMG_EXTS_SEEN else base
            stem = "".join("_" if ch in BAD_NAME_CHARS else ch for ch in stem).strip().rstrip(". ")[:120]
            if not valid_stem(stem):
                stem = "wallpaper"

        ext = FETCH_EXT.get(fmt, ".png")                            # gif / tiff / ... are converted to png
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / (stem + ext)
        if explicit and dest.exists():
            return fail(f"{dest.name} already exists.")
        n = 1
        while dest.exists():                                        # name taken (link-derived names): add a number
            dest = folder / f"{stem} ({n}){ext}"
            n += 1

        tmp = dest.with_name(dest.name + ".part")                   # not an image extension, so the scanner ignores it
        if fmt in FETCH_EXT:
            tmp.write_bytes(data)
        else:
            if im.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                im = im.convert("RGB")
            im.save(tmp, "PNG")
        os.replace(tmp, dest)
        tmp = None
        files, keys = scan_files(folder)
        signals.scanned.emit(files, keys, folder)                   # make the picker pick the new file up ...
        signals.fetched.emit(True, f"Saved {dest.name}", str(dest))     # ... then jump to it
    except urllib.error.HTTPError as e:
        fail(f"Download failed: the server said {e.code} {e.reason}")
    except urllib.error.URLError as e:
        fail(f"Couldn't reach that address ({e.reason})")
    except TimeoutError:
        fail("The download timed out.")
    except OSError as e:
        fail(f"Couldn't save the file: {e}")
    except Exception as e:
        log(f"fetch failed: {e!r}")
        fail(f"Download failed: {e}")
    finally:
        if tmp is not None:
            try:
                tmp.unlink()
            except OSError:
                pass


class SHFILEOPSTRUCTW(ctypes.Structure):
    _pack_ = 1 if ctypes.sizeof(ctypes.c_void_p) == 4 else 8
    _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint),
                ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p)]


def move_to_trash(path) -> str:
    """Send a file to the Recycle Bin (or delete it for good if DELETE_TO_RECYCLE_BIN is False).
    Returns '' on success, otherwise a short error text."""
    path = os.path.abspath(str(path))
    try:
        if not DELETE_TO_RECYCLE_BIN:
            os.remove(path)
            return ""
        op = SHFILEOPSTRUCTW()
        op.wFunc = 3                                   # FO_DELETE
        op.pFrom = path + "\0"                         # the list must end with a double NUL
        op.fFlags = 0x0040 | 0x0010 | 0x0004 | 0x0400  # ALLOWUNDO | NOCONFIRMATION | SILENT | NOERRORUI
        sh = ctypes.WinDLL("shell32", use_last_error=True)
        sh.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
        sh.SHFileOperationW.restype = ctypes.c_int
        rc = sh.SHFileOperationW(ctypes.byref(op))
        if rc != 0 or op.fAnyOperationsAborted or os.path.exists(path):
            return f"Windows couldn't move it to the Recycle Bin (code {rc})"
        return ""
    except Exception as e:
        return str(e)


# ------------------------------------------------------------ sound effects
# Soft "tick" sounds plus a cute one for the corner icon. The clips are built into this file
# (_SND_B64 at the bottom). They are played through one audio stream that is opened once and kept
# open (Windows waveOut), so a sound starts within a few ms - PlaySound re-opened the audio device on
# every call, which is what made fast hovering / clicking lag behind. The UI thread only drops the
# sound's name into a slot; a helper thread cuts the old sound and starts the newest one, so a burst of
# requests collapses to the last one and nothing queues up.
_SYNTH = ("rise", "boom", "close")     # clips generated in code (no embedded data)
_SOUND_GAP = {"hover": 0.12, "tick": 0.03, "bounce": 0.05}    # min seconds between two plays of one sound
_SND_BASE_VOLUME = 0.5               # loudness the clips were rendered at
SOUND_ON = True
_SND_LAST = {}
_LAST_UI_SOUND = [0.0]        # when we last played our own sound (so it is never mistaken for music)
_SND_LOCK, _SND_EVT = threading.Lock(), threading.Event()
_SND_REQ = [None]                    # newest requested sound name
_SND_THREAD = []
_VOL_GEN = [0]                        # bumped whenever the volume changes
_WINMM = []


class WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD),
                ("nSamplesPerSec", wintypes.DWORD), ("nAvgBytesPerSec", wintypes.DWORD),
                ("nBlockAlign", wintypes.WORD), ("wBitsPerSample", wintypes.WORD),
                ("cbSize", wintypes.WORD)]


class WAVEHDR(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD),
                ("dwBytesRecorded", wintypes.DWORD), ("dwUser", ctypes.c_size_t),
                ("dwFlags", wintypes.DWORD), ("dwLoops", wintypes.DWORD),
                ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]


def set_sound_enabled(on):
    global SOUND_ON
    SOUND_ON = bool(on)


def set_volume(pct):
    """Volume in percent (1-100). The audio stream is rebuilt at the new level on the next sound."""
    global SOUND_VOLUME
    SOUND_VOLUME = max(1, min(100, int(pct))) / 100
    _VOL_GEN[0] += 1


def _winmm():
    if not _WINMM:
        m = ctypes.WinDLL("winmm")
        V, U = ctypes.c_void_p, ctypes.c_uint
        m.waveOutOpen.argtypes = [ctypes.POINTER(V), U, ctypes.POINTER(WAVEFORMATEX),
                                  ctypes.c_size_t, ctypes.c_size_t, U]
        for fn in ("waveOutPrepareHeader", "waveOutUnprepareHeader", "waveOutWrite"):
            getattr(m, fn).argtypes = [V, ctypes.POINTER(WAVEHDR), U]
        m.waveOutReset.argtypes = [V]
        m.waveOutClose.argtypes = [V]
        _WINMM.append(m)
    return _WINMM[0]


def _synth_pcm(name) -> bytes:
    """Generated clips: 'rise' = energy gathering while the ball flies in, 'boom' = the explosion,
    'close' = a short falling blip when the picker is dismissed. Scaled to SOUND_VOLUME."""
    from array import array
    sr, tau, rnd = 22050, 2 * math.pi, random.Random(11)
    out, ph, ph2, lp = [], 0.0, 0.0, 0.0
    if name == "rise":
        n = int(sr * max(0.15, INTRO_BALL * INTRO_MS / 1000.0))
        for i in range(n):
            u = i / n
            ph += tau * (70 + 900 * u ** 2.4) / sr
            ph2 += tau * (140 + 1800 * u ** 2.4) / sr
            lp += 0.35 * (rnd.uniform(-1, 1) - lp)
            env = u ** 1.6 * (1.0 if u < 0.96 else (1.0 - u) / 0.04)
            out.append(env * (0.7 * math.sin(ph) + 0.25 * math.sin(ph2) + 0.5 * lp * u))
        level = 0.55
    elif name == "boom":
        n = int(sr * 0.95)
        for i in range(n):
            u = i / n
            ph += tau * (34 + 120 * math.exp(-u * 10)) / sr
            lp += 0.10 * (rnd.uniform(-1, 1) - lp)
            env = math.exp(-u * 4.0) * min(1.0, i / 40.0)
            out.append(env * (math.sin(ph) + 2.2 * lp * math.exp(-u * 7)))
        level = 0.85
    else:
        n = int(sr * 0.16)
        for i in range(n):
            u = i / n
            ph += tau * (620 - 420 * u) / sr
            out.append((1 - u) ** 2 * min(1.0, i / 30.0) * math.sin(ph))
        level = 0.5
    peak = max(1e-6, max(abs(v) for v in out))
    g = level * SOUND_VOLUME * 32767 / peak
    return array("h", (max(-32768, min(32767, int(v * g))) for v in out)).tobytes()


def _sound_pcm(name) -> bytes:
    """Raw 16-bit samples of a clip, scaled to SOUND_VOLUME."""
    if name in _SYNTH:
        return _synth_pcm(name)
    import wave
    from array import array
    with wave.open(io.BytesIO(base64.b64decode(_SND_B64[name]))) as w:
        frames = w.readframes(w.getnframes())
    f = SOUND_VOLUME / _SND_BASE_VOLUME
    if abs(f - 1.0) > 0.01:
        pcm = array("h")
        pcm.frombytes(frames)
        frames = array("h", (max(-32768, min(32767, int(v * f))) for v in pcm)).tobytes()
    return frames


class _Stream:
    """One open audio output (22 kHz mono 16-bit) with every clip pre-loaded and ready to fire."""

    def __init__(self):
        self.m, self.h, self.clips = _winmm(), ctypes.c_void_p(), {}
        self.gen = _VOL_GEN[0]                         # which volume these clips were rendered at
        fmt = WAVEFORMATEX(1, 1, 22050, 44100, 2, 16, 0)
        rc = self.m.waveOutOpen(ctypes.byref(self.h), 0xFFFFFFFF, ctypes.byref(fmt), 0, 0, 0)  # default device
        if rc:
            raise OSError(f"waveOutOpen failed ({rc})")
        for name in (*_SND_B64, *_SYNTH):
            pcm = _sound_pcm(name)
            buf = ctypes.create_string_buffer(pcm, len(pcm))
            hdr = WAVEHDR()
            hdr.lpData, hdr.dwBufferLength = ctypes.addressof(buf), len(pcm)
            if self.m.waveOutPrepareHeader(self.h, ctypes.byref(hdr), ctypes.sizeof(hdr)):
                raise OSError("waveOutPrepareHeader failed")
            self.clips[name] = (buf, hdr)

    def play(self, name):
        _, hdr = self.clips[name]
        self.m.waveOutReset(self.h)                    # cut whatever is playing right now ...
        return self.m.waveOutWrite(self.h, ctypes.byref(hdr), ctypes.sizeof(hdr))   # ... and start the new one

    def close(self):
        try:
            self.m.waveOutReset(self.h)
            for _, hdr in self.clips.values():
                self.m.waveOutUnprepareHeader(self.h, ctypes.byref(hdr), ctypes.sizeof(hdr))
            self.m.waveOutClose(self.h)
        except Exception:
            pass


def _sound_worker():
    global SOUND_ON
    stream = None
    try:
        stream = _Stream()                             # opened right away, so the first sound isn't slow
        while True:
            _SND_EVT.wait()
            with _SND_LOCK:
                name = _SND_REQ[0]
                _SND_EVT.clear()
            if name is None:
                continue
            if stream.gen != _VOL_GEN[0]:              # volume changed: re-render the clips
                stream.close()
                stream = _Stream()
            if stream.play(name) != 0:                 # device went away (headphones unplugged...): reopen once
                stream.close()
                stream = _Stream()
                stream.play(name)
    except Exception as e:
        log(f"sound effects disabled: {e!r}")          # e.g. no audio device: stop trying
        SOUND_ON = False


def start_sound_engine():
    if not _SND_THREAD or not _SND_THREAD[0].is_alive():
        _SND_THREAD[:] = [threading.Thread(target=_sound_worker, daemon=True)]
        _SND_THREAD[0].start()


def play_sound(name):
    """Fire-and-forget UI sound: never blocks, and the newest sound cuts off the one still playing."""
    if not SOUND_ON:
        return
    now = time.perf_counter()
    if now - _SND_LAST.get(name, 0.0) < _SOUND_GAP.get(name, 0.08):
        return
    _SND_LAST[name] = now
    _LAST_UI_SOUND[0] = time.monotonic()
    start_sound_engine()
    with _SND_LOCK:
        _SND_REQ[0] = name
        _SND_EVT.set()


# ------------------------------------------------------------ global hotkey
WM_HOTKEY, HOTKEY_ID = 0x0312, 0xA11A


class HotkeyFilter(QAbstractNativeEventFilter):
    """Catches the global hotkey (WM_HOTKEY) and the 'show' ping sent by a second launch."""

    def __init__(self, on_hotkey, on_show):
        super().__init__()
        self.on_hotkey, self.on_show = on_hotkey, on_show

    def nativeEventFilter(self, event_type, message):
        try:
            if bytes(event_type) == b"windows_generic_MSG":
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    QTimer.singleShot(0, self.on_hotkey)
                    return True, 0
                if msg.message == WM_SHOW_PICKER:
                    QTimer.singleShot(0, self.on_show)
                    return True, 0
        except Exception:
            pass
        return False, 0


def register_hotkey():
    ok = ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, HOTKEY_MODS | 0x4000, HOTKEY_VK)
    if not ok:      # 0x4000 = MOD_NOREPEAT
        log(f"RegisterHotKey failed (error {ctypes.windll.kernel32.GetLastError()}) - "
            "is another program (AutoHotkey, whkd...) already using this hotkey?")
    return bool(ok)


# --------------------------------------------------------- transition effects
EFFECTS = ["fade", "wipe", "diag", "circle", "slide", "zoom", "blinds",
           "dissolve", "curtain", "glitch", "ripple"]
D_COLS, D_ROWS = 32, 18


def make_params(name):
    prm = {
        "name": name,
        "dir": random.choice("lrud"),
        "flip": random.random() < 0.5,
        "cx": random.uniform(0.2, 0.8),
        "cy": random.uniform(0.2, 0.8),
        "thr": [random.random() for _ in range(D_COLS * D_ROWS)],
    }
    if name == "burn":
        prm["bm"] = make_burn_map(192, 108)
    elif name == "glitch":
        prm["gl_n"] = 26
        prm["gl_off"] = [random.uniform(-0.12, 0.12) for _ in range(26)]
        prm["gl_thr"] = [random.random() * 0.8 for _ in range(26)]
    return prm


# ---- fire: a burn-time map (low = burns first) drives a soft mask + an ember/char overlay ----
BURN_E, BURN_C, BURN_RAMP = 8, 14, 3          # ember width, char width, edge softness (in map levels)


def make_burn_map(w, h):
    """(bytes, w, h): smooth blobs (organic edge) + distance from a random ignition point (spreads out)."""
    def octave(gw, gh):
        g = [[random.random() for _ in range(gw + 2)] for _ in range(gh + 2)]
        xs = []
        for x in range(w):
            fx = x / w * gw
            ix = int(fx)
            tx = fx - ix
            xs.append((ix, tx * tx * (3 - 2 * tx)))
        out = []
        for y in range(h):
            fy = y / h * gh
            iy = int(fy)
            ty = fy - iy
            ty = ty * ty * (3 - 2 * ty)
            r0, r1 = g[iy], g[iy + 1]
            for ix, tx in xs:
                a = r0[ix] + (r0[ix + 1] - r0[ix]) * tx
                b = r1[ix] + (r1[ix + 1] - r1[ix]) * tx
                out.append(a + (b - a) * ty)
        return out

    o1, o2, o3 = octave(5, 3), octave(14, 8), octave(36, 20)
    cx, cy = random.uniform(0.25, 0.75), random.uniform(0.3, 0.7)
    asp = w / h
    dmax = max(math.hypot(ax * asp, ay) for ax in (cx, 1 - cx) for ay in (cy, 1 - cy))
    vals = []
    for y in range(h):
        dy = y / h - cy
        for x in range(w):
            k = y * w + x
            dist = math.hypot((x / w - cx) * asp, dy) / dmax
            vals.append(0.5 * dist + 0.5 * (0.6 * o1[k] + 0.28 * o2[k] + 0.12 * o3[k]))
    lo, hi = min(vals), max(vals)
    sc = 255.0 / max(1e-9, hi - lo)
    return bytes(min(255, max(0, int((v - lo) * sc))) for v in vals), w, h


def burn_u(p):
    """Burn front (in map levels) for progress p: nothing burnt at 0, everything gone at 1."""
    span = BURN_E + BURN_C + 3
    return -span + p * (256 + span)


def _lerp(a, b, m):
    return tuple(int(a[i] + (b[i] - a[i]) * m) for i in range(3))


def burn_tables(u):
    """Lookup tables (256 each): card alpha, and the overlay's R, G, B, A, for burn front u."""
    A, R, G, B, O = (bytearray(256) for _ in range(5))
    E, C, ramp = BURN_E, BURN_C, BURN_RAMP
    for n in range(256):
        d = n - u
        if d <= 0:
            continue                                   # gone
        A[n] = 255 if d >= ramp else int(255 * d / ramp)
        soft = min(1.0, d / ramp)
        if d < E:                                      # glowing ember: white-yellow -> orange -> deep red
            k = d / E
            col = _lerp((255, 246, 190), (255, 150, 25), k / 0.5) if k < 0.5 else _lerp((255, 150, 25), (120, 20, 6), (k - 0.5) / 0.5)
            R[n], G[n], B[n], O[n] = col[0], col[1], col[2], int(255 * soft)
        elif d < E + C:                                # scorched edge
            k = (d - E) / C
            R[n], G[n], B[n], O[n] = 28, 14, 8, int(235 * (1 - k) ** 1.3)
    return A, R, G, B, O


def burn_images(bm, u):
    """(mask, overlay) as RGBA QImages at map size."""
    data, w, h = bm
    A, R, G, B, O = burn_tables(u)
    m = bytearray(4 * w * h)
    m[3::4] = data.translate(A)
    o = bytearray(4 * w * h)
    o[0::4] = data.translate(R)
    o[1::4] = data.translate(G)
    o[2::4] = data.translate(B)
    o[3::4] = data.translate(O)
    mb, ob = bytes(m), bytes(o)                        # keep the buffers alive until the copies are made
    fmt = QImage.Format.Format_RGBA8888
    mask = QImage(mb, w, h, 4 * w, fmt).copy()
    ov = QImage(ob, w, h, 4 * w, fmt).copy()
    return mask, ov


def burn_pixmap(face, bm, p):
    """`face` (transparent-cornered pixmap) eaten away by fire at progress p."""
    mask, ov = burn_images(bm, burn_u(p))
    out = face.copy()
    out.setDevicePixelRatio(face.devicePixelRatio())
    dpr = out.devicePixelRatio() or 1.0
    tgt = QRectF(0, 0, out.width() / dpr, out.height() / dpr)
    q = QPainter(out)
    q.setRenderHint(QPainter.SmoothPixmapTransform)
    q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
    q.drawImage(tgt, mask)
    q.setCompositionMode(QPainter.CompositionMode_SourceAtop)
    q.drawImage(tgt, ov)
    q.end()
    return out


def _cell_rand(c, r, salt):
    """Deterministic pseudo-random number in [0, 1) for a cell of the endless wall."""
    h = ((c * 73856093) ^ (r * 19349663) ^ (salt * 83492791)) & 0xFFFFFFFF
    h = ((h ^ (h >> 15)) * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 3266489917) & 0xFFFFFFFF
    h ^= h >> 16
    return h / 4294967296.0


def _ease_out_back(u, s=1.5):
    """0 -> 1 with a little overshoot on the way (cards pop out past their orbit, then settle)."""
    u = max(0.0, min(1.0, u)) - 1.0
    return 1.0 + (s + 1) * u * u * u + s * u * u


def heart_path(cx, cy, s):
    """Heart shape centred on (cx, cy), roughly s px wide."""
    path = QPainterPath()
    path.moveTo(cx, cy + 0.35 * s)
    path.cubicTo(cx - 0.75 * s, cy - 0.05 * s, cx - 0.45 * s, cy - 0.55 * s, cx, cy - 0.20 * s)
    path.cubicTo(cx + 0.45 * s, cy - 0.55 * s, cx + 0.75 * s, cy - 0.05 * s, cx, cy + 0.35 * s)
    return path


def blit(p, pm, rect):
    p.drawPixmap(rect, pm, QRectF(pm.rect()))


def tex(pm, dpr):
    b = QBrush(pm)
    b.setTransform(QTransform.fromScale(1 / dpr, 1 / dpr))
    return b


def draw_effect(p, old, new, t, W, H, dpr, r):
    full = QRectF(0, 0, W, H)
    name = r["name"]
    if t >= 0.999:
        blit(p, new, full)
        return
    if name == "slide":
        dx, dy = {"l": (-1, 0), "r": (1, 0), "u": (0, -1), "d": (0, 1)}[r["dir"]]
        blit(p, old, full.translated(dx * W * t, dy * H * t))
        blit(p, new, full.translated(-dx * W * (1 - t), -dy * H * (1 - t)))
        return

    if name == "burn":                       # the old wallpaper burns away, revealing the new one
        blit(p, new, full)
        mask, ov = burn_images(r["bm"], burn_u(t))
        bufs = r.setdefault("_bufs", {})
        key = old.cacheKey()
        buf = bufs.get(key)
        if buf is None or buf.size() != old.size():
            buf = QPixmap(old.size())
            buf.fill(Qt.transparent)
            bufs[key] = buf
        q = QPainter(buf)
        q.setRenderHint(QPainter.SmoothPixmapTransform)
        tgt = QRectF(0, 0, buf.width(), buf.height())
        q.setCompositionMode(QPainter.CompositionMode_Source)
        q.drawPixmap(tgt, old, QRectF(old.rect()))
        q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        q.drawImage(tgt, mask)
        q.setCompositionMode(QPainter.CompositionMode_SourceAtop)
        q.drawImage(tgt, ov)
        q.end()
        p.drawPixmap(full, buf, QRectF(buf.rect()))
        return

    blit(p, old, full)
    p.setPen(Qt.NoPen)
    if name == "fade":
        p.setOpacity(t)
        blit(p, new, full)
    elif name == "wipe":
        rect = {"l": QRectF(0, 0, W * t, H), "r": QRectF(W * (1 - t), 0, W * t, H),
                "u": QRectF(0, 0, W, H * t), "d": QRectF(0, H * (1 - t), W, H * t)}[r["dir"]]
        p.save()
        p.setClipRect(rect)
        blit(p, new, full)
        p.restore()
    elif name == "diag":
        k = H * 0.45
        xt = (W + k) * t
        pts = [(0, 0), (xt, 0), (xt - k, H), (0, H)]
        if r["flip"]:
            pts = [(W - x, y) for x, y in pts]
        p.setBrush(tex(new, dpr))
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
    elif name == "circle":
        cx, cy = r["cx"] * W, r["cy"] * H
        rad = t * math.hypot(max(cx, W - cx), max(cy, H - cy))
        p.setBrush(tex(new, dpr))
        p.drawEllipse(QPointF(cx, cy), rad, rad)
    elif name == "zoom":
        s = 1.3 - 0.3 * t
        p.setOpacity(t)
        blit(p, new, QRectF(W / 2 - W * s / 2, H / 2 - H * s / 2, W * s, H * s))
    elif name == "blinds":
        n = 16
        reg = QRegion()
        if r["dir"] in "lr":
            bw = W / n
            for b in range(n):
                w = int(math.ceil(bw * t))
                x = int((b + 1) * bw) - w if r["flip"] else int(b * bw)
                reg = reg.united(QRegion(QRect(x, 0, w, int(H))))
        else:
            bh = H / n
            for b in range(n):
                h = int(math.ceil(bh * t))
                y = int((b + 1) * bh) - h if r["flip"] else int(b * bh)
                reg = reg.united(QRegion(QRect(0, y, int(W), h)))
        p.save()
        p.setClipRegion(reg)
        blit(p, new, full)
        p.restore()
    elif name == "dissolve":
        cw, ch = W / D_COLS, H / D_ROWS
        reg = QRegion()
        for j in range(D_ROWS):
            for i in range(D_COLS):
                if r["thr"][j * D_COLS + i] <= t:
                    reg = reg.united(QRegion(QRect(int(i * cw), int(j * ch),
                                                   int(cw) + 2, int(ch) + 2)))
        p.save()
        p.setClipRegion(reg)
        blit(p, new, full)
        p.restore()
    elif name == "curtain":
        if r["dir"] in "lr":
            rect = QRectF(W / 2 * (1 - t), 0, W * t, H)
        else:
            rect = QRectF(0, H / 2 * (1 - t), W, H * t)
        p.save()
        p.setClipRect(rect)
        blit(p, new, full)
        p.restore()
    elif name == "glitch":                    # horizontal slices tear sideways and snap to the new picture
        nb = r["gl_n"]
        bh = H / nb
        amp = math.sin(math.pi * t)
        for j in range(nb):
            y0 = int(j * bh)
            y1 = int(H) + 1 if j == nb - 1 else int((j + 1) * bh) + 1
            src = new if r["gl_thr"][j] <= t else old
            p.save()
            p.setClipRect(QRectF(0, y0, W, y1 - y0))
            blit(p, src, full.translated(r["gl_off"][j] * W * amp, 0))
            p.restore()
    elif name == "ripple":                    # a shockwave ring pushes the new picture outwards
        cx, cy = r["cx"] * W, r["cy"] * H
        rad = t * math.hypot(max(cx, W - cx), max(cy, H - cy)) * 1.05
        s = 1 + 0.05 * t
        blit(p, old, QRectF(cx - cx * s, cy - cy * s, W * s, H * s))
        p.setBrush(tex(new, dpr))
        p.drawEllipse(QPointF(cx, cy), rad, rad)
        fade = 1.0 - t
        p.setBrush(Qt.NoBrush)
        for m, a, wd in ((1.0, 220, 4), (0.94, 120, 10), (0.86, 55, 18)):
            p.setPen(QPen(QColor(255, 255, 255, int(a * fade)), wd * (0.6 + fade)))
            p.drawEllipse(QPointF(cx, cy), rad * m, rad * m)


_OverlayBase = QWidget
if USE_GL_OVERLAY:
    try:
        os.environ.setdefault("QT_OPENGL", "desktop")      # real GPU GL, not ANGLE / software GL (read when QApplication starts)
        from PySide6.QtOpenGLWidgets import QOpenGLWidget as _OverlayBase
    except Exception as _e:
        log(f"GL overlay unavailable, using the raster overlay: {_e!r}")
        _OverlayBase = QWidget


_TIMER_RES = [0]


def hi_res_timer(on):
    """timeBeginPeriod(1) / timeEndPeriod(1): Windows' default 15.6 ms timer tick gives uneven 15 / 31 ms frame pacing."""
    if not HI_RES_TIMER:
        return
    try:
        if on and not _TIMER_RES[0]:
            ctypes.windll.winmm.timeBeginPeriod(1)
            _TIMER_RES[0] = 1
        elif not on and _TIMER_RES[0]:
            ctypes.windll.winmm.timeEndPeriod(1)
            _TIMER_RES[0] = 0
    except Exception:
        pass


class Overlay(_OverlayBase):
    """Frame renderer that lives inside the desktop (wallpaper) layer, behind all apps."""

    def __init__(self, geom, old, new, dpr, params):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setGeometry(geom)
        self.old, self.new, self.dpr, self.prm, self.t = old, new, dpr, params, 0.0
        self.hwnd, self.anchor, self.native_rect = 0, None, None
        self.defview = None                      # set when the overlay lives inside Progman (behind the icons)
        self.paint_ms, self._n = [], 0           # per-frame paint times (for the log)

    def attach(self, anchor, x, y, w, h):
        """Stack above the desktop layer while still hidden, so it can never flash over apps."""
        try:
            self.hwnd = int(self.winId())        # creates the native window; nothing is visible yet
            self.anchor = anchor
            self.native_rect = (int(x), int(y), int(w), int(h))
            dv = desktop_icon_host(anchor)
            if dv:                               # Win 11 24H2+: go *behind* the desktop icons, not over them
                try:
                    if native_adopt(self.hwnd, anchor, dv, *self.native_rect):
                        self.defview = dv
                        return True
                except Exception as e:
                    log(f"native_adopt failed: {e!r}")
                log("overlay could not join the desktop layer; desktop icons will be covered during the transition")
            return native_prepare(self.hwnd, anchor, *self.native_rect)
        except Exception as e:
            log(f"attach failed: {e!r}")
            return False

    def _restack(self):
        if self.defview:
            native_stack_child(self.hwnd, self.anchor, self.defview, *self.native_rect)
        else:
            native_stack(self.hwnd, self.anchor, *self.native_rect)

    def present(self):
        self.show()
        self._restack()                                            # keep it under the apps (and icons)

    def ensure_order(self):
        """If Windows raised the desktop / icons above us mid-animation, put the overlay back in place."""
        try:
            u = native().u
            if self.defview:
                if u.GetWindow(self.hwnd, GW_HWNDPREV) != self.defview:         # read-only check
                    self._restack()
            elif u.GetWindow(self.anchor, GW_HWNDPREV) != self.hwnd:
                native_stack(self.hwnd, self.anchor, *self.native_rect)
        except Exception as e:
            log(f"ensure_order failed: {e!r}")

    def set_t(self, t):
        self.t = t
        self._n += 1
        if self._n % 8 == 1:                     # a z-order check every frame is wasted work, and a restack can block on Explorer
            self.ensure_order()
        self.update()

    def _paint(self):
        t0 = time.perf_counter()
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        draw_effect(p, self.old, self.new, self.t, self.width(), self.height(),
                    self.dpr, self.prm)
        p.end()
        self.paint_ms.append((time.perf_counter() - t0) * 1000.0)

    if _OverlayBase is QWidget:
        def paintEvent(self, _):
            self._paint()
    else:
        def paintGL(self):                       # QOpenGLWidget: paintEvent is internal, paint here
            self._paint()


class Transition:
    def __init__(self, old_path, new_path, on_done, effect=None):
        self.new_path, self.on_done = new_path, on_done
        self.prm = make_params(effect or random.choice(EFFECTS))
        self.overlays, self.thread, self.waited = [], None, 0
        self.bmp, self.waited_prep = None, 0
        # convert the new wallpaper right away (in parallel with building the overlays), so none
        # of that heavy work is left to compete with the animation
        self.t_prep = threading.Thread(target=self._prepare, daemon=True)
        self.t_prep.start()
        try:
            self._build(old_path, new_path)
        except Exception as e:   # a failed effect must never block the wallpaper change
            log(f"transition disabled: {e!r}")
            self._drop()
        self.anim = QVariantAnimation()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setDuration(random.randint(*TRANSITION_MS))
        self.anim.setEasingCurve(getattr(QEasingCurve, TRANSITION_EASING, QEasingCurve.InOutCubic))
        self.anim.valueChanged.connect(self._tick)
        self.anim.finished.connect(self._finish)

    def _build(self, old_path, new_path):
        if not (old_path and Path(old_path).is_file()):
            raise RuntimeError("current wallpaper unknown")
        anchor = desktop_anchor()
        if not anchor:
            raise RuntimeError("desktop layer not found")
        screens = QGuiApplication.screens()
        rects = screen_native_rects(screens)
        for scr, (px, py, pw, ph) in zip(screens, rects):
            o = Overlay(scr.geometry(),
                        cover_pixmap_px(old_path, pw, ph), cover_pixmap_px(new_path, pw, ph),
                        scr.devicePixelRatio(), self.prm)
            self.overlays.append(o)
            # 1px narrower than the monitor, like the NVIDIA overlay in your log: a window that covers
            # the whole monitor makes Windows/YASB think a fullscreen app started and hide the bar.
            if not o.attach(anchor, px, py, pw - 1, ph):
                raise RuntimeError("could not stack the overlay above the desktop")

    def _drop(self):
        for o in self.overlays:
            o.old = o.new = QPixmap()               # give the two screen-size pixmaps back right away
            o.close()
        self.overlays = []
        self.prm.pop("_bufs", None)                 # the burn effect's per-screen scratch pixmaps

    def start(self):
        hi_res_timer(True)
        for o in self.overlays:
            o.present()
        QTimer.singleShot(120, self._begin)

    def _prepare(self):
        try:
            self.bmp = prepare_wallpaper(Path(self.new_path))
            hint_vapor(self.bmp)            # the bar starts recolouring during the transition, from the same cropped file Windows gets
        except Exception as e:
            log(f"prepare_wallpaper failed: {e!r}")

    def _begin(self):
        if self.t_prep.is_alive() and self.waited_prep < 6000:   # the overlay just shows the old
            self.waited_prep += 30                               # wallpaper meanwhile: invisible
            QTimer.singleShot(30, self._begin)
            return
        if not self.overlays:
            self.anim.setDuration(1)
        # NOTE: Windows is NOT told about the new wallpaper yet. Explorer decoding + applying it (and the
        # settings broadcast) in the middle of the animation is what made the frames stutter. The overlay
        # already shows the new image at t = 1, so _finish() applies it once the animation has ended.
        self.anim.start()

    def _apply(self):
        try:
            if self.bmp:
                apply_wallpaper_file(self.bmp)
            else:
                bmp = prepare_wallpaper(Path(self.new_path))
                hint_vapor(bmp)
                apply_wallpaper_file(bmp)
            # update_dynamic_theme is started by _finish(), after the animation, so it can't steal frames
        except Exception as e:
            log(f"set_wallpaper failed: {e!r}")

    def _tick(self, v):
        for o in self.overlays:
            o.set_t(float(v))

    def _finish(self):
        self._tick(1.0)
        self._log_stats()
        self.thread = threading.Thread(target=self._apply, daemon=True)
        self.thread.start()
        # the hue / CSS update used to start together with the animation and fight it for the GIL
        threading.Thread(target=update_dynamic_theme, args=(Path(self.new_path),), daemon=True).start()
        self._wait_for_wallpaper()

    def _log_stats(self):
        if not LOG_FRAME_STATS:
            return
        try:
            for i, o in enumerate(self.overlays):
                ms = o.paint_ms[:-1] or o.paint_ms         # the last paint is the forced t = 1 one
                if ms:
                    log(f"transition {self.prm['name']} screen {i}: {len(ms)} frames in {self.anim.duration()} ms "
                        f"({len(ms) * 1000.0 / max(1, self.anim.duration()):.0f} fps), paint avg {sum(ms) / len(ms):.1f} ms, "
                        f"max {max(ms):.1f} ms, >16 ms: {sum(1 for v in ms if v > 16.7)}"
                        f"{' [GL]' if _OverlayBase is not QWidget else ''}")
        except Exception as e:
            log(f"frame stats failed: {e!r}")

    def _wait_for_wallpaper(self):      # non-blocking: keep the UI alive while Windows applies it
        if self.thread and self.thread.is_alive() and self.waited < 4000:
            self.waited += 50
            QTimer.singleShot(50, self._wait_for_wallpaper)
        else:
            QTimer.singleShot(700, self._close)   # let Windows finish painting the new wallpaper

    def _close(self):
        hi_res_timer(False)
        self._drop()
        self.on_done()


# --------------------------------------------------------------- the picker
class Picker(QWidget):
    def __init__(self, files, colors, keys, meta, signals, pending, start_index, folder):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)   # Tool: no taskbar entry
        self._bg = None                                  # desktop snapshot drawn behind the dim (see SNAPSHOT_BACKDROP)
        if SNAPSHOT_BACKDROP:
            self.setAttribute(Qt.WA_OpaquePaintEvent)    # opaque window: no layered/per-pixel-alpha surface in DWM
        else:
            self.setAttribute(Qt.WA_TranslucentBackground)
        scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        g = scr.geometry()   # 1px narrower than the monitor so YASB doesn't treat the picker as fullscreen
        self.setGeometry(g.x(), g.y(), g.width() - 1, g.height())

        self.all, self.colors, self.keys, self.meta = files, colors, keys, meta
        self.pending = pending
        self.items = list(files)
        self.sel = start_index
        self.pos = float(start_index)
        self.query, self.filt = "", None
        self.sel_all = False        # Ctrl+A: whole search text selected
        self.undo_stack, self.redo_stack = [], []       # search-text history for Ctrl+Z / Ctrl+Y
        _h = load_json(HISTORY_FILE, [])
        self.hist = [x for x in _h if isinstance(x, str)][-HISTORY_MAX:] if isinstance(_h, list) else []
        self.hist_i, self.hist_draft = None, ""          # Up / Down recall position (None = not browsing)
        self.setMouseTracking(True)
        self.load_settings()                              # everything below is remembered in settings.json
        self.ach_mode = False                             # Ctrl+B achievements panel
        self.toast = None                                 # small pop-up message (achievement unlocked, ;spin on ...)
        self.toast_t, self._toast_rect, self._toast_step, self.toast_dur = 0.0, QRectF(), -1, 2.6
        self.toast_anim = QVariantAnimation(self)         # runs the little progress line along the pop-up's bottom
        self.toast_anim.setDuration(2600)
        self.toast_anim.setStartValue(0.0)
        self.toast_anim.setEndValue(1.0)
        self.toast_anim.valueChanged.connect(self._toast_tick)
        self.toast_anim.finished.connect(self._hide_toast)
        self.spin_angle, self.spin_speed, self.spin_hold, self._spin_last = 0.0, 0.0, 0.0, 0.0
        self.music, self._hits, self._misses = False, 0, 0
        self.spin_clock = QTimer(self)                    # drives the icon spin (only runs while it is needed)
        self.spin_clock.setInterval(16)
        self.spin_clock.timeout.connect(self._spin_tick)
        self.music_clock = QTimer(self)                   # checks whether the speakers are playing something
        self.music_clock.setInterval(350)
        self.music_clock.timeout.connect(self._music_poll)
        if SOUND_ON:
            start_sound_engine()                          # open the audio stream now, in the background
        self.crop_mode, self.crop, self.drag = False, None, None
        self.help_mode = False
        self.crop_frame, self.badge_rect, self._art, self._art_dpr = QRectF(), QRectF(), None, None
        self.hover, self.credit_t, self._pill_w = False, 0.0, 260.0
        self.hanim = QVariantAnimation(self)             # slides the credit text out on hover
        self.hanim.setDuration(240)
        self.hanim.setEasingCurve(QEasingCurve.OutCubic)
        self.hanim.valueChanged.connect(self._credit_tick)
        self.hv, self.wig_t = 0.0, 1.0                   # icon hover amount (pops past 1) / wiggle progress
        self.hvanim = QVariantAnimation(self)            # icon pops up, lifts and glows on hover
        self.hvanim.setDuration(380)
        self.hvanim.valueChanged.connect(self._hv_tick)
        self.wanim = QVariantAnimation(self)             # one damped wiggle each time the mouse enters
        self.wanim.setDuration(750)
        self.wanim.setStartValue(0.0)
        self.wanim.setEndValue(1.0)
        self.wanim.valueChanged.connect(self._wig_tick)
        self.bounce_t = 1.0                              # 1 = at rest; 0..1 = squish-bounce playing
        self.banim = QVariantAnimation(self)
        self.banim.setDuration(900)
        self.banim.setStartValue(0.0)
        self.banim.setEndValue(1.0)
        self.banim.valueChanged.connect(self._bounce_tick)
        self.search_t, self.caret = 0.0, True
        self.cache = OrderedDict()
        self._cache_cap = None
        self.faces = OrderedDict()                       # orbit: round, un-shaded wallpaper discs at 3 sizes (cheap to blit every frame)
        self._shade_pm, self._shade_S = None, 0          # orbit: shared sphere-shading overlay
        self._planet_pm, self._planet_key = None, None   # orbit: the pre-rendered centre planet
        self._planet_glow, self._planet_geo = None, None # black hole: separate glow layer (it breathes) + disk geometry (hot spot)
        self._bh_t0 = time.perf_counter()                # black-hole animation clock
        self.planet_clock = QTimer(self)                 # gentle black-hole animation: ~30 fps, only its own area is repainted
        self.planet_clock.setInterval(33)
        self.planet_clock.timeout.connect(self._planet_tick)
        self._warm_q, self._reveal = [], False
        self._cache_limit = CACHE_MAX_OPEN
        self.idle = QTimer(self)                          # frees RAM once the picker has been hidden a while
        self.idle.setSingleShot(True)
        self.idle.setInterval(IDLE_FREE_MS)
        self.idle.timeout.connect(self._idle_free)
        self.bar_rect, self.chip_rect, self.dot_rects = QRectF(), QRectF(), []
        self.favs = {str(x) for x in load_json(FAV_FILE, []) if isinstance(x, str)}
        self.fav_only = False
        self.fav_rect, self.heart_rect = QRectF(), QRectF()
        self.applying = False
        self._depth, self._fade, self._acc = {}, {}, {}  # orbit: per-card depth (-1 back .. 1 front) / edge fade / planet accent colours
        self._tilt, self._cells = {}, {}                 # canvas: per-card tilt / (column, row) of each drawn card
        self._cell, self._cam = (0, 0), [0.0, 0.0]       # canvas: focused cell, camera position on the wall (px)
        self._cam_a, self._cam_b = [0.0, 0.0], [0.0, 0.0]
        self._csel = self._cn = self._cH = self._cC = None
        self._canim = QVariantAnimation(self)
        self._canim.setStartValue(0.0)
        self._canim.setEndValue(1.0)
        self._canim.setDuration(280)
        self._canim.setEasingCurve(QEasingCurve.OutCubic)
        self._canim.valueChanged.connect(self._cam_tick)
        self.intro = None                                # opening animation: {'p': 0..1, 'sparks': [...]}
        self._intro_anim = QVariantAnimation(self)
        self._intro_anim.setStartValue(0.0)
        self._intro_anim.setEndValue(1.0)
        self._intro_anim.setDuration(INTRO_MS)
        self._intro_anim.valueChanged.connect(self._intro_tick)
        self._intro_anim.finished.connect(self._intro_end)
        self.transition = None
        self.folder, self.signals = folder, signals
        self.pool = QThreadPool.globalInstance()
        self.inflight, self.scanning = set(), False
        self.home = files[start_index % len(files)] if files else None   # last applied wallpaper
        self.setWindowTitle(WINDOW_TITLE)
        self._safety = QTimer(self)
        self._safety.setSingleShot(True)
        self._safety.timeout.connect(self._apply_done)

        self.anim = QVariantAnimation(self)
        self.anim.setDuration(GO_MS)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._set_pos)

        self.sanim = QVariantAnimation(self)
        self.sanim.setDuration(180)
        self.sanim.setEasingCurve(QEasingCurve.OutCubic)
        self.sanim.valueChanged.connect(self._set_search_t)

        self.blink = QTimer(self)
        self.blink.setInterval(530)
        self.blink.timeout.connect(self._blink)
        self.blink.start()

        self.refilter = QTimer(self)
        self.refilter.setSingleShot(True)
        self.refilter.setInterval(200)
        self.refilter.timeout.connect(self.apply_filter)

        signals.done.connect(self.on_job_done)
        signals.scanned.connect(self.on_scanned)
        signals.fetched.connect(self.on_fetched)

    # ---- show / hide (the picker lives in the background between uses) ----
    def summon(self, rescan=True):
        if self.applying:
            return
        scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        g = scr.geometry()   # 1px narrower than the monitor so YASB doesn't treat the picker as fullscreen
        self.setGeometry(g.x(), g.y(), g.width() - 1, g.height())
        self.query, self.filt, self.fav_only = "", None, False       # fresh state, like a new launch
        self.sel_all = False
        self.undo_stack, self.redo_stack = [], []
        self.crop_mode, self.crop, self.drag = False, None, None
        self.help_mode = False
        self.load_settings()                                         # pick up edits made via ;config
        self.ach_mode = False
        self.toast = None
        self.toast_anim.stop()
        self.spin_angle, self.spin_speed, self.spin_hold, self._spin_last = 0.0, 0.0, 0.0, 0.0
        self.music, self._hits, self._misses = False, 0, 0
        self.hover, self.credit_t = False, 0.0
        self.hanim.stop()
        self.hvanim.stop()
        self.wanim.stop()
        self.hv, self.wig_t = 0.0, 1.0
        self.banim.stop()
        self.bounce_t = 1.0
        self.search_t = 0.0
        self.sanim.stop()
        self.apply_filter()
        if self.home in self.items:                                  # start on the applied wallpaper
            self.sel = self.items.index(self.home)
            self.pos = float(self.sel)
        self.idle.stop()
        if SNAPSHOT_BACKDROP:
            try:
                self._bg = scr.grabWindow(0)             # taken while the picker is still hidden
            except Exception as e:
                log(f"desktop snapshot failed: {e!r}")
                self._bg = None
        self._start_intro()
        self._reveal = True
        self.setWindowOpacity(0.0)                       # the first (stale) frame is shown invisibly ...
        self.show()
        QTimer.singleShot(80, self._reveal_now)          # ... and revealed right after the fresh one is painted (safety net)
        QTimer.singleShot(0, self.grab_focus)
        self._prewarm()
        self.blink.start()
        self._bh_t0 = time.perf_counter()
        self.planet_clock.start()
        self.hist_i = None
        self._start_music_watch()
        if rescan:
            self.start_scan()

    def dismiss(self, quiet=False):
        if not quiet and self.isVisible():
            play_sound("close")
        self.hide()
        self._intro_anim.stop()
        self.intro = None
        self._bg = None                                  # give the screen-sized snapshot back
        self.blink.stop()
        self.planet_clock.stop()
        self.music_clock.stop()
        self.spin_clock.stop()
        while len(self.cache) > CACHE_KEEP_HIDDEN:
            self.cache.popitem(last=False)
        self.faces.clear()
        self._warm_q = []
        self.idle.start()

    def _reveal_now(self):
        self._reveal = False
        if self.windowOpacity() < 1.0:
            self.setWindowOpacity(1.0)

    def _prewarm(self):
        """While the intro ball is still flying, build everything the explosion needs (planet, thumbnails,
        discs), one small piece per event-loop tick, so the first frames of the burst don't stutter."""
        self._warm_q = []
        if LAYOUT != "orbit" or not self.items:
            return
        try:
            lay = sorted(self.layout_items(), key=lambda it: it[5])
            self._warm_q = ["planet"] + [self.items[it[0] % len(self.items)] for it in lay]
        except Exception as e:
            log(f"prewarm skipped: {e!r}")
            self._warm_q = []
        QTimer.singleShot(0, self._warm_step)

    def _warm_step(self):
        if not self._warm_q or not self.isVisible():
            self._warm_q = []
            return
        job = self._warm_q.pop(0)
        try:
            if job == "planet":
                self._planet_pixmap(self.orbit_geom()[2], self.planet_accent())
            else:
                for lv in (0, 1, 2):
                    self._face_level(job, lv)
        except Exception as e:
            log(f"prewarm step failed: {e!r}")
        QTimer.singleShot(0, self._warm_step)

    def _idle_free(self):
        """Hidden for a while: drop every cached thumbnail and return memory to Windows."""
        if self.isVisible() or self.applying:
            return
        self.cache.clear()
        self.faces.clear()
        self._planet_pm = self._planet_key = self._shade_pm = None
        self._planet_glow = self._planet_geo = None
        trim_memory()

    def changeEvent(self, e):
        # A full-screen, always-on-top window that keeps sitting there after you switch away
        # is what blocks clicks. Hide as soon as something else becomes the active window.
        if (e.type() == QEvent.ActivationChange and self.isVisible()
                and not self.isActiveWindow() and not self.applying):
            QTimer.singleShot(250, self._hide_if_inactive)
        super().changeEvent(e)

    def _hide_if_inactive(self):
        if self.isVisible() and not self.isActiveWindow() and not self.applying:
            self.dismiss(True)

    def toggle(self):
        if self.applying:
            return
        if self.isVisible():
            self.dismiss()
        else:
            self.summon()

    def show_or_focus(self):
        if self.isVisible():
            self.grab_focus()
        else:
            self.summon()

    def start_scan(self):
        if self.scanning:
            return
        self.scanning = True
        self.pool.start(Scanner(self.folder, self.signals), 10)

    def on_scanned(self, files, keys, folder=None):
        if folder is not None and folder != self.folder:
            return                              # result of a scan of the folder we just switched away from
        self.scanning = False
        if files is None or keys == self.keys:
            return
        for p in files:
            if self.keys.get(p) != keys[p]:
                self.cache.pop(p, None)
        jobs = [p for p in files if p not in self.inflight
                and (not thumb_path(keys[p]).exists() or keys[p] not in self.meta)]
        self.all, self.keys = files, keys
        self.colors = {p: self.meta[keys[p]] for p in files if keys[p] in self.meta}
        self.pending += len(jobs)
        for p in jobs:
            self.inflight.add(p)
            self.pool.start(Job(p, keys[p], keys[p] not in self.meta, self.signals), 0)
        self.apply_filter()

    def _apply_done(self):
        if not self.applying:
            return
        self.applying = False
        self._safety.stop()
        t, self.transition = self.transition, None
        if t is not None:
            t._drop()
        tmp, self._tmp_wall = getattr(self, "_tmp_wall", None), None
        if tmp:
            try:
                Path(tmp).unlink()
            except OSError:
                pass                                    # still in use: cleaned up on next start
        self.dismiss(True)

    # ---- state ----
    def _set_pos(self, v):
        self.pos = float(v)
        if LAYOUT == "orbit" and not self.intro:
            self.update(self._stage_rect())               # only the planet/ring area changes: skip toolbar + corners
        else:
            self.update()

    def _planet_rect(self):
        cx, cy, D, _, _ = self.orbit_geom()
        ext = D * 1.4 * 1.06 + 4                          # the glow canvas, plus room for its breathing
        return QRectF(cx - ext / 2, cy - ext / 2, ext, ext).toAlignedRect()

    def _planet_tick(self):
        if (not self.isVisible() or self.intro or self.applying or LAYOUT != "orbit" or not self.items
                or self.crop_mode or self.help_mode or self.ach_mode):
            return
        self.update(self._planet_rect())                  # just the black hole's area

    def _stage_rect(self):
        W, H = self.width(), self.height()
        _, cy, D, _, ry = self.orbit_geom()
        top = max(0, int(min(cy - D * 0.7 - 2, cy - ry - H * RING_H * 0.3 - 14)))     # back of the ring / top of the planet
        bottom = int(cy + ry + self.focus_size()[1] * 0.55 + 62)               # under the focused card's shadow / name chip
        return QRect(0, top, W, max(1, min(H, bottom) - top))

    def _set_search_t(self, v):
        self.search_t = float(v)
        self.update()

    def _blink(self):
        self.caret = not self.caret
        if self.query:                                    # only the search bar changes: don't redraw the whole screen
            self.update(self.bar_rect.adjusted(-4, -4, 4, 4).toAlignedRect())

    def go(self, i):
        if len(self.items) < 2:
            return
        if LAYOUT == "canvas":                         # left/right = along a row, a whole-row step = up/down
            delta = int(i) - self.sel
            if delta:
                C = self.canvas_cols()
                if C > 1 and abs(delta) >= C and delta % C == 0:
                    self.canvas_move(0, delta // C)
                else:
                    self.canvas_move(delta, 0)
            return
        play_sound("tick")
        self.sel = int(i)          # unbounded: the carousel wraps around (index = sel % count)
        self.anim.stop()
        self.anim.setStartValue(float(self.pos))
        self.anim.setEndValue(float(self.sel))
        self.anim.start()

    def set_query(self, q, record=True):
        if record and q != self.query:
            self.undo_stack.append(self.query)
            del self.undo_stack[:-200]
            self.redo_stack.clear()
        self.query = q
        self.sel_all = False
        self.sanim.stop()
        self.sanim.setStartValue(self.search_t)
        self.sanim.setEndValue(1.0 if q else 0.0)
        self.sanim.start()
        self.apply_filter()

    def toggle_fav_only(self):
        self.fav_only = not self.fav_only
        self.apply_filter()

    def toggle_fav(self):
        if not self.items:
            return
        idx = self.sel % len(self.items)
        key = str(self.items[idx])
        if key in self.favs:
            self.favs.discard(key)
            play_sound("unfav")
        else:
            self.favs.add(key)
            play_sound("fav")
        save_json(FAV_FILE, sorted(self.favs))
        if self.fav_only and key not in self.favs:      # it just left the favourites view
            self.apply_filter()
            if self.items:
                self.sel = min(idx, len(self.items) - 1)
                self.pos = float(self.sel)
                self.update()
        else:
            self.update()

    def set_filter(self, name):
        self.filt = name
        self.apply_filter()

    def command(self):
        """The ';command' currently typed in the search bar ('' if it is a normal search)."""
        q = self.query.strip().lower()
        return q if q.startswith(";") else ""

    def notify(self, title, msg):
        """Small pop-up inside the picker while it is open; a tray balloon when it is hidden."""
        if self.isVisible():
            self.show_toast(msg)
        else:
            tray = getattr(self, "tray", None)
            if tray is not None:
                tray.showMessage(title, msg, QSystemTrayIcon.Information, 4000)
        log(f"{title}: {msg}")

    def cmd_color(self):
        """Colour name if the typed command is a colour (';red' -> 'Red'), else None."""
        cmd = self.command()[1:]
        if cmd == "grey":
            cmd = "gray"
        for name, _ in COLORS:
            if name.lower() == cmd:
                return name
        return None

    def eff_filt(self):
        """Active colour filter: a clicked colour square, or a typed ';colour' command."""
        return self.cmd_color() or self.filt

    def run_command(self):
        """Run folder commands (on Enter) and close the picker. Returns True if the query was a command."""
        cmd = self.command()
        if not cmd:
            return False
        a = self.cmd_arg(";fetch", keep_quotes=True)          # needs its quotes: ;fetch "link" -n "name"
        if a is not None:
            self.cmd_fetch(a)
            return True
        for name, handler in ((";path", self.cmd_path), (";rename", self.cmd_rename),
                              (";volume", self.cmd_volume), (";color", self.cmd_setcolor)):
            a = self.cmd_arg(name)
            if a is not None:
                handler(a)
                return True
        if cmd == ";delete":
            self.delete_current()
            return True
        if cmd == ";random":
            self.random_pick()
            return True
        if cmd == ";sound":
            on = not SOUND_ON
            set_sound_enabled(on)
            save_json(SETTINGS_FILE, {**load_json(SETTINGS_FILE, {}), "sounds": on})
            self.set_query("")                           # stay open
            self.show_toast("Sound " + ("on" if on else "off"))
            play_sound("fav")                            # (silent when it was just turned off)
            return True
        if cmd == ";toggle":
            self.show_names = not self.show_names
            save_json(SETTINGS_FILE, {**load_json(SETTINGS_FILE, {}), "show_names": self.show_names})
            self.set_query("")                           # stay open so the change is visible
            self.show_toast("File names " + ("shown" if self.show_names else "hidden"))
            return True
        if cmd == ";crop":
            self.start_crop()
            if self.crop_mode:
                self.show_toast("Crop mode", "Enter applies the crop, Esc cancels")
            return True
        if cmd == ";clicks":
            self.show_click_count = not self.show_click_count
            save_setting(show_clicks=self.show_click_count)
            self.set_query("")                           # stay open
            self.show_toast("Click counter " + ("on" if self.show_click_count else "off"))
            self._update_badge()
            return True
        if cmd == ";spin":
            self.spin_on = not self.spin_on
            save_setting(spin=self.spin_on)
            self.set_query("")
            self.show_toast("Icon spin " + ("on" if self.spin_on else "off"),
                            "It spins while music plays." if self.spin_on else "")
            self._start_music_watch()
            return True
        if cmd == ";resetc":
            self.icon_clicks = 0
            self.unlocked = set()
            save_setting(icon_clicks=0, achievements=[])
            self.set_query("")
            self.show_toast("Clicks and achievements reset", "Back to zero. The icon has forgotten you completely.")
            self._update_badge()
            return True
        if cmd == ";config":
            self.dismiss()
            self.notify("Harmony", "Opening the settings file")
            QTimer.singleShot(0, self.open_config)
            return True
        if cmd == ";help":
            self.set_query("")
            self.help_mode = True
            self.update()
            return True
        if cmd in (";quit", ";q"):
            self.quit_app()
            return True
        if cmd == ";locate":
            self.dismiss()
            self.notify("Harmony", "Showing the app in Explorer")
            QTimer.singleShot(0, lambda: reveal_in_explorer(SCRIPT_PATH))
            return True
        target = {";cache": CACHE_DIR, ";wallpapers": ACTIVE_DIR}.get(cmd)
        if target is not None:
            self.dismiss()
            self.notify("Harmony", "Opening the " + ("cache" if cmd == ";cache" else "wallpaper") + " folder")
            QTimer.singleShot(0, lambda: open_folder(target))     # once the picker is hidden
            return True
        n = len(self.items)
        if cmd == ";fav":                                         # Enter keeps the filter, just say what it shows
            if n:
                self.show_toast("Favourites only", f"{n} wallpaper{'' if n == 1 else 's'}")
            else:
                self.show_toast("No favourites yet", "Press Space on a wallpaper to add one")
            return True
        color = self.cmd_color()
        if color:
            if n:
                self.show_toast(f"{color} wallpapers", f"{n} match{'' if n == 1 else 'es'}")
            else:
                self.show_toast(f"No {color.lower()} wallpapers", "Nothing matches that colour")
            return True
        self.show_toast("Unknown command", f"{cmd} isn't a command - type ;help for the list")
        return True

    def cmd_arg(self, name, keep_quotes=False):
        """Text typed after a ';command' (case kept; None if the query isn't that command)."""
        raw = self.query.strip()
        if raw.lower().startswith(name):
            rest = raw[len(name):]
            if rest == "" or rest[0].isspace():
                return rest.strip() if keep_quotes else rest.strip().strip("\"'")
        return None

    def focused(self):
        return self.items[self.sel % len(self.items)] if self.items else None

    # ---- ;path ----
    def cmd_path(self, arg):
        if arg:                                           # ';path D:/Wallpapers'
            if self.change_folder(Path(os.path.expandvars(os.path.expanduser(arg)))):
                self.set_query("")                        # stay open so the new folder is visible
            return
        self.dismiss()                                    # bare ';path': folder dialog (picker is on top, so hide it)
        QTimer.singleShot(0, self._pick_folder_dialog)

    def _pick_folder_dialog(self):
        start = str(self.folder) if Path(self.folder).is_dir() else str(Path.home())
        chosen = QFileDialog.getExistingDirectory(None, "Harmony - choose your wallpaper folder", start)
        if chosen:
            self.change_folder(Path(chosen))
        self.summon(rescan=False)

    def change_folder(self, folder):
        """Switch to another wallpaper folder (remembered across restarts). False if it has no images."""
        global ACTIVE_DIR
        folder = Path(folder)
        files, keys = scan_files(folder)
        if not files:
            self.notify("Harmony", f"No images found in: {folder}")
            return False
        ACTIVE_DIR = self.folder = folder
        save_json(SETTINGS_FILE, {**load_json(SETTINGS_FILE, {}), "wallpaper_dir": str(folder)})
        self.cache.clear()
        self.scanning = False
        self.on_scanned(files, keys, folder)
        self.notify("Harmony", f"Wallpaper folder: {folder}")
        return True

    # ---- ;fetch ----
    def cmd_fetch(self, arg):
        url, name, err = parse_fetch_args(arg)
        if err:
            self.notify("Harmony", err)              # keep what was typed so it can be fixed
            return
        self.set_query("")                                    # stay open; the download runs in the background
        self.show_toast("Downloading...", url)
        threading.Thread(target=fetch_worker, args=(url, name, Path(self.folder), self.signals),
                         daemon=True).start()

    def on_fetched(self, ok, msg, path):
        if ok:
            p = Path(path)
            if p not in self.items and p in self.keys:        # hidden by a colour / favourites filter: show it anyway
                self.filt, self.fav_only = None, False
                self.apply_filter()
            if p in self.items:
                self.sel = self.items.index(p)
                self.pos = float(self.sel)
                self.update()
        self.notify("Harmony", msg)

    # ---- ;volume ----
    def cmd_volume(self, arg):
        if not arg:                                       # bare ';volume': just report the level
            self.set_query("")
            self.show_toast(f"Volume: {round(SOUND_VOLUME * 100)}", "Change it with ;volume 1-100")
            return
        try:
            pct = int(arg.rstrip("%").strip())
        except ValueError:
            self.notify("Harmony", "Usage: ;volume 1-100")
            return
        set_volume(pct)
        save_json(SETTINGS_FILE, {**load_json(SETTINGS_FILE, {}), "volume": round(SOUND_VOLUME * 100)})
        self.set_query("")                                # stay open
        self.show_toast(f"Volume: {round(SOUND_VOLUME * 100)}")
        play_sound("fav")                                 # preview at the new level (silent if ;sound is off)

    # ---- ;color ----
    def cmd_setcolor(self, arg):
        """';color red' - override the automatic colour of the focused wallpaper (saved in colors.json).
        Cost: one dict write + one tiny JSON save. Nothing is re-scanned or re-decoded."""
        names = [n for n, _ in COLORS]
        cur = self.focused()
        if cur is None:
            self.notify("Harmony", "No wallpaper to recolour.")
            return
        want = arg.strip().lower()
        if want == "grey":
            want = "gray"
        if not want:                                      # bare ';color': show the current one + the choices
            self.set_query("")
            self.show_toast(f"Colour: {self.colors.get(cur, 'unknown')}",
                            "Set it with ;color " + " / ".join(n.lower() for n in names))
            return
        name = next((n for n in names if n.lower() == want), None)
        if name is None:
            self.notify("Harmony", "Colours: " + ", ".join(n.lower() for n in names))
            return
        key = self.keys.get(cur)
        if not key:
            return
        self.colors[cur] = name
        self.meta[key] = name                             # in meta = never auto-classified again
        save_json(META_FILE, self.meta)
        self.set_query("")                                # stay open
        self.apply_filter()
        self.show_toast(f"Colour set to {name}", cur.stem)

    # ---- ;rename ----
    def cmd_rename(self, arg):
        cur = self.focused()
        if cur is None:
            self.notify("Harmony", "No wallpaper to rename.")
            return
        if not arg:                                       # bare ';rename': pre-fill the bar with the current name
            self.set_query(f";rename {cur.stem}")
            return
        stem = arg
        if stem.lower().endswith(cur.suffix.lower()):
            stem = stem[:-len(cur.suffix)]
        stem = stem.strip().rstrip(". ")
        bad = set('<>:"/\\|?*') | {chr(c) for c in range(32)}
        reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
        if not stem or any(ch in bad for ch in stem) or stem.split(".")[0].upper() in reserved:
            self.notify("Harmony", "That isn't a valid file name.")
            return
        new = cur.with_name(stem + cur.suffix)
        if str(new) == str(cur):
            return
        if new.exists() and os.path.normcase(str(new)) != os.path.normcase(str(cur)):
            self.notify("Harmony", f"{new.name} already exists.")
            return
        try:
            os.rename(cur, new)
        except OSError as e:
            self.notify("Harmony", f"Couldn't rename: {e}")
            return
        # keep every record that is keyed by the old path pointing at the new one
        idx = self.sel % len(self.items)
        old_key = self.keys.pop(cur, None)
        new_key = key_of(new)
        self.keys[new] = new_key
        col = self.colors.pop(cur, None)
        if col:
            self.colors[new] = col
        if old_key:                                       # carry the thumbnail + colour over: no regeneration
            try:
                if thumb_path(old_key).exists():
                    os.replace(thumb_path(old_key), thumb_path(new_key))
            except OSError:
                pass
            if old_key in self.meta:
                self.meta[new_key] = self.meta.pop(old_key)
                save_json(META_FILE, self.meta)
        self.cache.pop(cur, None)
        self.items[idx] = new
        self.all = sorted([new if p == cur else p for p in self.all], key=lambda p: p.name.lower())
        if str(cur) in self.favs:
            self.favs.discard(str(cur))
            self.favs.add(str(new))
            save_json(FAV_FILE, sorted(self.favs))
        state = load_json(STATE_FILE, {})
        if state.get("last") == str(cur):
            state["last"] = str(new)
            save_json(STATE_FILE, state)
        if self.home == cur:
            self.home = new
        self.set_query("")                                # stay open, still focused on the renamed wallpaper
        self.notify("Harmony", f"Renamed to {new.name}")

    # ---- ;random ----
    def random_pick(self):
        self.set_query("")                                # drop the typed command, keep the heart / colour filters
        if not self.items:
            self.notify("Harmony", "No wallpapers to pick from.")
            return
        choices = [p for p in self.items if p != self.home] or self.items     # not the one you already have
        self.sel = self.items.index(random.choice(choices))
        self.pos = float(self.sel)
        self.apply()

    # ---- ;delete ----
    def delete_current(self):
        cur = self.focused()
        if cur is None:
            self.notify("Harmony", "No wallpaper to delete.")
            return
        err = move_to_trash(cur)
        if err:
            self.notify("Harmony", f"Couldn't delete {cur.name}: {err}")
            return
        idx = self.sel % len(self.items)
        self.items.pop(idx)
        self.all = [p for p in self.all if p != cur]
        key = self.keys.pop(cur, None)
        self.colors.pop(cur, None)
        self.cache.pop(cur, None)
        if key:
            try:
                thumb_path(key).unlink()
            except OSError:
                pass
            if self.meta.pop(key, None) is not None:
                save_json(META_FILE, self.meta)
        if str(cur) in self.favs:
            self.favs.discard(str(cur))
            save_json(FAV_FILE, sorted(self.favs))
        if self.home == cur:
            self.home = None
        self.sel = idx if idx < len(self.items) else 0    # the next wallpaper takes its place
        self.set_query("")
        play_sound("delete")
        self.notify("Harmony", f"Deleted {cur.name}")

    def quit_app(self):
        self.hide()
        tray = getattr(self, "tray", None)
        if tray is not None:
            tray.hide()                                      # no ghost icon left behind
        try:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception:
            pass
        QTimer.singleShot(1500, lambda: os._exit(0))         # force-exit if Qt shutdown stalls
        QApplication.quit()

    def apply_filter(self):
        cur = self.items[self.sel % len(self.items)] if self.items else None
        cmd = self.command()
        toks = [] if cmd else self.query.lower().split()
        fav_only = self.fav_only or cmd == ";fav"
        filt = self.eff_filt()
        out = []
        for p in self.all:
            col = self.colors.get(p, "")
            if filt and col != filt:
                continue
            if fav_only and str(p) not in self.favs:
                continue
            name = p.stem.lower()
            if all(t in name or (col and t in col.lower()) for t in toks):
                out.append(p)
        self.items = out
        self.sel = out.index(cur) if cur in out else 0
        self.anim.stop()
        self.pos = float(self.sel)
        self.update()

    def on_job_done(self, path, color):
        p = Path(path)
        self.pending -= 1
        self.inflight.discard(p)
        self.cache.pop(p, None)               # drop any stale low-res copy
        if color and p in self.keys:
            self.colors[p] = color
            self.meta[self.keys[p]] = color
            if self.filt or self.query:
                self.refilter.start()
        if self.pending <= 0 or self.pending % 40 == 0:
            save_json(META_FILE, self.meta)
        if self.pending > 0 and self.pending % 50 == 0 and not self.isVisible():
            trim_memory()                     # long thumbnail batch while hidden: don't let the heap pile up
        if self.pending <= 0 and not self.isVisible():
            self.idle.start()
        self.update()

    # ---- thumbnails ----
    def thumb_cap(self):
        """Largest size (physical px) any card is ever drawn at; a cached thumbnail never needs more."""
        H, W = self.height(), self.width()
        if H <= 0 or W <= 0:
            return None
        if LAYOUT == "orbit":                         # the focused card is the biggest thing drawn
            fw, fh = self.focus_size()
            dpr = self.devicePixelRatioF()
            return math.ceil(fw * dpr), math.ceil(fh * dpr)
        hc = H * CARD_H
        wc = max(hc * 0.8, min(hc * (W / H) - SKEW * hc, W * 0.56))
        dpr = self.devicePixelRatioF()
        return math.ceil((wc + SKEW * hc) * dpr), math.ceil(hc * dpr)

    def thumb(self, p):
        cap = self.thumb_cap()
        if cap != self._cache_cap:                    # screen size / scaling changed
            self.cache.clear()
            self.faces.clear()
            self._cache_cap = cap
        pm = self.cache.get(p)
        if pm is not None:
            self.cache.move_to_end(p)
            return pm
        f = thumb_path(self.keys[p])
        if not f.exists():
            return None
        rd = QImageReader(str(f))
        if cap:
            sz = rd.size()
            if sz.isValid():
                sc = max(cap[0] / sz.width(), cap[1] / sz.height())
                if sc < 0.95:                         # decode straight to the drawn size (less RAM, faster)
                    rd.setScaledSize(QSize(max(1, round(sz.width() * sc)),
                                           max(1, round(sz.height() * sc))))
        img = rd.read()
        if img.isNull():
            return None
        pm = QPixmap.fromImage(img)
        self.cache[p] = pm
        while len(self.cache) > self._cache_limit:
            self.cache.popitem(last=False)
        return pm

    def focus_size(self):
        """(width, height) in logical px of the focused wallpaper card."""
        W, H = self.width(), self.height()
        rx = self.orbit_geom()[3]
        fh = min(H * FOCUS_H, min(W * 0.6, rx * 1.05) / FOCUS_ASPECT)
        return fh * FOCUS_ASPECT, fh

    def ring_px(self):
        """Diameter (device px) of the biggest round (unfocused) wallpaper disc."""
        return max(32, round(self.height() * RING_H * self.devicePixelRatioF()))

    def _face_level(self, item, lvl):
        """Round wallpaper disc, centre-cropped, at full / half / quarter size (small planets blit the smaller
        ones, so nothing is ever shrunk by more than 2x = no shimmering while the ring turns)."""
        pm = self.thumb(item)
        if pm is None:
            return None
        key = (pm.cacheKey(), lvl)
        f = self.faces.get(key)
        if f is not None:
            self.faces.move_to_end(key)
            return f
        size = max(16, self.ring_px() >> lvl)
        k = size / max(1, min(pm.width(), pm.height()))
        src = pm
        if abs(k - 1.0) > 0.01:
            src = pm.scaled(max(1, round(pm.width() * k)), max(1, round(pm.height() * k)),
                            Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        f = QPixmap(size, size)
        f.fill(Qt.transparent)
        q = QPainter(f)
        q.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        br = QBrush(src)
        br.setTransform(QTransform.fromTranslate((size - src.width()) / 2, (size - src.height()) / 2))
        q.setPen(Qt.NoPen)
        q.setBrush(br)
        q.drawEllipse(QRectF(0, 0, size, size))
        q.end()
        self.faces[key] = f
        while len(self.faces) > 48:
            self.faces.popitem(last=False)
        return f

    def face(self, item, w_px):
        S = self.ring_px()
        lvl = 2 if (S >> 2) >= w_px * 0.97 else 1 if (S >> 1) >= w_px * 0.97 else 0
        return self._face_level(item, lvl)

    def _shade_disc(self, S):
        """Sphere shading (lit from the top-left) as a reusable overlay."""
        if self._shade_pm is None or self._shade_S != S:
            pm = QPixmap(S, S)
            pm.fill(Qt.transparent)
            q = QPainter(pm)
            q.setRenderHint(QPainter.Antialiasing)
            R = S / 2
            g = QRadialGradient(QPointF(R - R * 0.35, R - R * 0.4), R * 1.55)
            g.setColorAt(0.0, QColor(255, 255, 255, 26))
            g.setColorAt(0.5, QColor(0, 0, 0, 0))
            g.setColorAt(1.0, QColor(0, 0, 0, 160))
            q.setPen(Qt.NoPen)
            q.setBrush(QBrush(g))
            q.drawEllipse(QRectF(0, 0, S, S))
            q.end()
            self._shade_pm, self._shade_S = pm, S
        return self._shade_pm

    # ---- layout ----
    def orbit_geom(self):
        """Planet centre / diameter and the orbit ellipse radii."""
        W, H = self.width(), self.height()
        return W / 2, H * 0.47, H * 0.46, min(W * 0.42, H * 0.95), H * 0.26

    def layout_items(self):
        """Cards on a tilted ring around the planet. Returns (i, x, y, w, h, d) with d = distance from the
        focus; also fills self._depth (-1 back .. 1 front) and self._fade (edge of the ring)."""
        if LAYOUT == "canvas":
            return self.canvas_layout()
        n = len(self.items)
        self._depth, self._fade = {}, {}
        if not n:
            return []
        H, W = self.height(), self.width()
        cx, cy, _, rx, ry = self.orbit_geom()
        M = min(12, n)                                   # cards on the ring at once
        step, half = 2 * math.pi / M, M / 2
        hb = H * RING_H                                  # base diameter of an orbiting wallpaper
        fw, fh = self.focus_size()
        fl = int(math.floor(self.pos))
        out = []
        for i in range(fl - M // 2 - 1, fl + M // 2 + 3):
            o = i - self.pos
            if o <= -half - 1e-9 or o > half + 1e-9:
                continue
            phi = math.pi / 2 - o * step                 # focus sits at the front (bottom) of the ring
            z = math.sin(phi)
            f = (z + 1) / 2
            foc = 1 - min(abs(o), 1.0)
            foc = foc * foc * (3 - 2 * foc)
            base = hb * (0.60 + 0.40 * f)
            h = base + (fh - base) * foc                     # the focused one grows and opens from a circle ...
            w = h * (1 + (FOCUS_ASPECT - 1) * foc)           # ... into the whole 16:9 wallpaper
            sx, sy = cx + rx * math.cos(phi), cy + ry * z
            self._depth[i] = z
            self._fade[i] = max(0.0, min(1.0, half - abs(o))) if n > M else 1.0
            out.append((i, sx - w / 2, sy - h / 2, w, h, abs(o)))
        return out

    @staticmethod
    def item_poly(x, y, w, h):
        s = SKEW * h
        return QPolygonF([QPointF(x + s / 2, y), QPointF(x + s / 2 + w, y),
                          QPointF(x - s / 2 + w, y + h), QPointF(x - s / 2, y + h)])

    # ---- painting ----
    def _backdrop(self, p, r):
        """Desktop snapshot (if any) + the dark dim, for rect r."""
        if self._bg is not None and not self._bg.isNull():
            d = self._bg.devicePixelRatio()
            rf = QRectF(r)
            p.drawPixmap(rf, self._bg, QRectF(rf.x() * d, rf.y() * d, rf.width() * d, rf.height() * d))
        elif SNAPSHOT_BACKDROP:
            p.fillRect(r, QColor(20, 20, 24))            # snapshot failed: plain dark backdrop
        p.fillRect(r, QColor(0, 0, 0, 115))

    def paintEvent(self, ev):
        if self._reveal:                                  # fresh frame is in the buffer: now show the window
            self._reveal = False
            QTimer.singleShot(0, self._reveal_now)
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        r = ev.rect()
        if (LAYOUT == "orbit" and self.toast and not (self.crop_mode or self.help_mode or self.ach_mode)
                and not self.bar_rect.isEmpty() and r.top() >= self.bar_rect.bottom()
                and r.bottom() <= self.height() * 0.17):                         # only the pop-up's line moved
            self._backdrop(p, r)
            self.draw_toast(p)
            return
        if (LAYOUT == "orbit" and not (self.crop_mode or self.help_mode or self.ach_mode) and self.badge_rect.width() > 0   # only the bottom strip changed
                and r.top() > self.height() * 0.90 + 40):                                      # ... clear of every card
            self._backdrop(p, r)
            self.draw_credit(p)                                          # skip the carousel + toolbar redraw
            return
        self._backdrop(p, self.rect())
        self.heart_rect = QRectF()
        if self.items:
            if LAYOUT == "canvas":
                drawn = self.draw_canvas(p)
            else:
                lay = self._intro_adjust(self.layout_items())     # (unchanged unless the opening animation runs)
                dz = self._depth
                back = sorted([it for it in lay if dz[it[0]] < 0], key=lambda r: dz[r[0]])
                front = sorted([it for it in lay if dz[it[0]] >= 0], key=lambda r: dz[r[0]])
                kp, kr = self._intro_scales()
                shake = self._intro_shake()
                p.save()
                if shake:
                    p.translate(shake[0], shake[1])
                drawn = self._draw_cards(p, back)
                self.draw_orbit(p, False, kr)
                self.draw_planet(p, kp)
                self.draw_orbit(p, True, kr)
                drawn += self._draw_cards(p, front)
                p.restore()
                self.draw_intro_fx(p)
            self._cache_limit = min(CACHE_MAX_OPEN, max(8, drawn + 4))     # cache only what is on screen
        else:
            p.setPen(QColor(220, 220, 225))
            p.setFont(QFont("Segoe UI", 16))
            msg = ("No favourites yet - press Space on a wallpaper to add one"
                   if (self.fav_only or self.command() == ";fav") and not self.favs else "No wallpapers match")
            p.drawText(self.rect(), Qt.AlignCenter, msg)
        if self._intro_phase()[0] is None and r.top() <= int(self.height() * 0.085 + 66):   # the bar pops in with the explosion
            self.draw_toolbar(p)                          # (skipped while only the carousel area repaints)
        self.draw_credit(p)
        if self.crop_mode:
            self.draw_crop(p)
        if self.help_mode:
            self.draw_help(p)
        if self.ach_mode:
            self.draw_achievements(p)
        self.draw_toast(p)

    def _credit_tick(self, v):
        self.credit_t = float(v)
        self._update_badge()

    def _bounce_tick(self, v):
        self.bounce_t = float(v)
        self._update_badge()

    def _update_badge(self):
        """Repaint just the corner image (plus room for its glow/hop) - cheap compared to the carousel."""
        left = 44 + (self._pill_w if (self.hover or self.credit_t > 0.001) else 0)
        self.update(self.badge_rect.adjusted(-left, -72, 44, 24).toAlignedRect())

    def _hv_tick(self, v):
        self.hv = float(v)
        self._update_badge()

    def _wig_tick(self, v):
        self.wig_t = float(v)
        self._update_badge()

    def wiggle_angle(self):
        """Degrees of tilt for the hover wiggle (damped swing that settles back to 0)."""
        t = self.wig_t
        if t >= 1.0:
            return 0.0
        return 11.0 * math.exp(-4.0 * t) * math.sin(2 * math.pi * 2.5 * t)

    # ---- remembered settings (settings.json) ----
    def load_settings(self):
        cfg = load_json(SETTINGS_FILE, {})
        cfg = cfg if isinstance(cfg, dict) else {}
        self.show_names = bool(cfg.get("show_names", False))
        set_sound_enabled(cfg.get("sounds", True))
        v = cfg.get("volume")
        if isinstance(v, (int, float)) and round(SOUND_VOLUME * 100) != max(1, min(100, int(v))):
            set_volume(v)
        n = cfg.get("icon_clicks", 0)
        self.icon_clicks = max(0, int(n)) if isinstance(n, (int, float)) else 0
        self.show_click_count = bool(cfg.get("show_clicks", False))      # ;clicks
        self.spin_on = bool(cfg.get("spin", True))                       # ;spin
        ach = cfg.get("achievements", [])
        self.unlocked = {a for a in ach if isinstance(a, int)} if isinstance(ach, list) else set()

    def save_all_settings(self):
        save_setting(show_names=self.show_names, sounds=bool(SOUND_ON), volume=round(SOUND_VOLUME * 100),
                     show_clicks=self.show_click_count, spin=self.spin_on,
                     icon_clicks=self.icon_clicks,
                     achievements=sorted(self.unlocked), wallpaper_dir=str(self.folder))

    def open_config(self):
        try:
            if not SETTINGS_FILE.exists():
                self.save_all_settings()                  # so the file lists every option
            import subprocess
            subprocess.Popen(["notepad.exe", str(SETTINGS_FILE)])
        except Exception as e:
            log(f"open config failed: {e!r}")
            reveal_in_explorer(SETTINGS_FILE)

    # ---- icon spin while music plays ----
    def _start_music_watch(self):
        if self.spin_on:
            self.music_clock.start()
            self._music_poll(first=True)
        else:
            self.music_clock.stop()
            self.music = False
            self._sync_spin()

    def _music_poll(self, first=False):
        if not self.spin_on or not self.isVisible():
            return
        if time.monotonic() - _LAST_UI_SOUND[0] < 1.0:
            return                                        # that was our own hover / click sound, not music
        if audio_peak() > MUSIC_PEAK:
            self._hits, self._misses = self._hits + (2 if first else 1), 0
        else:
            self._hits, self._misses = 0, self._misses + 1
        if self._hits >= 2:
            self.music = True
        elif self._misses >= 4:                           # ~1.4 s of silence: the music really stopped
            self.music = False
        self._sync_spin()

    def _sync_spin(self):
        if (self.spin_on and self.music) or self.spin_speed > 0 or abs(self.spin_angle) > 0.5:
            if not self.spin_clock.isActive():
                self._spin_last = 0.0
                self.spin_clock.start()

    def _spin_tick(self):
        now = time.perf_counter()
        dt = min(0.05, now - self._spin_last) if self._spin_last else 0.016
        self._spin_last = now
        changed = False
        if self.spin_on and self.music and now >= self.spin_hold:      # winding up / spinning
            self.spin_speed = min(SPIN_DPS, self.spin_speed + SPIN_ACCEL * dt)
            self.spin_angle = (self.spin_angle + self.spin_speed * dt) % 360.0
            changed = True
        elif self.spin_speed > 0:                                      # music stopped: wind down
            self.spin_speed = max(0.0, self.spin_speed - SPIN_ACCEL * 1.5 * dt)
            self.spin_angle = (self.spin_angle + self.spin_speed * dt) % 360.0
            changed = True
        else:                                                          # glide back upright
            a = self.spin_angle % 360.0
            d = -a if a <= 180.0 else 360.0 - a
            if abs(d) < 0.4:
                changed = self.spin_angle != 0.0
                self.spin_angle = 0.0
                if not (self.spin_on and self.music):
                    self.spin_clock.stop()
            else:
                self.spin_angle = a + d * min(1.0, dt * 9.0)
                changed = True
        if changed:
            self._update_badge()

    def snap_spin(self):
        """Clicking the icon snaps it straight back upright; it only starts spinning again after the bounce."""
        self.spin_angle, self.spin_speed = 0.0, 0.0
        self.spin_hold = time.perf_counter() + 0.9
        self._sync_spin()

    # ---- pop-up messages + achievements ----
    def show_toast(self, title, sub="", gold=False):
        self.toast = {"title": title, "sub": sub, "gold": gold}
        self.toast_t, self._toast_step = 0.0, -1
        self.toast_dur = 3.4 if gold else 2.6                # achievements stay a bit longer: the trophy needs time to shine
        self.toast_anim.stop()
        self.toast_anim.setDuration(int(self.toast_dur * 1000))
        self.toast_anim.start()
        self.update()

    def _toast_tick(self, v):
        self.toast_t = float(v)
        step = int(self.toast_t * self.toast_dur * 30)    # ~30 repaints a second is plenty
        if self.toast and step != self._toast_step and not self._toast_rect.isEmpty():
            self._toast_step = step
            g = self.toast["gold"]                        # the trophy pop-up slides up and sparkles past its edges
            self.update(self._toast_rect.adjusted(-14 if g else -4, -14 if g else -4,
                                                  14 if g else 4, 34 if g else 4).toAlignedRect())

    def _hide_toast(self):
        self.toast = None
        self.update()

    def check_achievements(self):
        new = [a for a in ACHIEVEMENTS if self.icon_clicks >= a[0] and a[0] not in self.unlocked]
        if not new:
            return
        self.unlocked.update(a[0] for a in new)
        save_setting(achievements=sorted(self.unlocked))
        _, name, joke = new[-1]
        self.show_toast(f"Achievement unlocked: {name}", joke, gold=True)
        play_sound("achievement")

    def bounce(self):
        """Play the squish-and-bounce on the corner image."""
        self.banim.stop()
        self.banim.start()
        play_sound("bounce")

    def bounce_pose(self):
        """(scale_x, scale_y, hop_px) for the current moment of the bounce."""
        t = self.bounce_t
        if t >= 1.0:
            return 1.0, 1.0, 0.0
        decay = math.exp(-3.4 * t)
        c = math.cos(2 * math.pi * 2.5 * t)
        squash = decay * c                              # >0 flat and wide, <0 tall and thin
        hop = 20 * decay * max(0.0, -c)                 # in the air while stretched
        return 1 + 0.30 * squash, 1 - 0.30 * squash, hop

    def set_hover(self, h):
        if h != self.hover:
            self.setCursor(Qt.PointingHandCursor) if h else self.unsetCursor()
            self.hover = h
            self.hanim.stop()
            self.hanim.setStartValue(self.credit_t)
            self.hanim.setEndValue(1.0 if h else 0.0)
            self.hanim.start()
            self.hvanim.stop()                           # icon: pop (with overshoot) in, ease out
            self.hvanim.setEasingCurve(QEasingCurve.OutBack if h else QEasingCurve.OutCubic)
            self.hvanim.setStartValue(self.hv)
            self.hvanim.setEndValue(1.0 if h else 0.0)
            self.hvanim.start()
            self.wanim.stop()
            if h:
                self.wanim.start()
                play_sound("hover")
            else:
                self.wig_t = 1.0

    def leaveEvent(self, e):
        self.set_hover(False)

    def draw_credit(self, p):
        """Artwork in the bottom-right corner; the credit text slides out to its left on hover."""
        size, m = 72, 18
        x, y = self.width() - m - size, self.height() - m - size
        self.badge_rect = QRectF(x, y, size, size)
        t = self.credit_t
        if t > 0.001:
            p.save()
            p.setFont(QFont("Segoe UI", 10))
            tw = p.fontMetrics().horizontalAdvance(CREDIT_TEXT)
            pad_l, pad_r, gap, ph = 14, 4, 2, 34
            pw = tw + pad_l + pad_r
            total = pw + gap + size / 2                 # the pill tucks under the image
            self._pill_w = total
            _, _, hop0 = self.bounce_pose()
            p.translate(0, -(hop0 + 7.0 * self.hv))     # rides along with the icon's lift / click hop
            p.setClipRect(QRectF(x - pw - gap, y, total, size))
            p.translate((1 - t) * total, 0)             # slides in from behind the image
            p.setOpacity(min(1.0, t * 1.6) * 0.96)
            pill = QRectF(x - pw - gap, y + (size - ph) / 2, total, ph)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(20, 20, 24, 238))
            p.drawRoundedRect(pill, ph / 2, ph / 2)
            p.setPen(QColor(235, 235, 240))
            p.drawText(QRectF(pill.left() + pad_l, pill.top(), tw + 2, ph),
                       Qt.AlignLeft | Qt.AlignVCenter, CREDIT_TEXT)
            p.restore()
        dpr = self.devicePixelRatioF()
        oversample = 1.25                                   # a little extra detail for the hover zoom
        if self._art is None or self._art_dpr != dpr:
            self._art = art_pixmap(round(size * dpr * oversample), "menu")
            self._art.setDevicePixelRatio(dpr * oversample)  # still size x size logical px
            self._art_dpr = dpr
        sx, sy, hop = self.bounce_pose()
        hv = self.hv
        lift = 7.0 * hv                                     # hover: rises, grows, tilts and glows
        cx, cy = x + size / 2, y + size / 2 - lift
        if hv > 0.01:
            a = int(90 * min(1.0, max(0.0, hv)))
            g = QRadialGradient(QPointF(cx, cy), size * 0.85)
            g.setColorAt(0.0, QColor(255, 255, 255, a))
            g.setColorAt(0.45, QColor(255, 255, 255, a))
            g.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.save()
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawEllipse(QPointF(cx, cy), size * 0.85, size * 0.85)
            p.restore()
        hs = 1 + 0.14 * hv
        p.save()
        p.setOpacity(0.97)
        p.translate(x + size / 2, y + size - hop - lift)   # squish from the bottom edge, like a blob on the floor
        p.scale(sx * hs, sy * hs)
        p.translate(0, -size / 2)
        p.rotate(self.wiggle_angle() + self.spin_angle)     # hover wiggle + music spin, around the image centre
        p.translate(-size / 2, -size / 2)
        p.drawPixmap(0, 0, self._art)
        p.restore()
        if self.show_click_count:                           # ;clicks: little counter badge on the icon's corner
            p.save()
            txt = f"{self.icon_clicks:,}"
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            pw, ph = p.fontMetrics().horizontalAdvance(txt) + 20, 22
            pill = QRectF(x + size - pw + 8, y - 10 - hop - lift, pw, ph)   # rides along with the icon's hop / lift
            p.setPen(QPen(QColor(255, 255, 255, 60), 1))
            p.setBrush(QColor(20, 20, 24, 240))
            p.drawRoundedRect(pill, ph / 2, ph / 2)
            p.setPen(QColor(235, 235, 240))
            p.drawText(pill, Qt.AlignCenter, txt)
            p.restore()

    # ---- ;crop mode: pick an area of the selected wallpaper ----
    def start_crop(self):
        if not self.items:
            return
        path = self.items[self.sel % len(self.items)]
        try:
            iw, ih = oriented_size(path)
            u32 = ctypes.windll.user32
            sw, sh = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
            aspect = sw / sh if sw and sh else self.width() / self.height()
            W, H, dpr = self.width(), self.height(), self.devicePixelRatioF()
            s = min((W - 160) / iw, (H - 200) / ih)        # logical px per source px
            fw, fh = iw * s, ih * s
            pw, ph = max(1, round(fw * dpr)), max(1, round(fh * dpr))
            rd = QImageReader(str(path))
            rd.setAutoTransform(True)
            if pw < iw:
                rd.setScaledSize(QSize(pw, ph))
            img = rd.read()
            if img.isNull():
                raise RuntimeError("could not read the image")
            if (img.width(), img.height()) != (pw, ph):
                img = img.scaled(pw, ph, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            max_rw = min(iw, ih * aspect)
            self.crop = dict(path=path, iw=iw, ih=ih, aspect=aspect, s=s, busy=False,
                             rw=max_rw, rx=(iw - max_rw) / 2, ry=(ih - max_rw / aspect) / 2,
                             pm=QPixmap.fromImage(img),
                             rect=QRectF((W - fw) / 2, (H - fh) / 2 - 10, fw, fh))
        except Exception as ex:
            log(f"crop start failed: {ex!r}")
            self.notify("Harmony", f"Couldn't open the crop view: {ex}")
            return
        self.set_query("")
        self.crop_mode, self.drag = True, None
        self.set_hover(False)
        self.update()

    def crop_clamp(self, rx, ry, rw):
        c = self.crop
        max_rw = min(c["iw"], c["ih"] * c["aspect"])
        rw = min(max_rw, max(max_rw * 0.08, rw))
        c["rw"] = rw
        c["rx"] = min(c["iw"] - rw, max(0.0, rx))
        c["ry"] = min(c["ih"] - rw / c["aspect"], max(0.0, ry))
        self.update()

    def crop_sel(self):
        """The selection rectangle in widget coordinates."""
        c = self.crop
        r, s = c["rect"], c["s"]
        return QRectF(r.left() + c["rx"] * s, r.top() + c["ry"] * s,
                      c["rw"] * s, c["rw"] / c["aspect"] * s)

    def crop_corner_at(self, pt):
        sel = self.crop_sel()
        for name, cp in (("tl", sel.topLeft()), ("tr", sel.topRight()),
                         ("bl", sel.bottomLeft()), ("br", sel.bottomRight())):
            if abs(pt.x() - cp.x()) <= 16 and abs(pt.y() - cp.y()) <= 16:
                return name
        return None

    def crop_zoom(self, f):
        c = self.crop
        cx, cy = c["rx"] + c["rw"] / 2, c["ry"] + c["rw"] / c["aspect"] / 2
        nw = c["rw"] * f
        self.crop_clamp(cx - nw / 2, cy - nw / c["aspect"] / 2, nw)

    def crop_cancel(self):
        self.crop_mode, self.crop, self.drag = False, None, None
        self.unsetCursor()
        self.update()

    def crop_key(self, e):
        c = self.crop
        k = e.key()
        step = c["iw"] * 0.01
        if c.get("busy"):
            return
        if k in (Qt.Key_Return, Qt.Key_Enter):
            c["busy"] = True
            self.update()
            QTimer.singleShot(30, self._crop_do)       # let the "Applying..." text paint first
        elif k == Qt.Key_Escape:
            self.crop_cancel()
        elif k in (Qt.Key_Plus, Qt.Key_Equal):
            self.crop_zoom(0.92)
        elif k == Qt.Key_Minus:
            self.crop_zoom(1 / 0.92)
        elif k == Qt.Key_R:
            self.crop_clamp(0, 0, 1e9)
            self.crop_clamp((c["iw"] - c["rw"]) / 2, (c["ih"] - c["rw"] / c["aspect"]) / 2, c["rw"])
        elif k == Qt.Key_Left:
            self.crop_clamp(c["rx"] - step, c["ry"], c["rw"])
        elif k == Qt.Key_Right:
            self.crop_clamp(c["rx"] + step, c["ry"], c["rw"])
        elif k == Qt.Key_Up:
            self.crop_clamp(c["rx"], c["ry"] - step, c["rw"])
        elif k == Qt.Key_Down:
            self.crop_clamp(c["rx"], c["ry"] + step, c["rw"])

    def _crop_do(self):
        """Cut the chosen area out of the original, save it and apply it like any wallpaper."""
        c = self.crop
        if not self.crop_mode or not c:
            return
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            u32 = ctypes.windll.user32
            sw, sh = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
            img = ImageOps.exif_transpose(Image.open(c["path"])).convert("RGB")
            rh = c["rw"] / c["aspect"]
            img = img.crop((round(c["rx"]), round(c["ry"]),
                            round(c["rx"] + c["rw"]), round(c["ry"] + rh)))
            if sw and sh and (img.width > sw or img.height > sh):
                img = img.resize((sw, sh), Image.LANCZOS)      # Windows would shrink it anyway
            out = CACHE_DIR / f"crop_tmp_{time.time_ns()}.png"
            img.save(out, compress_level=1)
        except Exception as ex:
            log(f"crop failed: {ex!r}")
            c["busy"] = False
            self.notify("Harmony", f"Crop failed: {ex}")
            self.update()
            return
        self.crop_mode, self.crop, self.drag = False, None, None
        self.unsetCursor()
        self.apply(override=out)

    def draw_trophy(self, p, cx, cy, size, el):
        """Little gold trophy: pops in with a bounce + wobble, a gold ring bursts out, a shine sweeps over the cup
        and sparkles twinkle around it. `el` = seconds since the pop-up appeared."""
        p.save()
        p.translate(cx, cy)
        t0 = min(1.0, el / 0.45)
        pop = 1 + 2.70158 * (t0 - 1) ** 3 + 1.70158 * (t0 - 1) ** 2        # ease-out-back: overshoots, settles
        k = size / 100.0
        wob = 14.0 * math.exp(-5.0 * el) * math.sin(2 * math.pi * 3.0 * el)
        bob = math.sin(el * 5.0) * 1.2 if el > 0.5 else 0.0
        if el < 0.6:                                                         # gold ring bursting outwards
            u = el / 0.6
            ring = QColor(255, 214, 10)
            ring.setAlphaF(0.75 * (1 - u))
            p.setPen(QPen(ring, 3.0 * (1 - u) + 0.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(0, 0), size * (0.22 + 0.5 * u), size * (0.22 + 0.5 * u))
        p.translate(0, bob)
        p.rotate(wob)
        p.scale(k * max(0.01, pop), k * max(0.01, pop))
        gold = QLinearGradient(-30, -34, 30, 40)
        gold.setColorAt(0.0, QColor(255, 240, 130))
        gold.setColorAt(0.55, QColor(255, 196, 30))
        gold.setColorAt(1.0, QColor(214, 140, 10))
        edge = QPen(QColor(150, 92, 0, 210), 1.6)
        edge.setJoinStyle(Qt.RoundJoin)
        handle = QPen(QColor(236, 168, 20), 6.0)
        handle.setCapStyle(Qt.RoundCap)
        p.setBrush(Qt.NoBrush)
        for s in (1, -1):                                                    # handles
            h = QPainterPath()
            h.moveTo(s * 25, -26)
            h.cubicTo(s * 47, -26, s * 46, -2, s * 19, 2)
            p.setPen(handle)
            p.drawPath(h)
        cup = QPainterPath()
        cup.moveTo(-27, -34)
        cup.lineTo(27, -34)
        cup.cubicTo(27, -3, 15, 12, 0, 14)
        cup.cubicTo(-15, 12, -27, -3, -27, -34)
        cup.closeSubpath()
        p.setPen(edge)
        p.setBrush(QBrush(gold))
        p.drawPath(cup)
        p.drawRect(QRectF(-5, 14, 10, 13))                                   # stem
        p.drawRoundedRect(QRectF(-23, 26, 46, 11), 3, 3)                     # base
        star = QPolygonF([QPointF(0.0 + 9 * math.sin(math.radians(a)) * (1.0 if j % 2 == 0 else 0.42),
                                  -14 - 9 * math.cos(math.radians(a)) * (1.0 if j % 2 == 0 else 0.42))
                          for j, a in enumerate(range(0, 360, 36))])
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 215))
        p.drawPolygon(star)                                                  # emblem on the cup
        s = ((el - 0.25) % 1.6) / 0.7 if el > 0.25 else 2.0                  # shine band sweeping across the cup
        if s < 1.0:
            x = -70 + 140 * s
            p.save()
            p.setClipPath(cup)
            p.setBrush(QColor(255, 255, 255, 150))
            p.drawPolygon(QPolygonF([QPointF(x - 9, -40), QPointF(x + 3, -40), QPointF(x + 19, 40), QPointF(x + 7, 40)]))
            p.restore()
        p.restore()
        if el > 0.3:                                                         # twinkling sparkles around the trophy
            p.save()
            p.translate(cx, cy)
            p.setPen(Qt.NoPen)
            for j, (ang, rad, ph) in enumerate(((-50, 40, 0.0), (35, 42, 1.3), (-125, 38, 2.4), (160, 40, 3.5), (95, 44, 4.6))):
                a = max(0.0, math.sin(el * 6.0 + ph))
                if a < 0.05:
                    continue
                sx, sy = math.cos(math.radians(ang)) * rad * k * 1.4, math.sin(math.radians(ang)) * rad * k * 1.4
                sz = (3.0 + 5.0 * a) * (size / 46.0)
                col = QColor(255, 244, 170) if j % 2 == 0 else QColor(255, 255, 255)
                col.setAlphaF(min(1.0, a * 1.2))
                p.setBrush(col)
                p.drawPolygon(QPolygonF([QPointF(sx, sy - sz), QPointF(sx + sz * 0.3, sy - sz * 0.3),
                                         QPointF(sx + sz, sy), QPointF(sx + sz * 0.3, sy + sz * 0.3),
                                         QPointF(sx, sy + sz), QPointF(sx - sz * 0.3, sy + sz * 0.3),
                                         QPointF(sx - sz, sy), QPointF(sx - sz * 0.3, sy - sz * 0.3)]))
            p.restore()

    def draw_toast(self, p):
        t = self.toast
        if not t:
            return
        gold = t["gold"]
        el = self.toast_t * self.toast_dur                   # seconds since it appeared
        extra = 64 if gold else 0                            # room for the trophy
        p.save()
        f1, f2 = QFont("Segoe UI", 11, QFont.Weight.DemiBold), QFont("Segoe UI", 10)
        room = max(200, self.width() - 160 - extra)
        p.setFont(f1)
        title = p.fontMetrics().elidedText(t["title"], Qt.ElideMiddle, room)
        w1 = p.fontMetrics().horizontalAdvance(title)
        p.setFont(f2)
        sub = p.fontMetrics().elidedText(t["sub"], Qt.ElideMiddle, room) if t["sub"] else ""
        w2 = p.fontMetrics().horizontalAdvance(sub) if sub else 0
        pw, ph = max(w1, w2) + 60 + extra, (66 if sub else 44) + 10        # +10: room for the progress line
        r = QRectF((self.width() - pw) / 2, self.height() * 0.085 + 54 + 16, pw, ph)   # just under the toolbar
        self._toast_rect = r
        if gold:                                             # slides up into place while fading in
            k = min(1.0, el / 0.25)
            k = 1 - (1 - k) ** 3
            p.setOpacity(k)
            p.translate(0, (1 - k) * 18)
        p.setPen(QPen(QColor(255, 200, 60, 210) if gold else QColor(255, 255, 255, 50), 1.5))
        p.setBrush(QColor(20, 20, 24, 245))
        p.drawRoundedRect(r, 14, 14)
        if gold:
            self.draw_trophy(p, r.left() + 16 + 24, r.top() + (r.height() - 10) / 2, 46, el)
        tx, tw = r.left() + extra, r.width() - extra
        p.setFont(f1)
        p.setPen(QColor(255, 214, 10) if gold else QColor(245, 245, 250))
        p.drawText(QRectF(tx, r.top() + (9 if sub else 0), tw, 24 if sub else ph - 10), Qt.AlignCenter, title)
        if sub:
            p.setFont(f2)
            p.setPen(QColor(200, 200, 210))
            p.drawText(QRectF(tx, r.top() + 34, tw, 24), Qt.AlignCenter, sub)
        lx, lw, ly = r.left() + 18, r.width() - 36, r.bottom() - 9      # progress line: fills as the pop-up runs out
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 36))
        p.drawRoundedRect(QRectF(lx, ly, lw, 3), 1.5, 1.5)
        p.setBrush(QColor(255, 214, 10) if gold else QColor(235, 235, 245, 210))
        p.drawRoundedRect(QRectF(lx, ly, lw * min(1.0, self.toast_t), 3), 1.5, 1.5)
        p.restore()

    def draw_achievements(self, p):
        W, H = self.width(), self.height()
        row, pad, title_h, pw = 66, 28, 56, 640
        ph = 2 * pad + title_h + row * len(ACHIEVEMENTS) + 34
        panel = QRectF((W - pw) / 2, max(10.0, (H - ph) / 2), pw, ph)
        p.fillRect(self.rect(), QColor(8, 8, 12, 215))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 20, 24, 245))
        p.drawRoundedRect(panel, 13, 13)
        x, y = panel.left() + pad, panel.top() + pad
        inner = pw - 2 * pad
        p.setPen(QColor(245, 245, 250))
        p.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        p.drawText(QRectF(x, y, inner, title_h - 8), Qt.AlignLeft | Qt.AlignVCenter, "Achievements")
        p.setPen(QColor(170, 170, 180))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRectF(x, y, inner, title_h - 8), Qt.AlignRight | Qt.AlignVCenter,
                   f"{len(self.unlocked)} / {len(ACHIEVEMENTS)} unlocked   |   {self.icon_clicks:,} clicks now")
        y += title_h
        for need, name, joke in ACHIEVEMENTS:
            done = need in self.unlocked
            c = QRectF(x, y + (row - 40) / 2, 40, 40)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 200, 40) if done else QColor(60, 60, 68))
            p.drawEllipse(c)
            p.setPen(QColor(40, 28, 0) if done else QColor(120, 120, 130))
            p.setFont(QFont("Segoe UI Symbol", 15))
            p.drawText(c, Qt.AlignCenter, "\u2605" if done else "?")
            tx, tw = x + 54, inner - 54
            p.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
            p.setPen(QColor(255, 255, 255) if done else QColor(140, 140, 150))
            p.drawText(QRectF(tx, y + 8, tw, 24), Qt.AlignLeft | Qt.AlignVCenter, name if done else "Locked")
            p.setFont(QFont("Segoe UI", 10))
            p.setPen(QColor(200, 200, 210) if done else QColor(120, 120, 130))
            p.drawText(QRectF(tx, y + 33, tw - 150, 24), Qt.AlignLeft | Qt.AlignVCenter,
                       joke if done else f"Click the icon {need:,} times")
            if not done:                                    # progress bar for locked ones
                bw = 130
                bar = QRectF(x + inner - bw, y + row / 2 - 3, bw, 6)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(60, 60, 68))
                p.drawRoundedRect(bar, 3, 3)
                p.setBrush(QColor(255, 200, 40))
                p.drawRoundedRect(QRectF(bar.left(), bar.top(), bw * min(1.0, self.icon_clicks / need), 6), 3, 3)
                p.setPen(QColor(150, 150, 160))
                p.drawText(QRectF(bar.left(), bar.bottom() + 4, bw, 18), Qt.AlignRight | Qt.AlignVCenter,
                           f"{min(self.icon_clicks, need):,} / {need:,}")
            y += row
        p.setPen(QColor(150, 150, 160))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRectF(panel.left(), y + 8, pw, 24), Qt.AlignCenter, "Press any key to close")

    def draw_help(self, p):
        W, H = self.width(), self.height()
        row, pad, title_h, col = 28, 28, 44, 240
        pw = col + 400 + 2 * pad
        ph = 2 * pad + title_h + row * len(HELP) + 34
        panel = QRectF((W - pw) / 2, max(10.0, (H - ph) / 2), pw, ph)
        p.fillRect(self.rect(), QColor(8, 8, 12, 215))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(20, 20, 24, 245))
        p.drawRoundedRect(panel, 13, 13)
        x, y = panel.left() + pad, panel.top() + pad
        left, right = Qt.AlignLeft | Qt.AlignVCenter, Qt.AlignCenter
        p.setPen(QColor(245, 245, 250))
        p.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        p.drawText(QRectF(x, y, pw - 2 * pad, title_h - 8), left, "Commands")
        y += title_h
        for cmd, desc in HELP:
            p.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
            p.setPen(QColor(255, 255, 255))
            p.drawText(QRectF(x, y, col, row), left, cmd)
            p.setFont(QFont("Segoe UI", 10))
            p.setPen(QColor(200, 200, 210))
            p.drawText(QRectF(x + col, y, pw - 2 * pad - col, row), left, desc)
            y += row
        p.setPen(QColor(150, 150, 160))
        p.drawText(QRectF(panel.left(), y + 8, pw, 24), right, "Press any key to close")

    def draw_crop(self, p):
        c = self.crop
        if not c:
            return
        W = self.width()
        p.fillRect(self.rect(), QColor(8, 8, 12, 240))
        r, pm = c["rect"], c["pm"]
        p.drawPixmap(r, pm, QRectF(0, 0, pm.width(), pm.height()))
        sel = self.crop_sel()
        outer, hole = QPainterPath(), QPainterPath()
        outer.addRect(r)
        hole.addRect(sel)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 160))
        p.drawPath(outer.subtracted(hole))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 235), 2))
        p.drawRect(sel)
        p.setPen(QPen(QColor(255, 255, 255, 90), 1))
        for i in (1, 2):
            x, y = sel.left() + sel.width() * i / 3, sel.top() + sel.height() * i / 3
            p.drawLine(QPointF(x, sel.top()), QPointF(x, sel.bottom()))
            p.drawLine(QPointF(sel.left(), y), QPointF(sel.right(), y))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255))
        for cp in (sel.topLeft(), sel.topRight(), sel.bottomLeft(), sel.bottomRight()):
            p.drawRect(QRectF(cp.x() - 5, cp.y() - 5, 10, 10))
        p.setPen(QColor(235, 235, 240))
        p.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        p.drawText(QRectF(r.left(), r.top() - 40, r.width(), 30), Qt.AlignLeft | Qt.AlignVCenter,
                   f"Crop wallpaper  -  {c['path'].name}")
        rh = c["rw"] / c["aspect"]
        p.setFont(QFont("Segoe UI", 10))
        p.setPen(QColor(200, 200, 210))
        p.drawText(QRectF(r.left(), r.bottom() + 10, r.width(), 24), Qt.AlignCenter,
                   f"Selected {round(c['rw'])} x {round(rh)} px  of  {c['iw']} x {c['ih']} px")
        p.setPen(QColor(150, 150, 160))
        p.drawText(QRectF(0, r.bottom() + 36, W, 24), Qt.AlignCenter,
                   "Drag: move   Drag corner / wheel / + -: resize   Arrows: nudge   "
                   "R: reset   Enter: apply   Esc: cancel")
        if c.get("busy"):
            p.fillRect(self.rect(), QColor(0, 0, 0, 150))
            p.setPen(QColor(245, 245, 250))
            p.setFont(QFont("Segoe UI", 16))
            p.drawText(self.rect(), Qt.AlignCenter, "Applying...")

    def draw_item(self, p, i, x, y, w, h, d):
        t = 1 - min(d, 1.0)
        rect = QRectF(x, y, w, h)
        rad = self.card_radius(w, h)
        z = self._depth.get(i, 1.0)
        f = (z + 1) / 2                                          # 0 = far side of the ring, 1 = nearest
        edge = self._fade.get(i, 1.0)
        fade = edge
        p.setPen(Qt.NoPen)
        p.setOpacity(1.0)
        for k, a in enumerate((34, 20, 10)):                    # soft layered drop shadow
            g = 5 + k * 8
            off = 10 + 10 * t
            p.setBrush(QColor(0, 0, 0, int(a * (0.55 + 0.75 * t) * fade * (0.4 + 0.6 * f))))
            p.drawRoundedRect(rect.adjusted(-g, -g + off, g, g + off), rad + g, rad + g)
        if t > 0.02 and LAYOUT == "orbit":                        # soft glow around the focused wallpaper
            p.setBrush(Qt.NoBrush)
            for g, a in ((2.5, 70), (7, 38), (13, 16)):
                p.setPen(QPen(QColor(255, 255, 255, int(a * t * edge)), 2.5))
                p.drawRoundedRect(rect.adjusted(-g, -g, g, g), rad + g, rad + g)
            p.setPen(Qt.NoPen)
        self.paint_card(p, i, x, y, w, h, d, fade=edge)
        shade = int(150 * (1 - f) ** 1.2 * edge)                 # cards on the far side sink into the dark
        if shade > 2 and d >= 0.5:
            p.setOpacity(1.0)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, shade))
            p.drawRoundedRect(rect, rad, rad)

    def paint_card(self, p, i, x, y, w, h, d, local=False, fade=1.0):
        """One wallpaper card: rounded photo, soft sheen, name plate and heart. (x, y) = top-left."""
        item = self.items[i % len(self.items)]
        t = 1 - min(d, 1.0)
        rect = QRectF(x, y, w, h)
        rad = self.card_radius(w, h)
        path = QPainterPath()
        path.addRoundedRect(rect, rad, rad)
        p.setPen(Qt.NoPen)
        p.setOpacity(max(0.55, 1 - 0.09 * d) * fade)
        orbit = LAYOUT == "orbit"
        dpr = self.devicePixelRatioF()
        m = max(0.0, min(1.0, (w / max(h, 1e-6) - 1.0) / (FOCUS_ASPECT - 1.0))) if orbit else 0.0   # 0 circle .. 1 card
        if orbit and d < 0.002 and not local:             # at rest: land the focused card exactly on device pixels = pin sharp
            x, y = round(x * dpr) / dpr, round(y * dpr) / dpr
            w, h = round(w * dpr) / dpr, round(h * dpr) / dpr
            rect = QRectF(x, y, w, h)
            rad = self.card_radius(w, h)
        fast = self.face(item, h * dpr) if (orbit and m < 0.03) else None
        if fast is not None:
            p.drawPixmap(rect, fast, QRectF(fast.rect()))
            sh = self._shade_disc(self.ring_px())         # (round planets keep the sphere shading)
            p.setOpacity(max(0.55, 1 - 0.09 * d) * fade * (1.0 - 0.8 * t))
            p.drawPixmap(rect, sh, QRectF(sh.rect()))
        else:
            path = QPainterPath()
            path.addRoundedRect(rect, rad, rad)
            pm = self.thumb(item)
            if pm:
                pw, ph = pm.width(), pm.height()
                sc = max(w / pw, h / ph)                            # cover the card, centre-cropped
                ox, oy = (pw * sc - w) / 2, (ph * sc - h) / 2
                br = QBrush(pm)
                br.setTransform(QTransform.fromScale(sc, sc) * QTransform.fromTranslate(x - ox, y - oy))
                p.setBrush(br)
            else:
                p.setBrush(QColor(38, 38, 42))
            p.drawPath(path)

            k_sh = (1.0 - 0.85 * m) if orbit else 1.0       # the focused wallpaper keeps almost none of the shading
            R = (min(w, h) if orbit else max(w, h)) / 2
            shade = QRadialGradient(QPointF(x + w / 2 - R * 0.35, y + h / 2 - R * 0.4), R * 1.55)
            shade.setColorAt(0.0, QColor(255, 255, 255, int(26 * k_sh)))
            shade.setColorAt(0.5, QColor(0, 0, 0, 0))
            shade.setColorAt(1.0, QColor(0, 0, 0, int(160 * k_sh)))
            p.setBrush(QBrush(shade))
            p.drawPath(path)

        if self.show_names and d < 0.5 and not local:                      # name chip under the focused planet
            k = max(0.0, 1 - d * 2)
            f = QFont("Segoe UI", 12)
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            fm = p.fontMetrics()
            name = fm.elidedText(item.name, Qt.ElideMiddle, int(max(160.0, w * 1.5)))
            tw = fm.horizontalAdvance(name) + 30
            chip = QRectF(x + w / 2 - tw / 2, y + h + 16, tw, 30)
            p.setOpacity(k * fade)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(20, 20, 24, 225))
            p.drawRoundedRect(chip, 15, 15)
            p.setPen(QColor(244, 244, 248))
            p.drawText(chip, Qt.AlignCenter, name)

        p.setOpacity(fade)                                                 # rim light
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, int(36 + 100 * t)), 1.4 + 0.8 * t))
        p.drawRoundedRect(rect.adjusted(0.7, 0.7, -0.7, -0.7), rad, rad)

        is_fav = str(item) in self.favs                                    # favourite heart, top-right
        if is_fav or d < 0.5:
            sz = max(12.0, min(34.0, h * 0.09))
            r = sz * 0.85
            if LAYOUT == "orbit":                                          # badge on the upper-right rim / card corner
                hx, hy = x + w / 2 + min(w, h) * 0.34, y + h / 2 - min(w, h) * 0.34
                hx += (x + w - 14 - r - hx) * m
                hy += (y + 14 + r - hy) * m
            else:                                                          # top-right corner of the card
                hx, hy = x + w - 14 - r, y + 14 + r
            chip = QRectF(hx - r, hy - r, 2 * r, 2 * r)
            if d < 0.5 and not local:
                self.heart_rect = chip
            p.setOpacity(max(0.55, 1 - 0.09 * d) * fade)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(10, 10, 14, 150))
            p.drawEllipse(chip)
            hp = heart_path(hx, hy + 1, sz * 0.95)
            if is_fav:
                p.setBrush(QColor(255, 77, 121))
                p.setPen(QPen(QColor(255, 255, 255, 230), 1.4))
            else:                                                          # hint that it can be favourited
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(255, 255, 255, 200), 1.6))
            p.drawPath(hp)
            p.setOpacity(1.0)

    # ---- the endless wall ----
    def card_radius(self, w, h):
        if LAYOUT != "orbit":
            return min(w, h) * 0.07
        m = max(0.0, min(1.0, (w / max(h, 1e-6) - 1.0) / (FOCUS_ASPECT - 1.0)))     # 0 = circle .. 1 = full card
        return min(w, h) / 2 * (1 - m) + min(w, h) * 0.07 * m

    def canvas_cols(self):
        return max(1, min(CANVAS_COLS, len(self.items)))

    def canvas_pitch(self):
        H = self.height()
        return H * 0.50, H * 0.29

    def cell_world(self, c, r):
        """Centre of cell (c, r) on the wall (px), plus its size factor and tilt (degrees)."""
        PX, PY = self.canvas_pitch()
        return (c * PX + (_cell_rand(c, r, 1) - 0.5) * 0.24 * PX,
                r * PY + (_cell_rand(c, r, 2) - 0.5) * 0.24 * PY,
                0.85 + 0.30 * _cell_rand(c, r, 3),
                (_cell_rand(c, r, 4) - 0.5) * 6.0)

    def _canvas_sync(self):
        """If the selection was changed from elsewhere (search, filter, reopen), snap the camera onto it."""
        n, H, C = len(self.items), self.height(), self.canvas_cols()
        if (self._csel, self._cn, self._cH, self._cC) != (self.sel, n, H, C):
            self._canim.stop()
            self._cell = (self.sel % C, self.sel // C)
            wx, wy, _, _ = self.cell_world(*self._cell)
            self._cam = [wx, wy]
            self._csel, self._cn, self._cH, self._cC = self.sel, n, H, C

    def _cam_tick(self, v):
        v = float(v)
        self._cam = [self._cam_a[0] + (self._cam_b[0] - self._cam_a[0]) * v,
                     self._cam_a[1] + (self._cam_b[1] - self._cam_a[1]) * v]
        self.update()

    def canvas_move(self, dc, dr):
        """Travel dc columns / dr rows across the wall (arrow keys)."""
        if len(self.items) < 2 or not (dc or dr):
            return
        self._canvas_sync()
        play_sound("tick")
        c, r = self._cell
        c, r = c + dc, r + dr
        self._cell = (c, r)
        self.sel += dc + dr * self.canvas_cols()
        self._csel = self.sel
        self.pos = float(self.sel)
        wx, wy, _, _ = self.cell_world(c, r)
        self._cam_a, self._cam_b = list(self._cam), [wx, wy]
        self._canim.stop()
        self._canim.start()

    def canvas_layout(self):
        """Cells around the camera as (uid, x, y, w, h, d); d = distance from the camera in cells.
        uid % len(items) is the wallpaper's index; _depth orders them (focused cell last)."""
        n = len(self.items)
        self._depth, self._fade, self._tilt, self._cells = {}, {}, {}, {}
        W, H = self.width(), self.height()
        if not n or H <= 0:
            return []
        self._canvas_sync()
        PX, PY = self.canvas_pitch()
        C = self.canvas_cols()
        cam = self._cam
        ox, oy = W / 2 - cam[0], H * 0.54 - cam[1]                 # wall -> screen
        c0, c1 = math.floor((-ox - 0.45 * H) / PX), math.ceil((W - ox + 0.45 * H) / PX)
        r0, r1 = math.floor((-oy - 0.25 * H) / PY), math.ceil((H - oy + 0.25 * H) / PY)
        bw, bh = H * 0.40, H * 0.225
        out = []
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                wx, wy, sz, tilt = self.cell_world(c, r)
                d = math.hypot((wx - cam[0]) / PX, (wy - cam[1]) / PY)
                foc = 1 - min(d, 1.0)
                foc = foc * foc * (3 - 2 * foc)
                s = (sz + (1.0 - sz) * foc) * (1 + 0.55 * foc)     # scattered sizes, the focused card is uniform and big
                w, h = bw * s, bh * s
                x, y = ox + wx - w / 2, oy + wy - h / 2
                if x + w < -20 or x > W + 20 or y + h < -20 or y > H + 20:
                    continue
                uid = r * C + c + n * (r * 4096 + c)               # unique per cell, uid % n = wallpaper index
                self._depth[uid] = 1.0 - min(2.0, 0.5 * d)
                self._fade[uid] = 1.0
                self._tilt[uid] = tilt * (1 - foc)
                self._cells[uid] = (c, r)
                out.append((uid, x, y, w, h, d))
        return out

    def draw_canvas(self, p):
        lay = self.canvas_layout()
        self.draw_canvas_grid(p)
        for it in sorted(lay, key=lambda r: self._depth[r[0]]):    # far first, the focused card on top
            i, x, y, w, h, d = it
            ang = self._tilt.get(i, 0.0)
            p.save()
            if abs(ang) > 0.01:
                p.translate(x + w / 2, y + h / 2)
                p.rotate(ang)
                p.translate(-(x + w / 2), -(y + h / 2))
            self.draw_item(p, *it)
            self.draw_card_deco(p, it)
            p.restore()
        self.draw_canvas_hud(p)
        return len(lay)

    def draw_canvas_grid(self, p):
        """Blueprint layer: dot lattice and coordinate crosses that slide with the wall."""
        W, H = self.width(), self.height()
        PX, PY = self.canvas_pitch()
        if PX <= 0:
            return
        ox, oy = W / 2 - self._cam[0], H * 0.54 - self._cam[1]
        g = H * 0.055
        pts = QPolygonF()
        x = ox % g
        while x < W:
            y = oy % g
            while y < H:
                pts.append(QPointF(x, y))
                y += g
            x += g
        p.setOpacity(1.0)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 34), 2.2, Qt.SolidLine, Qt.RoundCap))
        p.drawPoints(pts)
        p.setFont(QFont("Consolas", 8))
        c0, c1 = math.floor((-ox) / PX) - 1, math.ceil((W - ox) / PX)
        r0, r1 = math.floor((-oy) / PY) - 1, math.ceil((H - oy) / PY)
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                sx, sy = ox + (c + 0.5) * PX, oy + (r + 0.5) * PY
                p.setPen(QPen(QColor(255, 255, 255, 70), 1.2))
                p.drawLine(QPointF(sx - 8, sy), QPointF(sx + 8, sy))
                p.drawLine(QPointF(sx, sy - 8), QPointF(sx, sy + 8))
                p.setPen(QColor(255, 255, 255, 60))
                p.drawText(QPointF(sx + 12, sy - 8), f"{c:+03d} {r:+03d}")

    def draw_card_deco(self, p, it):
        """Index tag above each card; viewfinder brackets round the focused one."""
        i, x, y, w, h, d = it
        n = len(self.items)
        t = 1 - min(d, 1.0)
        p.setOpacity(max(0.0, 0.9 - 0.12 * d))
        p.setFont(QFont("Consolas", 9))
        p.setPen(QColor(255, 255, 255, 170))
        p.setBrush(Qt.NoBrush)
        p.drawText(QPointF(x, y - 8), f"{(i % n) + 1:03d}")
        if t > 0.02:
            m, L = 12.0, 24.0
            pen = QPen(QColor(255, 255, 255, int(230 * t)), 2.2)
            pen.setCapStyle(Qt.FlatCap)
            p.setOpacity(1.0)
            p.setPen(pen)
            gx0, gy0, gx1, gy1 = x - m, y - m, x + w + m, y + h + m
            for ax, ay, sx, sy in ((gx0, gy0, 1, 1), (gx1, gy0, -1, 1), (gx0, gy1, 1, -1), (gx1, gy1, -1, -1)):
                p.drawLine(QPointF(ax, ay), QPointF(ax + sx * L, ay))
                p.drawLine(QPointF(ax, ay), QPointF(ax, ay + sy * L))
        p.setOpacity(1.0)

    def draw_canvas_hud(self, p):
        n = len(self.items)
        if not n:
            return
        c, r = self._cell
        p.setOpacity(1.0)
        p.setFont(QFont("Consolas", 10))
        p.setPen(QColor(255, 255, 255, 130))
        p.drawText(QPointF(28, 40), f"{self.sel % n + 1:03d} / {n:03d}     X {c:+d}   Y {r:+d}")
        p.setPen(QColor(255, 255, 255, 70))
        p.drawText(QPointF(28, 60), "ARROWS  travel      ENTER  apply      SPACE  favourite")

    # ---- opening animation: a ball flies up from below the screen and explodes into the system ----
    def _start_intro(self):
        self._intro_anim.stop()
        if not INTRO or LAYOUT != "orbit" or not self.items:
            self.intro = None
            return
        sparks = [(random.uniform(0, 2 * math.pi), random.uniform(260, 1150), random.uniform(1.6, 4.2))
                  for _ in range(90)]
        self.intro = {"p": 0.0, "sparks": sparks, "boom": False}
        self._intro_anim.start()
        play_sound("rise")

    def _intro_tick(self, v):
        if self.intro:
            self.intro["p"] = float(v)
            if not self.intro["boom"] and self.intro["p"] >= INTRO_BALL:
                self.intro["boom"] = True
                play_sound("boom")                       # the ball hits the centre
            self.update()

    def _intro_end(self):
        self.intro = None
        self.update()

    def _intro_phase(self):
        """(ball progress 0..1 while it flies, else None ; explosion progress 0..1). Not running: (None, 1.0)."""
        if not self.intro:
            return None, 1.0
        pr = self.intro["p"]
        if pr < INTRO_BALL:
            return pr / INTRO_BALL, 0.0
        return None, (pr - INTRO_BALL) / (1 - INTRO_BALL)

    def _intro_scales(self):
        """Scale of the central planet and of the orbit ring during the explosion."""
        if not self.intro:
            return 1.0, 1.0
        ball, b = self._intro_phase()
        if ball is not None:
            return 0.0, 0.0
        return _ease_out_back(b / 0.7, 1.1), _ease_out_back(b / 0.8, 1.0)

    def _intro_shake(self):
        if not self.intro:
            return None
        ball, b = self._intro_phase()
        if ball is None and b < 0.22:
            amp = 9 * (1 - b / 0.22) ** 2
            return amp * math.sin(b * 160), amp * math.cos(b * 190)
        return None

    def _intro_adjust(self, lay):
        """During the explosion every planet bursts out of the centre to its orbit slot (staggered, with overshoot)."""
        if not self.intro:
            return lay
        ball, b = self._intro_phase()
        if ball is not None:
            return []
        cx, cy, _, _, _ = self.orbit_geom()
        out = []
        for i, x, y, w, h, d in lay:
            u = max(0.0, min(1.0, (b - 0.04 * min(d, 6.0)) / 0.76))
            e = _ease_out_back(u)
            self._fade[i] = min(self._fade.get(i, 1.0), max(0.0, min(1.0, u * 1.6)))
            nw, nh = w * e, h * e
            if nw < 3 or nh < 3:
                continue
            mx, my = cx + (x + w / 2 - cx) * e, cy + (y + h / 2 - cy) * e
            out.append((i, mx - nw / 2, my - nh / 2, nw, nh, d))
        return out

    def draw_intro_fx(self, p):
        if not self.intro:
            return
        ball, b = self._intro_phase()
        cx, cy, _, _, _ = self.orbit_geom()
        W, H = self.width(), self.height()
        acc = self.planet_accent()
        p.setOpacity(1.0)
        p.setPen(Qt.NoPen)
        if ball is not None:                                   # the ball rises from below the screen
            q = ball ** 1.7
            by = (H + 70) + (cy - (H + 70)) * q
            rb = 14 + 16 * ball
            for k in range(9, 0, -1):                          # trail, below the ball
                c = QColor(acc)
                c.setAlpha(int(110 * (1 - k / 10)))
                p.setBrush(c)
                rk = rb * (1 - 0.08 * k)
                p.drawEllipse(QPointF(cx, by + k * rb * 0.9), rk, rk)
            g0, g1 = QColor(acc), QColor(acc)
            g0.setAlpha(150)
            g1.setAlpha(0)
            glow = QRadialGradient(QPointF(cx, by), rb * 3.2)
            glow.setColorAt(0, g0)
            glow.setColorAt(1, g1)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF(cx, by), rb * 3.2, rb * 3.2)
            core = QRadialGradient(QPointF(cx - rb * 0.3, by - rb * 0.3), rb * 1.3)
            core.setColorAt(0, QColor(255, 255, 255))
            core.setColorAt(1, acc)
            p.setBrush(QBrush(core))
            p.drawEllipse(QPointF(cx, by), rb, rb)
            return
        fl = max(0.0, 1.0 - b / 0.18)                          # impact flash
        if fl > 0:
            c0, c1 = QColor(255, 255, 255, int(190 * fl)), QColor(255, 255, 255, 0)
            flash = QRadialGradient(QPointF(cx, cy), H * 0.7)
            flash.setColorAt(0, c0)
            flash.setColorAt(1, c1)
            p.setBrush(QBrush(flash))
            p.drawEllipse(QPointF(cx, cy), H * 0.7, H * 0.7)
        rmax = math.hypot(W, H) * 0.6                          # shockwave rings
        p.setBrush(Qt.NoBrush)
        for speed, wd, squash in ((1.0, 5.0, 1.0), (0.75, 3.0, 0.4)):
            u = min(1.0, b * speed * 1.15)
            alpha = int(210 * (1 - u) ** 1.5)
            if alpha > 2:
                rad = rmax * (1 - (1 - u) ** 2)
                p.setPen(QPen(QColor(255, 255, 255, alpha), wd * (1 - u) + 1))
                p.drawEllipse(QPointF(cx, cy), rad, rad * squash)
        p.setPen(Qt.NoPen)                                     # sparks
        eo = 1 - (1 - min(1.0, b * 1.1)) ** 3
        al = max(0.0, 1.0 - b) ** 1.4
        if al >= 0.02:
            for ang, spd, sz in self.intro["sparks"]:
                dist = spd * eo
                p.setBrush(QColor(255, int(170 + 70 * al), int(60 + 120 * al), int(255 * al)))
                rs = sz * (0.6 + al * 0.6)
                p.drawEllipse(QPointF(cx + math.cos(ang) * dist, cy + math.sin(ang) * dist * 0.75), rs, rs)

    # ---- the planet (the applied wallpaper) and its orbit ----
    def _draw_cards(self, p, group):
        W, drawn = self.width(), 0
        for it in group:
            _, x, _, w, _, _ = it
            if x + w < 0 or x > W:
                continue                         # off-screen: don't decode its thumbnail at all
            self.draw_item(p, *it)
            drawn += 1
        return drawn

    def draw_orbit(self, p, front, k=1.0):
        """Faint orbit ring: far half behind the planet, near half in front of it."""
        cx, cy, _, rx, ry = self.orbit_geom()
        if k < 0.02:
            return
        rx, ry = rx * k, ry * k
        path = QPainterPath()
        steps, start = 90, (0.0 if front else math.pi)            # near half: sin(phi) >= 0 (lower on screen)
        for k in range(steps + 1):
            phi = start + math.pi * k / steps
            pt = QPointF(cx + rx * math.cos(phi), cy + ry * math.sin(phi))
            if k == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        p.setOpacity(1.0)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, int((44 if front else 22) * min(1.0, k))), 1.5))
        p.drawPath(path)

    def planet_accent(self):
        """Dominant tint of the applied wallpaper, used for the planet's atmosphere."""
        key = str(self.home)
        c = self._acc.get(key)
        if c is None:
            c = QColor(120, 170, 255)
            try:
                pm = self.thumb(self.home) if self.home in self.keys else None
                if pm:
                    px = pm.toImage().scaled(1, 1, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).pixelColor(0, 0)
                    c = QColor.fromHsv(max(0, px.hsvHue()), min(255, px.hsvSaturation() + 60), 235)
            except Exception:
                pass
            self._acc[key] = c
        return c

    def _planet_pixmap(self, D, acc):
        """The centre black hole: event horizon, lensed halo and a tilted accretion disk (back half behind the
        hole, front half across it), painted once and cached. The glow follows the applied wallpaper's colour
        unless PLANET_HUE is set."""
        dpr = self.devicePixelRatioF()
        S = max(8, round(D * dpr))
        key = (S, acc.rgb(), PLANET_HUE)
        if self._planet_pm is not None and self._planet_key == key:
            return self._planet_pm
        E = round(S * 1.4)
        R, c = S / 2.0, E / 2.0
        hue = (PLANET_HUE % 360) / 360.0 if PLANET_HUE is not None else max(0.0, acc.hsvHueF())

        def hsv(h, sat, val):
            return QColor.fromHsvF(h % 1.0, max(0.0, min(1.0, sat)), max(0.0, min(1.0, val)))

        def al(col, a):
            col = QColor(col)
            col.setAlpha(a)
            return col

        hot, mid, edge = hsv(hue + 0.02, 0.20, 1.0), hsv(hue, 0.88, 1.0), hsv(hue - 0.03, 0.95, 0.55)
        rh, ro, tilt = R * 0.46, R * 1.32, 0.27           # horizon radius / disk radius / disk squash
        ctr = QPointF(c, c)

        disk = QPixmap(E, E)                              # the accretion disk (one side brighter: relativistic beaming)
        disk.fill(Qt.transparent)
        q = QPainter(disk)
        q.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        q.setPen(Qt.NoPen)
        q.translate(c, c)
        q.scale(1.0, tilt)
        ri = rh * 1.15 / ro
        dg = QRadialGradient(QPointF(0, 0), ro)
        dg.setColorAt(0.0, al(hot, 0))
        dg.setColorAt(ri - 0.01, al(hot, 0))
        dg.setColorAt(ri, al(hot, 255))
        dg.setColorAt(0.55, al(mid, 245))
        dg.setColorAt(0.78, al(edge, 150))
        dg.setColorAt(1.0, al(edge, 0))
        q.setBrush(QBrush(dg))
        q.drawEllipse(QPointF(0, 0), ro, ro)
        q.resetTransform()
        q.setCompositionMode(QPainter.CompositionMode_DestinationOut)
        fade = QLinearGradient(c - ro, 0, c + ro, 0)
        fade.setColorAt(0.0, QColor(0, 0, 0, 170))
        fade.setColorAt(0.5, QColor(0, 0, 0, 40))
        fade.setColorAt(1.0, QColor(0, 0, 0, 0))
        q.setBrush(QBrush(fade))
        q.drawRect(0, 0, E, E)
        q.end()

        gl = QPixmap(E, E)                                # ambient light around everything: its own layer, so it can breathe
        gl.fill(Qt.transparent)
        q = QPainter(gl)
        q.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        q.setPen(Qt.NoPen)
        glow = QRadialGradient(ctr, R * 1.4)
        glow.setColorAt(0.0, al(mid, 0))
        glow.setColorAt(0.28, al(mid, 80))
        glow.setColorAt(0.50, al(mid, 34))
        glow.setColorAt(1.0, al(mid, 0))
        q.setBrush(QBrush(glow))
        q.drawEllipse(ctr, R * 1.4, R * 1.4)
        q.end()

        pm = QPixmap(E, E)
        pm.fill(Qt.transparent)
        q = QPainter(pm)
        q.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        q.setPen(Qt.NoPen)
        rl = rh * 2.0                                     # light of the far side of the disk, bent around the hole
        halo = QRadialGradient(ctr, rl)
        halo.setColorAt(0.0, al(hot, 0))
        halo.setColorAt(0.47, al(hot, 0))
        halo.setColorAt(0.52, al(hot, 235))
        halo.setColorAt(0.60, al(mid, 150))
        halo.setColorAt(0.78, al(edge, 50))
        halo.setColorAt(1.0, al(edge, 0))
        q.setBrush(QBrush(halo))
        q.drawEllipse(ctr, rl, rl)
        y0 = int(c)
        q.setClipRect(QRect(0, 0, E, y0))                 # far half of the disk: goes behind the hole
        q.drawPixmap(0, 0, disk)
        q.setClipping(False)
        q.setBrush(QColor(0, 0, 0))                       # the event horizon
        q.drawEllipse(ctr, rh, rh)
        q.setBrush(Qt.NoBrush)
        q.setPen(QPen(al(hot, 235), max(1.5, rh * 0.045)))     # photon ring
        q.drawEllipse(ctr, rh * 1.01, rh * 1.01)
        q.setPen(Qt.NoPen)
        q.setClipRect(QRect(0, y0, E, E - y0))            # near half of the disk: sweeps across the hole
        q.drawPixmap(0, 0, disk)
        q.setClipping(False)
        q.end()
        self._planet_pm, self._planet_key = pm, key
        self._planet_glow, self._planet_geo = gl, (rh, tilt, E, hot, mid)
        return pm

    def draw_planet(self, p, k=1.0):
        cx, cy, D, _, _ = self.orbit_geom()
        if D * k < 4:
            return
        pm = self._planet_pixmap(D, self.planet_accent())
        dpr = self.devicePixelRatioF()
        ext = pm.width() / dpr * k                        # logical size of the glow canvas
        x0, y0 = cx - ext / 2, cy - ext / 2
        if k == 1.0:                                      # at rest: whole device pixels, so it stays sharp
            x0, y0 = round(x0 * dpr) / dpr, round(y0 * dpr) / dpr
        t = time.perf_counter() - self._bh_t0
        breath = 0.5 + 0.5 * math.sin(t * 2 * math.pi / 5.5)     # slow 0..1 swell (about 5.5 s per breath)
        gl = self._planet_glow
        if gl is not None:                                # glow swells ~5 % and dims ~20 % at its lowest
            gs = ext * (0.975 + 0.05 * breath)
            p.setOpacity(0.80 + 0.20 * breath)
            p.drawPixmap(QRectF(cx - gs / 2, cy - gs / 2, gs, gs), gl, QRectF(gl.rect()))
        p.setOpacity(1.0)
        p.drawPixmap(QRectF(x0, y0, ext, ext), pm, QRectF(pm.rect()))
        self._draw_hot_spot(p, x0, y0, ext, t)

    def _draw_hot_spot(self, p, x0, y0, ext, t):
        """A soft knot of bright gas circling the accretion disk: stronger on the approaching (right) side,
        hidden while it passes behind the hole. One lap takes 7 s."""
        geo = self._planet_geo
        if geo is None:
            return
        rh, tilt, E, hot, mid = geo
        s = ext / E
        th = t * 2 * math.pi / 7.0
        c, sn = math.cos(th), math.sin(th)
        px, py = x0 + (E / 2 + rh * 1.32 * c) * s, y0 + (E / 2 + rh * 1.32 * tilt * sn) * s
        a = 150 * (0.55 + 0.45 * c)
        rad = rh * 0.34 * s
        g = QRadialGradient(QPointF(0, 0), rad)
        for pos, col, f in ((0.0, hot, 1.0), (0.45, mid, 0.45), (1.0, mid, 0.0)):
            col = QColor(col)
            col.setAlpha(int(a * f))
            g.setColorAt(pos, col)
        p.save()
        if sn < 0:                                        # far side of the disk: the hole covers it
            keep, hole = QPainterPath(), QPainterPath()
            keep.addRect(QRectF(x0, y0, ext, ext))
            hole.addEllipse(QPointF(x0 + ext / 2, y0 + ext / 2), rh * s, rh * s)
            p.setClipPath(keep.subtracted(hole), Qt.IntersectClip)
        p.setOpacity(1.0)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.translate(px, py)
        p.scale(1.0, 0.62)                                # flattened along the disk
        p.drawEllipse(QPointF(0, 0), rad, rad)
        p.restore()

    def _go_transition(self):
        self.hide()
        self.transition.start()

    def draw_toolbar(self, p):
        """Filter bar: one floating capsule - [ label pill | heart ] | colour dots | (search)."""
        dot, gap, pad, ch, chip_w, div = 20, 14, 8, 32, 112, 18
        fw = 320 * self.search_t
        n = len(COLORS)
        total = (pad * 2 + chip_w + 6 + ch + div + n * dot + (n - 1) * gap +
                 ((div + fw) if fw > 1 else 0))
        x0, y0 = (self.width() - total) / 2, self.height() * 0.085
        self.bar_rect = QRectF(x0, y0, total, ch + pad * 2)
        rad = self.bar_rect.height() / 2
        filt = self.eff_filt()
        accent = dict(COLORS).get(filt)                      # hex of the active colour filter, if any

        # capsule: soft shadow, dark body, hairline rim
        p.setPen(Qt.NoPen)
        for i, a in enumerate((12, 8, 5)):
            g = 3 + i * 4
            p.setBrush(QColor(0, 0, 0, a))
            p.drawRoundedRect(self.bar_rect.adjusted(-g, -g + 5, g, g + 5), rad + g, rad + g)
        p.setBrush(QColor(22, 22, 27, 242))
        p.setPen(QPen(QColor(255, 255, 255, 24), 1))
        p.drawRoundedRect(self.bar_rect.adjusted(0.5, 0.5, -0.5, -0.5), rad, rad)

        x, y = x0 + pad, y0 + pad

        # label pill: "All" / "Favourites" / the active colour (tinted, with a dot)
        self.chip_rect = QRectF(x, y, chip_w, ch)
        p.setPen(Qt.NoPen)
        if accent:
            tint = QColor(accent)
            tint.setAlpha(46)
            p.setBrush(tint)
        else:
            p.setBrush(QColor(255, 255, 255, 18))
        p.drawRoundedRect(self.chip_rect, ch / 2, ch / 2)
        label = filt or ("Favourites" if self.fav_only else "All")
        f = QFont("Segoe UI", 10)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        text_rect = QRectF(self.chip_rect)
        if accent:
            p.setBrush(QColor(accent))
            p.drawEllipse(QPointF(self.chip_rect.left() + 17, self.chip_rect.center().y()), 4.5, 4.5)
            text_rect.adjust(24, 0, 0, 0)
        p.setPen(QColor(236, 236, 242))
        p.drawText(text_rect, Qt.AlignCenter, label)
        x += chip_w + 6

        # favourites toggle: round button
        self.fav_rect = QRectF(x, y, ch, ch)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 77, 121) if self.fav_only else QColor(255, 255, 255, 18))
        p.drawEllipse(self.fav_rect)
        hp = heart_path(self.fav_rect.center().x(), self.fav_rect.center().y() + 1, 15)
        if self.fav_only:
            p.setBrush(QColor(255, 255, 255))
            p.setPen(Qt.NoPen)
        else:
            p.setBrush(QColor(255, 77, 121) if self.favs else Qt.NoBrush)
            p.setPen(QPen(QColor(255, 77, 121) if self.favs else QColor(150, 150, 162), 1.8))
        p.drawPath(hp)
        x += ch

        # divider
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawLine(QPointF(x + div / 2, y + 6), QPointF(x + div / 2, y + ch - 6))
        x += div

        # colour dots: small circles, the active one gets a ring, the others fade back
        self.dot_rects = []
        for name, hexc in COLORS:
            r = QRectF(x, y + (ch - dot) / 2, dot, dot)
            self.dot_rects.append((QRectF(x - gap / 2, y, dot + gap, ch), name))
            active = filt == name
            p.setOpacity(0.4 if (filt and not active) else 1.0)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(hexc))
            p.drawEllipse(r)
            if active:
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(hexc), 2))
                p.drawEllipse(r.adjusted(-4, -4, 4, 4))
            p.setOpacity(1.0)
            x += dot + gap
        x -= gap

        if fw > 1:
            p.setPen(QPen(QColor(255, 255, 255, 30), 1))
            p.drawLine(QPointF(x + div / 2, y + 6), QPointF(x + div / 2, y + ch - 6))
            x += div
            f = QRectF(x, y, fw, ch)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 18))
            p.drawRoundedRect(f, ch / 2, ch / 2)
            p.save()
            p.setClipRect(f)
            mx, my = f.left() + 20, f.center().y() - 2
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(200, 200, 210), 2))
            p.drawEllipse(QPointF(mx, my), 6, 6)
            p.drawLine(QPointF(mx + 4.5, my + 4.5), QPointF(mx + 10, my + 10))
            p.setFont(QFont("Segoe UI", 11))
            p.setPen(QColor(245, 245, 250))
            if self.sel_all and self.query:
                qt_ = p.fontMetrics().elidedText(self.query, Qt.ElideLeft, int(max(10, 320 - 40 - 52)))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(70, 110, 200, 170))
                p.drawRoundedRect(QRectF(f.left() + 40, f.center().y() - 11,
                                         p.fontMetrics().horizontalAdvance(qt_) + 2, 22), 3, 3)
                p.setPen(QColor(245, 245, 250))
            text = self.query + ("|" if self.caret else " ")
            text = p.fontMetrics().elidedText(text, Qt.ElideLeft, int(max(10, 320 - 40 - 52)))
            p.drawText(QRectF(f.left() + 40, f.top(), 320 - 92, ch),
                       Qt.AlignLeft | Qt.AlignVCenter, text)
            p.setPen(QColor(130, 130, 140))
            p.drawText(QRectF(f.left() + 320 - 56, f.top(), 48, ch),
                       Qt.AlignRight | Qt.AlignVCenter, str(len(self.items)))
            p.restore()

    # ---- clipboard / undo ----
    def copy_query(self):
        if self.query:
            QGuiApplication.clipboard().setText(self.query)

    def paste_query(self, was_all):
        t = " ".join(QGuiApplication.clipboard().text().split())      # one line, tidy whitespace
        if t:
            self.set_query(t if was_all else self.query + t)

    def undo_query(self):
        if self.undo_stack:
            self.redo_stack.append(self.query)
            self.set_query(self.undo_stack.pop(), record=False)

    def redo_query(self):
        if self.redo_stack:
            self.undo_stack.append(self.query)
            self.set_query(self.redo_stack.pop(), record=False)

    # ---- typed-text history (Up / Down) ----
    def hist_push(self, text):
        t = (text or "").strip()
        if not t:
            return
        if t in self.hist:
            self.hist.remove(t)
        self.hist.append(t)
        del self.hist[:-HISTORY_MAX]
        self.hist_i = None
        try:
            save_json(HISTORY_FILE, self.hist)
        except Exception as ex:
            log(f"history save failed: {ex!r}")

    def hist_nav(self, step):
        """-1 (Up) = older text, +1 (Down) = newer; past the newest restores what you were typing."""
        if not self.hist:
            return
        if self.hist_i is None:
            if step > 0:
                return
            self.hist_draft = self.query
            self.hist_i = len(self.hist)
        i = self.hist_i + step
        if i >= len(self.hist):
            self.hist_i = None
            self.set_query(self.hist_draft)
            return
        self.hist_i = max(0, i)
        self.set_query(self.hist[self.hist_i])

    # ---- input ----
    def keyPressEvent(self, e):
        if self.ach_mode:
            if e.key() not in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
                self.ach_mode = False
                self.update()
            return
        if self.help_mode:
            if e.key() not in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
                self.help_mode = False
                self.update()
            return
        if self.crop_mode:
            self.crop_key(e)
            return
        k, mods = e.key(), e.modifiers()
        was_all = self.sel_all
        if k not in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            self.sel_all = False
        if k not in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            self.hist_i = None
        ctrl = bool(mods & Qt.ControlModifier)
        if k == Qt.Key_A and ctrl:
            if self.query:
                self.sel_all = True
                self.update()
        elif k == Qt.Key_C and ctrl:
            self.sel_all = was_all          # copying keeps the selection highlight
            self.copy_query()
            self.update()
        elif k == Qt.Key_V and ctrl:
            self.paste_query(was_all)
        elif k == Qt.Key_Z and ctrl and not (mods & Qt.ShiftModifier):
            self.undo_query()
        elif (k == Qt.Key_Y and ctrl) or (k == Qt.Key_Z and ctrl and (mods & Qt.ShiftModifier)):
            self.redo_query()
        elif k == Qt.Key_Escape:
            if self.query:
                self.hist_push(self.query)
                self.set_query("")
            else:
                self.dismiss()
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self.hist_push(self.query)
            if not self.run_command():
                self.apply()
        elif k == Qt.Key_Left:
            self.go(self.sel - 1)
        elif k == Qt.Key_Right:
            self.go(self.sel + 1)
        elif k == Qt.Key_Up:
            if LAYOUT == "canvas" and not self.query and self.hist_i is None:
                self.canvas_move(0, -1)
            else:
                self.hist_nav(-1)
        elif k == Qt.Key_Down:
            if LAYOUT == "canvas" and not self.query and self.hist_i is None:
                self.canvas_move(0, 1)
            else:
                self.hist_nav(1)
        elif k == Qt.Key_Home:
            n = len(self.items) or 1
            self.go(self.sel - self.sel % n)
        elif k == Qt.Key_End:
            n = len(self.items) or 1
            self.go(self.sel - self.sel % n + n - 1)
        elif k == Qt.Key_PageUp:
            self.go(self.sel - 5)
        elif k == Qt.Key_PageDown:
            self.go(self.sel + 5)
        elif k == Qt.Key_Backspace:
            self.set_query("" if was_all else self.query[:-1])
        elif k == Qt.Key_Space and not self.query:
            self.toggle_fav()
        elif k == Qt.Key_F and (mods & Qt.ControlModifier):
            self.toggle_fav()
        elif k == Qt.Key_B and ctrl:                    # achievements
            self.ach_mode = True
            self.update()
        else:
            t = e.text()
            if (t and t.isprintable() and not (mods & (Qt.ControlModifier | Qt.AltModifier))
                    and not (t == " " and not self.query)):
                self.set_query(t if was_all else self.query + t)

    def wheelEvent(self, e):
        d = e.angleDelta().y() or e.angleDelta().x()
        if self.help_mode or self.ach_mode:
            return
        if self.crop_mode:
            if d and self.crop and not self.crop.get("busy"):
                self.crop_zoom(0.92 if d > 0 else 1 / 0.92)
            return
        if d:
            if LAYOUT == "canvas":                     # wheel = up/down the wall, sideways wheel / Shift+wheel = left/right
                ax, ay = e.angleDelta().x(), e.angleDelta().y()
                if abs(ax) > abs(ay) or (e.modifiers() & Qt.ShiftModifier):
                    self.canvas_move(-1 if (ax or ay) > 0 else 1, 0)
                else:
                    self.canvas_move(0, -1 if ay > 0 else 1)
            else:
                self.go(self.sel + (-1 if d > 0 else 1))

    def mouseMoveEvent(self, e):
        pt = e.position()
        if self.crop_mode:
            c = self.crop
            if not c or c.get("busy"):
                return
            if self.drag is None:
                corner = self.crop_corner_at(pt)
                if corner in ("tl", "br"):
                    self.setCursor(Qt.SizeFDiagCursor)
                elif corner in ("tr", "bl"):
                    self.setCursor(Qt.SizeBDiagCursor)
                elif self.crop_sel().contains(pt):
                    self.setCursor(Qt.SizeAllCursor)
                else:
                    self.unsetCursor()
                return
            s, rect = c["s"], c["rect"]
            if self.drag[0] == "move":
                _, x0, y0, rx0, ry0 = self.drag
                self.crop_clamp(rx0 + (pt.x() - x0) / s, ry0 + (pt.y() - y0) / s, c["rw"])
            else:
                _, corner, anchor = self.drag
                asp = c["aspect"]
                rw = max(abs(pt.x() - anchor.x()), abs(pt.y() - anchor.y()) * asp) / s
                ax, ay = (anchor.x() - rect.left()) / s, (anchor.y() - rect.top()) / s
                right, bottom = corner in ("tr", "br"), corner in ("bl", "br")
                rw = min(rw, (c["iw"] - ax) if right else ax,
                         ((c["ih"] - ay) if bottom else ay) * asp)
                self.crop_clamp(ax if right else ax - rw, ay if bottom else ay - rw / asp, rw)
            return
        self.set_hover(self.badge_rect.contains(pt))

    def mouseReleaseEvent(self, e):
        self.drag = None

    def mousePressEvent(self, e):
        pt = e.position()
        if self.ach_mode:
            self.ach_mode = False
            self.update()
            return
        if self.help_mode:
            self.help_mode = False
            self.update()
            return
        if self.crop_mode:
            c = self.crop
            if not c or c.get("busy"):
                return
            if e.button() == Qt.RightButton:
                self.crop_cancel()
            elif e.button() == Qt.LeftButton:
                corner = self.crop_corner_at(pt)
                sel = self.crop_sel()
                if corner:
                    anchor = {"tl": sel.bottomRight(), "tr": sel.bottomLeft(),
                              "bl": sel.topRight(), "br": sel.topLeft()}[corner]
                    self.drag = ("resize", corner, anchor)
                elif sel.contains(pt):
                    self.drag = ("move", pt.x(), pt.y(), c["rx"], c["ry"])
            return
        if e.button() == Qt.RightButton:
            self.dismiss()
            return
        if e.button() == Qt.LeftButton and self.badge_rect.contains(pt):
            self.icon_clicks += 1
            save_setting(icon_clicks=self.icon_clicks)
            self.snap_spin()                             # spinning icon snaps back upright on click
            self.bounce()
            self.check_achievements()                    # after the bounce, so its chime is the sound that plays
            self._update_badge()
            return
        if self.chip_rect.contains(pt):
            self.set_filter(None)
            return
        for rect, name in self.dot_rects:
            if rect.contains(pt):
                self.set_filter(None if self.filt == name else name)
                return
        if self.fav_rect.contains(pt):
            self.toggle_fav_only()
            return
        if self.bar_rect.contains(pt):
            return
        if self.heart_rect.contains(pt):
            self.toggle_fav()
            return
        if LAYOUT == "canvas":
            for i, x, y, w, h, d in sorted(self.layout_items(), key=lambda r: r[5]):    # nearest the camera = on top
                if QRectF(x, y, w, h).contains(pt):
                    if d < 0.5:
                        self.apply()
                    else:
                        c, r = self._cells[i]
                        self.canvas_move(c - self._cell[0], r - self._cell[1])
                    return
            self.dismiss()
            return
        cx, cy, D, _, _ = self.orbit_geom()
        on_planet = math.hypot(pt.x() - cx, pt.y() - cy) <= D / 2
        for i, x, y, w, h, d in sorted(self.layout_items(), key=lambda r: -self._depth.get(r[0], 0.0)):
            z = self._depth.get(i, 1.0)
            if (on_planet and z < 0) or self._fade.get(i, 1.0) < 0.3:
                continue                                           # hidden behind the planet / fading out
            hit = (QRectF(x, y, w, h).contains(pt) if w > h * 1.05
                   else math.hypot(pt.x() - (x + w / 2), pt.y() - (y + h / 2)) <= min(w, h) / 2)
            if hit:
                if i == self.sel:
                    self.apply()
                else:
                    self.go(i)
                return
        if on_planet:
            return
        self.dismiss()

    # ---- apply ----
    def apply(self, override=None):
        """Apply the selected wallpaper (or `override`: a cropped copy of it, deleted afterwards)."""
        if not self.items or self.applying:
            return
        self.applying = True
        play_sound("apply")
        orig = self.items[self.sel % len(self.items)]
        new = override or orig
        self._tmp_wall = override
        old = current_wallpaper()
        state = load_json(STATE_FILE, {})
        pool = [e for e in EFFECTS if e != state.get("effect")]
        effect = random.choice(pool)
        save_json(STATE_FILE, {"last": str(orig), "effect": effect})
        self.home = orig
        self._safety.start(8000)                        # safety net: never get stuck hidden
        # the hue / CSS update is started by Transition._finish (after the animation), not here
        try:
            self.transition = Transition(old, str(new), self._apply_done, effect)
            self._go_transition()
        except Exception as e:
            log(f"apply failed: {e!r}")
            try:
                set_wallpaper(new)
            except Exception:
                pass
            self._apply_done()

    def grab_focus(self):
        self.raise_()
        self.activateWindow()
        self.setFocus()
        try:        # a window shown from a hotkey sometimes needs this to really get the keyboard
            u = native().u
            u.SetForegroundWindow.argtypes = [ctypes.c_void_p]
            u.SetForegroundWindow(int(self.winId()))
        except Exception:
            pass


# --------------------------------------------------------------------- main
def main():
    def _hook(et, ev, tb):
        import traceback
        log("".join(traceback.format_exception(et, ev, tb)))
    sys.excepthook = _hook
    sys.setswitchinterval(0.002)                     # let helper threads (sound) run sooner while the UI paints
    background = "--background" in sys.argv          # start hidden (use this at login)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    global ACTIVE_DIR
    saved_dir = load_json(SETTINGS_FILE, {}).get("wallpaper_dir")      # set with ;path
    folder = Path(args[0]) if args else Path(saved_dir) if saved_dir else WALLPAPER_DIR
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    files, keys = scan_files(folder)
    if not files:                       # missing/empty folder: let the user choose one instead of giving up
        chosen = QFileDialog.getExistingDirectory(
            None, "Harmony - choose your wallpaper folder",
            str(folder) if folder.is_dir() else str(Path.home()))
        if chosen:
            folder = Path(chosen)
            files, keys = scan_files(folder)
            if files:
                save_json(SETTINGS_FILE, {**load_json(SETTINGS_FILE, {}), "wallpaper_dir": str(folder)})
    if not files:
        QMessageBox.warning(None, "Harmony", f"No images found in:\n{folder}")
        return
    ACTIVE_DIR = folder

    meta = load_json(META_FILE, {})
    cleanup_junk(keys, meta)
    colors = {p: meta[keys[p]] for p in files if keys[p] in meta}

    last = load_json(STATE_FILE, {}).get("last")
    start = 0
    if last:
        try:
            start = files.index(Path(last))
        except ValueError:
            pass

    signals = Signals()
    pool = QThreadPool.globalInstance()
    pool.setMaxThreadCount(min(GEN_THREADS, max(2, (os.cpu_count() or 4) - 1)))
    jobs = [(i, p) for i, p in enumerate(files)
            if not thumb_path(keys[p]).exists() or keys[p] not in meta]

    picker = Picker(files, colors, keys, meta, signals, len(jobs), start, folder)
    picker.inflight = {p for _, p in jobs}
    picker.winId()          # create the native window now so a second launch can find it
    hotkeys = HotkeyFilter(picker.toggle, picker.show_or_focus)
    app.installNativeEventFilter(hotkeys)
    register_hotkey()
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(art_icon(), app)
        tray.setToolTip("Harmony")
        menu = QMenu()
        menu.addAction("Open picker", picker.show_or_focus)
        menu.addAction("Open wallpaper folder", lambda: open_folder(ACTIVE_DIR))
        menu.addSeparator()
        menu.addAction("Quit", picker.quit_app)
        tray.setContextMenu(menu)
        tray.activated.connect(lambda r: picker.show_or_focus()
                               if r == QSystemTrayIcon.Trigger else None)
        tray.show()
        picker.tray, picker.tray_menu = tray, menu           # keep references alive
    if not background:
        picker.summon(rescan=False)
    else:
        picker.idle.start()                              # trim startup memory once things have settled
    for i, p in jobs:       # nearest to the starting wallpaper first
        pool.start(Job(p, keys[p], keys[p] not in meta, signals), -abs(i - start))

    sys.exit(app.exec())


# ------------------------------------------------------------ built-in sounds
# 22 kHz mono WAV clips, base64-encoded (rendered at _SND_BASE_VOLUME; SOUND_VOLUME rescales them).
_SND_B64 = {
    "achievement": (
        "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"
        "6f+v/3r/VP9B/zz/Pf9B/0//dP+4/xYAegDIAOsA3wC1AIEAVAA1AB0ABwDv/9j/xf+z/5n/b/83/wT/8f4T/3D/8/96AOUAIQEvAR4B"
        "/ADVAKcAcwA6AAMA0v+m/3f/P/8C/8/+vv7i/jr/sP8gAGwAiQCAAGgAVgBUAF8AbQBzAHEAZwBTADIAAQDF/47/c/+G/8b/HgBwAKAA"
        "ogB9AEUADQDc/6//gf9S/yv/F/8b/zP/Vf93/5r/yv8PAG0A0gAnAVYBVwE0AQABywCbAG4AOwACAMn/lP9o/z7/Df/S/pn+ef6K/tX+"
        "T//d/1wAuADuAAUBCwEIAfoA3wC1AIQAUwAmAPr/xv+L/1T/M/89/3X/y/8eAFQAXAA9AA8A6v/Z/9z/5//w//H/7P/i/9D/tf+U/3j/"
        "df+b/+7/WQDBAAUBFwH7AMYAjQBcADAAAQDN/5T/ZP9D/zT/MP8x/zn/Uf+F/9b/NwCSAM0A3ADEAJoAcgBWAEUANgAhAAgA7v/V/7n/"
        "kf9b/yD/9v73/jD/nP8eAJcA6wAQARAB+gDZALQAhwBTABsA5/+4/4z/Xf8m//L+1P7h/iT/kP8IAGkAnACeAIEAXwBKAEYATgBYAF0A"
        "WwBRADwAFwDi/6f/ev9y/5j/5v89AIEAmwCJAFkAIQDw/8f/ov9+/1v/Qv88/0n/Yf97/5P/sf/i/ysAigDpAC4BSgE7AQ8B2gCoAHsA"
        "TgAaAOP/rf9//1b/K//3/rv+i/59/qf+Cf+Q/xwAkgDiAA0BHgEeARIB+ADPAJoAZQA0AAkA3f+q/3H/Q/8z/0//lP/q/zEAUwBKACIA"
        "9f/V/8r/zv/Y/+D/5P/n/+X/3P/H/63/m/+m/9j/LQCPAN8ABgH/ANUAngBrAEAAFgDo/7H/ev9P/zT/Kf8m/yr/N/9b/5v/9f9UAKMA"
        "zQDPALUAlAB6AGsAYABPADQAEwDy/9H/q/96/z//Cv/x/gn/Vv/K/0QAqQDlAPkA8ADZALsAlgBpADMA/f/K/5//dv9K/xv/+P7z/h7/"
        "d//r/1YAnACvAJgAbQBIADUANAA9ACAAKgAuACkAFgD0/8T/lf9//5H/0P8oAH4AtgDCAKkAfQBPACkABgDg/7L/gv9b/0L/Ov87/0H/"
        "UP9y/7H/CwB0ANIADQEbAQQB2QCsAIUAYgA8AA8A4P+1/5H/b/9J/xr/6v7P/t3+IP+N/wsAfQDLAPEA+ADsANgAvQCYAGsAOwAQAO3/"
        "zP+l/3f/SP8r/zP/aP+9/xUAVQBpAFYALgAKAPj/+v8HABcAJAAqACkAHAAAANT/pP+F/4v/vf8PAGgAqQDBALEAiQBbADMAEQDu/8L/"
        "k/9o/0r/Pf86/z7/Sv9l/5v/7/9VALgA/gAYAQoB4wC2AI4AawBHAB0A7//D/53/fP9Z/y3//f7a/tr+DP9s/+b/WgCyAOIA8QDrANoA"
        "wgCiAHgASQAcAPj/1/+0/4j/WP81/zH/Wf+m/wAARwBoAF4AOgASAPr/9f8AAA4AHAAlACgAIAAKAOP/tP+O/4j/rf/4/1AAmQC9ALcA"
        "lABnAD0AGwD6/9L/o/92/1T/Qf87/zz/RP9Z/4f/0/82AJwA6wASAQ4B7ADAAJcAdABSACoA/v/R/6r/iP9n/z7/D//n/tz+/v5Q/8L/"
        "NwCWANEA6ADnANsAxwCqAIQAVgApAAEA4v/A/5j/af9B/zP/Tv+R/+j/NgBjAGQARgAcAP7/8//5/wYAFAAfACQAIgARAPH/w/+a/4n/"
        "of/h/zcAhgC2ALsAngByAEgAJQAEAOD/s/+G/2D/SP89/zz/QP9Q/3b/uf8WAH4A1gAJARAB9QDKAKAAfABbADYACwDf/7b/lP90/0//"
        "Iv/3/uH+9P43/6D/FAB5ALwA3QDiANoAyQCxAI4AYwA1AA0A7P/M/6f/ev9P/zj/Rv9+/9H/IwBaAGcAUAAoAAQA8//z////DAAYACAA"
        "IQAXAP3/0/+n/43/mP/O/x4AcgCrALsApwB+AFMALgAOAOz/w/+V/2z/UP9B/zz/Pv9J/2f/ov/5/18AvQD8AA8B/ADUAKkAhABkAEEA"
        "GQDt/8P/oP+B/17/NP8H/+r+8P4k/4H/8v9aAKYAzwDcANcAygC2AJcAbwBCABgA9v/X/7X/iv9e/0D/Qv9u/7r/DgBOAGgAWQA0AA0A"
        "9f/w//j/BAAQABoAHwAaAAUA4f+1/5T/lP+9/wcAWwCdALkArgCJAF4AOAAYAPj/0f+l/3r/Wv9H/z7/Pf9E/1v/jf/d/0AAowDrAAoB"
        "AQHdALMAjABsAEsAJQD7/9D/rP+M/2z/Rf8Z//b+7/4V/2b/0f86AI4AwADTANQAygC5AJ8AegBPACQAAADh/8H/mv9u/0r/Qv9i/6X/"
        "+f9AAGQAYAA/ABcA+v/u//L//f8JABQAGwAbAA0A7v/D/57/k/+w//L/RACMALQAswCUAGkAQQAhAAIA3/+0/4n/Zf9N/0H/Pf9A/1H/"
        "ev/C/yEAhgDYAAMBBAHmALwAlQB0AFUAMQAIAN7/uP+Y/3n/Vf8q/wP/8/4L/07/sf8bAHQArgDJAM4AyAC7AKUAhQBbADAACQDr/8z/"
        "qP9+/1f/Rf9Z/5L/4/8vAF4AZQBKACIAAADu/+3/9v8BAA0AFgAaABIA+f/S/6r/lv+m/97/LQB6AKsAtQCdAHQASwApAAsA6//D/5j/"
        "cf9W/0b/P/8+/0r/av+p/wIAaADBAPgABAHuAMYAnQB7AF0APAAVAOv/xP+j/4X/Y/87/xL/+v4F/zv/lf/9/1kAmgC9AMgAxQC8AKoA"
        "jQBnADwAFAD0/9f/tf+N/2T/S/9T/4L/zf8cAFQAZgBUAC4ACADx/+v/8P/7/wYAEQAXABQAAQDf/7b/m/+g/83/FgBlAJ8AtAClAH8A"
        "VgAyABQA9v/R/6f/fv9f/0z/Qf8+/0T/Xf+T/+b/SQCoAOoAAgH0AM8ApgCDAGUARgAhAPj/0P+u/5D/cf9L/yL/BP8D/yz/e//e/z0A"
        "hQCvAL8AwQC6AK0AlQByAEgAHwD+/+H/wv+c/3L/VP9R/3X/uf8HAEgAZQBcADkAEgD2/+r/6//0/wAACgATABUACADr/8T/o/+e/77/"
        "AABPAJEAsACqAIoAYAA7AB0AAADe/7X/jP9q/1P/Rf8//0H/U/9//8r/KgCMANgA/AD4ANgArwCKAGwATgAsAAQA3f+5/5v/ff9a/zL/"
        "D/8F/yH/ZP/B/yEAbwCgALYAuwC4AK4AmwB7AFQAKwAHAOr/zf+p/4H/Xv9S/2r/pv/0/zgAYABhAEQAHQD8/+v/6P/u//n/AwAOABMA"
        "DAD2/9H/rf+e/7T/7f85AIAAqgCtAJMAawBFACUACQDq/8T/m/92/1v/S/9B/z//S/9v/7H/DABvAMMA8wD5AOAAuQCSAHMAVgA3ABEA"
        "6v/F/6b/if9o/0H/Hf8K/xr/Uf+n/wUAVwCPAKsAtQC0AK4AnwCEAF8ANgARAPP/1/+2/5D/av9X/2T/lf/f/ycAWABkAE4AKAADAO7/"
        "5v/q//L//f8IABAADwD+/93/uP+i/6z/3P8jAG0AoACuAJsAdgBOAC0AEQD1/9H/qf+D/2X/Uf9F/z//Rf9h/5r/7/9RAKsA5wD4AOcA"
        "wgCbAHoAXgBAABwA9v/Q/7D/lP91/1H/K/8S/xb/Qv+O/+r/PgB8AJ8ArQCwAKwAoQCLAGkAQgAbAPz/4P/C/57/d/9d/2D/h//L/xUA"
        "TgBkAFcANAANAPL/5v/m/+z/9v8BAAwADwADAOn/xP+p/6j/zf8OAFkAkwCsAKEAgABYADYAGgD//93/t/+Q/3D/Wf9K/0H/Qv9W/4X/"
        "0/8zAJEA1wD0AOwAywCjAIEAZABIACcAAQDc/7v/nv+B/1//Of8c/xf/Nv95/9D/JgBpAJIApACqAKkAoQCQAHMATQAmAAUA6f/N/6v/"
        "hf9m/2D/fP+4/wEAQABhAF0APwAYAPn/6P/j/+j/8P/7/wYADQAHAPL/0P+x/6j/wf/7/0QAhQCnAKYAiQBjAD8AIQAHAOn/xP+d/3v/"
        "Yf9Q/0T/Qf9N/3P/uP8UAHYAxADtAO4A0wCsAIgAawBQADEADQDo/8b/qf+N/23/SP8n/xr/Lv9m/7f/DQBUAIMAmgCjAKUAoQCUAHsA"
        "WAAxAA4A8v/X/7f/kv9x/2L/dP+n/+7/MQBbAGEASQAjAAAA6//j/+T/6v/1/wAACQAJAPr/3P+7/6r/uP/q/y8AdACfAKgAkgBtAEgA"
        "KQAPAPP/0f+r/4f/a/9W/0j/Qf9H/2X/of/3/1gArgDiAO4A2gC1AJAAcQBXADsAGAD0/9H/s/+Y/3n/Vv80/yD/Kf9W/6D/9f8/AHMA"
        "kACcAJ8AngCVAIEAYgA8ABgA+//g/8P/n/98/2f/b/+Z/9v/IABSAGIAUgAuAAkA8P/j/+H/5f/u//r/BQAJAAAA5v/F/67/s//a/xsA"
        "YQCVAKcAmQB3AFEAMQAXAP3/3f+4/5T/df9e/07/RP9E/1n/i//b/zoAlQDUAOwA3wC+AJgAeABeAEMAIwAAANz/vf+i/4X/ZP9B/yj/"
        "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"
        "FwARAAsABAD9//X/7//q/+P/2//U/9H/1//o////FQAnAC4ALAAlAB0AFgARAAsABAD9//b/8f/r/+X/3v/W/9P/2f/n//3/EwAkACwA"
        "KgAkABwAFgAQAAsABAD+//f/8v/t/+f/4P/Z/9X/2v/n//z/EAAhACkAKQAjABsAFQAQAAsABQD///j/8//u/+n/4v/b/9j/2//o//v/"
        "DgAfACcAJwAhABoAFAAPAAoABQD///n/9P/v/+r/5P/e/9r/3f/o//r/DAAcACQAJQAgABkAEwAPAAoABQAAAPr/9f/x/+z/5v/g/9z/"
        "3v/o//n/CgAaACIAIwAeABgAEgAOAAoABQAAAPv/9v/y/+7/6P/i/97/4P/p//j/CAAXACAAIQAdABcAEgANAAoABQAAAPv/9//z/+//"
        "6v/k/+H/4v/q//f/BwAVAB0AHwAbABYAEQANAAkABQAAAPz/+P/0//D/7P/n/+P/5P/q//f/BQATABsAHQAaABUAEAAMAAkABQAAAP3/"
        "+f/1//L/7v/p/+X/5f/r//f/BAARABkAGwAYABQADwALAAgABQABAP3/+f/2//P/7//r/+f/5//s//f/AwAPABYAGQAXABIADgALAAgA"
        "BQABAP7/+v/3//T/8f/t/+r/6f/t//f/AQANABQAFwAVABEADQAKAAcABAABAP7/+//4//b/8//v/+z/6//v//f/AAALABIAFAATABAA"
        "DAAJAAcABAABAP///P/5//f/9P/x/+7/7f/w//f/AAAJABAAEgARAA4ACwAIAAYABAABAP///P/6//j/9v/z//D/7//x//j/AAAIAA4A"
        "EAAQAA0ACgAIAAYABAABAP///f/7//n/9//0//L/8f/z//j/AAAGAAwADgAOAAwACQAHAAUAAwABAAAA/v/8//r/+P/2//T/8//0//n/"
        "//8FAAoADAAMAAoACAAGAAQAAwABAAAA/v/8//v/+v/4//b/9f/2//r///8EAAgACgAKAAkABwAFAAQAAgABAAAA///9//z/+//5//j/"
        "9//4//v///8DAAYACAAIAAcABQAEAAMAAgABAAAA///+//3//P/7//r/+f/5//z///8CAAUABgAGAAUABAADAAIAAQAAAAAA//////7/"
        "/f/8//v/+//7//3///8BAAMABAAFAAQAAwACAAEAAQAAAAAAAAD//////v/+//3//f/9//7///8AAAIAAwADAAIAAgABAAEAAAAAAAAA"
        "AAAAAAAA////////////////AAAAAAAAAQABAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
    ),
    "tick": (
        "UklGRlYLAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YTILAAAAAD4BpQZuAUwFgf/Y9Mj3R+Sl5r7a/+I7/jgfxxSx"
        "GNwc1xpGBlX49fz32y7oAd1l5nH5BBA6JKgYQxggD5QB4vuX61nib96T5ufucP+VE4obvxnGF3sNsgD5+w7zRO1+5gHlB/VZ//QQ"
        "nxtgF9YSvweOA9v8AvSB7eblr+l386oCShBNGQcZGBHkCc4APvzV9IHumek/6ir0/AJbDhwWuhTUDoUHYQIa+6r0O+4d6wHso/XW"
        "Ag0P7xQZFOwNcQdmAVv8QPZN79/rGu6d9uUCsw3FEp0R1QyuBlMBZfyH9s7wye3976T3NQPpDK4RlxCqCwkG4wBS/Nr2uPEN7zTx"
        "vvjyAtYLExD3DpkKVgXqAHT8f/fR8m/wlvKO+SsDSwvrDskNlwnUBKAAj/wk+MLzofHZ8176FQN/CrsNnQzMCGgEgAC5/Jf4pPTU"
        "8uT0DfsZA8wJuQyQC/YH7gNdAOj8D/l59dnz3vWe+xEDKgm6C5AKNAeEAz4ADv2C+Tj2z/TK9iv8CAOTCNAKpAmJBiMDHgAw/e/5"
        "7va19aH3pvz5Av8H9wnSCOwFzAILAFP9UPqU94b2ZfgW/eUCeAcvCQ4IXgV/Avf/dP2w+jD4SfcX+Xj90gL3BnQIWwfdBDoC5/+W"
        "/Qf7wfj897n5z/28An4Gyge4BmgE/AHa/7b9WvtI+aH4Tvod/qQCDAYsByMG/QPEAc7/1f2o+8X5OfnV+mP+jAKiBZoGmgWcA5IB"
        "xf/y/fH7OvrG+VH7oP50Aj4FEwYdBUQDZQG+/w7+Nfym+kj6wvvX/loC4QSXBaoE9QI8Abj/Kf51/Av7v/op/Af/QQKJBCQFQQSs"
        "AhgBs/9D/rH8aPst+4b8Mf8oAjgEugTiA2sC+ACw/1z+6fy/+5P72/xX/w8C6wNYBIoDLwLbAK3/c/4e/RD88Psp/Xj/9gGkA/4D"
        "OgP5AcEArP+J/lD9W/xG/HD9lP/dAWEDqwPxAsgBqgCr/5/+fv2h/JX8sP2u/8YBIwNfA64CnAGVAKv/s/6p/eH83vzq/cP/rwHp"
        "AhgDcQJ0AYMAq//G/tL9Hf0h/R/+1v+YAbMC1wI5Ak8BcgCs/9n++P1V/V/9T/7n/4IBgQKcAgYCLgFkAK3/6v4b/oj9mP17/vX/"
        "bQFSAmUC2AERAVcAr//6/jz+uP3M/aP+AABZASYCMgKtAfYASwCx/wr/W/7k/fz9xv4KAEYB/QEDAocB3QBBALP/GP94/g7+KP7n"
        "/hIAMwHXAdkBYwHHADgAtf8m/5P+NP5Q/gT/GQAhAbQBsQFDAbMAMAC3/zT/rf5X/nX+H/8fABABlAGNASYBoQAoALr/QP/E/nj+"
        "l/43/yQAAAF1AWwBCwGRACIAvP9M/9r+lv63/k3/KADwAFkBTQHzAIIAHQC//1f/7/6y/tP+YP8rAOIAPwExAdwAdQAYAMH/Yf8C"
        "/8z+7v5y/y0A1AAnARcByABpABMAxP9r/xT/5P4G/4L/LgDGABABAAG2AF4AEADG/3T/JP/6/hz/kP8vALoA+wDqAKUAVAAMAMn/"
        "ff80/w//MP+d/zAArgDoANYAlgBMAAoAy/+G/0L/Iv9D/6n/MACjANYAxACIAEQABwDO/43/UP8z/1P/s/8wAJgAxQCzAHsAPQAF"
        "AND/lf9d/0P/Y/+9/y8AjgC2AKQAcAA2AAMA0v+b/2j/Uv9x/8X/LwCFAKgAlgBlADAAAQDV/6L/c/9g/37/zP8uAHwAmwCJAFwA"
        "KwAAANf/qP99/23/iv/T/y0AdACOAH0AUwAmAAAA2f+u/4f/ef+V/9n/KwBsAIMAcgBLACIA///b/7P/kP+E/5//3v8qAGUAeQBo"
        "AEQAHgD+/93/uP+Y/47/qP/j/ykAXgBvAF8APgAbAP3/3/+9/5//l/+w/+f/JwBXAGYAVwA4ABgA/f/g/8H/p/+g/7j/6/8mAFEA"
        "XgBPADIAFQD8/+L/xf+t/6f/vv/u/yQASwBXAEgALgATAPz/5P/J/7P/r//F//H/IwBGAFAAQgApABEA/P/l/83/uf+1/8r/9P8h"
        "AEEASQA8ACUADwD8/+f/0P++/7z/0P/2/yAAPQBDADcAIgANAPv/6P/U/8P/wf/U//j/HgA4AD4AMgAeAAsA+//q/9f/yP/G/9n/"
        "+v8dADQAOQAtABsACgD7/+v/2f/M/8v/3P/7/xsAMAA0ACkAGQAJAPv/7P/c/9D/0P/g//3/GgAtADAAJgAWAAcA+//t/9//1P/U"
        "/+P//v8YACoALAAiABQABgD7/+//4f/X/9j/5v///xcAJgAoAB8AEgAGAPv/8P/j/9r/2//p/wAAFgAkACUAHAAQAAUA/P/x/+X/"
        "3f/e/+v/AAAVACEAIgAaAA4ABAD8//H/5//g/+H/7f8AABMAHgAfABcADQADAPz/8v/p/+L/5P/w/wEAEQAbABoAEwALAAMA/P/1"
        "/+3/6f/q//T/AQAOABUAFAAPAAgAAgD9//f/8v/u//D/9/8BAAoADwAPAAsABgABAP7/+v/2//P/9P/6/wEABwALAAoABwAEAAAA"
        "///8//n/9//4//z/AAAFAAcABgAEAAIAAAD///7//P/7//z//v8AAAMABAADAAIAAQAAAAAA//////7///8AAAAAAAABAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    ),
    "hover": (
        "UklGRvITAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0Yc4TAAAAAMIAMANr/8oAyfxk9SX2EO8J+uP+ywcxD8QRUv7V"
        "+cP5r/cE7+XxdwaQBh8WDQy8Azv9gPko+JPsX/Hh+joFew9CDC0HCALs/1b4oPHU8ML02f5xDFgQVgsoB2IB0/1m9/7wkvQC+TAF"
        "/A15DB0JMwJV/4v6yvRh8wb2egCYCW8N3QqYBvsBmfz89/vyxvRz+4cF0QuHC8YHYQNg/pD6uPXE80r3RwDBBz8LZglvBZgADf3U"
        "+Kz1NPYZ/PoDxgktChkH/gLu/in7Svek9dv4CgDxBsIJNAhgBNkAo/3Q+c72WPd0/HMDoAj3CA0GcQI2/+37e/go97r57P8NBpMI"
        "HAfEA6MAxP2H+gH4Z/jt/B0DWAevByYFCgJN/4b8mvlP+KL6+P9DBXkHKwZZA5gAFP5V+xb5c/lM/aoCZwa1Bn4EygFr//T8Z/pY"
        "+Vr7AgCVBHoGXwXlAosAXv7w+wP6Vfqo/VMCigXJBeADigGC/1/9KPs7+vr7AQD5A54FpQR/AnYAlP56/M/6F/v4/QUCzgQGBV4D"
        "VwGS/7f9zfv++oH8AABzA+AEBwQrAmcAxP7x/H/7v/s9/r8BKwRbBOsCKQGh/wT+XPyp+/n8AAD9AjkEfgPhAVkA7v5Z/Rj8UPx5"
        "/oQBnQPGA4cCAQGt/0j+2fw9/GD9AACXAqkDBwOgAU0AE/+0/Z78zvyt/lABIgNFAzEC3wC4/4P+RP29/Lr9AAA/Ai0DoAJpAUMA"
        "M/8C/hH9O/3a/iQBtwLWAuYBwQDC/7b+of0s/Qf+AADyAcACRgI5AToATv9G/nX9mf0C//0AWgJ1AqUBpwDK/+L+8v2N/Ur+AACw"
        "AWMC+QEPATIAZv+B/sz96/0k/9sACgIhAm0BkQDS/wj/OP7g/YX+AAB2ARECtQHrACsAev+0/hf+Mv5B/74AxQHZAT0BfgDY/yn/"
        "df4p/rf+AABEAcsBewHMACUAjP/g/lj+cP5a/6QAiAGaARIBbQDd/0b/qv5n/uP+AAAZAY4BSQGwACAAnP8H/5H+pf5x/44AVAFj"
        "Ae4AXgDi/1//1/6e/gn/AAD0AFkBHQGZABwAqf8o/8L+0/6E/3sAJwE0Ac4AUgDm/3T///7N/ir/AADTACsB9wCEABgAtf9F/+z+"
        "+/6U/2sA/wALAbMARwDq/4f/If/2/kf/AAC3AAMB1gBzABUAv/9e/xH/Hv+j/10A3QDnAJsAPQDt/5f/P/8a/1//AACeAOAAuQBj"
        "ABIAyP9z/zH/PP+v/1AAwADIAIYANQDv/6X/Wf84/3X/AACJAMIAoQBWABAAz/+G/0z/Vv+6/0UApgCuAHQALgDy/7H/b/9T/4f/"
        "AAB3AKgAiwBLAA0A1v+W/2T/bf/D/zwAkACWAGUAKAD0/7z/gv9q/5j/AABnAJIAeQBBAAwA2/+l/3n/gf/M/zQAfQCCAFcAIgD1"
        "/8X/k/9+/6X/AABZAH4AaAA4AAoA4P+x/4v/kv/T/y0AbABxAEsAHgD3/83/ov+P/7L/AABNAG4AWgAwAAkA5f+7/5v/oP/Z/ycA"
        "XgBiAEEAGgD4/9T/rv+e/7z/AABDAF8ATgAqAAcA6P/F/6j/rf/e/yIAUQBVADkAFgD5/9r/uf+s/8X/AAA6AFIARAAkAAYA7P/N"
        "/7T/uP/j/x0ARgBJADEAEwD6/9//w/+3/83/AAAyAEcAOwAfAAUA7v/U/77/wv/n/xkAPQBAACoAEQD7/+P/y//B/9T/AAArAD4A"
        "MwAbAAUA8f/Z/8f/yv/q/xYANQA3ACUADgD8/+f/0v/J/9r/AAAmADUALAAXAAQA8//f/8//0f/t/xMALgAwACAADAD8/+v/2P/R"
        "/9//AAAhAC4AJgAUAAMA9f/j/9X/2P/w/xAAJwApABsACwD9/+3/3v/X/+P/AAAcACgAIQARAAMA9v/n/9v/3f/y/w4AIgAkABgA"
        "CQD9//D/4v/c/+f/AAAYACMAHQAPAAIA+P/q/+D/4v/0/wwAHgAfABUACAD+//L/5v/h/+v/AAAVAB4AGQANAAIA+f/t/+T/5v/1"
        "/woAGgAbABIABwD+//T/6v/l/+7/AAASABoAFQALAAIA+v/w/+j/6f/3/wkAFgAXAA8ABgD+//b/7f/p//H/AAAPABUAEQAJAAEA"
        "+//0/+7/7//5/wYAEAAQAAsABAD///n/9P/x//b/AAAKAA0ACwAFAAEA/f/4//X/9v/8/wQACQAKAAYAAgAAAPz/+f/3//r/AAAF"
        "AAcABgADAAAA///8//r/+//+/wIABQAFAAMAAQAAAP7//f/8//7/AAACAAMAAgABAAAAAAD///7///8AAAAAAQABAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMgA6wCi"
        "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"
        "//f///8IAAoABgABAP7/+f/4//z/AwAIAAYAAgAAAP3/+v/7/wAABAAFAAMAAAD///z//P/+/wEABAADAAEAAAD///3//v8AAAIA"
        "AgABAAAAAAD/////AAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAA="
    ),
    "bounce": (
        "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"
        "5ACQADMA4f+I/y3/Cv9W////qAD0ANIAeQAgAM//dP8h/xT/eP8oAMEA8gC+AGIADQC8/2H/GP8j/57/UADUAOoApwBMAPv/qf9O"
        "/xT/Of/I/3YA4QDdAJAANwDp/5T/Pf8W/1b/8/+XAOcAzAB4ACIA1v+A/y//Hv94/x4AswDmALcAYAAPAML/a/8l/y3/n/9JAMgA"
        "3wCgAEkA/P+u/1f/IP9D/8r/cADWANIAiAAzAOn/mf9G/yH/Yf/4/5MA3ADAAG8AHgDV/4P/N/8q/4X/JACvANsAqgBXAAoAwf9t"
        "/y3/O/+u/1AAwwDSAJIAPwD3/6v/Wf8q/1T/3P93AM8AwwB5ACkA4/+V/0j/Lv91/woAmQDTAK8AYAAUAM7/f/87/zv/nf84ALIA"
        "zgCXAEcAAAC4/2n/NP9Q/8r/YwDDAMEAfgAwAOz/ov9W/zT/b//6/4cAygCvAGQAGgDX/4v/Rv8+/5X/KACkAMcAmABLAAUAwf90"
        "/z3/Uf/B/1UAuAC9AH4AMwDx/6r/YP88/27/8v98AMEAqwBkABwA3P+T/0//RP+U/yEAmwDAAJQASgAGAMX/e/9F/1b/wf9PALAA"
        "tgB7ADIA8v+u/2b/Q/9z//H/dwC6AKUAYAAbAN3/lv9W/0v/mf8iAJcAuQCOAEYABQDG/3//S/9e/8f/UACrAK4AdAAuAPH/r/9q"
        "/0r/fP/4/3gAtACcAFkAFwDb/5b/Wf9U/6T/KQCWALEAhAA/AAEAxP9//1D/af/T/1YAqAClAGoAJwDs/6z/av9S/4r/BAB8AK4A"
        "kQBPABAA1v+T/1z/Xv+0/zUAmACpAHgANQD7/77/fP9V/3j/5f9hAKYAmQBdAB0A5f+m/2n/Wv+c/xcAhACoAIMAQgAHAM7/jf9d"
        "/2z/yv9HAJoAngBpACkA8v+2/3f/XP+L//z/bwCjAIsATgASANv/nf9n/2b/tP8tAIwAnwBzADQA/f/E/4X/YP9//+X/WgCcAJAA"
        "WAAbAOb/q/9y/2X/o/8XAH0AnQB6AD0ABQDP/5L/aP96/9P/RACLAIkAWAAgAPH/v/+N/3r/p/8DAFwAfgBnADcACgDi/7X/kv+Y"
        "/9P/JgBhAGcARgAdAPr/1/+y/6H/uv/5/zkAVwBKACoACgDv/9L/uf+5/9z/EgA8AEMALwAVAP//6v/T/8f/0//4/x4AMQAsABkA"
        "BwD5/+n/3P/b/+z/BgAbAB8AFgAKAAAA+P/v/+v/7//8/wgADgAMAAcAAgD///3//P/9////AAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    ),
    "apply": (
        "UklGRmAwAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YTwwAAAAAP4AMAZLAsEGKAI9+WX9Su3B7gbeINpD5qv9dPpN"
        "DW8hUyogGzMO0BKF9lAAWext4ZXbl99r8DD0BQvkGBYbRhxeD1oHpQFoAE32Pu3c6KPjmuTE8jcACgtEGGEbCxsaE1gIFgYI+hv1"
        "xO8m5v7l7ue69SEEHBBXGTEYpxVwDmcHuwAO/Mf1fO026R/n1u7P+dcHRhJ9FjsW/xEQCrkEh/7C+Gnyru0c6bLqDPIS/u4IUBLa"
        "FVYU/g7kCJoCmf0Y+Lbypu3S6r3t1vXwAMALqxIBFN8Q0AsnBjsBpvxE97nxoe337N/w3/laBHcNXRI9EpgOSAlfBKT/G/sp9kHx"
        "Nu7K7g308vynBjEOUhFTEDsMNweqAon+Nfpy9VHxVe8j8Tn38v+jCIwOOBAzDvIJYwVjAYD9UPn19GfxjPCM8yn6kgIQCmsOzg4i"
        "DP4H4AMrAIz8mvig9OrxFPLz9df8qwT0CuMNPw0pCjoGhAIv/7/79fd49J3yx/NX+EH/VwZbCw0NowtjCLgEYwFP/gP7efeI9Ivz"
        "mfWq+l8BkgdgC/8LBQrDBmkDbQCM/WL6JffQ9Kv0fPfX/CUDZAgNC80KdwhSBU0Cmv/f/Nv5+/ZO9fb1YfnQ/pIE1Ah3CokJBAcR"
        "BF4B5P5G/HD5+/b79V73OvuNAKYF7wiwCUMIswX+ApIARP7B+yT5JvfR9tb4+PwIAmQGwwjICAcHhgQUAuX/t/1R+/f4e/fK91P6"
        "k/49A9QGXgjNB90FfwNNAU//O/32+uz49vfd+Mn7AAAsBP8GzQfNBssEnAKlAM3+zvyy+gL5lPgA+i/9OgHXBO4GHwfSBdYD2gEV"
        "AFn+cfyH+jr5T/kr+3v+PwJCBawGXgbjBP4CNgGb//T9JPx1+pH5IPpT/KX/DAN1BUUGlgUGBEMCqgAw/5v96Pt++gT6Aftw/agA"
        "owN2BcMFzwQ+A6MBNADS/k39wPuh+o/66ft7/oMBBwROBTAFEASOAhsB0P9//g39q/vd+i770vxu/zICPQQGBZQEXgP0AagAeP82"
        "/tn8q/sw+9v7tf1DALYCSgSnBPgDvAJwAUYAK//2/bX8wPuX+4/8jP76ABIDNQQ3BGADLAL/APP/5/7A/Z/86PsP/Eb9Uf+OAUcD"
        "BAS/A9ACrgGgAKv/rP6V/Zr8JPyT/Pr9AAABAlwDvwNEA00CQQFPAG3/d/50/aX8cPwf/ab+lwBTAlQDawPLAtcB4wAKADX/S/5f"
        "/b/8yfyu/UX/FAGGAjQDDwNZAnABlQDQ/wT/Jv5X/en8Lv08/tX/dgGfAgMDrwLuARYBUgCc/9r+Cf5b/SD9mv3F/lEAvwGfAsQC"
        "TwKPAckAGQBv/7X+9v1s/WP9Cf5G/7oA7wGMAn4C8wE6AYgA6f9H/5X+7P2J/bD9ef66/w4BCQJqAjMCngHwAFAAv/8k/33+7P2x"
        "/QL+5v4gAE0BDwI8AugBUAGwACEAmv8G/2v+9v3i/Vn+Tf94AHkBBQIGAp8BCwF6APr/ef/s/mH+Cf4c/rH+rP+/AJMB7gHMAVoB"
        "zgBMANj/Xf/X/l7+Jv5b/gj/AAD2AJ0BzAGRARsBmgAmALn/RP/H/mT+Sv6e/lr/SAAdAZkBpAFXAeIAbQAFAJ//Lv+9/nD+df7j"
        "/qf/hAA2AYoBeAEgAbAARwDp/4f/HP+5/oT+pf4n/+v/tABCAXIBSgHtAIUAJwDQ/3P/D/+7/p/+2f5p/yYA1gBCAVQBHAG/AGAA"
        "DAC7/2H/Bf/D/r/+D/+n/1kA7gA5ATIB8ACWAEEA9f+o/1L/Af/R/uT+Rf/f/4EA+gAoAQ4BxwBzACYA4f+X/0b/Af/k/gz/ef8P"
        "AKAA/QASAeoAoQBUABAAz/+I/z7/Bf/8/jX/q/85ALUA+AD5AMcAgAA6AP3/wP98/zn/D/8Y/1//2P9bAMEA7QDdAKYAYwAkAO3/"
        "sv9y/zj/HP82/4n/AAB2AMYA3QDAAIgASgASAN7/pv9q/zr/Lv9W/7H/IgCJAMQAygClAGwANAACANL/m/9l/0D/Q/93/9X/PwCV"
        "AL0AtACKAFQAIgD1/8b/k/9j/0r/Wv+Y//b/VgCaALEAngByAEAAEgDp/7z/jP9k/1f/c/+4/xIAZwCaAKMAiABcAC4ABQDf/7T/"
        "iP9o/2b/jP/V/yoAcgCWAJMAcwBIAB8A+//W/63/hv9v/3j/pv/w/z4AeACOAIEAXwA3ABIA8f/O/6f/hv94/4v/v/8HAEwAeQCD"
        "AHAATQAoAAcA6f/H/6P/iP+D/5//1/8bAFcAdwB3AF8APQAcAP//4f/B/6H/jP+R/7P/7f8sAF0AcgBqAE8ALwARAPf/2/+8/6D/"
        "k/+f/8f/AAA4AF8AagBcAEEAIwAIAPD/1f+4/6H/m/+v/9r/EABBAF4AYQBPADQAGQABAOr/0P+2/6T/pf+//+z/HgBHAFoAVgBC"
        "ACgAEAD7/+X/zP+1/6n/sP/O//z/KQBKAFUATAA2AB4ACQD1/+D/yf+1/6//vP/e/wgAMQBKAE4AQQAsABYAAgDw/9z/x/+3/7b/"
        "yf/s/xQANgBIAEYANwAiAA8A/v/s/9j/xf+6/7//1f/5/x0AOQBEAD4ALQAaAAgA+f/o/9b/xf+//8j/4f8DACQAOgA/ADYAJQAT"
        "AAMA9f/l/9T/x//E/9L/7f8NACkAOQA5AC0AHQANAAAA8v/i/9L/yf/L/9v/9/8VACwANgAzACYAFgAIAPz/7v/g/9L/zP/S/+X/"
        "AAAbAC0AMwAsAB8AEQAEAPn/7P/e/9P/0P/Z/+7/CAAfAC0ALgAmABkADAAAAPb/6f/d/9T/1f/h//f/DgAiACsAKQAfABMABwD+"
        "//P/5//c/9b/2v/o//7/EwAjACkAJAAaAA4ABAD7//H/5v/c/9n/4P/w/wQAFwAjACUAHwAVAAoAAQD5/+//5f/d/93/5v/3/wkA"
        "GgAiACEAGgAQAAcA///3/+3/5P/f/+H/7P/9/w4AGwAgAB0AFgAMAAQA/f/1/+z/5P/h/+X/8f8BABEAHAAeABkAEQAJAAEA+//z"
        "/+v/5f/k/+r/9/8GABQAGwAbABYADgAGAAAA+f/y/+r/5v/n/+///P8KABUAGgAYABIACgAEAP7/+P/x/+r/5//q//P/AAANABUA"
        "GAAVAA8ACAACAP3/9v/w/+v/6f/u//j/AwAPABUAFgASAAwABQAAAPv/9f/v/+v/6//x//z/BwAQABQAFAAPAAkAAwD///r/9P/v"
        "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"
        "/vP/zAHCApUCtAG4ANz/+P4A/lX9i/3W/rEALwKoAigCOwFZAIz/qv7M/XD9Df6U/0wBXQJoArUB0QAHAEL/Zf6z/bD9qP5EALsB"
        "XAIQAkcBdwDA//z+L/65/RL+TP/cAPsBNAKuAeQAKgB9/7z+DP7f/Y7+7P9QAQ8C8gFMAY8A6f8//4b+Av4l/hj/ewCdAf0BoQHx"
        "AEYArf8F/17+FP6F/qb/8QDCAc8BSwGhAAkAdv/R/kr+Q/73/ioARgHDAY4B+QBdANT/Qf+n/kz+iv5x/50AeAGnAUYBrgAjAKL/"
        "Ef+M/mf+5f7q//YAiQF3AfwAbgDy/3P/6P6E/pr+TP9VADEBfQE7AbgAOADF/0j/yv6Q/uD+tv+uAE8BXAH7AHsACQCc/yD/uv6x"
        "/jX/GQDvAFEBLAG9AEgA4v91/wH/uv7l/pD/cAAWAT4B9gCFAB0AvP9Q/+z+zf4p/+r/swAlARoBvwBVAPj/mf8x/+X+8v51/zoA"
        "4QAdAe4AjAAsANf/ef8a/+3+Jv/E/34A+QAFAb4AXwAJALf/W/8N/wT/ZP8OALAA/ADjAJAAOADr/5r/Q/8N/yr/qP9PAM4A7gC6"
        "AGYAFwDQ/3//M/8a/1z/6/+DANoA1ACRAEEA/P+1/2f/Lf81/5T/KACmANUAtABrACMA4/+d/1b/Mv9a/8//WwC5AMQAkABJAAgA"
        "y/+H/0v/Q/+J/wcAgQC8AKsAbQArAPL/tf90/0r/X/+7/zgAmQCyAI0ATgATAN3/of9o/1T/g//t/18AogCgAG4AMgD+/8r/j/9j"
        "/2f/rf8bAHoAoACIAFEAGwDs/7f/gv9m/4P/2f9BAIkAkwBtADgABwDa/6f/ev9y/6X/AgBeAIwAgQBTACIA9//K/5n/ef+G/8r/"
        "JwBxAIYAagA7AA8A5/+6/4//f/+h//D/RQB5AHgAVAAnAAAA2f+t/4v/jf/A/xIAWgB3AGYAPgAVAPL/y/+j/43/of/h/y8AZgBv"
        "AFMAKwAGAOX/vv+c/5X/uv8AAEUAaABhAD8AGgD6/9j/tP+b/6T/1v8cAFMAZABQAC0ADADu/83/rP+f/7j/8v8yAFoAWgA/AB4A"
        "AADj/8P/qf+p/8//CwBCAFkATQAvABAA9v/Z/7v/qv+4/+f/IgBLAFMAPgAhAAUA7P/Q/7b/sP/L////MgBOAEkAMAAUAPz/4//I"
        "/7X/u//f/xMAPgBLAD0AIgAJAPT/2//C/7j/yf/0/yQAQwBEADAAFwAAAOv/0/+//7//2v8HADEAQgA6ACQADQD5/+T/zf/A/8r/"
        "7P8YADgAPgAvABkABADy/93/yf/E/9f//v8lADoANwAkAA8A/v/r/9f/yP/M/+f/DQAtADgALgAaAAcA9//l/9L/yv/W//b/GgAx"
        "ADMAJAARAAEA8f/f/9D/z//j/wQAJAAyACwAGwAKAPz/6//a/9D/1//x/xEAKQAuACQAEwADAPb/5v/X/9P/4f/+/xsAKwApABsA"
        "DAD///H/4f/W/9n/7f8JACEAKgAiABQABgD6/+z/3v/Y/+H/+P8TACUAJgAbAA0AAQD1/+j/3P/b/+r/AgAaACUAIQAVAAgA/f/x"
        "/+T/3P/h//T/DAAeACMAGwAOAAMA+f/t/+L/3v/p//7/EwAgAB8AFQAJAAAA9f/q/+H/4//x/wYAGQAfABoADwAEAPz/8f/n/+L/"
        "6P/6/w4AGwAdABUACgABAPj/7v/m/+X/7/8BABMAGwAZABAABgD+//X/7P/m/+n/9/8IABYAGgAUAAsAAgD7//L/6v/n/+7//v8O"
        "ABgAFwAQAAcAAAD4//D/6f/q//X/BAASABcAEwALAAMA/f/1/+7/6v/u//v/CgAUABUAEAAIAAAA+//z/+z/6//z/wAADgAUABIA"
        "DAAEAP//+P/x/+z/7//5/wYAEAATAA8ACAACAP3/9v/w/+3/8//+/woAEgARAAwABQAAAPv/9P/w//D/+P8CAAwAEAANAAgAAgD/"
        "//r/9f/y//X//f8FAAsADAAJAAQAAAD9//n/9v/2//r/AAAGAAoACQAFAAIAAAD9//r/+P/5//3/AgAGAAcABQADAAAA///9//v/"
        "+v/8/wAAAwAFAAUAAwABAAAA///+//3//f/+/wAAAgADAAIAAQAAAAAA//////7///8AAAAAAQABAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGYEdwHR"
        "AsP6jfrz6wrlDAboEqAjvCJlGoPr6OYU0Sfc2v4HHVsYzRYkFwsEqe2t3zHUk/XWCyIqvCKyCTf/EO886rbdQeMxA5Ad3SCuFEsD"
        "TfU24o3e9+Q4/RUbrCXuEQwEP/uY6QzeTeS2+nEXzCB+GhcM7Pkk75Tjs+SI+MYS3x+7GJIKAgBy847m8uIn8vsNBx55GugNrgAx"
        "9cfniuGu7rkHvhsZG0IPqgJP99Hq5uJN67cDjhc8G24R1wTT+Zbtv+Ss6bb+IhReG9ASVweD/Knwo+aG6IT6HhA5GkgUAQkz/rrz"
        "U+mr5zf27AtwGEcVmwovADf2auvP5zPzDwiLFiUWTwwLAnD4HO5y6GPw1gMpFF4Wyg2sA7X6efBk6XXuBgBtET0WFA8kBX784/Lm"
        "6gjtXPxdDpgVSxCnBj3+PPWs7EPsGPkWC5EUOBEfCLz/X/eL7iHsQPaxBx4T6xGICTIBSvmc8Gzs7PNTBEQRQxLUCo8CDvum8i/t"
        "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"
        "/+//4//l//r/EgAeABcACgD///L/5v/k//X/DgAcABgADAAAAPX/6f/k//L/CQAaABkADgACAPj/7P/l/+7/BAAXABkADwAEAPr/"
        "7//m/+z/AAAUABkAEQAGAPz/8f/o/+v//P8QABgAEgAHAP7/9P/q/+r/+f8MABcAEwAJAAAA9//s/+r/9f8IABYAFAALAAEA+f/v"
        "/+r/8/8EABMAFQAMAAIA+//x/+v/8P8BABEAFQANAAQA/f/z/+z/7//+/w4AFAAPAAUA/v/2/+7/7v/7/wsAEwAQAAcAAAD4/+//"
        "7v/4/wgAEgAQAAgAAAD6//H/7v/2/wUAEAARAAkAAQD7//P/7v/0/wIADgARAAsAAwD9//X/7//y/wAADAARAAwABAD+//f/8f/y"
        "//3/CgAQAAwABQAAAPn/8v/x//r/BwAPAA0ABgAAAPr/9P/x//j/BQAOAA4ABwABAPz/9f/x//f/AgAMAA4ACAACAP3/9//y//X/"
        "AAALAA4ACQADAP7/+P/z//T//v8JAA0ACgAEAP//+v/0//T//P8HAA0ACgAFAAAA+//1//T/+v8EAAwACwAGAAAA/P/3//T/+f8C"
        "AAoACwAGAAEA/f/4//X/+P8AAAkACwAHAAIA/v/5//X/9////wgACwAIAAMA///7//b/9v/9/wYACgAIAAMAAAD8//f/9v/8/wQA"
        "CgAJAAQAAAD9//j/9v/7/wIACQAJAAUAAQD+//n/9//6/wEACAAJAAYAAQD+//r/9//5/wAABgAJAAYAAgD///v/+P/4//7/BQAJ"
        "AAcAAwAAAPz/+f/4//3/BAAIAAcAAwAAAP3/+f/4//z/AgAHAAcABAAAAP7/+v/4//v/AQAHAAcABAABAP//+//5//r/AAAGAAcA"
        "BQABAP///P/5//r///8EAAcABQACAAAA/f/6//r//v8DAAcABgACAAAA/f/6//r//f8CAAYABgADAAAA/v/7//r//P8BAAYABgAD"
        "AAAA///8//r//P8AAAUABgAEAAEA///9//r/+/8AAAQABgAEAAEAAAD9//v/+////wMABQAEAAIAAAD+//v/+//+/wIABQAFAAIA"
        "AAD+//z/+//9/wEABQAFAAIAAAD///z/+//9/wAABAAFAAMAAAD///3/+//8/wAAAwAFAAMAAQAAAP7//P/8////AwAEAAMAAQAA"
        "AP7//P/8////AgAEAAQAAgAAAP///f/8//7/AQAEAAQAAgAAAP///f/8//7/AAADAAQAAgAAAP///v/8//3/AAADAAQAAgAAAAAA"
        "/v/8//3/AAACAAQAAwABAAAA/v/9//3///8CAAMAAwABAAAA///9//3///8BAAMAAwABAAAA///+//3//v8AAAMAAwACAAAAAAD+"
        "//3//v8AAAIAAwACAAAAAAD+//3//v8AAAIAAwACAAAAAAD///3//f8AAAEAAwACAAEAAAD///7//f///wEAAwACAAEAAAD///7/"
        "/f///wAAAgACAAEAAAAAAP7//v/+/wAAAgACAAEAAAAAAP///v/+/wAAAgACAAEAAAAAAP///v/+/wAAAQACAAIAAAAAAP///v/+"
        "////AQACAAIAAQAAAP///v/+////AAACAAIAAQAAAAAA///+////AAACAAIAAQAAAAAA///+////AAABAAIAAQAAAAAA///+////"
        "AAABAAIAAQAAAAAA///+//7/AAABAAIAAQAAAAAAAAD///7///8AAAIAAQAAAAAAAAD///7///8AAAEAAQABAAAAAAD///////8A"
        "AAEAAQABAAAAAAD///////8AAAEAAQABAAAAAAAAAP////8AAAEAAQABAAAAAAAAAP////8AAAAAAQABAAAAAAAAAP////8AAAAA"
        "AQABAAAAAAAAAP///////wAAAQABAAAAAAAAAP///////wAAAQABAAEAAAAAAAAA/////wAAAAABAAEAAAAAAAAA/////wAAAAAB"
        "AAEAAAAAAAAA/////wAAAAABAAEAAAAAAAAA/////wAAAAABAAEAAAAAAAAAAAD/////AAABAAEAAAAAAAAAAAD/////AAAAAAEA"
        "AAAAAAAAAAD/////AAAAAAEAAAAAAAAAAAD/////AAAAAAEAAQAAAAAAAAAAAP//AAAAAAAAAQAAAAAAAAAAAP//AAAAAAAAAQAA"
        "AAAAAAAAAP//AAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAA="
    ),
    "fav": (
        "UklGRmwdAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YUgdAAAAAEABjQWe/ycC5vs58Afx/eEo73r0lwaeGkslEgbS"
        "/bX+q/sy59veRfUD9R8blRnXEzEJCQIzATLsWegg5YfpDv9HDFoWtRWyEYcESPpp80HoxOLx7r//fQ7hGjYYvBHqBkL7vvbV58Hl"
        "k+6p+0UPQxaeF44PgAXI/rbzhOwc6CvuKf1DD54YhBUuDsUDDP7K9V3u8ukj7sv8Tg2xFGUUcgw8BAL9rfa87RHqQO9h/UULSRR4"
        "EwINOgWE/rr2dO+V64fwFP2NCswSKhLGC7gEbv6C91Lw3ezI8In8NAr8EW0RhguzBGb+gvjR8TLurPFW/AwJnBCLENIKXAS+/tb4"
        "oPL87hfyMvwzCKcPhQ+OCmYE9v5z+Y7zFfDL8kT8oQetDskO9gk1BDD//Pl49ATxbPM1/OEGtQ0ADocJIwRo/4X6PfXu8Q70HfxE"
        "BtsMQg0hCQAEh//2+vz1zvKm9CL8qAUFDIUMtgjhA6P/V/ur9przLvUk/CQFPwvYC1MIxQPB/7j7UPdZ9Lf1JvyjBIAKMgv0B6oD"
        "3/8U/Or3DPU39i78LgTPCZYKlgeMA/b/Zvx6+Lf1s/Y5/MEDKAkCCj0HbQMKALP8Afla9in3RvxfA4sIdQnoBlADHAD6/H/58faa"
        "91X8AwP4B+4IlQY0Ay0AO/31+YD3B/hm/LACbgdvCEYGGAM8AHf9Y/oH+G/4efxjAu0G9gf7BfwCSACv/cn6hvjS+Iz8HQJ0BoQH"
        "swXiAlMA4v0o+/34Mfmh/NwBAgYXB24FxwJdABH+gPtu+Yz5t/yhAZgFsQYsBa4CZQA9/tP72Pni+c38awE0BU8G7ASVAmwAZf4g"
        "/Dv6Nfrk/DoB1gTzBbAEfAJyAIr+aPyZ+oP6/PwNAX8EnAV2BGQCdwCs/qr88PrO+hP95AAtBEkFPgRNAnsAy/7o/EP7Fvsr/b8A"
        "4AP7BAkENwJ+AOj+Iv2R+1n7Qv2eAJkDsATXAyECgAAC/1j92vua+1r9fwBWA2oEpwMMAoEAGv+K/R781/ty/WQAFwMoBHgD9wGD"
        "ADD/uP1e/BL8if1LAN0C6QNMA+MBgwBF/+T9m/xJ/KD9NQCmAq4DIgPQAYMAV/8M/tP8fvy2/SEAcwJ2A/oCvgGDAGj/Mf4I/bD8"
        "zf0PAEQCQQPUAqsBggB4/1T+Ov3g/OP9AAAXAg8DrwKaAYEAhv90/mn9Df34/fL/7gHgAowCiQF/AJT/kv6U/Tf9Df7m/8gBswJr"
        "AnkBfgCg/67+vf1g/SH+2/+kAYkCSwJpAXwAqv/H/uT9hv01/tL/gwFiAi0CWgF6ALT/3/4I/qv9Sf7J/2QBPAIQAksBdwC+//X+"
        "Kv7N/Vv+wv9HARkC9QE9AXUAxv8K/0n+7v1u/rz/LAH4AdsBMAFzAM3/Hf9n/gz+f/63/xMB2AHCASMBcADU/y//gv4q/pD+s//8"
        "ALsBqwEWAW0A2v8//5z+Rf6h/q//5gCfAZQBCgFrAOD/Tv+0/l/+sf6s/9MAhQF/Af4AaADl/1z/y/54/sD+qv/AAGwBagHzAGUA"
        "6v9p/+D+j/7P/qj/rwBVAVcB6ABiAO7/df/0/qX+3f6n/58APwFFAd4AYADy/4H/Bv+6/uv+p/+RACoBMwHUAF0A9f+L/xf/zv74"
        "/qb/gwAXASIBygBaAPj/lP8o/+D+Bf+n/3cABAETAcEAVwD7/53/N//y/hH/p/9rAPMABAG4AFUA/f+l/0X/Av8d/6j/YQDjAPUA"
        "sABSAAAArf9S/xL/KP+p/1cA1ADoAKgATwAAALT/Xv8g/zP/qv9OAMYA2wCgAE0AAgC6/2n/Lv89/6v/RgC5AM8AmABKAAQAwP90"
        "/zv/R/+t/z4ArADDAJEARwAFAMb/fv9H/1H/r/83AKAAuACKAEUABgDL/4f/U/9a/7D/MQCVAK4AhABCAAcAz/+Q/17/Yv+y/ysA"
        "iwCkAH4AQAAIANT/mP9o/2v/tP8lAIEAmwB4AD4ACQDY/5//cf9y/7b/IAB4AJIAcgA7AAkA2/+m/3r/ev+4/xwAcACKAGwAOQAK"
        "AN//rf+D/4H/uv8YAGgAggBnADcACgDi/7P/i/+I/73/FABhAHoAYgA1AAsA5P+5/5L/jv+//xEAWgBzAF0AMwALAOf/vv+Z/5T/"
        "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"
        "/28ARAEVAXAA3f89/77+D/82ACgBIAGHAPX/X//V/vj+AAAFASYBnAALAH//7/7r/s7/3gAmAbAAIACc/wz/5f6g/7MAIAHCADQA"
        "tv8q/+f+ef+GABUB0gBHAM7/R//w/lj/WAADAd4AWgDk/2T//v4//ysA7QDnAGwA9/+A/xD/Lf8AANEA6wB9AAgAmf8m/yL/2P+y"
        "AOsAjQAZALD/Pf8e/7T/kADnAJsAKQDF/1T/H/+U/2sA3QCoADkA2P9s/yb/ev9HANAAsgBIAOn/g/8y/2b/IgC9ALkAVgD5/5n/"
        "QP9X/wAApwC8AGQABwCu/1H/Tv/g/44AvABxABQAwP9k/0v/w/9zALkAfAAhANH/d/9M/6r/VgCxAIYALgDg/4r/Uv+V/zkApgCO"
        "ADkA7v+c/1v/hP8bAJcAlABFAPv/rv9n/3n/AACGAJcAUAAFAL7/dP9y/+f/cgCXAFoAEADN/4P/b//P/1wAlABjABoA2v+S/3D/"
        "u/9FAI4AawAkAOf/of91/6r/LQCFAHIALgDy/7D/fP+d/xYAeQB2ADcA/P++/4X/lP8AAGsAeQBAAAQAy/+Q/47/7P9bAHkASAAN"
        "ANf/nP+M/9n/SQB2AFAAFQDi/6j/jf/J/zcAcQBWAB0A7P+0/5H/u/8kAGoAWwAlAPX/wP+W/7H/EQBhAF8ALAD9/8v/nv+q/wAA"
        "VgBgADMAAwDW/6b/pf/w/0kAYAA6AAoA3/+w/6P/4f87AF8AQAARAOj/uv+k/9T/LABbAEUAFwDw/8T/p//J/x0AVQBJAB0A9//N"
        "/6v/wf8OAE4ATAAjAP3/1v+x/7v/AABEAE0AKQACAN7/uP+3//P/OgBNAC4ACADm/8D/tv/n/y8ATAAzAA0A7f/I/7b/3f8jAEkA"
        "NwASAPP/0P+5/9T/FwBEADoAFwD5/9f/vP/O/wsAPgA8ABwA/v/f/8H/yf8AADcAPgAhAAIA5f/H/8b/9v8uAD4AJQAGAOv/zf/F"
        "/+z/JQA8ACkACwDx/9P/xf/k/xwAOgAsAA8A9v/Z/8f/3f8SADYALgATAPr/4P/K/9j/CQAyADAAFgD//+X/zv/U/wAALAAxABoA"
        "AQDr/9L/0v/4/yUAMQAdAAUA8P/X/9H/8P8eADAAIAAIAPT/3P/R/+r/FgAuACMADAD4/+H/0v/k/w8AKwAlAA8A/P/m/9X/4P8H"
        "ACgAJwASAP//6//Y/93/AAAjACcAFQABAO//2//b//r/HgAnABcABADz/9//2v/0/xgAJwAaAAcA9v/j/9r/7v8SACUAHAAJAPr/"
        "5//c/+r/DAAjAB4ADAD9/+v/3v/m/wUAIAAfAA4A///v/+D/5P8AABwAHwAQAAEA8v/j/+L/+/8YAB8AEwADAPb/5v/i//b/EwAf"
        "ABUABQD4/+n/4v/y/w4AHgAWAAcA+//s/+P/7v8JABwAGAAJAP3/8P/l/+z/BAAZABkACwAAAPP/5v/q/wAAFgAZAA0AAAD1/+n/"
        "6P/8/xMAGQAPAAIA+P/r/+j/+P8PABkAEAAEAPr/7v/o//X/CwAYABIABgD8//D/6f/y/wcAFgATAAcA/v/z/+r/8P8DABQAFAAJ"
        "AAAA9f/s/+7/AAASABQACgAAAPj/7v/t//3/DwAUAAwAAgD6/+//7f/6/wwAFAANAAMA+//y/+3/9/8JABMADgAEAP3/9P/u//X/"
        "BgASAA8ABgD+//b/7//z/wMAEAAQAAcAAAD4//D/8v8AAA4AEAAIAAAA+f/x//H//v8MABAACQABAPv/8//x//v/CgAQAAoAAgD8"
        "//X/8f/5/wcADwALAAMA/v/2//H/9/8EAA4ADAAFAP//+P/y//b/AgANAAwABgAAAPn/8//1/wAACwANAAYAAAD7//T/9P/+/wkA"
        "DQAHAAEA/P/2//T//P8IAAwACAACAP3/9//0//r/BgAMAAkAAwD+//j/9P/5/wMACwAJAAQA///6//X/+P8BAAoACgAEAAAA+//2"
        "//f/AAAJAAoABQAAAPz/9//3////BwAKAAYAAQD9//j/9v/9/wYACgAGAAEA/v/5//b//P8EAAkABwACAP//+v/3//v/AwAJAAcA"
        "AwD///v/9//6/wEACAAIAAMAAAD8//j/+f8AAAcACAAEAAAA/f/5//n///8GAAgABQAAAP7/+v/4//7/BQAIAAUAAQD+//r/+P/9"
        "/wMABwAGAAIA///7//n//P8CAAcABgACAAAA/P/5//v/AQAGAAYAAwAAAP3/+v/6/wAABQAGAAMAAAD+//r/+v///wUABgAEAAAA"
        "/v/7//r//v8EAAYABAABAP///P/6//3/AwAGAAQAAQD///z/+v/9/wIABQAFAAIAAAD9//v//P8AAAUABQACAAAA/v/7//z/AAAE"
        "AAUAAgAAAP7/+//7/wAABAAFAAMAAAD///z/+////wMABQADAAAA///9//v//v8CAAUAAwABAAAA/f/8//3/AQAEAAQAAQAAAP7/"
        "/P/9/wAABAAEAAEAAAD+//z//f8AAAMABAACAAAA///8//z/AAADAAQAAgAAAP///f/8////AgAEAAIAAAD///3//P///wEABAAD"
        "AAEAAAD+//3//v8BAAMAAwABAAAA/v/9//7/AAADAAMAAQAAAP///f/9/wAAAwADAAEAAAD///3//f8AAAIAAwACAAAA///+//3/"
        "//8CAAMAAgAAAAAA/v/9////AQADAAIAAAAAAP7//f///wEAAwACAAEAAAD///3//v8AAAIAAgABAAAA///+//7/AAACAAIAAQAA"
        "AP///v/+/wAAAgACAAEAAAAAAP7//v8AAAEAAgABAAAAAAD+//7///8BAAIAAQAAAAAA///+////AAACAAIAAAAAAP///v///wAA"
        "AgACAAEAAAD///7///8AAAEAAgABAAAAAAD+//7/AAABAAIAAQAAAAAA///+/wAAAQACAAEAAAAAAP///v///wEAAgABAAAAAAD/"
        "//7///8AAAEAAQAAAAAA////////AAABAAEAAAAAAAAA/////wAAAQABAAAAAAAAAP////8AAAEAAQABAAAAAAD/////AAABAAEA"
        "AQAAAAAA/////wAAAAABAAEAAAAAAP///////wAAAQABAAAAAAAAAP////8AAAEAAQAAAAAAAAD/////AAABAAEAAAAAAAAA////"
        "/wAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
    ),
    "unfav": (
        "UklGRmwdAABXQVZFZm10IBAAAAABAAEAIlYAAESsAAACABAAZGF0YUgdAAAAAEABjQWe/ycC5vs58Afx/eEo73r0lwaeGkslEgbS"
        "/bX+q/sy59veRfUD9R8blRnXEzEJCQIzATLsWegg5YfpDv9HDFoWtRWyEYcESPpp80HoxOLx7r//fQ7hGjYYvBHqBkL7vvbV58Hl"
        "k+6p+0UPQxaeF44PgAXI/rbzhOwc6CvuKf1DD54YhBUuDsUDDP7K9V3u8ukj7sv8Tg2xFGUUcgw8BAL9rfa87RHqQO9h/UULSRR4"
        "EwINOgWE/rr2dO+V64fwFP2NCswSKhLGC7gEbv6C91Lw3ezI8In8NAr8EW0RhguzBGb+gvjR8TLurPFW/AwJnBCLENIKXAS+/tb4"
        "oPL87hfyMvwzCKcPhQ+OCmYE9v5z+Y7zFfDL8kT8oQetDskO9gk1BDD//Pl49ATxbPM1/OEGtQ0ADocJIwRo/4X6PfXu8Q70HfxE"
        "BtsMQg0hCQAEh//2+vz1zvKm9CL8qAUFDIUMtgjhA6P/V/ur9przLvUk/CQFPwvYC1MIxQPB/7j7UPdZ9Lf1JvyjBIAKMgv0B6oD"
        "3/8U/Or3DPU39i78LgTPCZYKlgeMA/b/Zvx6+Lf1s/Y5/MEDKAkCCj0HbQMKALP8Afla9in3RvxfA4sIdQnoBlADHAD6/H/58faa"
        "91X8AwP4B+4IlQY0Ay0AO/31+YD3B/hm/LACbgdvCEYGGAM8AHf9Y/oH+G/4efxjAu0G9gf7BfwCSACv/cn6hvjS+Iz8HQJ0BoQH"
        "swXiAlMA4v0o+/34Mfmh/NwBAgYXB24FxwJdABH+gPtu+Yz5t/yhAZgFsQYsBa4CZQA9/tP72Pni+c38awE0BU8G7ASVAmwAZf4g"
        "/Dv6Nfrk/DoB1gTzBbAEfAJyAIr+aPyZ+oP6/PwNAX8EnAV2BGQCdwCs/qr88PrO+hP95AAtBEkFPgRNAnsAy/7o/EP7Fvsr/b8A"
        "4AP7BAkENwJ+AOj+Iv2R+1n7Qv2eAJkDsATXAyECgAAC/1j92vua+1r9fwBWA2oEpwMMAoEAGv+K/R781/ty/WQAFwMoBHgD9wGD"
        "ADD/uP1e/BL8if1LAN0C6QNMA+MBgwBF/+T9m/xJ/KD9NQCmAq4DIgPQAYMAV/8M/tP8fvy2/SEAcwJ2A/oCvgGDAGj/Mf4I/bD8"
        "zf0PAEQCQQPUAqsBggB4/1T+Ov3g/OP9AAAXAg8DrwKaAYEAhv90/mn9Df34/fL/7gHgAowCiQF/AJT/kv6U/Tf9Df7m/8gBswJr"
        "AnkBfgCg/67+vf1g/SH+2/+kAYkCSwJpAXwAqv/H/uT9hv01/tL/gwFiAi0CWgF6ALT/3/4I/qv9Sf7J/2QBPAIQAksBdwC+//X+"
        "Kv7N/Vv+wv9HARkC9QE9AXUAxv8K/0n+7v1u/rz/LAH4AdsBMAFzAM3/Hf9n/gz+f/63/xMB2AHCASMBcADU/y//gv4q/pD+s//8"
        "ALsBqwEWAW0A2v8//5z+Rf6h/q//5gCfAZQBCgFrAOD/Tv+0/l/+sf6s/9MAhQF/Af4AaADl/1z/y/54/sD+qv/AAGwBagHzAGUA"
        "6v9p/+D+j/7P/qj/rwBVAVcB6ABiAO7/df/0/qX+3f6n/58APwFFAd4AYADy/4H/Bv+6/uv+p/+RACoBMwHUAF0A9f+L/xf/zv74"
        "/qb/gwAXASIBygBaAPj/lP8o/+D+Bf+n/3cABAETAcEAVwD7/53/N//y/hH/p/9rAPMABAG4AFUA/f+l/0X/Av8d/6j/YQDjAPUA"
        "sABSAAAArf9S/xL/KP+p/1cA1ADoAKgATwAAALT/Xv8g/zP/qv9OAMYA2wCgAE0AAgC6/2n/Lv89/6v/RgC5AM8AmABKAAQAwP90"
        "/zv/R/+t/z4ArADDAJEARwAFAMb/fv9H/1H/r/83AKAAuACKAEUABgDL/4f/U/9a/7D/MQCVAK4AhABCAAcAz/+Q/17/Yv+y/ysA"
        "iwCkAH4AQAAIANT/mP9o/2v/tP8lAIEAmwB4AD4ACQDY/5//cf9y/7b/IAB4AJIAcgA7AAkA2/+m/3r/ev+4/xwAcACKAGwAOQAK"
        "AN//rf+D/4H/uv8YAGgAggBnADcACgDi/7P/i/+I/73/FABhAHoAYgA1AAsA5P+5/5L/jv+//xEAWgBzAF0AMwALAOf/vv+Z/5T/"
        "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"
        "/iH/yP9/AAwBSQEzAeYAiQAzAOX/k/85/+n+w/7m/lr/AAClABUBNQENAb4AZwAZANH/gf8u/+r+2f4S/5D/MADAABQBHAHoAJkA"
        "SgADAL7/cv8l//H+9P4//8P/WgDTAAsB/wDEAHgAMADx/67/Zf8h//3+E/9s//L/ewDcAP0A4gCiAFsAGwDf/5//Wv8h/w7/Nf+Y"
        "/xoAkwDeAOoAwwCEAEIACADQ/5L/U/8l/yL/Wf/C/z0ApQDZANQApgBoAC0A+f/D/4f/Tv8t/zr/fv/p/1oArgDPAL0AiwBQABsA"
        "6v+2/37/Tf85/1X/of8LAHAAsgDBAKQAcQA7AAsA3v+s/3f/T/9J/3H/xP8oAIAArwCwAI0AWgApAP7/0v+i/3P/Vf9b/47/5P9B"
        "AIkAqQCdAHYARgAaAPL/yP+a/3H/Xf9w/6v/AABUAI4AngCKAGEANQANAOj/v/+U/3L/af+G/8f/GQBjAI0AkQB3AE4AJgABAN//"
        "t/+Q/3X/d/+d/+H/LgBsAIkAgwBkAD0AGQD4/9b/sf+O/3v/h/+0//n/PwBxAIIAdABTAC8ADQDw/8//q/+O/4T/mP/L/w0ASwBy"
        "AHgAZABDACIABADo/8j/p/+Q/47/q//h/x8AVABvAG0AVQA1ABcA/P/h/8L/pf+U/5v/vf/0/y4AWQBqAGEARwApAA0A9f/a/77/"
        "pP+a/6j/0P8FADkAWwBjAFQAOgAeAAUA7//V/7r/pv+i/7f/4f8UAEEAWgBaAEgALgAVAP//6f/Q/7j/qP+s/8b/8v8hAEYAVgBQ"
        "ADwAJAANAPn/5P/M/7f/rf+2/9X/AAArAEkAUQBHADIAGwAGAPT/3//J/7f/s//C/+P/DAAyAEgASgA9ACgAEwAAAO//2//H/7n/"
        "uv/N//D/FwA3AEYAQwAzAB8ADAD8/+v/1//G/7z/wv/Z//3/IAA6AEIAOwAqABgABwD4/+f/1f/G/8D/y//l/wcAJwA6AD0AMwAi"
        "ABEAAgD0/+P/0//H/8b/1P/w/xAAKwA5ADgAKwAbAAsA/v/w/+H/0v/J/8z/3v/6/xcALgA2ADEAJAAVAAcA+//t/97/0f/M/9P/"
        "5/8CAB0ALgAyACsAHQAPAAMA9//q/9z/0v/Q/9v/8P8KACEALgAuACUAFwALAAAA9P/o/9v/0//V/+L/+f8RACQALAApAB8AEgAG"
        "AP3/8v/m/9v/1f/a/+r/AAAWACUAKQAkABkADgADAPr/7//k/9v/2f/g//H/BgAaACUAJgAfABQACgAAAPj/7f/j/9z/3P/m//j/"
        "DAAcACQAIgAaABAABgD+//X/6//i/93/4P/s////EAAdACIAHgAWAAwAAwD8//P/6v/i/+D/5f/y/wMAFAAeAB8AGgARAAkAAQD6"
        "//L/6f/j/+L/6v/4/wgAFgAdABwAFgAOAAYA///4//D/6P/k/+b/7//9/wwAFwAcABkAEgAKAAMA/v/2/+//6P/m/+n/9P8BAA8A"
        "GAAaABYADwAIAAEA/P/1/+7/6f/o/+3/+P8FABEAFwAXABMADAAFAAAA+v/0/+3/6f/q//H//f8IABIAFgAVABAACQADAP//+f/z"
        "/+3/6v/t//X/AAALABMAFQASAA0ABwABAP3/+P/y/+3/7P/w//n/AwANABMAEwAQAAoABQAAAPz/9//x/+7/7v/z//z/BgAOABIA"
        "EQANAAgAAwD///v/9v/x/+7/8P/2/wAACAAPABEADwALAAYAAQD+//r/9f/x//D/8v/5/wEACgAPABAADQAJAAQAAAD9//n/9P/x"
        "//H/9f/8/wQACwAPAA4ACwAHAAMAAAD8//j/9P/y//P/9////wYADAAOAA0ACQAFAAEA///7//f/9P/z//X/+v8AAAcADAANAAsA"
        "BwAEAAAA/v/7//f/9P/0//f//P8CAAgADAAMAAkABgACAAAA/f/6//f/9f/1//n//v8EAAkACwAKAAgABAABAAAA/f/5//f/9f/2"
        "//v/AAAFAAkACwAJAAYAAwAAAP///P/5//f/9v/4//z/AQAGAAkACgAIAAUAAgAAAP7/+//5//f/9//6//7/AwAHAAkACQAHAAQA"
        "AQAAAP7/+//5//f/+P/7/wAABAAHAAkACAAFAAMAAAD///3/+//5//j/+f/9/wAABQAHAAgABgAEAAIAAAD///3/+v/5//n/+//+"
        "/wIABQAHAAcABQADAAEAAAD+//z/+v/5//n//P8AAAMABgAHAAYABAACAAAAAAD+//z/+v/5//r//f8AAAQABgAGAAUABAACAAAA"
        "///9//z/+v/6//v//v8BAAQABgAGAAUAAwABAAAA///9//v/+v/7//z///8CAAQABgAFAAQAAgAAAAAA/v/9//v/+//7//3/AAAD"
        "AAUABQAEAAMAAQAAAAAA/v/9//v/+//8//7/AAADAAUABQAEAAIAAQAAAP///v/8//z//P/9////AQADAAQABAADAAIAAAAAAP//"
        "/v/8//z//P/+/wAAAgAEAAQABAACAAEAAAAAAP///f/8//z//f///wAAAgAEAAQAAwACAAEAAAAAAP7//f/8//z//f///wEAAwAD"
        "AAMAAwABAAAAAAD///7//f/9//3//v8AAAEAAwADAAMAAgABAAAAAAD///7//f/9//3///8AAAIAAwADAAMAAgABAAAAAAD///7/"
        "/f/9//7///8AAAIAAwADAAIAAQAAAAAAAAD///7//f/9//7/AAABAAIAAwACAAIAAQAAAAAA//////7//v/+////AAABAAIAAgAC"
        "AAEAAAAAAAAA//////7//v/+////AAABAAIAAgACAAEAAAAAAAAA///+//7//v///wAAAAABAAIAAgABAAEAAAAAAAAA///+//7/"
        "/v///wAAAQACAAIAAgABAAAAAAAAAAAA///+//7///8AAAAAAQACAAIAAQABAAAAAAAAAP/////+//7///8AAAAAAQACAAEAAQAA"
        "AAAAAAAAAP////////////8AAAAAAQABAAEAAQAAAAAAAAAAAP//////////AAAAAAEAAQABAAEAAQAAAAAAAAAAAP//////////"
        "AAAAAAEAAQABAAEAAAAAAAAAAAAAAP//////////AAAAAAEAAQABAAEAAAAAAAAAAAAAAP///////wAAAAAAAAEAAQABAAAAAAAA"
        "AAAAAAAAAAAA//8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
    ),
    "delete": (
        "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"
        "JwT9A8IDeAMfA78CYQIPAtUBvgHRARECfgIQA7sDcgQjBb8FNwaBBpcGdwYnBq4FFwVtBLoDCANbArcBGgGBAOv/UP+w/g3+af3K"
        "/Dv8xftx+0j7TfuB++D7YPz2/JL9Jv6j/v3+Lv8y/wr/vv5W/tv9Wv3a/GT8+vuf+1H7DfvQ+pj6Y/o2+hP6AfoK+jb6i/oP+8P7"
        "pfyt/dD+AAAuAUwCTAMkBM4ESAWTBbYFtwWhBXoFSQUUBdsEngRcBBEEuwNZA+0CegIGApoBPgH7ANgA2gAAAUkBrAEhApwCDwNv"
        "A7MD1APQA6cDXQP5AoMCAwJ/Af4AgQAJAJb/Iv+s/jP+tP0z/bP8OvzQ+3z7Rvsy+0L7dvvI+zL8qfwi/ZP98f03/l/+av5b/jf+"
        "BP7L/ZP9Yv07/R/9Dv0H/QX9Bv0K/Q/9F/0n/UP9cv26/R7+of5C//3/ywCkAXwCSQMABJkEDgVbBYMFiAVvBUAFAQW4BGsEGwTJ"
        "A3YDHwPEAmEC+gGOASIBuwBfABYA5v/R/9r/AAA9AI0A5wBBAZIB0gH5AQUC9QHKAYgBNQHXAHMADgCr/0r/7f6Q/jP+1P1x/Q39"
        "qfxJ/PP7rft8+2b7bPuR+9H7KPyP/AD9cf3a/TX+f/60/tb+5/7r/un+5P7h/uT+7f7+/hP/K/9D/1n/bf9//5H/pv/C/+r/IQBr"
        "AMkAOAG2ATsCwwJDA7YDEwRXBH8EiQR5BFIEGQTTA4UDNAPiApICQwL0AaQBUgH+AKgAUgAAALb/eP9K/zH/Lf9A/2f/nv/e/yEA"
        "YQCWALsAzADHAKwAfwBCAPv/rf9c/w3/v/51/i7+6P2j/V39F/3T/JL8Wfws/A/8BvwU/Dr8ePzL/C79nP0O/n7+5v5C/4//zf/8"
        "/x0ANwBKAFsAbAB/AJQAqgDAANMA4wDtAPMA9AD0APUA+gAIASEBRwF6AbgB/gFHAo8C0AIFAykDOwM5AyMD/QLJAowCSQIEAsAB"
        "fgE+AQABxACHAEkACwDN/4//Vv8k//z+4v7X/tz+8P4R/zv/av+X/7//3P/r/+v/2/+8/5H/Xv8k/+n+r/54/kT+Ff7p/cD9mf1z"
        "/VD9MP0W/QX9AP0J/SP9UP2O/d39Ov6g/gv/dv/b/zYAhgDIAP0AJQFBAVYBZQFxAXoBggGKAY8BkQGOAYcBegFoAVQBPgErARwB"
        "FAEWASMBOQFXAXwBogHHAeYB/AEGAgQC9AHYAbMBhgFUASEB7QC8AIwAXwAyAAYA2/+t/37/T/8i//j+1f65/qj+o/6p/rn+0f7v"
        "/g//LP9E/1P/Wf9T/0T/LP8N/+v+yP6m/of+bf5W/kT+Nv4r/iH+Gv4W/hX+Gf4l/jr+W/6H/sD+Bf9T/6j/AABYAKsA9wA5AW8B"
        "mAG1AccB0QHTAdABygHCAbgBqwGdAYsBdQFcAT8BIAEAAeEAxQCwAKEAnACfAKsAvQDTAOsAAQESARwBHgEXAQcB7wDRAK8AigBk"
        "AD8AGwD5/9f/tf+T/2//S/8l/wD/3P68/qL+j/6E/oL+if6Y/q3+xv7f/vf+C/8Z/yH/Iv8e/xX/Cv/9/vL+6v7k/uP+5f7q/vL+"
        "+v4E/w//G/8q/zv/Uv9v/5L/vf/w/ycAZACjAOEAHAFQAX0BnwG3AcUByQHGAbwBrQGbAYcBcgFbAUQBKwERAfQA1gC3AJcAeABd"
        "AEUANAApACYAKgA1AEMAVQBmAHYAgQCGAIUAfABuAFkAQAAlAAgA6//O/7L/lv97/1//Q/8m/wj/6/7O/rX+n/6P/ob+hP6K/pj+"
        "q/7E/t/++v4V/y3/Qf9R/13/Zf9r/3D/df97/4P/jv+a/6j/tv/F/9T/4v/v//z/CQAYACkAPgBYAHUAlgC6AN8ABAEmAUQBXQFu"
        "AXgBegF1AWoBWQFFAS8BGAEAAegA0QC5AKEAiABvAFYAPAAkAA0A+//r/+H/3f/e/+P/7f/6/wYAEgAcACEAIgAdABMABADy/93/"
        "xv+u/5b/f/9p/1T/P/8q/xb/Af/u/tv+y/6+/rb+s/62/sD+0f7n/gH/H/8//17/fP+Y/7H/xv/Y/+f/9P8AAAoAFgAiAC4AOwBH"
        "AFMAXQBmAG0AcgB3AHsAgACGAI8AmgCoALgAyQDbAOwA+wAGAQ0BDwELAQMB9wDmANQAwACrAJcAgwBwAF0ASwA4ACYAEwABAO//"
        "3v/P/8L/uf+z/7L/tP+5/8D/yf/R/9j/3P/d/9n/0v/H/7r/qv+Y/4f/dv9m/1f/Sf88/zH/Jv8c/xP/DP8G/wP/A/8I/xH/H/8y"
        "/0r/Zf+D/6L/wv/h//3/FgAsAD8ATwBbAGYAbwB3AH4AhQCMAJEAlgCZAJsAmwCaAJcAlACRAI4AjQCMAI0AkACTAJYAmgCcAJ0A"
        "nACYAJIAigCAAHUAaABbAE4AQQA1ACkAHgAUAAkAAAD2/+v/4f/X/87/xv++/7f/sv+t/6r/pv+j/6D/nf+Y/5P/jv+H/4D/ef9y"
        "/2z/Zv9i/17/XP9b/1v/Xf9g/2X/av9x/3n/g/+O/5r/p/+1/8P/0v/i//H/AAAOAB0ALAA5AEcAUwBfAGoAdAB9AIQAiwCQAJQA"
        "lwCZAJoAmgCYAJYAkwCPAIoAhQB/AHkAcgBrAGQAXQBVAE4ARwBAADkAMgArACUAHgAYABIADAAGAAAA+//1//D/6v/k/97/2P/R"
        "/8v/xf++/7f/sf+q/6T/nv+Y/5L/jf+I/4P/gP98/3r/eP94/3j/ef97/37/gv+H/43/lP+c/6T/rv+4/8P/zv/a/+b/8v/+/wkA"
        "FQAhAC0AOABCAEwAVQBdAGUAawBxAHUAeQB7AH0AfgB+AH0AewB5AHUAcgBtAGkAZABeAFkAUwBNAEcAQQA7ADUALwAqACQAHwAa"
        "ABQADwALAAYAAQD9//j/9P/v/+r/5f/g/9v/1v/Q/8v/xv/A/7v/tv+x/6z/p/+j/57/m/+Y/5X/k/+R/5D/kP+R/5P/lf+Y/5z/"
        "of+m/63/s/+7/8P/zP/V/9//6P/y//z/BgAPABkAIwAsADQAPQBEAEsAUQBXAFsAXwBiAGUAZgBnAGcAZgBlAGMAYQBeAFoAVgBS"
        "AE4ASQBFAEAAOwA2ADEALAAoACMAHgAaABYAEgANAAkABQABAP//+//3//P/7//r/+f/4//e/9r/1v/R/83/yf/E/8D/vP+4/7T/"
        "sf+u/6v/qf+n/6b/pf+l/6X/pv+o/6r/rv+x/7b/u//A/8b/zf/U/9v/4//r//P//P8DAAsAEwAbACIAKQAwADYAPABBAEYASgBN"
        "AFAAUgBTAFQAVABUAFMAUQBPAE0ASgBHAEQAQQA9ADkANQAxAC0AKQAlACEAHQAaABYAEgAPAAwACAAFAAIAAAD8//n/9v/z/+//"
        "7P/p/+X/4v/e/9v/1//T/9D/zP/J/8b/w//A/73/u/+5/7f/tv+2/7X/tv+2/7j/uv+8/7//wv/G/8v/0P/V/9v/4f/n/+7/9P/7"
        "/wEACAAOABQAGgAfACQAKAAsADAAMwA1ADcAOAA5ADkAOQA4ADcANgA0ADIAMAAuACsAKQAmACMAIAAeABsAGAAWABMAEQAPAA0A"
        "CwAJAAcABQAEAAIAAQAAAP///v/9//v/+v/5//j/9//2//b/9f/0//P/8//y//L/8f/x//H/8f/x//H/8v/y//P/8//0//X/9v/3"
        "//j/+f/6//r/+//8//3//v//////AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAA="
    ),
}


# ------------------------------------------------------------ built-in artwork
# 256x256 WebP images, base64-encoded: "tray" = tray icon (transparent), "menu" = corner image in the picker.
_ART_B64 = {
    "tray": (
        "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"
        "BRAAAAAAAA=="
    ),
    "menu": (
        "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"
    ),
}


if __name__ == "__main__":
    main()
