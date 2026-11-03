"""
App Launcher for Synapse  (PySide6)  -  same glass look as the Vapor shell

It reads cc_theme.json (the file Vapor's theme card writes), so recoloring Vapor recolors the launcher live (picked up
within about half a second). Nothing has to sit next to it: Vapor, vaporctl and Harmony are found on their own
(through the PATH entry Vapor adds); launcher_settings.json -> "customizations" can point at them if they are elsewhere.

Run it with:  pythonw Synapse.pyw        (or build Synapse.exe, see the end of this note: every feature works the same)
  - first run starts it in the background and opens it
  - every later run toggles it (open / close), so bind that command to a hotkey or a bar button
  - pythonw Synapse.pyw --hidden   preloads it silently at login so the first open is instant

Commands (type them in the search box, Enter applies):
  >setbackground "path"   set the launcher background image   (">setbackground none" removes it)
  >setmedia "path"        show an image / GIF / video in the image card  (">setmedia none" removes it)
  >cmd [command]          open Windows Command Prompt (or run a command in a new prompt window)
  >log [folder]           open the Synapse log file in your editor (folder = show it in Explorer)
  >ocr [clip | "path"]    read text from the screen: drag a box over it and it is copied to the clipboard
                          (>ocr clip reads the picture on the clipboard, >ocr "path" reads an image file; uses Windows' built-in OCR)
  >yt <link>             download a YouTube video as MP4 with yt-dlp (add -a for the advanced window: thumbnail preview,
                          format, quality, folder, embed cover art)
  >pathdownload [path]    set the download folder (leave path empty to choose it in a folder picker)
  >exit  (or >quit)       close the launcher process completely (it starts again on the next launch)
  >setcard "path"         set the image behind the card  (">setcard none" removes it)
  >setquote <text>        change the text on the quote card  (\n in the text starts a new line; ">setquote reset" = default)
  >setmedia "path" -c     same as >setmedia, then drag a box over the picture to choose the area  (>setmedia -c
                          re-crops what is already set; works for >setcard too)
  >zen on|off             compact mode: hides the side panel, shows only the search bar and drops results down
  >clearcache [-a]        clear every cache with live progress: Vapor, Harmony, Synapse, temp files
                          (settings, favourites and your theme are kept)
                          the last row (or -a) opens the advanced display: every file, its size and whether it was deleted
  >acrylic [on|off]       toggle the blur behind the window
  >customizations [on|off]  one switch for your whole setup: on = hide the taskbar, open Komorebi and open Harmony;
                          off = close Komorebi and Harmony and bring the taskbar back
  >vapor set name <name>  change the name on the Vapor profile card  (>vapor set name --reset = Windows user name again)
  >vapor set pfp ["path"] [-c]  set the Vapor profile picture (no path = pick a file); -c opens a round cropper first and
                          saves a sharp square PNG for it  (>vapor set pfp -c re-crops the last picture, >vapor set pfp reset removes it)
  >vapor update [--check|--force|--extras]  look for a newer Vapor release on GitHub and open the Vapor installer in its own
                          command window (--check only looks, --force reinstalls, --extras asks about the extra packages)
  >vapor <anything>       any other vaporctl command (type >vapor to see them all):  >vapor status  >vapor fetch  >vapor volume 40
                          >vapor mute  >vapor media next  >vapor ws 2  >vapor layout  >vapor hide|show|toggle  >vapor alert "title"
                          >vapor notify "title"  >vapor timer 10m  >vapor remind 7pm "call mom"  >vapor reminders  >vapor note "text"
                          >vapor ringtone test  >vapor wallpaper random  >vapor set location Pokhara  >vapor reload  >vapor autostart on
                          >vapor restart  >vapor doctor  >vapor log  >vapor paths  >vapor config set <key> <value>  >vapor --version
  >lcbar [on|off]         start / close the Vapor shell (empty = toggle)
  >taskbar [on|off]       show / hide the Windows taskbar completely (all monitors, no gap left on screen)
                          off = hidden, on = shown until Synapse starts next time (it is hidden again then)
  >animations [on|off]    open/close fade
  >transparency 0-100     0 = solid, 100 = clear

Alt+Space opens / closes it from anywhere while it is running in the background. Start it at login with
  pythonw Synapse.pyw --hidden      (running the script again still toggles it too)
Ctrl+B retracts the right side and slides it back out; it is remembered.
Drag any empty glass to move the launcher (remembered); double-click empty glass to put it back.

  >add ["path"] [name]    add an app / script / folder to the list (just >add opens a file picker);  >add remove <name>
Alt+Up / Alt+Down step through your earlier >commands; plain Up / Down move through the results.
  (while the launcher is open Synapse takes Alt+Up / Alt+Down ahead of whkd / Komorebi's hotkeys; they work normally again
   the moment it closes)
Shift+Enter shows the highlighted app / file in Explorer (selected); Ctrl+Shift+Enter opens it as administrator.

launcher_settings.json (>config opens it):
  "customizations": {"harmony": "C:/path/to/harmony.pyw"}   where Harmony (the wallpaper picker) lives; empty = look for it
                                                           next to Synapse / in the Vapor folder
  "taskbar_always_hidden": true                            the taskbar is hidden every time Synapse starts and stays hidden
                                                           when Synapse closes (>taskbar on only shows it until the next
                                                           start; set false to go back to the normal taskbar)
Tab autocompletes: it finishes a >command name (and on/off arguments) or fills the box with the highlighted app / file name.

Type to search Start Menu apps. Type a sum like 12*(3+4), or start with = (=sqrt(16)+2^3) for a calculator (Enter copies the result).
Put the name in quotes ("hello") to search your files and folders instead of apps; Enter opens it.
File search covers your home folder and every fixed drive (C:, D:, ...). It uses Everything (voidtools) when it is running: install it from voidtools.com and keep it running, and
optionally drop Everything64.dll (from the Everything SDK) or es.exe next to this file. Without it, a built-in index is used.
Anything else can be searched on the web. Up/Down move, Enter opens, Esc closes.

Everything Synapse writes (launcher_settings.json, usage, theme, log) goes to the hidden folder %LOCALAPPDATA%\\Synapse (>config opens
the settings file); nothing is created next to Synapse.pyw / Synapse.exe.

Build an exe:   py -m pip install pyinstaller
                py -m PyInstaller --noconsole --onedir --name Synapse Synapse.pyw        (add --icon your.ico if you like)
  --onedir (a folder with Synapse.exe in it) starts faster than --onefile, which unpacks itself on every launch.
  yt-dlp, vaporctl and Harmony run through the Python that is on your PATH (the one Vapor already uses) or the yt-dlp.exe.

Fonts: CaskaydiaCove NFP (all text), CaskaydiaCove NFM (calculator, key hints, quote card), Segoe Fluent Icons (glyphs only)
"""
import sys
sys.dont_write_bytecode = True
import ast
import colorsys
import fnmatch
import bisect
import heapq
from collections import deque
import ctypes
from ctypes import wintypes
import base64
import importlib.machinery
import contextlib
import importlib.util
import io
import json
import math
import operator as op
import os
import re
import subprocess
import sys
import shutil
import threading
import tempfile
import time
import traceback
import webbrowser
from functools import lru_cache
import urllib.request
from urllib.parse import quote

from PySide6.QtCore import (QAbstractTableModel, QEasingCurve, QEvent, QFileInfo, QModelIndex, QObject, QPoint, QPointF, QRect, QRectF, Qt, QTimer, QUrl, QVariantAnimation,
                            Signal)
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QFontMetrics, QIcon, QImage, QImageReader, QKeySequence, QLinearGradient, QMovie, QPainter, QPainterPath,
                           QAction, QPen, QPixmap, QPolygonF, QRegion, QShortcut)
QMediaPlayer = QVideoSink = None                        # QtMultimedia is big, so it is only imported when a video is set
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, 
                               QFileDialog, QFileIconProvider, QHeaderView, QTableView,
                               QGraphicsBlurEffect, QGraphicsScene, QHBoxLayout, QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton, QSystemTrayIcon, QVBoxLayout, QWidget)

# ----------------------------------------------------------------- settings
FROZEN = bool(getattr(sys, "frozen", False))                       # True when this is Synapse.exe (PyInstaller & co.)
HERE = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))     # next to the script / exe: only ever READ from
DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "Synapse")   # everything Synapse writes lives here


def _init_data_dir():
    """Settings, usage and theme go to a hidden folder in %LOCALAPPDATA%, so nothing is generated next to Synapse.
    Files an older version left next to the script are moved there once."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        ctypes.windll.kernel32.SetFileAttributesW(DATA_DIR, 0x2)                   # FILE_ATTRIBUTE_HIDDEN
        for n in ("launcher_settings.json", "launcher_usage.json", "cc_theme.json"):
            old, new = os.path.join(HERE, n), os.path.join(DATA_DIR, n)
            if os.path.isfile(old) and not os.path.exists(new):
                shutil.move(old, new)
    except Exception:  # noqa: BLE001
        pass


_init_data_dir()
SERVER = "synapse_app_launcher"
USAGE_FILE = os.path.join(DATA_DIR, "launcher_usage.json")
_CFG_REF = {}                     # the launcher's settings dict (one shared object: helpers outside the window class read it too)
W, H, R = 980, 612, 18            # window size, corner radius
LEFT_X, LEFT_W = 18, 560          # left pane: search + list
RIGHT_X, RIGHT_W = 598, 364       # right pane: image, theme slider, stats, quote, system strip
SEARCH_Y, SEARCH_H, LIST_Y = 18, 46, 76
ROW_H, MAX_VIS = 50, 9            # row height, rows visible before the list scrolls
DEFAULT_QUOTE = "Good things take time."   # shown until you set your own with >setquote  (saved as "quote_text" in launcher_settings.json)
WM = {"vapor": dict(label="Vapor", check=lambda: vapor_running(), start_fn=lambda: vapor_start(), stop_fn=lambda: vapor_stop()),
      "komorebi": dict(label="Komorebi", procs=("komorebi.exe",), start=["komorebic", "start", "--whkd", "--masir"],
                       stop=["komorebic", "stop", "--whkd", "--masir"], stop_fallback=["komorebic", "stop"])}
                                  # Komorebi button under the card: click to start / stop it (stop_fallback is tried if the full stop doesn't end it)
TOP_FRACTION = 0.08               # how far down the screen it appears
TEXT_FONT, MONO_FONT, ICON_FONT = "CaskaydiaCove NFP", "CaskaydiaCove NFM", "Segoe Fluent Icons"
FALLBACKS = ["CaskaydiaCove Nerd Font Propo", "CaskaydiaCove Nerd Font", "CaskaydiaCove Nerd Font Mono", "Cascadia Code"]   # Caskaydia only, no Segoe
SKIP = ("uninstall", "readme", "license", "documentation", "release notes", "website", "help")
# Windows tools that have no Start Menu shortcut (Paint, Calculator, ... are Store apps on Windows 11, so scan_apps never sees
# a .lnk for them).  (title, exe, extra search words)  -> typing "mspaint" or "paint" now finds Paint.
BUILTIN_APPS = (("Paint", "mspaint.exe", "mspaint"), ("Notepad", "notepad.exe", "notepad"), ("Calculator", "calc.exe", "calc"),
                ("Task Manager", "taskmgr.exe", "taskmgr"), ("Registry Editor", "regedit.exe", "regedit"),
                ("Snipping Tool", "SnippingTool.exe", "snippingtool snip"), ("Character Map", "charmap.exe", "charmap"),
                ("System Information", "msinfo32.exe", "msinfo32"), ("Control Panel", "control.exe", "control"),
                ("Resource Monitor", "resmon.exe", "resmon"), ("Disk Cleanup", "cleanmgr.exe", "cleanmgr"),
                ("Remote Desktop Connection", "mstsc.exe", "mstsc rdp"))
BUILTIN_FALLBACK = {"mspaint.exe": "ms-paint:"}       # Windows 11 Paint when no mspaint.exe can be found on disk


LOG = os.path.join(tempfile.gettempdir(), "synapse_app_launcher.log")
SETTINGS_FILE = os.path.join(DATA_DIR, "launcher_settings.json")  # persistent launcher configuration (hidden folder)
BG_OPACITY = 1.0
IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".ico", ".tif", ".tiff"}
GIF_EXT = {".gif"}
VID_EXT = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".m4v", ".wmv"}
CLEAR_WORDS = ("none", "clear", "reset", "off", "remove")
COMMANDS = {"setbackground": ("Set background", "\uEB9F", "Use an image as the launcher background"),
            "setmedia": ("Set media", "\uE8B9", "Image, GIF or video in the image card  (add -c to pick the area)"),
            "setcard": ("Set card image", "\uEB9F", "Image behind the card  (add -c to pick the area)"),
            "setquote": ("Set quote", "\uE8BD", "Text on the quote card  (>setquote reset = default)"),
            "acrylic": ("Acrylic blur", "\uE790", "Turn the blur behind the window on or off"),
            "transparency": ("Transparency", "\uE706", "How see-through the window is, 0 to 100"),
            "zen": ("Zen mode", "\uE9E9", "Compact launcher: just the search bar, results drop down  (>zen on / off)"),
            "clearcache": ("Clear cache", "\uE74D", "Clear the Vapor, Harmony, Synapse and temp file caches  (-a opens the advanced file list)"),
            "scan": ("Scan apps", "\uE72C", "Look for newly installed apps now (apps are otherwise only indexed when Synapse starts)"),
            "reload": ("Reload launcher", "\uE72C", "Refresh app and file indexes, weather, cached images and launcher display"),
            "config": ("Open config", "\uE713", "Open launcher_settings.json in your chosen editor"),
            "editor": ("Choose file editor", "\uE70F", "Select the native app used by >config (defaults to Notepad)"),
            "cmd": ("Command Prompt", "\uE756", "Open Windows Command Prompt, optionally running a command"),
            "yt": ("YouTube download", "\uE896", "Download a URL as MP4 by default; use -a to pick format and quality"),
            "pathdownload": ("Download folder", "\uE8B7", "Choose or set the folder where yt-dlp downloads are saved"),
            "log": ("Open log", "\uE8A5", "Open the Synapse log file  (>log folder shows it in Explorer)"),
            "ocr": ("Screen OCR", "\uE722", "Drag over any text on screen and copy it  (>ocr clip = clipboard picture, >ocr \"path\" = image file)"),
            "animations": ("Animations", "\uE916", "Open / close fade on or off"),
            "customizations": ("Customizations", "\uE771", "Hide the taskbar and open Komorebi and Harmony  (>customizations off undoes it)"),
            "lcbar": ("Vapor on / off", "\uE700", "Start or close the Vapor shell  (>lcbar on / off, empty toggles)"),
            "taskbar": ("Taskbar", "\uE7C4", "Show or hide the Windows taskbar completely  (>taskbar on / off)"),
            "add": ("Add app", "\uE710", "Add an app, script or folder to the list  (just >add to browse for it)"),
            "vapor": ("Vapor", "\uE77B", "Control your Vapor shell"),
            "exit": ("Exit launcher", "\uE7E8", "Quit the launcher process completely")}
CMD_KEYS = {"setbackground": "background", "setmedia": "media", "setcard": "quote"}
CMD_ALIAS = {"fluidbar": "lcbar", "fbar": "lcbar", "quote": "setquote", "cache": "clearcache", "refresh": "clearcache", "reindex": "clearcache", "quit": "exit", "snip": "ocr", "logs": "log", "readtext": "ocr", "animation": "animations", "fx": "animations", "tb": "taskbar", "customization": "customizations", "customisations": "customizations", "rice": "customizations", "close": "exit", "blur": "acrylic", "opacity": "transparency", "downloadpath": "pathdownload", "setdownloadpath": "pathdownload", "vaporctl": "vapor", "vctl": "vapor"}
HINT_TITLES = {"lcbar": ">lcbar [on|off]", "customizations": ">customizations [on|off]", "taskbar": ">taskbar [on|off]", "zen": ">zen [on|off]", "exit": ">exit", "clearcache": ">clearcache [-a]", "acrylic": ">acrylic [on|off]", "transparency": ">transparency 0-100",
               "setmedia": '>setmedia "path" [-c]', "setcard": '>setcard "path" [-c]', "setquote": ">setquote <text>",
               "config": ">config", "editor": ">editor [path to editor.exe]", "cmd": ">cmd [command]", "reload": ">reload", "scan": ">scan",
               "yt": ">yt <link> [-a]", "pathdownload": ">pathdownload [folder path]", "add": '>add ["path"] [name]', "animations": ">animations [on|off]", "ocr": '>ocr [clip | "path"]', "log": ">log [folder]", "vapor": ">vapor"}
HOTKEY_ID = 0xA11                 # global Alt+Space (registered with Windows while the launcher process runs)


def log(msg):
    try:
        if os.path.getsize(LOG) > 262144:                      # keep the log small: start over once it grows past 256 KB
            os.remove(LOG)
    except OSError:
        pass
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))
    except OSError:
        pass


sys.excepthook = lambda et, ev, tb: log("".join(traceback.format_exception(et, ev, tb)))


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        d = d if isinstance(d, dict) else {}
    except ValueError:
        return {}                                              # unreadable file: never overwrite it with defaults
    except OSError:
        d = {}                                                 # no file yet: it is created with the defaults below
    changed = False
    c = d.get("customizations")
    if c is None:
        d["customizations"], changed = {"harmony": ""}, True        # the line to fill in: where Harmony lives
    elif isinstance(c, dict) and "harmony" not in c and "wallpaper_picker" not in c:
        c["harmony"], changed = "", True
    if "taskbar_always_hidden" not in d:
        d["taskbar_always_hidden"], changed = True, True
    if changed:
        save_settings(d)
    return d


def save_settings(d):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
    except OSError:
        log("could not save settings:\n" + traceback.format_exc())


# ----------------------------------------------------------------- Windows taskbar
ABM_GETSTATE, ABM_SETSTATE = 0x4, 0xA
ABS_AUTOHIDE, ABS_ALWAYSONTOP = 0x1, 0x2
SW_HIDE, SW_SHOWNA = 0, 8
_TB = {}


class APPBARDATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uCallbackMessage", wintypes.UINT),
                ("uEdge", wintypes.UINT), ("rc", wintypes.RECT), ("lParam", wintypes.LPARAM)]


def _tb_api():
    """Private user32 / shell32 handles, so setting argtypes here can't affect any other ctypes call in this file."""
    if not _TB:
        u, sh = ctypes.WinDLL("user32"), ctypes.WinDLL("shell32")
        u.FindWindowW.argtypes, u.FindWindowW.restype = [wintypes.LPCWSTR, wintypes.LPCWSTR], wintypes.HWND
        u.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
        u.FindWindowExW.restype = wintypes.HWND
        u.ShowWindow.argtypes, u.ShowWindow.restype = [wintypes.HWND, ctypes.c_int], wintypes.BOOL
        u.IsWindowVisible.argtypes, u.IsWindowVisible.restype = [wintypes.HWND], wintypes.BOOL
        sh.SHAppBarMessage.argtypes, sh.SHAppBarMessage.restype = [wintypes.DWORD, ctypes.POINTER(APPBARDATA)], ctypes.c_size_t
        _TB.update(u=u, sh=sh)
    return _TB["u"], _TB["sh"]


def taskbar_windows():
    """The main taskbar plus the taskbar of every other monitor."""
    u, _sh = _tb_api()
    found = []
    main_ = u.FindWindowW("Shell_TrayWnd", None)
    if main_:
        found.append(main_)
    h = u.FindWindowExW(None, None, "Shell_SecondaryTrayWnd", None)
    while h:
        found.append(h)
        h = u.FindWindowExW(None, h, "Shell_SecondaryTrayWnd", None)
    return found


def taskbar_autohide_state():
    _u, sh = _tb_api()
    abd = APPBARDATA()
    abd.cbSize = ctypes.sizeof(abd)
    return bool(sh.SHAppBarMessage(ABM_GETSTATE, ctypes.byref(abd)) & ABS_AUTOHIDE)


def taskbar_set_autohide(on):
    """Auto-hide frees the strip of screen the taskbar reserves, so maximised windows use the full height."""
    u, sh = _tb_api()
    abd = APPBARDATA()
    abd.cbSize = ctypes.sizeof(abd)
    abd.hWnd = u.FindWindowW("Shell_TrayWnd", None)
    abd.lParam = ABS_AUTOHIDE if on else ABS_ALWAYSONTOP
    sh.SHAppBarMessage(ABM_SETSTATE, ctypes.byref(abd))


def taskbar_show_windows(visible):
    u, _sh = _tb_api()
    for h in taskbar_windows():
        if bool(u.IsWindowVisible(h)) != visible:
            u.ShowWindow(h, SW_SHOWNA if visible else SW_HIDE)
        if visible:                                   # undo taskbar_hide_bridge()
            c = u.FindWindowExW(h, None, "Windows.UI.Composition.DesktopWindowContentBridge", None)
            while c:
                if not u.IsWindowVisible(c):
                    u.ShowWindow(c, SW_SHOWNA)
                c = u.FindWindowExW(h, c, "Windows.UI.Composition.DesktopWindowContentBridge", None)


def taskbar_hide_bridge():
    """Windows 11 draws the taskbar icons in a child XAML window that can stay painted (icons floating with no bar)
    after the taskbar window itself is hidden. Hide that child too; it is shown again by taskbar_show_windows()."""
    u, _sh = _tb_api()
    for h in taskbar_windows():
        c = u.FindWindowExW(h, None, "Windows.UI.Composition.DesktopWindowContentBridge", None)
        while c:
            if u.IsWindowVisible(c):
                u.ShowWindow(c, SW_HIDE)
            c = u.FindWindowExW(h, c, "Windows.UI.Composition.DesktopWindowContentBridge", None)


def clean_path(s):
    """Accepts C:\\a b\\x.png, "C:\\a b\\x.png" (Copy as path) and ~/x.png."""
    s = s.strip().strip("\"'").strip()
    return os.path.expandvars(os.path.expanduser(s))


def shrink(pm, w, h):
    """Keep no more pixels than the card needs (a 4K wallpaper is ~33 MB as a pixmap)."""
    if pm.isNull():
        return pm
    dpr = max(1.0, QApplication.primaryScreen().devicePixelRatio())
    tw, th = int(w * dpr), int(h * dpr)
    if pm.width() > tw and pm.height() > th:
        return pm.scaled(tw, th, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    return pm


def split_crop(arg):
    """'"C:\\a b.png" -c' -> ('"C:\\a b.png"', True);  '-c' -> ('', True)."""
    a = arg.strip()
    if os.path.isfile(clean_path(a)):                          # the whole thing is a real file name: leave it alone
        return a, False
    rest, found = _flag(a, "-c", "--crop")
    return (rest, True) if found else (a, False)


def crop_pm(pm, crop):
    """crop = (x, y, w, h) as fractions of the picture."""
    if not crop or pm.isNull():
        return pm
    try:
        x, y, w, h = (float(v) for v in crop)
    except (TypeError, ValueError):
        return pm
    r = QRect(int(x * pm.width()), int(y * pm.height()), max(1, int(w * pm.width())), max(1, int(h * pm.height())))
    r = r.intersected(pm.rect())
    return pm.copy(r) if not r.isEmpty() else pm


TRAY_ICON_B64 = (
    "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"
)


def tray_pixmap():
    pm = QPixmap()
    pm.loadFromData(base64.b64decode("".join(TRAY_ICON_B64.split())), "PNG")
    return pm


def trim_memory():
    """Give freed memory back to Windows (what Task Manager shows) while the launcher sits hidden."""
    try:
        import gc
        gc.collect()
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.EmptyWorkingSet.argtypes = [ctypes.c_void_p]
        psapi.EmptyWorkingSet(k32.GetCurrentProcess())
    except Exception:  # noqa: BLE001
        pass


def _need_video():
    global QMediaPlayer, QVideoSink
    if QMediaPlayer is None:
        try:
            from PySide6.QtMultimedia import QMediaPlayer as _P, QVideoSink as _S
            QMediaPlayer, QVideoSink = _P, _S
        except ImportError:
            return False
    return True


# ------------------------------------------------------------------ theme (cc_theme.json: the file Vapor's theme card writes)
THEME_NAME = "cc_theme.json"
_THEME = {"path": "", "at": 0.0}


def theme_file():
    """cc_theme.json in the Vapor folder (so Vapor and Synapse share one theme), else next to Synapse."""
    now = time.time()
    if _THEME["path"] and now - _THEME["at"] < 5:
        return _THEME["path"]
    path = os.path.join(DATA_DIR, THEME_NAME)
    try:
        vc = vaporctl_path(_CFG_REF)
        if vc and os.path.isfile(os.path.join(os.path.dirname(vc), THEME_NAME)):
            path = os.path.join(os.path.dirname(vc), THEME_NAME)
    except Exception:  # noqa: BLE001
        pass
    _THEME.update(path=path, at=now)
    return path


def theme_state():
    try:
        with open(theme_file(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def write_theme_state(**kv):
    st = theme_state()
    st.update(kv)
    try:
        with open(theme_file(), "w", encoding="utf-8") as f:
            json.dump(st, f, indent=2)
    except OSError:
        log("could not write cc_theme.json:\n" + traceback.format_exc())


DEFAULT_BASE = dict(accent="#4cc2ff", tint="150,175,255", bg=(3, 4, 10, 153), outline=(150, 175, 255, 60),
                    sub="rgb(150,150,165)", on="black", acrylic=(0x40 << 24) | (42 << 16) | (32 << 8) | 16)
BASE = dict(DEFAULT_BASE)


def refresh_base():
    """Un-rotated palette (hue 0): the default blue, with the saturation / lightness saved from the advanced color editor."""
    global BASE
    base = dict(DEFAULT_BASE)
    st = theme_state()
    try:
        sat, light = int(st.get("color_sat", 100)), int(st.get("color_light", 88))
    except (TypeError, ValueError):
        sat, light = 100, 88
    if (sat, light) != (100, 88):
        base["accent"] = QColor.fromHsv(0, max(0, min(255, round(sat * 2.55))), max(0, min(255, round(light * 2.55)))).name()
    BASE = base


def _c3(spec):
    c = qc(spec)
    return (c.red(), c.green(), c.blue())


def themed(hue):
    b = BASE
    if not hue:
        return dict(b)
    accent = "#%02x%02x%02x" % rot_rgb(_c3(b["accent"]), hue)
    tint = "%d,%d,%d" % rot_rgb(_c3("rgb(%s)" % b["tint"]), hue)
    bg = tuple(rot_rgb(tuple(b["bg"][:3]), hue)) + (b["bg"][3],)
    outline = tuple(rot_rgb(tuple(b["outline"][:3]), hue)) + (b["outline"][3],)
    sub_ = "rgb(%d,%d,%d)" % rot_rgb(_c3(b["sub"]), hue)
    a = int(b["acrylic"])
    r, g, bl = rot_rgb((a & 255, (a >> 8) & 255, (a >> 16) & 255), hue)
    acrylic = ((a >> 24) & 255) << 24 | bl << 16 | g << 8 | r
    return dict(accent=accent, tint=tint, bg=bg, outline=outline, sub=sub_, on=b["on"], acrylic=acrylic)


def saved_hue():
    try:
        return max(0, min(359, int(theme_state().get("hue", 0) or 0)))
    except (TypeError, ValueError):
        return 0


def write_hue_file(hue):
    write_theme_state(hue=hue, theme=(hue or None))


def qc(spec, alpha=None):
    if isinstance(spec, str) and spec.startswith("#"):
        c = QColor(spec)
    else:
        nums = [int(n) for n in re.findall(r"\d+", spec)][:3]
        c = QColor(*nums)
    if alpha is not None:
        c.setAlpha(alpha)
    return c


def make_qss(t):
    fam = ", ".join("'%s'" % f for f in [TEXT_FONT] + FALLBACKS)
    return f"""
* {{ font-family: {fam}; font-size: 12px; color: white; }}
QLabel {{ background: transparent; }}
#sIcon {{ font-family: '{ICON_FONT}'; font-size: 18px; color: {t['accent']}; }}
QLineEdit {{ background: transparent; border: none; font-size: 17px;
             selection-background-color: {t['accent']}; selection-color: {t['on']}; placeholder-text-color: {t['sub']}; }}
#foot {{ font-family: '{MONO_FONT}', 'CaskaydiaCove Nerd Font Mono', 'Cascadia Code'; font-size: 10px; color: {t['sub']}; }}
"""


@lru_cache(maxsize=128)
def rounded_region(w, h, r):
    base = QRegion(0, 0, w, h)
    for left in (True, False):
        for top in (True, False):
            sq = QRegion(0 if left else w - r, 0 if top else h - r, r, r)
            circle = QRegion(0 if left else w - 2 * r, 0 if top else h - 2 * r, 2 * r, 2 * r,
                             QRegion.RegionType.Ellipse)
            base = base.subtracted(sq).united(circle.intersected(sq))
    return base


# ------------------------------------------------------------------ search
def scan_apps(custom=()):
    roots = [os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
             os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs")]
    found = {}
    for root in roots:
        for dp, _dirs, files in os.walk(root):
            for f in files:
                name, ext = os.path.splitext(f)
                if ext.lower() not in (".lnk", ".url", ".appref-ms") or any(s in name.lower() for s in SKIP):
                    continue
                found.setdefault(name.lower(), dict(kind="app", title=name, sub="Application", path=os.path.join(dp, f)))
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    for title, exe, alias in BUILTIN_APPS:
        path = ""
        for d in (os.path.join(sysroot, "System32"), sysroot, os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WindowsApps")):
            cand = os.path.join(d, exe)
            if os.path.lexists(cand):                         # lexists: Windows 11's "app execution aliases" are reparse points
                path = cand
                break
        path = path or BUILTIN_FALLBACK.get(exe.lower(), "")
        if not path:
            continue
        if title.lower() in found:
            found[title.lower()]["alias"] = alias                 # already in the Start Menu: just teach it the exe name
        else:
            found[title.lower()] = dict(kind="app", title=title, sub="Application", path=path, alias=alias)
    for c in custom or ():                                   # apps added with >add (portable apps, other drives, scripts ...)
        try:
            title, path = str(c.get("title") or "").strip(), str(c.get("path") or "").strip()
        except AttributeError:
            continue
        if title and path and os.path.exists(path):
            found[title.lower()] = dict(kind="app", title=title, sub="Application", path=path)
    return sorted(found.values(), key=lambda a: a["title"].lower())


FILE_ROOTS = [os.path.expanduser("~")]            # always searched first; every fixed drive (C:, D:, E: ...) is added automatically
FILE_SKIP = {"appdata", "node_modules", "__pycache__", "site-packages", "$recycle.bin", "system volume information",
             "application data", "local settings", "cookies", "venv", ".venv", ".git", ".cache", ".gradle", ".m2", ".npm"}
DRIVE_SKIP = {"windows", "program files", "program files (x86)", "programdata", "$recycle.bin", "system volume information",
              "recovery", "config.msi", "$windows.~bt", "$windows.~ws", "msocache", "perflogs"}    # only skipped at the top of a drive
FILE_LIMIT = 250000                                # most entries kept in the index (shallow folders are indexed first)


def fixed_drives():
    """['C:\\\\', 'D:\\\\', ...] for every fixed (non-removable, non-network) drive."""
    out = []
    try:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if mask & (1 << i):
                root = "%s:\\" % chr(65 + i)
                if ctypes.windll.kernel32.GetDriveTypeW(root) == 3:        # DRIVE_FIXED
                    out.append(root)
    except Exception:  # noqa: BLE001
        pass
    return out


def scan_files(extra_roots=()):
    """Breadth-first walk of the home folder + every fixed drive (+ file_roots from the settings) -> [(lowercase name, full path)]."""
    roots, seen = [], set()
    for r in list(FILE_ROOTS) + list(extra_roots or ()) + fixed_drives():
        r = clean_path(str(r))
        k = os.path.normcase(os.path.abspath(r)) if r else ""
        if k and k not in seen and os.path.isdir(r):
            seen.add(k)
            roots.append(r)
    drive_roots = {os.path.normcase(os.path.abspath(r)) for r in roots if os.path.dirname(os.path.abspath(r)) == os.path.abspath(r)}
    out, queue = [], deque(roots)
    while queue and len(out) < FILE_LIMIT:
        d = queue.popleft()
        at_top = os.path.normcase(os.path.abspath(d)) in drive_roots
        try:
            with os.scandir(d) as it:
                for e in it:
                    nl = e.name.lower()
                    try:
                        if e.is_symlink():
                            continue
                        isd = e.is_dir(follow_symlinks=False)
                    except OSError:
                        continue
                    if isd and (nl in FILE_SKIP or (at_top and nl in DRIVE_SKIP)):
                        continue
                    if isd and os.path.normcase(os.path.abspath(e.path)) in seen:
                        continue                                  # a root that is already queued (e.g. your home folder under C:\)
                    out.append((nl, e.path))
                    if isd:
                        queue.append(e.path)
        except OSError:
            continue
    return out


# ---- Everything (voidtools) -- instant file search through its SDK dll or es.exe; falls back to the built-in index
_EV_DLLS = [os.path.join(HERE, "Everything64.dll"), os.path.join(HERE, "Everything32.dll"),
            r"C:\Program Files\Everything\Everything64.dll", r"C:\Program Files (x86)\Everything\Everything64.dll",
            r"C:\Program Files\Everything 1.5a\Everything64.dll", "Everything64.dll"]
_EV_ES = [os.path.join(HERE, "es.exe"), r"C:\Program Files\Everything\es.exe", r"C:\Program Files (x86)\Everything\es.exe",
          r"C:\Program Files\Everything 1.5a\es.exe"]
_EVY = dict(dll=None, tried=False, es=None, lock=threading.Lock())


def _ev_load():
    if _EVY["tried"]:
        return
    _EVY["tried"] = True
    for d in _EV_DLLS:
        try:
            if os.path.isabs(d) and not os.path.isfile(d):
                continue
            dll = ctypes.WinDLL(d)
            dll.Everything_SetSearchW.argtypes = [wintypes.LPCWSTR]
            dll.Everything_SetMax.argtypes = [wintypes.DWORD]
            dll.Everything_SetRequestFlags.argtypes = [wintypes.DWORD]
            dll.Everything_SetSort.argtypes = [wintypes.DWORD]
            dll.Everything_QueryW.argtypes = [wintypes.BOOL]
            dll.Everything_QueryW.restype = wintypes.BOOL
            dll.Everything_GetNumResults.restype = wintypes.DWORD
            dll.Everything_GetResultFullPathNameW.argtypes = [wintypes.DWORD, ctypes.c_wchar_p, wintypes.DWORD]
            _EVY["dll"] = dll
            break
        except (OSError, AttributeError):
            continue
    for e in _EV_ES:
        if os.path.isfile(e):
            _EVY["es"] = e
            break
    if not _EVY["es"]:
        import shutil
        _EVY["es"] = shutil.which("es.exe") or shutil.which("es")


def everything_ready():
    """True when Everything is installed and running (so file search can skip our own index entirely)."""
    _ev_load()
    if _EVY["dll"] is not None:
        try:
            return bool(_EVY["dll"].Everything_IsDBLoaded())
        except Exception:  # noqa: BLE001
            return False
    return bool(_EVY["es"]) and bool(ctypes.windll.user32.FindWindowW("EVERYTHING_TASKBAR_NOTIFICATION", None)
                                    or ctypes.windll.user32.FindWindowW("EVERYTHING", None))


def everything_search(term, limit=40):
    """Returns a list of full paths, or None if Everything isn't available (caller then uses the built-in index)."""
    _ev_load()
    term = term.strip()
    if not term:
        return []
    if _EVY["dll"] is not None:
        with _EVY["lock"]:
            try:
                dll = _EVY["dll"]
                dll.Everything_SetSearchW(term)
                dll.Everything_SetMax(limit)
                dll.Everything_SetRequestFlags(0x00000004)               # EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME
                dll.Everything_SetSort(1)                                # name ascending; Everything ranks by match first
                if dll.Everything_QueryW(True):
                    buf = ctypes.create_unicode_buffer(32768)
                    out = []
                    for i in range(min(dll.Everything_GetNumResults(), limit)):
                        dll.Everything_GetResultFullPathNameW(i, buf, 32768)
                        out.append(buf.value)
                    return out
            except Exception:  # noqa: BLE001
                log("everything dll failed:\n" + traceback.format_exc())
    if _EVY["es"]:
        try:
            r = subprocess.run([_EVY["es"], "-n", str(limit), term], capture_output=True, text=True, timeout=3,
                               creationflags=0x08000000, encoding="utf-8", errors="replace")
            if r.returncode == 0:
                return [ln for ln in r.stdout.splitlines() if ln.strip()]
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def match_files(index, term, limit=40):
    """'hello' finds hello.txt, hello.py, my hello notes.md ...   Words must all appear in the name; * and ? work too."""
    tl = term.lower().strip()
    toks = tl.split()
    if not toks:
        return []
    glob = "*" in tl or "?" in tl
    hits = []
    for nl, path in index:
        if glob:
            if not fnmatch.fnmatch(nl, tl):
                continue
            sc = len(nl)
        else:
            if not all(t in nl for t in toks):
                continue
            stem = nl.rsplit(".", 1)[0] if "." in nl[1:] else nl
            sc = (0 if tl in (nl, stem) else 1 if nl.startswith(toks[0]) else 2) * 1000 + len(nl)
        hits.append((sc, path))
    return [p for _s, p in heapq.nsmallest(limit, hits, key=lambda x: x[0])]


def fuzzy(q, name):
    n = name.lower()
    if n == q:
        return 1000
    if n.startswith(q):
        return 800 - len(n) + len(q)
    if (" " + q) in n:
        return 600 - n.index(" " + q)
    if q in n:
        return 400 - n.index(q)
    i = 0
    for ch in n:
        if i < len(q) and ch == q[i]:
            i += 1
    return 100 - len(n) if i == len(q) else None


_OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.FloorDiv: op.floordiv,
        ast.Pow: op.pow, ast.Mod: op.mod, ast.USub: op.neg, ast.UAdd: op.pos}
_CONSTS = dict(pi=math.pi, e=math.e, tau=math.tau)
_FUNCS = dict(sqrt=math.sqrt, sin=math.sin, cos=math.cos, tan=math.tan, asin=math.asin, acos=math.acos, atan=math.atan,
              log=math.log10, log10=math.log10, log2=math.log2, ln=math.log, exp=math.exp, abs=abs, round=round,
              floor=math.floor, ceil=math.ceil, deg=math.degrees, rad=math.radians, fact=math.factorial)


def _ev(n):
    if isinstance(n, ast.Expression):
        return _ev(n.body)
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return n.value
    if isinstance(n, ast.Name) and n.id.lower() in _CONSTS:
        return _CONSTS[n.id.lower()]
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id.lower() in _FUNCS and not n.keywords \
            and 1 <= len(n.args) <= 2:
        args = [_ev(x) for x in n.args]
        if n.func.id.lower() == "fact" and not (0 <= args[0] <= 170):
            raise ValueError
        return _FUNCS[n.func.id.lower()](*args)
    if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
        a, b = _ev(n.left), _ev(n.right)
        if isinstance(n.op, ast.Pow) and abs(b) > 100:
            raise ValueError
        return _OPS[type(n.op)](a, b)
    if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
        return _OPS[type(n.op)](_ev(n.operand))
    raise ValueError


def calc(q, explicit=False):
    """Plain sums (12*(3+4)) work anywhere; a leading = switches on calculator mode, which also allows
    functions and constants: =sqrt(16)+2^3, =sin(pi/2), =round(2.567,1)."""
    s = q.strip().lstrip("=").strip().replace("\u00d7", "*").replace("\u00f7", "/")
    if explicit:
        if not s or not re.fullmatch(r"[\w\s+\-*/().%^,]+", s):
            return None
    elif not re.fullmatch(r"[\d\s+\-*/().%^]+", s) or not re.search(r"[+\-*/%^]", s.lstrip("-")):
        return None
    try:
        v = _ev(ast.parse(s.replace("^", "**"), mode="eval"))
        if isinstance(v, complex) or math.isnan(v) or math.isinf(v):
            return None
        return str(int(v)) if float(v).is_integer() and abs(v) < 1e15 else "%.10g" % v
    except Exception:  # noqa: BLE001
        return None


# ------------------------------------------------------------------ icons for .url shortcuts (Steam games)
def _square_pm(path, size=32):
    pm = QPixmap(path)
    if pm.isNull():
        return None
    if pm.width() != pm.height():                           # header / capsule art -> centre square
        side = min(pm.width(), pm.height())
        pm = pm.copy((pm.width() - side) // 2, (pm.height() - side) // 2, side, side)
    return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


@lru_cache(maxsize=1)
def _steam_dir():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            d = winreg.QueryValueEx(k, "SteamPath")[0]
            if os.path.isdir(d):
                return os.path.normpath(d)
    except Exception:  # noqa: BLE001
        pass
    for d in (os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Steam"), os.path.join(os.environ.get("ProgramFiles", ""), "Steam")):
        if os.path.isdir(d):
            return d
    return ""


def url_icon(path):
    """Icon for an Internet Shortcut: its IconFile (.ico) if that still exists, else for steam://rungameid/<id>
    the art Steam cached in appcache\\librarycache. Returns None when nothing usable is found."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except OSError:
        return None
    icon_file = re.search(r"^IconFile=(.+)$", txt, re.M)
    target = re.search(r"^URL=(.+)$", txt, re.M)
    if icon_file:
        ic = os.path.expandvars(icon_file.group(1).strip().strip('"'))
        if ic.lower().endswith(".ico") and os.path.isfile(ic):
            pm = QIcon(ic).pixmap(32, 32)
            if not pm.isNull():
                return pm
    m = re.search(r"steam://(?:rungameid|run|launch)/(\d+)", target.group(1) if target else "", re.I)
    if not m:
        return None
    appid = m.group(1)
    base = _steam_dir()
    if not base and icon_file:                              # ...\Steam\steam\games\x.ico -> ...\Steam
        base = os.path.dirname(os.path.dirname(os.path.dirname(icon_file.group(1).strip().strip('"'))))
    cache = os.path.join(base, "appcache", "librarycache")
    if not os.path.isdir(cache):
        return None
    old = os.path.join(cache, appid + "_icon.jpg")           # older Steam layout
    if os.path.isfile(old):
        return _square_pm(old)
    folder = os.path.join(cache, appid)                      # newer layout: <appid>\<40-hex hash>.jpg is the small icon
    if os.path.isdir(folder):
        found = []
        for dp, _d, files in os.walk(folder):
            found += [os.path.join(dp, f) for f in files if f.lower().endswith((".jpg", ".png"))]
        for pat in (r"[0-9a-f]{40}\.jpg", r"library_capsule\.|library_600x900\.", r"header\.|capsule_184x69\.|logo\."):
            for f in found:
                if re.match(pat, os.path.basename(f), re.I):
                    pm = _square_pm(f)
                    if pm is not None:
                        return pm
    return None


def paint_pixmap(size=32):
    """Paint has no icon the shell can read when it is the Store app (mspaint.exe is just an alias), so draw one:
    a rounded tile with a palette glyph."""
    dpr = 2
    pm = QPixmap(size * dpr, size * dpr)
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0.0, QColor(255, 154, 72))
    g.setColorAt(0.55, QColor(244, 84, 140))
    g.setColorAt(1.0, QColor(126, 92, 255))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(1, 1, size - 2, size - 2), size * 0.26, size * 0.26)
    p.setFont(_font(int(size * 0.58), icon=True))
    p.setPen(QColor("white"))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "\uE790")      # Segoe Fluent "Color" palette
    p.end()
    return pm


# ------------------------------------------------------------------ result list (custom painted, animated)
def quote_text(cfg):
    """The text on the quote card: launcher_settings.json -> "quote_text" (>setquote), else DEFAULT_QUOTE."""
    t = str((cfg or {}).get("quote_text") or "").replace("\\n", "\n").strip()
    return t or DEFAULT_QUOTE


def _wrap_lines(text, fm, maxw):
    """Word-wrap text to maxw pixels with the given QFontMetrics (keeps explicit new lines, splits words wider than the card)."""
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            cand = (line + " " + word) if line else word
            if fm.horizontalAdvance(cand) <= maxw:
                line = cand
                continue
            if line:
                out.append(line)
            while len(word) > 1 and fm.horizontalAdvance(word) > maxw:
                k = len(word)
                while k > 1 and fm.horizontalAdvance(word[:k]) > maxw:
                    k -= 1
                out.append(word[:k])
                word = word[k:]
            line = word
        out.append(line)
    return out


def fit_quote(text, w, h):
    """(font, lines, line height): the biggest size at which the quote fits the card; very long text is cut with an ellipsis."""
    for px in (13, 12, 11, 10, 9):
        f = _font(px, mono=True)
        fm = QFontMetrics(f)
        lines = _wrap_lines(text, fm, w)
        if len(lines) * fm.lineSpacing() <= h:
            return f, lines, fm.lineSpacing()
    keep = max(1, int(h // fm.lineSpacing()))
    lines = lines[:keep]
    lines[-1] = fm.elidedText(lines[-1] + "\u2026", Qt.TextElideMode.ElideRight, w)
    return f, lines, fm.lineSpacing()


def _font(px, weight=QFont.Weight.Normal, mono=False, icon=False):
    f = QFont()
    f.setFamilies([ICON_FONT] if icon else [MONO_FONT if mono else TEXT_FONT] + FALLBACKS)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


class ResultList(QWidget):
    picked = Signal()

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.t = theme
        self.empty_text = ""
        self.items, self.sel, self.hover = [], 0, -1
        self._hl = self._scroll = 0.0
        self._reveal = 1.0
        self._an = {}
        self._icons = {}
        self._prov = QFileIconProvider()
        self.setMouseTracking(True)

    def tween(self, attr, end, ms=170, curve=QEasingCurve.Type.OutCubic):
        a = self._an.get(attr)
        if a is None:
            a = QVariantAnimation(self)
            a.valueChanged.connect(lambda v, at=attr: (setattr(self, at, float(v)), self.update()))
            self._an[attr] = a
        a.stop()
        a.setEasingCurve(curve)
        a.setDuration(ms)
        a.setStartValue(float(getattr(self, attr)))
        a.setEndValue(float(end))
        a.start()

    def set_items(self, items):
        self.items, self.sel, self.hover = items, 0, -1
        self._hl = self._scroll = 0.0
        self._reveal = 0.0
        self.tween("_reveal", 1.0, 320)

    def move_sel(self, d):
        if not self.items:
            return
        self.set_sel(max(0, min(len(self.items) - 1, self.sel + d)))

    def set_sel(self, i):
        self.sel = i
        self.tween("_hl", i * ROW_H, 170)
        top = self._an["_scroll"].endValue() if "_scroll" in self._an and self._an["_scroll"].state() else self._scroll
        top = float(top)
        vis = self.height()
        if i * ROW_H < top:
            self.tween("_scroll", i * ROW_H, 200)
        elif (i + 1) * ROW_H > top + vis:
            self.tween("_scroll", (i + 1) * ROW_H - vis, 200)

    def current(self):
        return self.items[self.sel] if self.items else None

    def icon_for(self, path):
        pm = self._icons.get(path)
        if pm is None:
            low = path.lower()
            if low.startswith("ms-paint:") or os.path.basename(low) == "mspaint.exe":
                pm = paint_pixmap()                       # Windows 11's Store Paint is an alias with no icon of its own
            else:
                if low.endswith(".url"):                  # Steam & friends: the shell often shows a blank page for these
                    pm = url_icon(path)
                if pm is None or pm.isNull():
                    pm = self._prov.icon(QFileInfo(path)).pixmap(32, 32)
            self._icons[path] = pm
        return pm

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        t = self.t
        accent, sub = qc(t["accent"]), qc(t["sub"])
        if not self.items:
            if self.empty_text:
                p.setPen(sub)
                p.setFont(_font(12, mono=True))
                p.drawText(QRectF(0, 0, self.width(), self.height()), Qt.AlignmentFlag.AlignCenter, self.empty_text)
            p.end()
            return
        if self.items:
            r = QRectF(8, self._hl - self._scroll + 3, self.width() - 16, ROW_H - 6)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc(t["accent"], 46))
            p.drawRoundedRect(r, 10, 10)
            p.setBrush(accent)
            p.drawRoundedRect(QRectF(r.left() + 3, r.center().y() - 9, 3, 18), 1.5, 1.5)
        for i, it in enumerate(self.items):
            y = i * ROW_H - self._scroll
            if y > self.height() or y + ROW_H < 0:
                continue
            a = max(0.0, min(1.0, self._reveal * 1.7 - i * 0.09)) if i < 9 else self._reveal
            p.setOpacity(a)
            y += (1 - a) * 8
            if i == self.hover and i != self.sel:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(qc("rgb(%s)" % t["tint"], 22))
                p.drawRoundedRect(QRectF(8, y + 3, self.width() - 16, ROW_H - 6), 10, 10)
            box = QRectF(22, y + (ROW_H - 30) / 2, 30, 30)
            pm = self.icon_for(it["path"]) if it["kind"] in ("app", "file") else None
            if pm is not None and not pm.isNull():
                p.drawPixmap(box.toRect().adjusted(1, 1, -1, -1), pm)
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(qc("rgb(%s)" % t["tint"], 34))
                p.drawRoundedRect(box, 8, 8)
                p.setFont(_font(16, icon=True))
                p.setPen(accent)
                p.drawText(box, Qt.AlignmentFlag.AlignCenter, it.get("glyph", "\uECAA"))
            calc_row = it["kind"] == "calc"
            p.setPen(QColor("white"))
            p.setFont(_font(17 if calc_row else 13, QFont.Weight.DemiBold, mono=calc_row))
            p.drawText(QRectF(64, y + 6, self.width() - 120, 22), Qt.AlignmentFlag.AlignVCenter, it["title"])
            p.setPen(sub)
            p.setFont(_font(11))
            p.drawText(QRectF(64, y + 27, self.width() - 120, 16), Qt.AlignmentFlag.AlignVCenter, it["sub"])
            if i == self.sel:
                p.setPen(sub)
                p.setFont(_font(12, mono=True))
                p.drawText(QRectF(self.width() - 56, y, 36, ROW_H), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "\u21B5")
        p.end()

    def _row_at(self, y):
        i = int((y + self._scroll) // ROW_H)
        return i if 0 <= i < len(self.items) else -1

    def mouseMoveEvent(self, e):
        i = self._row_at(e.position().y())
        if i != self.hover:
            self.hover = i
            if i >= 0 and i != self.sel:
                self.set_sel(i)
            self.update()

    def mousePressEvent(self, e):
        i = self._row_at(e.position().y())
        if i >= 0:
            self.set_sel(i)
            self.picked.emit()

    def wheelEvent(self, e):
        mx = max(0.0, len(self.items) * ROW_H - self.height())
        cur = float(self._an["_scroll"].endValue()) if "_scroll" in self._an and self._an["_scroll"].state() else self._scroll
        self.tween("_scroll", max(0.0, min(mx, cur - e.angleDelta().y() * 0.5)), 160)

    def leaveEvent(self, _e):
        self.hover = -1
        self.update()


# ------------------------------------------------------------------ small data helpers (no extra packages)
class _PWR(ctypes.Structure):
    _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("pct", ctypes.c_ubyte), ("sys", ctypes.c_ubyte),
                ("life", ctypes.c_ulong), ("full", ctypes.c_ulong)]


def wmo_text(c):
    for lim, txt in ((0, "Clear Sky"), (1, "Mainly Clear"), (2, "Partly Cloudy"), (3, "Overcast"), (48, "Foggy"),
                     (57, "Drizzle"), (67, "Rain"), (77, "Snow"), (82, "Showers"), (86, "Snow Showers"), (99, "Thunderstorm")):
        if c <= lim:
            return txt
    return "Cloudy"


def fetch_weather():
    import urllib.request
    place, lat, lon, fahr = weather_location(_CFG_REF)
    WX["place"] = place
    url = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s&current=temperature_2m,weather_code"
           "&timezone=auto%s" % (lat, lon, "&temperature_unit=fahrenheit" if fahr else ""))
    with urllib.request.urlopen(url, timeout=6) as r:
        d = json.load(r)
    code = int(d["current"]["weather_code"])
    return dict(temp=round(d["current"]["temperature_2m"]), unit="F" if fahr else "C", code=code, text=wmo_text(code), place=place)


class _FT(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]


def cpu_times():
    idle, kern, user = _FT(), _FT(), _FT()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
    f = lambda x: (x.hi << 32) | x.lo                            # noqa: E731
    return f(idle), f(kern) + f(user)                            # kernel time already includes idle time


def rot_rgb(rgb, deg):
    h, s_, v = colorsys.rgb_to_hsv(*(c / 255.0 for c in rgb))
    r, g, b = colorsys.hsv_to_rgb((h + deg / 360.0) % 1.0, s_, v)
    return (round(r * 255), round(g * 255), round(b * 255))


# ---- little icons drawn with the painter (so no icon-font guessing)
def sparkle(cx, cy, r):
    pts = []
    for i in range(8):
        ang = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.28
        pts.append(QPointF(cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    return QPolygonF(pts)


def _line_pen(p, col, w=1.6):
    p.setPen(QPen(col, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)


def draw_battery(p, x, y, pct, col):
    _line_pen(p, col)
    p.drawRoundedRect(QRectF(x + 5, y + 4, 20, 30), 4, 4)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(col)
    p.drawRoundedRect(QRectF(x + 11, y, 8, 3.5), 1, 1)
    h = 22.0 * max(4, min(100, pct)) / 100.0
    p.drawRoundedRect(QRectF(x + 9, y + 8 + 22 - h, 12, h), 2, 2)


def draw_chip(p, x, y, col):
    _line_pen(p, col)
    p.drawRoundedRect(QRectF(x + 8, y + 8, 22, 22), 3, 3)
    p.drawRect(QRectF(x + 14, y + 14, 10, 10))
    for i in range(3):
        o = 12 + i * 7
        p.drawLine(QPointF(x + o, y + 2), QPointF(x + o, y + 8))
        p.drawLine(QPointF(x + o, y + 30), QPointF(x + o, y + 36))
        p.drawLine(QPointF(x + 2, y + o), QPointF(x + 8, y + o))
        p.drawLine(QPointF(x + 30, y + o), QPointF(x + 36, y + o))


def draw_gpu(p, x, y, col):
    _line_pen(p, col)
    p.drawRoundedRect(QRectF(x + 3, y + 7, 32, 24), 4, 4)
    p.drawEllipse(QPointF(x + 19, y + 19), 8, 8)
    p.drawEllipse(QPointF(x + 19, y + 19), 2.5, 2.5)


def draw_bolt(p, x, y, col, s=1.0):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(col)
    pts = [(5, 0), (0, 8), (4, 8), (2, 15), (9, 5), (5, 5)]
    p.drawPolygon(QPolygonF([QPointF(x + a * s, y + b * s) for a, b in pts]))


def draw_spark(p, rect, vals, col):
    """Smooth sparkline (0-100 scale) with a soft fill under it."""
    if len(vals) < 2:
        return
    n = len(vals)
    pts = [QPointF(rect.x() + rect.width() * i / (n - 1), rect.bottom() - rect.height() * max(0.0, min(100.0, v)) / 100.0)
           for i, v in enumerate(vals)]
    line = QPainterPath(pts[0])
    for a, b in zip(pts, pts[1:]):
        mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
        line.quadTo(a, mid)
    line.lineTo(pts[-1])
    fill = QPainterPath(line)
    fill.lineTo(QPointF(rect.right(), rect.bottom()))
    fill.lineTo(QPointF(rect.x(), rect.bottom()))
    fill.closeSubpath()
    g = QLinearGradient(0, rect.y(), 0, rect.bottom())
    top = QColor(col)
    top.setAlpha(80)
    bot = QColor(col)
    bot.setAlpha(0)
    g.setColorAt(0, top)
    g.setColorAt(1, bot)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.drawPath(fill)
    _line_pen(p, col, 1.8)
    p.drawPath(line)


def draw_weather_icon(p, x, y, code, col):
    _line_pen(p, col)
    if code <= 1:
        p.drawEllipse(QPointF(x + 17, y + 17), 6, 6)
        for i in range(8):
            ang = math.pi / 4 * i
            p.drawLine(QPointF(x + 17 + 10 * math.cos(ang), y + 17 + 10 * math.sin(ang)),
                       QPointF(x + 17 + 14 * math.cos(ang), y + 17 + 14 * math.sin(ang)))
        return
    path = QPainterPath()
    path.addEllipse(QRectF(x + 2, y + 14, 13, 13))
    path.addEllipse(QRectF(x + 8, y + 5, 17, 17))
    path.addEllipse(QRectF(x + 19, y + 12, 14, 14))
    path.addRect(QRectF(x + 9, y + 17, 17, 10))
    p.drawPath(path.simplified())


# ------------------------------------------------------------------ Vapor (>vapor ...): talks to vaporctl.py
PFP_SIZE = 512            # profile pictures are saved at most this many pixels square (Vapor shows them at a fraction of this,
                          # so even a 4K screen stays sharp; bigger would only cost memory)
VAPOR = ""                # optional: folder of the Vapor shell.  Leave empty: it is found through the PATH entry Vapor adds
                          # (override: launcher_settings.json -> "customizations": {"vapor": "..."})
# (fill text, shown usage, description, glyph)  -  a fill ending in a space still needs an argument
VAPOR_HINTS = (("status", "status", "Volume, battery, wifi, media, workspace, layout, bar state", "\uE946"),
               ("fetch", "fetch", "Logo + version + live status in one coloured card", "\uE946"),
               ("update", "update [--check|--force|--extras]", "Open the Vapor installer in a command window and update  (--check only looks)", "\uE896"),
               ("update --check", "update --check", "Only look for a newer release, change nothing", "\uE896"),
               ("--version", "--version", "Installed Vapor version", "\uE946"),
               ("set name ", "set name <name>", "Name on the profile card", "\uE77B"),
               ("set name --reset", "set name --reset", "Use your Windows user name again", "\uE77B"),
               ("set pfp", 'set pfp ["path"] [-c]', "Profile picture  (-c = crop it round first, no path = pick a file, reset = remove)", "\uE91B"),
               ("set location ", "set location <place|auto> [--f|--c]", "Weather place, e.g. Pokhara or Paris, France  (auto = from your IP)", "\uE707"),
               ("start", "start", "Start Vapor", "\uE768"),
               ("restart", "restart", "Restart Vapor", "\uE72C"),
               ("quit", "quit", "Close Vapor", "\uE7E8"),
               ("stop --force", "stop [--force]", "Close Vapor  (--force kills a hung copy)", "\uE7E8"),
               ("toggle", "toggle", "Slide the bar away / back", "\uE700"),
               ("hide", "hide", "Slide the bar away", "\uE700"),
               ("show", "show", "Slide the bar back", "\uE700"),
               ("volume", "volume [N|+N|-N]", "Show / set / step the volume", "\uE767"),
               ("mute", "mute [on|off]", "Toggle (or force) mute", "\uE74F"),
               ("media", "media [play|next|prev]", "Control the active player, no argument shows what is playing", "\uE8D6"),
               ("ws ", "ws <N|next|prev>", "Switch komorebi workspace  (N starts at 1)", "\uE7F4"),
               ("layout", "layout [next|prev]", "Cycle the komorebi layout", "\uE80A"),
               ("alert ", 'alert "title" ["text"]', "In-bar alert card + ringtone  (>vapor dismiss stops it)", "\uE7E7"),
               ("dismiss", "dismiss", "Dismiss the current alert / stop the ringtone", "\uE711"),
               ("notify ", 'notify "title" ["text"]', "Normal Windows toast", "\uE8BD"),
               ("remind ", 'remind <when> "text" [--every daily|weekly|monthly]', 'Add a reminder, e.g. remind 7pm "call mom"', "\uE823"),
               ("reminders", "reminders [list|rm <N>]", "List the reminders + the running timer", "\uE823"),
               ("timer ", "timer <5m|1h30m|90|cancel>", "Start the clock-page timer", "\uE916"),
               ("note", 'note ["text"] [-t "title"]', "Add a note  (no text = list, show <N>, rm <N>)", "\uE70B"),
               ("ringtone", "ringtone [path|test]", "Show / replace the alarm sound (an .mp3) / play it once", "\uE8D6"),
               ("wallpaper", "wallpaper [file|random|next|prev|dir <folder>]", "Show / set the desktop wallpaper", "\uE91B"),
               ("reload", "reload", "Re-read config.json without restarting", "\uE72C"),
               ("autostart", "autostart [on|off]", "Start Vapor at every login", "\uE768"),
               ("log", "log [N]", "Last N lines of vapor.log  (default 40)", "\uE8A5"),
               ("paths", "paths", "Where config, files, log and settings live", "\uE8B7"),
               ("config", "config", "Open config.json", "\uE713"),
               ("config get", "config get [key]", "Show one config.json key  (no key = all of them)", "\uE713"),
               ("config set ", "config set <key> <value>", "Change one config.json key", "\uE713"),
               ("config unset ", "config unset <key>", "Remove one config.json key", "\uE713"),
               ("files", "files", "Open the Vapor files folder", "\uE8B7"),
               ("doctor", "doctor [--report]", "Check install, config, log and helpers  (--report adds the log tail + config for bug reports)", "\uE9D9"),
               ("help", "help", "The full vaporctl command list", "\uE897"))


def read_image(path):
    """QImage with the camera's rotation (EXIF) applied, so what the cropper shows is what the picture really looks like."""
    r = QImageReader(path)
    r.setAutoTransform(True)
    return r.read()


def crop_square(img, crop, size=PFP_SIZE):
    """crop = (x, y, w, h) as fractions of the picture, from the round cropper -> a square QImage, cut from the ORIGINAL pixels
    (not from the screen-sized preview), reduced with the smooth filter only when it is bigger than `size`, never enlarged."""
    W, H = img.width(), img.height()
    x, y, w, h = (float(v) for v in crop)
    side = max(1, min(int(round((w * W + h * H) / 2)), W, H))
    px = max(0, min(W - side, int(round(x * W))))
    py = max(0, min(H - side, int(round(y * H))))
    out = img.copy(px, py, side, side)
    if side > size:
        out = out.scaled(size, size, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return out.convertToFormat(QImage.Format.Format_ARGB32 if out.hasAlphaChannel() else QImage.Format.Format_RGB32)


def vapor_tokens(s):
    return [a or b for a, b in re.findall(r'"([^"]*)"|(\S+)', s)]


def _flag(rest, *flags):
    """Takes a leading or trailing flag word off `rest` -> (rest, found)."""
    pat, found = "|".join(re.escape(f) for f in flags), False
    m = re.search(r"(?:^|\s)(?:%s)\s*$" % pat, rest, re.I)
    if m:
        rest, found = rest[:m.start()].strip(), True
    m = re.match(r"\s*(?:%s)(?:\s+|$)" % pat, rest, re.I)
    if m:
        rest, found = rest[m.end():].strip(), True
    return rest, found


def vapor_plan(arg):
    """What `>vapor <arg>` means.  mode: 'pfp' (path, crop) | 'need' (a value is missing) | 'run' (vargs = vaporctl arguments)."""
    a = re.sub(r"(?i)^(?:pfp|picture|avatar)\b", "set pfp", arg.strip())
    a = re.sub(r"(?i)^(?:setname|name)\b", "set name", a)
    m = re.match(r"(?is)set\s+(?:pfp|picture|avatar)\b\s*(.*)$", a)
    if m:
        rest, crop = _flag(m.group(1).strip(), "-c", "--crop", "crop")
        if rest.strip('"').strip().lower() in CLEAR_WORDS:
            return dict(mode="run", vargs=["pfp", "reset"])
        return dict(mode="pfp", path=clean_path(rest) if rest else "", crop=crop)
    m = re.match(r"(?is)set\s+(?:name|username)\b\s*(.*)$", a)
    if m:
        rest = m.group(1).strip()
        if not rest:
            return dict(mode="need", what="a name,  e.g.  >vapor set name Alex")
        if rest.lower() in ("--reset", "reset", "default", "none", "clear"):
            return dict(mode="run", vargs=["set", "name", "--reset"], title="Reset the Vapor name")
        return dict(mode="run", vargs=["set", "name", rest.strip('"').strip()], title="Set the Vapor name to \u201c%s\u201d" % rest.strip('"').strip())
    m = re.match(r"(?is)(?:update|upgrade)\b\s*(.*)$", a)
    if m:
        flags = [f.lower() for f in vapor_tokens(m.group(1))]
        return dict(mode="update", vargs=["update"] + flags, check="--check" in flags, force="--force" in flags, extras="--extras" in flags)
    return dict(mode="run", vargs=vapor_tokens(arg))


_VPATH = {"found": "", "key": None, "at": 0.0}


def _path_dirs():
    """Folders on PATH: this process's, plus the user and system Path read straight from the registry.  Vapor adds its own
    folder to the user Path, and a launcher that was already running never sees that in its own environment."""
    dirs = os.environ.get("PATH", "").split(";")
    try:
        import winreg
        for root, sub_ in ((winreg.HKEY_CURRENT_USER, "Environment"),
                           (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
            try:
                with winreg.OpenKey(root, sub_) as k:
                    dirs += str(winreg.QueryValueEx(k, "Path")[0]).split(";")
            except OSError:
                pass
    except ImportError:
        pass
    return [os.path.expandvars(d.strip().strip('"')) for d in dirs if d.strip()]


def vaporctl_path(cfg):
    """Full path of vaporctl.py, or ''.  Found on its own: the folder Vapor put on your PATH (or recorded in
    %LOCALAPPDATA%\\vapor\\path_entry.txt), else next to Synapse.  "customizations": {"vapor": "folder"} overrides it.
    Cached, because this is asked on every key you type after >vapor."""
    c = cfg.get("customizations")
    c = c if isinstance(c, dict) else {}
    key, now = (str(c.get("vapor") or ""), VAPOR), time.time()
    if _VPATH["key"] == key:
        if _VPATH["found"] and os.path.isfile(_VPATH["found"]):
            return _VPATH["found"]
        if not _VPATH["found"] and now - _VPATH["at"] < 5:
            return ""

    def probe(cand):
        if not cand:
            return ""
        p = clean_path(str(cand))
        f = p if os.path.basename(p).lower() == "vaporctl.py" else os.path.join(p if os.path.isdir(p) else os.path.dirname(p), "vaporctl.py")
        return f if os.path.isfile(f) else ""

    found = probe(c.get("vapor")) or probe(VAPOR)
    if not found:
        for d in _path_dirs():
            found = probe(d)
            if found:
                break
    if not found:
        try:
            with open(os.path.join(os.environ.get("LOCALAPPDATA", ""), "vapor", "path_entry.txt"), encoding="utf-8") as f:
                found = probe(f.read().strip())
        except OSError:
            pass
    if not found:
        found = probe(HERE)
    _VPATH.update(found=found, key=key, at=now)
    return found


def system_python(console=False):
    """A real Python interpreter.  Running as a script that is the current one; inside Synapse.exe sys.executable is
    Synapse itself (starting it with -m or a script would open another launcher), so look on PATH instead."""
    if not FROZEN:
        exe = sys.executable
        alt = os.path.join(os.path.dirname(exe), "python.exe" if console else "pythonw.exe")
        return alt if os.path.isfile(alt) else exe
    names = ("python", "py") if console else ("pythonw", "pyw", "python")
    for skip_store in (True, False):                                # the Microsoft Store stubs are only a last resort
        for n in names:
            w = shutil.which(n)
            if w and not (skip_store and "windowsapps" in w.lower()):
                return w
    return ""


_VCTL = {"path": "", "mod": None}
_VCTL_LOCK = threading.Lock()


class _SysProxy:
    """vaporctl starts Vapor with sys.executable; inside a frozen Synapse.exe that would be Synapse itself."""
    def __init__(self, exe):
        self.executable = exe

    def __getattr__(self, name):
        return getattr(sys, name)


def _vctl_module(cfg):
    path = vaporctl_path(cfg)
    if not path:
        return None
    with _VCTL_LOCK:
        if _VCTL["mod"] is None or _VCTL["path"] != path:
            spec = importlib.util.spec_from_file_location("vaporctl", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _VCTL["mod"], _VCTL["path"] = mod, path
        return _VCTL["mod"]


def run_vaporctl(cfg, argv):
    """Runs a vaporctl command in this process (nothing to install, no console window) -> (ok, text).  Call from a thread."""
    if FROZEN:                                       # Synapse.exe has none of vaporctl's modules: run it with a real Python
        vpath = vaporctl_path(cfg)
        py = system_python(console=True)
        if not vpath:
            return False, 'vaporctl.py not found on your PATH  -  start Vapor once (it adds its folder to PATH), or set "customizations": {"vapor": "folder"}'
        if not py:
            return False, "Python was not found on your PATH  -  vaporctl needs it (the same Python that runs Vapor)"
        runner = ("import sys, os, runpy\np, pw = sys.argv[1], sys.argv[2]\n"
                  "if os.path.isfile(pw): sys.executable = pw\n"
                  "sys.argv = [p] + sys.argv[3:]\nrunpy.run_path(p, run_name='__main__')")
        try:
            r = subprocess.run([py, "-c", runner, vpath, system_python(console=False) or "", *[str(a) for a in argv]],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
                               stdin=subprocess.DEVNULL, cwd=os.path.dirname(vpath), creationflags=0x08000000)
        except subprocess.TimeoutExpired:
            return False, "vaporctl took too long"
        except OSError as e:
            return False, "%s: %s" % (type(e).__name__, e)
        return r.returncode == 0, ((r.stdout or "") + (r.stderr or "")).strip() or "done"
    mod = _vctl_module(cfg)
    if mod is None:
        return False, 'vaporctl.py not found on your PATH  -  start Vapor once (it adds its folder to PATH), or set "customizations": {"vapor": "folder"}'
    with _VCTL_LOCK:
        if getattr(sys, "frozen", False):
            pyw = shutil.which("pythonw") or shutil.which("pyw") or shutil.which("python")
            if pyw:
                mod.sys = _SysProxy(pyw)
        out, err, code = io.StringIO(), io.StringIO(), 0
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                mod.main([str(a) for a in argv])
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        except Exception as e:  # noqa: BLE001
            return False, "%s: %s" % (type(e).__name__, e)
    return code == 0, (out.getvalue() + err.getvalue()).strip() or "done"


def open_vapor_installer(cfg, extras=False, force=False):
    """`>vapor update`: opens the Vapor installer (scripts/install.ps1, the one-liner of the first install: logo, download
    animation) in its own command window, aimed at the folder Vapor lives in.  Config and files/ are kept by the installer.
    -> (ok, one line of text).  Call from a thread."""
    vpath = vaporctl_path(cfg)
    if not vpath:
        return False, 'vaporctl.py not found on your PATH  -  start Vapor once, or set "customizations": {"vapor": "folder"}'
    vdir = os.path.dirname(vpath)
    if not force and not os.path.isfile(os.path.join(vdir, "Vapor.exe")):
        return False, "Vapor runs from source here (no Vapor.exe)  -  git pull, or >vapor update --force to run the installer anyway"
    try:
        mod = _vctl_module(cfg)
    except Exception:  # noqa: BLE001
        mod = None
    repo = getattr(mod, "REPO", "") or os.environ.get("VAPOR_REPO") or "LoLCraft2L/Vapor-Shell"
    url = getattr(mod, "INSTALL_URL", "") or "https://raw.githubusercontent.com/%s/main/scripts/install.ps1" % repo
    ps = "& ([scriptblock]::Create((irm '%s'))) -Repo '%s' -Dir '%s'%s; Start-Sleep -Seconds 4" % (
        url, repo, vdir.replace("'", "''"), " -AskExtras" if extras else "")
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                         cwd=tempfile.gettempdir(),                  # never inside the folder it is about to replace
                         close_fds=True, creationflags=0x00000010)   # CREATE_NEW_CONSOLE: its own command window
    except OSError as e:
        return False, "could not open PowerShell: %s" % e
    return True, "Vapor installer opened in a command window  -  Vapor restarts when it is done"


_K32 = []


def vapor_running():
    """Is Vapor up?  Reads the pid it records in %LOCALAPPDATA%/vapor/cli.json and checks that the process is alive -
    no network call, so it never blocks (the launcher asks this while you type)."""
    try:
        with open(os.path.join(os.environ.get("LOCALAPPDATA", ""), "vapor", "cli.json"), encoding="utf-8") as f:
            pid = int(json.load(f).get("pid", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return False
    if pid <= 0:
        return False
    if not _K32:
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.argtypes, k.OpenProcess.restype = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE
        k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        _K32.append(k)
    k = _K32[0]
    h = k.OpenProcess(0x1000, False, pid)                       # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = wintypes.DWORD()
        return bool(k.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259      # STILL_ACTIVE
    finally:
        k.CloseHandle(h)


def vapor_start():
    ok, text = run_vaporctl(_CFG_REF, ["start"])
    return "" if ok else ((text.splitlines() or ["Couldn't start Vapor"])[0])


def vapor_stop():
    ok, text = run_vaporctl(_CFG_REF, ["stop"])
    if not ok:
        ok, text = run_vaporctl(_CFG_REF, ["stop", "--force"])
    return "" if ok else ((text.splitlines() or ["Couldn't stop Vapor"])[0])


# ------------------------------------------------------------------ places found at run time (nothing personal is hardcoded)
WX = {}                   # weather: the place last used (shown on the card until the first forecast arrives)
CACHE_DIRS = ("cache", ".cache", "caches", "qmlcache", "thumbs", "thumbnails", "thumbnail_cache", "previews", "covers")


def dotfiles_dirs(cfg):
    """Folders for the Dotfiles button (click = first, Alt+click = second): launcher_settings.json -> "dotfiles": "path" or
    ["first", "second"].  Default: the .config folder in your user profile."""
    d = cfg.get("dotfiles")
    d = [d] if isinstance(d, str) else [x for x in (d or []) if isinstance(x, str)]
    d = [clean_path(x) for x in d if x.strip()]
    return d or [os.path.join(os.path.expanduser("~"), ".config")]


_VCONF = {"f": "", "at": 0.0}


def vapor_config_file(cfg):
    """Vapor's config.json (it holds the weather place set with `vaporctl set location`), or ''.  Looked for next to
    vaporctl.py, in the folder from \"customizations\": {\"vapor\": ...} / VAPOR, in the folder Vapor recorded in
    %LOCALAPPDATA%\\vapor\\path_entry.txt, and in any PATH folder that holds Vapor.exe / vaporctl.exe, so the packaged
    build (which has no vaporctl.py) is found too.  Cached for 30 s."""
    now = time.time()
    if now - _VCONF["at"] < 30 and (not _VCONF["f"] or os.path.isfile(_VCONF["f"])):
        return _VCONF["f"]
    folders = []

    def add(p):
        if p:
            p = clean_path(str(p))
            folders.append(p if os.path.isdir(p) else os.path.dirname(p))

    vc = vaporctl_path(cfg)
    if vc:
        folders.append(os.path.dirname(vc))
    c = cfg.get("customizations")
    add((c if isinstance(c, dict) else {}).get("vapor"))
    add(VAPOR)
    try:
        with open(os.path.join(os.environ.get("LOCALAPPDATA", ""), "vapor", "path_entry.txt"), encoding="utf-8") as f:
            add(f.read().strip())
    except OSError:
        pass
    for d in [HERE] + _path_dirs():
        if any(os.path.isfile(os.path.join(d, n)) for n in ("Vapor.exe", "vaporctl.exe", "vaporctl.cmd", "vaporctl.py", "vapor.pyw")):
            folders.append(d)
    found = ""
    for d in folders:
        f = os.path.join(d, "config.json")
        if os.path.isfile(f):
            found = f
            break
    _VCONF.update(f=found, at=now)
    return found


def vapor_location_sig(cfg):
    """Changes whenever Vapor's config.json is saved (for example by `>vapor set location Paris`)."""
    try:
        f = vapor_config_file(cfg)
        return (f, os.path.getmtime(f)) if f else None
    except OSError:
        return None


def weather_location(cfg):
    """(place, lat, lon, fahrenheit): the place Vapor uses (>vapor set location ...), read from Vapor's config.json.  If
    Vapor is installed but on automatic, or isn't found: launcher_settings.json -> \"weather\": {\"place\": \"Pokhara\",
    \"lat\": 28.21, \"lon\": 83.99} (only when Vapor isn't found), else guessed once per run from your IP address."""
    import urllib.request
    vf = vapor_config_file(cfg)
    if vf:
        try:
            with open(vf, encoding="utf-8") as f:
                loc = json.load(f).get("location")
            if isinstance(loc, dict):
                return (str(loc.get("name") or "Weather"), float(loc["lat"]), float(loc["lon"]),
                        bool(loc.get("fahrenheit", False)))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
    else:
        w = cfg.get("weather")
        if isinstance(w, dict):
            try:
                return str(w.get("place") or "Weather"), float(w["lat"]), float(w["lon"]), bool(w.get("fahrenheit", False))
            except (KeyError, TypeError, ValueError):
                pass
    if "ip" not in WX:
        try:
            with urllib.request.urlopen("http://ip-api.com/json/?fields=status,city,lat,lon,countryCode", timeout=5) as r:
                d = json.load(r)
            WX["ip"] = ((str(d.get("city") or "Weather"), float(d["lat"]), float(d["lon"]), d.get("countryCode") == "US")
                        if d.get("status") == "success" else None)
        except Exception:  # noqa: BLE001
            WX["ip"] = None
    if WX["ip"]:
        return WX["ip"]
    raise ValueError("no weather location (set it with >vapor set location <place>)")


def _tree_size(path):
    try:
        if os.path.isfile(path) or os.path.islink(path):
            return os.path.getsize(path)
    except OSError:
        return 0
    total = 0
    for dp, _d, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def clean_groups(cfg):
    """What >clearcache removes -> [{"key": ..., "items": [(path, size), ...]}].  Settings, favourites, usage history, your theme
    and Vapor's config are never touched.  Extra paths: launcher_settings.json -> "cache_paths": {"vapor": [...], "harmony": [...],
    "synapse": [...], "temp": [...]}."""
    extra = cfg.get("cache_paths") if isinstance(cfg.get("cache_paths"), dict) else {}
    local, tmp, seen = os.environ.get("LOCALAPPDATA", ""), tempfile.gettempdir(), set()
    vc = vaporctl_path(cfg)
    vdir = os.path.dirname(vc) if vc else ""
    hp = picker_path(cfg)
    hdir = os.path.dirname(hp) if hp else ""

    def build(paths):
        items = []
        for p in paths:
            p = clean_path(str(p)) if p else ""
            key = os.path.normcase(os.path.abspath(p)) if p else ""
            if not p or key in seen or not os.path.lexists(p):
                continue
            seen.add(key)
            items.append((p, _tree_size(p)))
        return items

    vapor = [os.path.join(vdir, "__pycache__")] if vdir else []
    vapor += [os.path.join(local, "vapor", n) for n in CACHE_DIRS + ("vapor.log",)]
    harmony = [os.path.join(hdir, "__pycache__")] if hdir else []
    harmony += [os.path.join(hdir, n) for n in CACHE_DIRS] if hdir else []
    for base in ("Harmony", "harmony", "wallpaper_picker", "WallpaperPicker"):
        harmony += [os.path.join(local, base, n) for n in CACHE_DIRS]
    synapse = [os.path.join(HERE, "__pycache__")]
    synapse_tmp, temp = [], []
    try:
        cutoff = time.time() - 1800                              # leave anything touched in the last half hour alone
        for n in sorted(os.listdir(tmp))[:4000]:
            p = os.path.join(tmp, n)
            if n.startswith("synapse_"):
                synapse_tmp.append(p)
            elif not n.startswith("_MEI"):                       # _MEI... = the folder a running Synapse.exe lives in
                try:
                    if os.lstat(p).st_mtime < cutoff:
                        temp.append(p)
                except OSError:
                    pass
    except OSError:
        pass
    groups = (("vapor", vapor), ("harmony", harmony), ("synapse", synapse + synapse_tmp), ("temp", temp))
    return [dict(key=k, items=build(list(paths) + list(extra.get(k) or []))) for k, paths in groups]


# ------------------------------------------------------------------ crop picker (for >setmedia ... -c / >setcard ... -c / >vapor set pfp -c)
class CropWindow(QWidget):
    """Drag the box to move it, drag a corner or scroll to resize it. Its shape is locked to the card's shape."""
    done = Signal(object)                         # (x, y, w, h) as fractions of the picture, or None if cancelled

    def __init__(self, pm, aspect, init, accent, label, circle=False):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.aspect, self.accent, self.label, self._fin = aspect, qc(accent), label, False
        self.circle = circle                         # round picker (profile picture): the box is a circle, always square
        self.pad, self.foot = 16, 46
        scr = QApplication.primaryScreen().availableGeometry()
        k = min(scr.width() * .8 / pm.width(), (scr.height() * .85 - self.foot - 2 * self.pad) / pm.height(), 1.5)
        self.iw, self.ih = max(120, int(pm.width() * k)), max(80, int(pm.height() * k))
        self.view = pm.scaled(self.iw, self.ih, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.resize(self.iw + 2 * self.pad, self.ih + 2 * self.pad + self.foot)
        self.move(scr.center().x() - self.width() // 2, scr.center().y() - self.height() // 2)
        self.sel = self._initial(init)
        self._mode, self._anchor, self._off, self._sx, self._sy = None, QPointF(), QPointF(), 1, 1

    def _max_w(self):
        return min(float(self.iw), self.ih * self.aspect)

    def _fit(self, r):
        w = max(24.0, min(r.width(), self._max_w()))
        h = w / self.aspect
        return QRectF(max(0.0, min(self.iw - w, r.x())), max(0.0, min(self.ih - h, r.y())), w, h)

    def _initial(self, init):
        if init:
            try:
                x, y, w, h = (float(v) for v in init)
                r = QRectF(x * self.iw, y * self.ih, w * self.iw, h * self.ih)
                if r.width() > 20:
                    return self._fit(r)
            except (TypeError, ValueError):
                pass
        w = self._max_w()
        h = w / self.aspect
        return QRectF((self.iw - w) / 2, (self.ih - h) / 2, w, h)

    def present(self):
        self.show()
        self.raise_()
        self.activateWindow()
        try:
            u = ctypes.windll.user32
            u.keybd_event(0x12, 0, 0, 0)
            u.keybd_event(0x12, 0, 2, 0)
            u.SetForegroundWindow(int(self.winId()))
        except Exception:  # noqa: BLE001
            pass
        self.setFocus()

    def _corners(self):
        r = self.sel
        return [r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()]

    def _handles(self):
        """Grab dots: on the rim of the circle (45 degrees) for the round picker, else on the box corners."""
        if not self.circle:
            return self._corners()
        c, k = self.sel.center(), self.sel.width() / 2 * 0.70710678
        return [QPointF(c.x() - k, c.y() - k), QPointF(c.x() + k, c.y() - k), QPointF(c.x() - k, c.y() + k), QPointF(c.x() + k, c.y() + k)]

    def _ipos(self, e):
        return e.position() - QPointF(self.pad, self.pad)

    @staticmethod
    def _near(p, c):
        return abs(p.x() - c.x()) < 16 and abs(p.y() - c.y()) < 16

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        p, cs = self._ipos(e), self._corners()
        for i, c in enumerate(self._handles()):
            if self._near(p, c):
                a = cs[3 - i]                                  # the opposite corner stays put
                self._mode, self._anchor = "size", a
                self._sx, self._sy = (1 if c.x() > a.x() else -1), (1 if c.y() > a.y() else -1)
                return
        if self.sel.contains(p):
            self._mode, self._off = "move", p - self.sel.topLeft()

    def mouseMoveEvent(self, e):
        p = self._ipos(e)
        if self._mode == "move":
            w, h = self.sel.width(), self.sel.height()
            self.sel = QRectF(max(0.0, min(self.iw - w, p.x() - self._off.x())),
                              max(0.0, min(self.ih - h, p.y() - self._off.y())), w, h)
            self.update()
        elif self._mode == "size":
            a = self._anchor
            wanted = max(abs(p.x() - a.x()), abs(p.y() - a.y()) * self.aspect)
            wav = (self.iw - a.x()) if self._sx > 0 else a.x()
            hav = (self.ih - a.y()) if self._sy > 0 else a.y()
            w = max(24.0, min(wanted, wav, hav * self.aspect))
            h = w / self.aspect
            self.sel = QRectF(a.x() if self._sx > 0 else a.x() - w, a.y() if self._sy > 0 else a.y() - h, w, h)
            self.update()
        else:
            if any(self._near(p, c) for c in self._handles()):
                cur = Qt.CursorShape.CrossCursor
            else:
                cur = Qt.CursorShape.SizeAllCursor if self.sel.contains(p) else Qt.CursorShape.ArrowCursor
            self.setCursor(cur)

    def mouseReleaseEvent(self, _e):
        self._mode = None

    def mouseDoubleClickEvent(self, _e):
        self._finish(True)

    def wheelEvent(self, e):
        f = 1.08 if e.angleDelta().y() > 0 else 1 / 1.08
        c = self.sel.center()
        w = max(24.0, min(self._max_w(), self.sel.width() * f))
        h = w / self.aspect
        self.sel = self._fit(QRectF(c.x() - w / 2, c.y() - h / 2, w, h))
        self.update()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish(True)
        elif e.key() == Qt.Key.Key_Escape:
            self._finish(False)
        elif e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            # Arrow keys pan the crop window over the source image; Shift moves faster.
            step = 12.0 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 2.0
            dx = -step if e.key() == Qt.Key.Key_Left else step if e.key() == Qt.Key.Key_Right else 0.0
            dy = -step if e.key() == Qt.Key.Key_Up else step if e.key() == Qt.Key.Key_Down else 0.0
            self.sel = self._fit(QRectF(self.sel.x() + dx, self.sel.y() + dy, self.sel.width(), self.sel.height()))
            self.update()
        else:
            super().keyPressEvent(e)

    def closeEvent(self, e):
        if not self._fin:
            self._fin = True
            self.done.emit(None)
        super().closeEvent(e)

    def _finish(self, ok):
        if self._fin:
            return
        self._fin = True
        r = self.sel
        self.done.emit((r.x() / self.iw, r.y() / self.ih, r.width() / self.iw, r.height() / self.ih) if ok else None)
        self.close()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.fillRect(self.rect(), QColor(14, 16, 24))
        pr = QRectF(self.pad, self.pad, self.iw, self.ih)
        p.drawPixmap(pr.topLeft(), self.view)
        sel = self.sel.translated(self.pad, self.pad)
        dim = QPainterPath()
        dim.addRect(pr)
        hole = QPainterPath()
        if self.circle:
            hole.addEllipse(sel)
        else:
            hole.addRect(sel)
        p.fillPath(dim.subtracted(hole), QColor(0, 0, 0, 150))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 70), 1))
        for i in (() if self.circle else (1, 2)):                                                  # rule-of-thirds guides
            p.drawLine(QPointF(sel.x() + sel.width() * i / 3, sel.y()), QPointF(sel.x() + sel.width() * i / 3, sel.bottom()))
            p.drawLine(QPointF(sel.x(), sel.y() + sel.height() * i / 3), QPointF(sel.right(), sel.y() + sel.height() * i / 3))
        p.setPen(QPen(self.accent, 2))
        if self.circle:
            p.drawEllipse(sel)
            p.setPen(QPen(QColor(255, 255, 255, 55), 1, Qt.PenStyle.DashLine))     # the square the circle is cut from
            p.drawRect(sel)
        else:
            p.drawRect(sel)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.accent)
        for c in self._handles():
            p.drawEllipse(c + QPointF(self.pad, self.pad), 5.5, 5.5)
        p.setPen(QColor("white"))
        p.setFont(_font(12, QFont.Weight.DemiBold, mono=True))
        p.drawText(QRectF(self.pad, self.ih + self.pad + 6, self.width() - 2 * self.pad, 18), Qt.AlignmentFlag.AlignVCenter, self.label)
        p.setPen(QColor(255, 255, 255, 150))
        p.setFont(_font(10, mono=True))
        p.drawText(QRectF(self.pad, self.ih + self.pad + 26, self.width() - 2 * self.pad, 16), Qt.AlignmentFlag.AlignVCenter,
                   "drag to move  \u2022  arrows pan (Shift = faster)  \u2022  scroll resize  \u2022  Enter apply / Esc cancel")
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        p.end()


class _KBDLL(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KeyGrab:
    """Alt+Up / Alt+Down while the launcher is open.  whkd (Komorebi's hotkey daemon) watches the keyboard with a
    low-level hook and swallows the keys it has bindings for before any window sees them.  Windows calls the hook that
    was installed LAST first, so this installs its own hook each time the launcher opens (and removes it when it
    closes): Synapse then gets these two keys ahead of whkd, only while it is open.  Everything else is passed on."""

    def __init__(self, callback):
        self.cb = callback                            # callback(is_up: bool), called from the hook thread
        self._stop = None
        self._tid = 0
        self._swallowed = set()

    def start(self):
        if self._stop is not None and not self._stop.is_set():
            return
        self._stop = threading.Event()
        self._swallowed = set()
        threading.Thread(target=self._run, args=(self._stop,), daemon=True, name="SynapseKeyGrab").start()

    def stop(self):
        ev = self._stop
        if ev is None or ev.is_set():
            return
        ev.set()
        tid = self._tid
        if tid:
            try:
                ctypes.WinDLL("user32").PostThreadMessageW(tid, 0x0012, 0, 0)     # WM_QUIT ends the hook thread's loop
            except Exception:  # noqa: BLE001
                pass

    def _run(self, stop):
        try:
            u, k32 = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("kernel32")
            LRESULT = ctypes.c_ssize_t
            HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
            u.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
            u.SetWindowsHookExW.restype = ctypes.c_void_p
            u.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            u.CallNextHookEx.restype = LRESULT
            u.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
            u.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
            k32.GetModuleHandleW.argtypes, k32.GetModuleHandleW.restype = [wintypes.LPCWSTR], wintypes.HMODULE
            hook = [None]
            swallowed = self._swallowed

            def proc(n_code, w_param, l_param):
                try:
                    if n_code == 0 and not stop.is_set():
                        kb = _KBDLL.from_address(l_param)
                        vk = kb.vkCode
                        if vk in (0x26, 0x28):                                    # VK_UP / VK_DOWN
                            if w_param in (0x100, 0x104) and kb.flags & 0x20:     # key down with Alt held (LLKHF_ALTDOWN)
                                swallowed.add(vk)
                                self.cb(vk == 0x26)
                                return 1                                          # whkd never sees it
                            if w_param in (0x101, 0x105) and vk in swallowed:
                                swallowed.discard(vk)
                                return 1
                except Exception:  # noqa: BLE001
                    pass
                return u.CallNextHookEx(hook[0], n_code, w_param, l_param)

            keep = HOOKPROC(proc)                                                 # must stay referenced while hooked
            msg = wintypes.MSG()
            u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)                      # creates this thread's message queue
            hook[0] = u.SetWindowsHookExW(13, keep, k32.GetModuleHandleW(None), 0)     # WH_KEYBOARD_LL
            if not hook[0]:
                log("Alt+Up/Down key grab could not be installed (error %d)" % ctypes.get_last_error())
                return
            self._tid = k32.GetCurrentThreadId()
            if not stop.is_set():
                while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    pass
            u.UnhookWindowsHookEx(hook[0])
            del keep
        except Exception:  # noqa: BLE001
            log("key grab thread failed:\n" + traceback.format_exc())
        finally:
            self._tid = 0
            stop.set()


def start_hotkey_thread(callback):
    """Registers Alt+Space and waits for WM_HOTKEY in its own thread (RegisterHotKey and GetMessage must share a thread),
    so it no longer depends on Qt's native event filter. Failures are written to the log file."""
    def run():
        u = ctypes.windll.user32
        try:
            if not u.RegisterHotKey(None, HOTKEY_ID, 0x0001 | 0x4000, 0x20):      # MOD_ALT | MOD_NOREPEAT, VK_SPACE
                log("Alt+Space could not be registered (error %d): another program already owns it "
                    "(PowerToys Run, Flow Launcher, Everything...). Close it or change its shortcut." % ctypes.GetLastError())
                return
            msg = wintypes.MSG()
            while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                    callback()
        except Exception:  # noqa: BLE001
            log("hotkey thread failed:\n" + traceback.format_exc())
    threading.Thread(target=run, daemon=True).start()


OCR_PS = r"""$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
    $null = [Windows.Storage.Streams.RandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
    $null = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
    $null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Foundation, ContentType = WindowsRuntime]
    $null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
    $asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
    function Await($op, $type) {
        $task = $asTask.MakeGenericMethod($type).Invoke($null, @($op))
        $task.Wait(-1) | Out-Null
        $task.Result
    }
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($args[0])) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if (-not $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language]::new("en-US")) }
    if (-not $engine) { throw "No OCR language is installed (Settings > Time & language > Language & region)" }
    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    ($result.Lines | ForEach-Object { $_.Text }) -join "`n"
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 2
}
"""


def run_ocr(path):
    """Read the text in an image with Windows' built-in OCR (Windows.Media.Ocr), through PowerShell - nothing to install."""
    script = os.path.join(tempfile.gettempdir(), "synapse_ocr.ps1")
    with open(script, "w", encoding="utf-8-sig") as f:
        f.write(OCR_PS)
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script, path],
                       capture_output=True, creationflags=0x08000000, timeout=45)
    out = r.stdout.decode("utf-8", "replace").strip()
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(err.splitlines()[-1] if err else "Windows OCR failed (code %d)" % r.returncode)
    return out


class OcrSnip(QWidget):
    """Frozen full-screen picture: drag a box over the text and let go to read it. Esc or a right-click cancels."""
    done = Signal(object)                         # QImage of the chosen area in real screen pixels, or None

    def __init__(self, shot, scr, accent):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.shot, self.accent = shot, qc(accent)
        sg = scr.geometry()
        self.k = shot.width() / max(1, sg.width())          # real pixels per logical pixel
        self.a = self.b = None
        self._fin = False
        self.setGeometry(sg)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _sel(self):
        return None if self.a is None or self.b is None else QRectF(self.a, self.b).normalized()

    def _finish(self, img):
        if self._fin:
            return
        self._fin = True
        self.hide()
        self.done.emit(img)
        self.deleteLater()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.a = self.b = e.position()
            self.update()
        else:
            self._finish(None)

    def mouseMoveEvent(self, e):
        if self.a is not None:
            self.b = e.position()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self.a is None:
            return
        self.b = e.position()
        r = self._sel()
        if r.width() < 6 or r.height() < 6:                  # a stray click: wait for a real drag
            self.a = self.b = None
            self.update()
            return
        k = self.k
        src = QRect(int(r.x() * k), int(r.y() * k), int(r.width() * k), int(r.height() * k)).intersected(self.shot.rect())
        self._finish(self.shot.copy(src).toImage())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self._finish(None)
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.drawPixmap(QRectF(self.rect()), self.shot, QRectF(self.shot.rect()))
        p.fillRect(self.rect(), QColor(0, 0, 0, 125))
        r = self._sel()
        if r is not None and r.width() > 1 and r.height() > 1:
            k = self.k
            p.drawPixmap(r, self.shot, QRectF(r.x() * k, r.y() * k, r.width() * k, r.height() * k))   # the box shows the picture undimmed
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(self.accent, 2))
            p.drawRect(r)
        p.setPen(QColor(255, 255, 255, 230))
        p.setFont(_font(12, mono=True))
        p.drawText(QRectF(0, 18, self.width(), 24), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                   "Drag over the text to copy it   \u2022   Esc to cancel")
        p.end()


class AdvancedColorEditor(QWidget):
    """Compact embedded HSV editor: saturation/value square, hue strip, and hex field."""
    currentColorChanged = Signal(QColor)

    def __init__(self, color, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._hue = max(0, self._color.hsvHue())
        self._sv_rect = QRect()
        self._hue_rect = QRect()
        self._drag_mode = ""
        self.hex_edit = QLineEdit(self)
        self.hex_edit.setMaxLength(7)
        self.hex_edit.setPlaceholderText("#RRGGBB")
        self.hex_edit.setStyleSheet("QLineEdit { color: #f1f3f7; background: rgba(255,255,255,12); border: 1px solid #41485b; border-radius: 7px; padding: 6px 9px; font: 12px 'CaskaydiaCove NFM', 'CaskaydiaCove Nerd Font Mono', 'Cascadia Code'; } QLineEdit:focus { border: 1px solid #43abe0; }")
        self.hex_edit.editingFinished.connect(self._apply_hex)
        self.setStyleSheet("background: transparent;")
        self._panel_color = QColor(20, 22, 32, 246)
        self._border_color = QColor(76, 194, 255, 70)
        self._sync_hex()

    def setCurrentColor(self, color):
        if not color.isValid():
            return
        self._color = QColor(color)
        hue = self._color.hsvHue()
        if hue >= 0:
            self._hue = hue
        self._sync_hex()
        self.update()

    def setTheme(self, theme):
        bg = theme.get("bg", (18, 20, 30, 245))
        if isinstance(bg, (tuple, list)):
            self._panel_color = QColor(int(bg[0]), int(bg[1]), int(bg[2]), 175)
        else:
            self._panel_color = QColor(bg)
            self._panel_color.setAlpha(175)
        self._border_color = qc(theme.get("accent", "#4cc2ff"))
        self._border_color.setAlpha(115)
        self.hex_edit.setStyleSheet(
            "QLineEdit { color: #f1f3f7; background: rgba(%d,%d,%d,92); " % (self._panel_color.red(), self._panel_color.green(), self._panel_color.blue()) +
            "border: 1px solid rgba(140,155,185,95); border-radius: 8px; "
            "padding: 6px 10px; font: 12px 'CaskaydiaCove NFM', 'CaskaydiaCove Nerd Font Mono', 'Cascadia Code'; } "
            "QLineEdit:focus { border: 1px solid %s; }" % self._border_color.name())
        self.update()

    def setHue(self, hue):
        self._hue = max(0, min(359, int(hue)))
        self._color = QColor.fromHsv(self._hue, max(0, self._color.saturation()), max(0, self._color.value()))
        self._sync_hex()
        self.update()
        self.currentColorChanged.emit(QColor(self._color))

    def _sync_hex(self):
        self.hex_edit.blockSignals(True)
        self.hex_edit.setText(self._color.name())
        self.hex_edit.blockSignals(False)

    def resizeEvent(self, event):
        w, h = self.width(), self.height()
        # The editor lives inside the expanded THEME COLOR card. Keep one hue
        # track below the SV square and a single hex field at the bottom.
        self._sv_rect = QRect(12, 12, max(10, w - 24), max(64, h - 90))
        hue_y = self._sv_rect.bottom() + 9
        self._hue_rect = QRect(14, hue_y, max(10, w - 28), 10)
        self.hex_edit.setGeometry(12, self._hue_rect.bottom() + 12, max(10, w - 24), 36)
        super().resizeEvent(event)

    def hueTrackY(self):
        # Parent-window Y coordinate, for its hit-testing helpers.
        return self.y() + self._hue_rect.center().y()

    def _set_from_point(self, pos, mode):
        if mode == "sv":
            r = self._sv_rect
            sat = max(0.0, min(1.0, (pos.x() - r.left()) / max(1, r.width() - 1)))
            val = 1.0 - max(0.0, min(1.0, (pos.y() - r.top()) / max(1, r.height() - 1)))
            self._color = QColor.fromHsv(self._hue, round(sat * 255), round(val * 255))
        elif mode == "hue":
            r = self._hue_rect
            self._hue = round(max(0.0, min(1.0, (pos.x() - r.left()) / max(1, r.width() - 1))) * 359)
            self._color = QColor.fromHsv(self._hue, max(0, self._color.saturation()), max(0, self._color.value()))
        self._sync_hex()
        self.update()
        self.currentColorChanged.emit(QColor(self._color))

    def _apply_hex(self):
        text = self.hex_edit.text().strip()
        if not text.startswith("#"):
            text = "#" + text
        color = QColor(text)
        if color.isValid():
            self._color = color
            if color.hsvHue() >= 0:
                self._hue = color.hsvHue()
            self._sync_hex()
            self.update()
            self.currentColorChanged.emit(QColor(color))
        else:
            self._sync_hex()

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        if self._sv_rect.contains(pos):
            self._drag_mode = "sv"
            self._set_from_point(pos, self._drag_mode)
        elif self._hue_rect.adjusted(-4, -7, 4, 7).contains(pos):
            self._drag_mode = "hue"
            self._set_from_point(pos, self._drag_mode)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_mode:
            self._set_from_point(event.position().toPoint(), self._drag_mode)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_mode = ""
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # No second opaque panel here: the expanded THEME COLOR card behind
        # this child supplies the same translucent, theme-tinted glass surface.
        r = self._sv_rect
        hue_color = QColor.fromHsv(self._hue, 255, 255)
        p.save()
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), 8, 8)
        p.setClipPath(path)
        p.fillRect(r, hue_color)
        white_grad = QLinearGradient(r.left(), 0, r.right(), 0)
        white_grad.setColorAt(0, QColor(255, 255, 255))
        white_grad.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(r, white_grad)
        black_grad = QLinearGradient(0, r.top(), 0, r.bottom())
        black_grad.setColorAt(0, QColor(0, 0, 0, 0))
        black_grad.setColorAt(1, QColor(0, 0, 0, 255))
        p.fillRect(r, black_grad)
        p.restore()
        # The same hue slider is relocated into the expanded card, directly below the SV square.
        hg = QLinearGradient(self._hue_rect.left(), 0, self._hue_rect.right(), 0)
        for i in range(13):
            hg.setColorAt(i / 12.0, QColor.fromHsv(round(i / 12.0 * 359), 255, 255))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(hg)
        p.drawRoundedRect(QRectF(self._hue_rect), 5, 5)
        hx = self._hue_rect.left() + self._hue / 359.0 * max(1, self._hue_rect.width() - 1)
        p.setPen(QPen(QColor(0, 0, 0, 180), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(hx, self._hue_rect.center().y()), 7, 7)
        p.setPen(QPen(QColor("white"), 2))
        p.drawEllipse(QPointF(hx, self._hue_rect.center().y()), 7, 7)
        sat = self._color.saturationF()
        val = self._color.valueF()
        sx = r.left() + sat * (r.width() - 1)
        sy = r.top() + (1.0 - val) * (r.height() - 1)
        p.setPen(QPen(QColor(0, 0, 0, 190), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(sx, sy), 7, 7)
        p.setPen(QPen(QColor("white"), 2))
        p.drawEllipse(QPointF(sx, sy), 7, 7)


# ------------------------------------------------------------------ gpu monitor
class GpuMonitor:
    """GPU load from ONE long-lived helper process (nvidia-smi -l, else typeperf) that only runs while the launcher is open.
    The old code started a fresh PowerShell every 2.5 s, which cost more CPU than anything else here (and showed up in the CPU tile)."""

    def __init__(self, callback):
        self.cb, self.proc, self._thr, self._stop = callback, None, None, threading.Event()

    def start(self):
        if self._thr is not None and self._thr.is_alive():
            return
        self._stop.clear()
        self._thr = threading.Thread(target=self._run, name="SynapseGpu", daemon=True)
        self._thr.start()

    def stop(self):
        self._stop.set()
        p, self.proc = self.proc, None
        if p is not None and p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass

    @staticmethod
    def _parse(mode, line):
        line = line.strip()
        if not line:
            return None
        try:
            if mode == "nvidia":
                return float(line.split()[0])
            parts = [x.strip().strip('"') for x in line.split(",")]
            if len(parts) < 2 or "PDH" in parts[0] or not re.search(r"[/:]", parts[0]):
                return None
            return sum(float(x) for x in parts[1:] if x)
        except ValueError:
            return None

    def _run(self):
        for mode in ("nvidia", "typeperf"):
            while not self._stop.is_set():
                cmd = (["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits", "-l", "2"] if mode == "nvidia"
                       else ["typeperf", r"\GPU Engine(*engtype_3D)\Utilization Percentage", "-si", "2"])
                try:
                    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                         text=True, creationflags=0x08000000)
                except (OSError, ValueError):
                    break                                          # tool not installed -> try the next one
                self.proc, got, n = p, False, 0
                try:
                    for line in p.stdout:
                        if self._stop.is_set():
                            break
                        v = self._parse(mode, line)
                        if v is not None:
                            got, n = True, n + 1
                            self.cb(v)
                            if mode == "typeperf" and n >= 15:      # typeperf expands the counter instances once, so refresh now and then
                                break
                except (OSError, ValueError):
                    pass
                finally:
                    try:
                        if p.poll() is None:
                            p.terminate()
                    except OSError:
                        pass
                if not got:
                    break                                          # started but never produced data -> next tool
                if mode == "nvidia" and not self._stop.is_set():
                    return
            if self._stop.is_set():
                return
        if not self._stop.is_set():
            self.cb(None)


# ------------------------------------------------------------------ launcher window
VK_BUTTONS = (0x01, 0x02, 0x04)                    # left / right / middle mouse
MIN_BTN, CLOSE_BTN = QRect(W - 18 - 64, 18, 30, 28), QRect(W - 18 - 30, 18, 30, 28)
CARD = QRect(RIGHT_X, 52, RIGHT_W, 240)
THEME = QRect(RIGHT_X, 302, RIGHT_W, 66)
TILES = [QRect(RIGHT_X + i * 124, 378, 116, 78) for i in range(3)]
QUOTE_R = QRect(RIGHT_X, 466, RIGHT_W, 56)
CLOCK = QRect(RIGHT_X, 532, RIGHT_W, 62)
WM_BTNS = {"komorebi": QRect(RIGHT_X + 8, 541, 112, 44), "dotfiles": QRect(RIGHT_X + 132, 541, 112, 44)}
C_GREEN, C_PURPLE = QColor(46, 230, 140), QColor(176, 110, 255)        # battery / GPU accents (CPU uses the theme accent)
TRACK_X0, TRACK_X1, TRACK_Y = THEME.x() + 20, THEME.right() - 20, THEME.y() + 48
# Keep the current-color swatch immediately beside Reset; the hit targets do not overlap.
COLOR_BTN = QRect(THEME.right() - 72, THEME.y() + 8, 24, 26)
RESET_R, SLIDER_HIT = QRect(THEME.right() - 48, THEME.y() + 8, 40, 26), QRect(THEME.x() + 8, THEME.y() + 32, THEME.width() - 16, 32)
# The advanced editor expands *inside* the THEME COLOR card. Its own panel
# is translucent and theme-tinted rather than a separate black box.
EDITOR_AREA = QRect(THEME.x() + 6, THEME.y() + 40, THEME.width() - 12, 244)
FOOT_Y = H - 44
COLLAPSED_W = RIGHT_X                                     # visible width with the right side retracted
ZEN_BAR_H = SEARCH_Y * 2 + SEARCH_H                       # zen mode: window height with only the search bar showing
HINTS = "\u2191\u2193 navigate  \u2022  Enter launch  \u2022  Ctrl+K search  \u2022  Ctrl+B side panel"


# ------------------------------------------------------------------ shared pieces for the advanced windows
def read_uptime():
    k32 = ctypes.windll.kernel32
    k32.GetTickCount64.restype = ctypes.c_ulonglong
    return k32.GetTickCount64() / 1000.0


class _PE32(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def process_names():
    """Lower-case names of every running process (one toolhelp snapshot, about a millisecond)."""
    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k32.Process32FirstW.argtypes = k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PE32)]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)                  # TH32CS_SNAPPROCESS
    names = set()
    if not snap or snap == ctypes.c_void_p(-1).value:
        return names
    try:
        pe = _PE32()
        pe.dwSize = ctypes.sizeof(pe)
        ok = k32.Process32FirstW(snap, ctypes.byref(pe))
        while ok:
            names.add(pe.szExeFile.lower())
            ok = k32.Process32NextW(snap, ctypes.byref(pe))
    finally:
        k32.CloseHandle(snap)
    return names


def wm_running():
    names, out = None, {}
    for k, v in WM.items():
        if v.get("check"):                                       # programs that report their own state (Vapor)
            try:
                out[k] = bool(v["check"]())
            except Exception:  # noqa: BLE001
                out[k] = False
        else:
            if names is None:
                names = process_names()
            out[k] = any(n in names for n in v["procs"])
    return out


def wm_wait(key, want, secs):
    end = time.time() + secs
    while time.time() < end:
        if wm_running()[key] == want:
            return True
        time.sleep(0.25)
    return wm_running()[key] == want


def wm_stop(key):
    cfg = WM[key]
    if cfg.get("stop_fn"):
        err = cfg["stop_fn"]()
        if err:
            return err
        return "" if wm_wait(key, False, 8) else "Couldn't stop %s" % cfg["label"]
    if not shutil.which(cfg["stop"][0]):
        return "%s: '%s' was not found on PATH" % (cfg["label"], cfg["stop"][0])
    for cmd in (cfg["stop"], cfg.get("stop_fallback")):
        if not cmd:
            continue
        try:
            subprocess.run(cmd, capture_output=True, timeout=20, creationflags=0x08000000)
        except subprocess.TimeoutExpired:
            pass
        if wm_wait(key, False, 6):
            return ""
    return "Couldn't stop %s" % cfg["label"]


def wm_start(key):
    cfg = WM[key]
    if cfg.get("start_fn"):
        err = cfg["start_fn"]()
        if err:
            return err
        return "" if wm_wait(key, True, 12) else "Couldn't start %s" % cfg["label"]
    if not shutil.which(cfg["start"][0]):
        return "%s: '%s' was not found on PATH" % (cfg["label"], cfg["start"][0])
    subprocess.Popen(cfg["start"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=0x00000008 | 0x00000200, close_fds=True)      # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    return "" if wm_wait(key, True, 8) else "Couldn't start %s" % cfg["label"]


def picker_path(cfg):
    """Harmony (the wallpaper picker): launcher_settings.json -> "customizations": {"harmony": "C:/path/harmony.pyw"} (the old
    "wallpaper_picker" key still works), otherwise the first script called *harmony* (or wallpaper + picker) next to Synapse
    or in the Vapor folder."""
    c = cfg.get("customizations")
    c = c if isinstance(c, dict) else {}
    c = c.get("harmony") or c.get("wallpaper_picker")
    dirs = [HERE]
    if c:
        c = clean_path(str(c))
        if os.path.isfile(c):
            return c
        if not os.path.isdir(c):                               # a wrong path is reported, not silently replaced
            return ""
        dirs = [c]                                             # a folder: look for Harmony inside it
    vc = vaporctl_path(cfg)
    if vc and os.path.dirname(vc) not in dirs:
        dirs.append(os.path.dirname(vc))
    for d in dirs:
        try:
            for n in sorted(os.listdir(d)):
                low = n.lower()
                if ("harmony" in low or ("wallpaper" in low and "picker" in low)) and low.endswith((".py", ".pyw", ".exe", ".bat", ".cmd", ".lnk")):
                    return os.path.join(d, n)
        except OSError:
            pass
    return ""


def _picker_ps(path, kill):
    """Finds the picker by its command line (it is usually a pythonw script, so the process name alone says nothing)."""
    name = os.path.basename(path).replace("'", "''")
    cond = ("$_.ProcessId -ne %d -and $_.CommandLine -and $_.Name -notlike 'powershell*' -and $_.Name -notlike 'pwsh*' "
            "-and $_.CommandLine -like '*%s*'") % (os.getpid(), name)
    ps = "Get-CimInstance Win32_Process | Where-Object { %s } | " % cond
    ps += "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" if kill else "Measure-Object | ForEach-Object { $_.Count }"
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True, text=True,
                       timeout=25, creationflags=0x08000000)
    return (r.stdout or "").strip()


def picker_running(path):
    try:
        return int(_picker_ps(path, False) or 0) > 0
    except (ValueError, subprocess.SubprocessError, OSError):
        return False


def picker_stop(path):
    if not picker_running(path):
        return ""
    try:
        _picker_ps(path, True)
    except (subprocess.SubprocessError, OSError):
        return "Couldn't close the Harmony"
    end = time.time() + 5
    while time.time() < end:
        if not picker_running(path):
            return ""
        time.sleep(0.4)
    return "Couldn't close the Harmony"


def picker_start(path):
    if picker_running(path):
        return ""
    try:
        if path.lower().endswith((".py", ".pyw")):
            exe = system_python(console=False)                      # pythonw: no console window
            if not exe:
                return "Python was not found on your PATH  -  Harmony needs it"
            subprocess.Popen([exe, path], cwd=os.path.dirname(path), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200, close_fds=True)
        else:
            os.startfile(path)
    except OSError:
        return "Couldn't start the Harmony"
    return ""


def fmt_bytes(n):
    n = float(max(0, n or 0))
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d B" % n) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def fmt_duration(sec):
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return ""
    if sec <= 0:
        return ""
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return ("%d:%02d:%02d" % (h, m, s)) if h else ("%d:%02d" % (m, s))


PROGRESS_DONE = QColor(74, 222, 128)
PROGRESS_WARN = QColor(251, 191, 36)


def draw_progress_bar(p, rect, pct, accent, done=False, color=None):
    """Smooth theme-coloured progress bar: soft glow, gradient fill, a light band travelling along the fill and a
    bright leading dot.  pct is 0-100, or None for an indeterminate bar (a glowing block sweeping across)."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    base = QColor(color) if color is not None else QColor(PROGRESS_DONE if done else accent)
    rad = rect.height() / 2.0
    track = QPainterPath()
    track.addRoundedRect(rect, rad, rad)
    tc = QColor(base)
    tc.setAlpha(42)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(tc)
    p.drawPath(track)
    now = time.monotonic()
    if pct is None:                                              # indeterminate: a block sweeps left to right
        span = rect.width() * 0.34
        x0 = rect.left() - span + (rect.width() + span) * ((now * 0.75) % 1.0)
        fill = QRectF(x0, rect.top(), span, rect.height()).intersected(rect)
    else:
        w = rect.width() * max(0.0, min(100.0, float(pct))) / 100.0
        fill = QRectF(rect.left(), rect.top(), w, rect.height())
        if 0 < w < rect.height():
            fill.setWidth(rect.height())                         # a tiny bar stays a pill instead of a sliver
    if fill.width() > 0.5:
        glow = QColor(base)
        glow.setAlpha(48)
        p.setBrush(glow)
        p.drawRoundedRect(fill.adjusted(-1.5, -2.0, 1.5, 2.0), rad + 2, rad + 2)
        p.setClipPath(track)
        g = QLinearGradient(fill.left(), 0, fill.left() + max(fill.width(), 1.0), 0)
        g.setColorAt(0.0, base.darker(135))
        g.setColorAt(1.0, base.lighter(125))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(fill, rad, rad)
        if pct is not None and not done:                         # shimmer
            sw = max(24.0, fill.width() * 0.35)
            sx = fill.left() - sw + (fill.width() + sw) * ((now * 0.9) % 1.0)
            sg = QLinearGradient(sx, 0, sx + sw, 0)
            sg.setColorAt(0.0, QColor(255, 255, 255, 0))
            sg.setColorAt(0.5, QColor(255, 255, 255, 70))
            sg.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(sg))
            p.drawRoundedRect(fill, rad, rad)
            if fill.width() > rect.height() * 1.5 and pct < 100:      # bright leading dot
                p.setBrush(QColor(255, 255, 255, 215))
                p.drawEllipse(QPointF(fill.right() - rad, fill.center().y()), rad * 0.55, rad * 0.55)
        p.setClipping(False)
    p.restore()


class GlowBar(QWidget):
    """Animated progress bar widget (see draw_progress_bar).  set_value(None) = indeterminate."""

    def __init__(self, accent, parent=None):
        super().__init__(parent)
        self.accent = QColor(accent)
        self.target = self.shown = 0.0
        self.indet, self.done, self.warn = True, False, False
        self.setFixedHeight(10)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def set_value(self, pct, done=False, warn=False):
        self.indet = pct is None
        if pct is not None:
            self.target = max(0.0, min(100.0, float(pct)))
            if self.target < self.shown:
                self.shown = self.target
        self.done, self.warn = done, warn
        if self.isVisible() and not self._timer.isActive():
            self._timer.start()
        self.update()

    def showEvent(self, e):
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def _tick(self):
        gap = self.target - self.shown
        if not self.indet:
            self.shown = self.target if abs(gap) < 0.05 else self.shown + gap * 0.18
            if self.done and abs(gap) < 0.05:
                self._timer.stop()                               # finished: nothing left to animate
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        draw_progress_bar(p, QRectF(0, 2, self.width(), self.height() - 4), None if self.indet else self.shown,
                          self.accent, self.done, PROGRESS_WARN if self.warn else None)
        p.end()


class ThumbCard(QWidget):
    """Rounded 16:9 preview with a loading shimmer, used by the advanced YouTube window."""

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.pm = QPixmap()
        self.state = "loading"                                   # loading | ready | none
        self.badge = ""
        self.setFixedSize(224, 126)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self.update)

    def set_image(self, pm):
        self.pm, self.state = pm, "ready"
        self._timer.stop()
        self.update()

    def set_none(self):
        self.state = "none"
        self._timer.stop()
        self.update()

    def set_badge(self, text):
        self.badge = text or ""
        self.update()

    def showEvent(self, e):
        if self.state == "loading":
            self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        th = self.theme
        tint, accent, sub = qc("rgb(%s)" % th["tint"]), qc(th["accent"]), qc(th["sub"])
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        p.save()
        p.setClipPath(path)
        p.fillRect(self.rect(), QColor(tint.red(), tint.green(), tint.blue(), 34))
        if self.state == "ready" and not self.pm.isNull():
            dpr = max(1.0, self.devicePixelRatioF())
            s = self.pm.scaled(int(self.width() * dpr), int(self.height() * dpr),
                               Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            s.setDevicePixelRatio(dpr)
            p.drawPixmap(QPointF(-(s.width() / dpr - self.width()) / 2.0, -(s.height() / dpr - self.height()) / 2.0), s)
        elif self.state == "loading":
            bw = self.width() * 0.45
            x = -bw + (self.width() + bw) * ((time.monotonic() * 0.8) % 1.0)
            g = QLinearGradient(x, 0, x + bw, 0)
            g.setColorAt(0.0, QColor(255, 255, 255, 0))
            g.setColorAt(0.5, QColor(255, 255, 255, 34))
            g.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(self.rect(), QBrush(g))
            p.setPen(sub)
            p.setFont(_font(10, mono=True))
            p.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, "loading preview...")
        else:
            p.setPen(sub)
            p.setFont(_font(26, icon=True))
            p.drawText(QRectF(0, 30, self.width(), 40), Qt.AlignmentFlag.AlignCenter, "\uEB9F")
            p.setFont(_font(10, mono=True))
            p.drawText(QRectF(0, 74, self.width(), 20), Qt.AlignmentFlag.AlignCenter, "no preview available")
        if self.badge:
            p.setFont(_font(10, QFont.Weight.DemiBold, mono=True))
            w = QFontMetrics(p.font()).horizontalAdvance(self.badge) + 14
            b = QRectF(self.width() - w - 8, self.height() - 26, w, 18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 175))
            p.drawRoundedRect(b, 6, 6)
            p.setPen(QColor("white"))
            p.drawText(b, Qt.AlignmentFlag.AlignCenter, self.badge)
        p.restore()
        edge = QColor(accent)
        edge.setAlpha(70)
        p.setPen(QPen(edge, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()


class MediaBridge(QObject):
    """Carries yt-dlp details and the preview picture from worker threads to the GUI thread."""
    info = Signal(object)
    thumb = Signal(object)
    quick = Signal(object)                        # title + channel from YouTube itself, before yt-dlp answers


_YT_PY = {}                                       # python path -> can it import yt_dlp (frozen exe only)


def ytdlp_command():
    """The command that runs yt-dlp (python -m yt_dlp, or the yt-dlp executable), or None when it isn't installed."""
    if FROZEN:                                                      # no yt_dlp inside Synapse.exe: the exe, else a real Python
        exe = shutil.which("yt-dlp")
        if exe:
            return [exe]
        py = system_python(console=True)
        if py and _YT_PY.get(py) is None:
            try:
                _YT_PY[py] = subprocess.run([py, "-c", "import yt_dlp"], capture_output=True, timeout=20, stdin=subprocess.DEVNULL,
                                            creationflags=0x08000000).returncode == 0
            except (subprocess.SubprocessError, OSError):
                _YT_PY[py] = False
        return [py, "-m", "yt_dlp"] if py and _YT_PY.get(py) else None
    try:
        module_available = importlib.util.find_spec("yt_dlp") is not None
    except (ImportError, ValueError):
        module_available = False
    if module_available:
        pyexe = sys.executable
        if os.path.basename(pyexe).lower() == "pythonw.exe":
            console_python = os.path.join(os.path.dirname(pyexe), "python.exe")
            if os.path.isfile(console_python):
                pyexe = console_python
        return [pyexe, "-m", "yt_dlp"]
    exe = shutil.which("yt-dlp")
    return [exe] if exe else None


def thumb_urls_for(url):
    """Picture URLs to try for a thumbnail link: a plain JPEG of the same YouTube video first (small and always
    decodable), then the link itself."""
    out = []
    m = re.search(r"/vi(?:_webp)?/([\w-]{11})/", url or "")
    if m:
        out.append("https://i.ytimg.com/vi/%s/hqdefault.jpg" % m.group(1))
    if url and url not in out:
        out.append(url)
    return out


def fetch_image(url):
    """Download a picture; returns a QImage (safe to build off the GUI thread) or None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read(6 * 1024 * 1024)
        img = QImage()
        if img.loadFromData(data) and not img.isNull():
            return img
    except Exception:  # noqa: BLE001
        pass
    return None


def _thumb_candidates(src, info):
    urls = []
    ths = [t for t in (src.get("thumbnails") or []) if isinstance(t, dict) and t.get("url")]
    ths.sort(key=lambda t: abs((t.get("width") or 0) - 640) if t.get("width") else 10 ** 6)
    for t in ths:
        if re.search(r"\.(jpe?g|png)(\?|$)", t["url"], re.I):
            urls.append(t["url"])
    for u in (src.get("thumbnail"), info.get("thumbnail")):
        if u and u not in urls:
            urls.append(u)
    vid = src.get("id")
    if vid and str(src.get("extractor_key", "")).lower().startswith("youtube"):
        urls.append("https://i.ytimg.com/vi/%s/hqdefault.jpg" % vid)
    return urls[:6]


def fetch_oembed(url):
    """Title + channel of a YouTube link straight from YouTube (instant, no yt-dlp); None when it can't be read."""
    try:
        req = urllib.request.Request("https://www.youtube.com/oembed?format=json&url=" + quote(url, safe=""),
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            d = json.loads(resp.read(200000).decode("utf-8", "replace"))
        return dict(title=str(d.get("title") or ""), author=str(d.get("author_name") or ""))
    except Exception:  # noqa: BLE001
        return None


def fetch_media_info(url):
    """Ask yt-dlp about a link without downloading it (title, channel, length, sizes, thumbnails).  None on failure."""
    cmd = ytdlp_command()
    if not cmd:
        log("yt details: yt-dlp was not found (pip install yt-dlp)")
        return None
    try:
        res = subprocess.run(cmd + ["-J", "--no-warnings", "--no-playlist", "--playlist-items", "1", "--skip-download",
                                    "--socket-timeout", "15", url],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45,
                             stdin=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if res.returncode != 0 or not res.stdout.strip():
            log("yt details: yt-dlp exited with code %s for %s\n%s" % (res.returncode, url, (res.stderr or "").strip()[-1500:]))
        info = json.loads(res.stdout) if res.returncode == 0 and res.stdout.strip() else None
    except subprocess.TimeoutExpired:
        log("yt details: yt-dlp gave no answer within 45s for " + url)
        return None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        log("yt details failed: %r" % (exc,))
        return None
    if not isinstance(info, dict):
        return None
    entries = [e for e in (info.get("entries") or []) if isinstance(e, dict)]
    is_pl = info.get("_type") == "playlist"
    src = entries[0] if (is_pl and entries) else info
    vid, aud = {}, 0
    for f in src.get("formats") or []:
        if not isinstance(f, dict):
            continue
        size = f.get("filesize") or f.get("filesize_approx") or 0
        h, v, a = f.get("height"), f.get("vcodec"), f.get("acodec")
        if v not in (None, "none") and h:
            vid[int(h)] = max(vid.get(int(h), 0), size)
        elif v == "none" and a not in (None, "none"):
            aud = max(aud, size)
    uploader = src.get("artist") or src.get("uploader") or src.get("channel") or info.get("uploader") or ""
    if isinstance(uploader, (list, tuple)):
        uploader = ", ".join(str(u) for u in uploader)
    title = (info.get("title") if is_pl else (src.get("track") or src.get("title"))) or ""
    return dict(title=str(title), uploader=str(uploader), duration=src.get("duration"), is_playlist=is_pl,
                count=int(info.get("playlist_count") or len(entries) or 0),
                music=bool(src.get("track")) or "music.youtube.com" in url.lower(),
                vid=vid, aud=aud, max_h=max(vid) if vid else 0, thumbs=_thumb_candidates(src, info))


class CacheFilesModel(QAbstractTableModel):
    """Table of every file the cache clean-up touches.  `files` is shared with the worker thread: each entry is
    [group key, path, size, status, reason, is_dir] and status goes wait -> run -> ok / gone / skip."""
    HEAD = ("RESULT", "NAME", "SIZE", "LOCATION")
    LABEL = {"wait": "Waiting", "run": "Deleting...", "ok": "Deleted", "gone": "Already gone", "skip": "Skipped"}

    def __init__(self, files, theme, parent=None):
        super().__init__(parent)
        self.files, self.view = files, []
        self.key, self.status, self.text = "all", "all", ""
        self.c_run, self.c_sub = QColor(theme["accent"]), qc(theme["sub"])
        self.c_ok, self.c_warn = QColor(PROGRESS_DONE), QColor(PROGRESS_WARN)

    def _match(self, f):
        if self.key != "all" and f[0] != self.key:
            return False
        if self.status == "ok" and f[3] not in ("ok", "gone"):
            return False
        if self.status == "skip" and f[3] != "skip":
            return False
        if self.status == "wait" and f[3] not in ("wait", "run"):
            return False
        return not self.text or self.text in f[1].lower()

    def compute(self):
        return [i for i, f in enumerate(self.files) if self._match(f)]

    def rebuild(self, new=None):
        new = self.compute() if new is None else new
        self.beginResetModel()
        self.view = new
        self.endResetModel()

    def refresh(self):
        """Pick up what the worker changed.  Returns True when the set of rows changed (the view was reset)."""
        if self.key == "all" and self.status == "all" and not self.text:
            if len(self.view) != len(self.files):
                self.rebuild(list(range(len(self.files))))
                return True
        else:
            new = self.compute()
            if new != self.view:
                self.rebuild(new)
                return True
        if self.view:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.view) - 1, 3))
        return False

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.view)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 4

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.HEAD[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        try:
            f = self.files[self.view[index.row()]]
        except IndexError:
            return None
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return self.LABEL.get(f[3], f[3])
            if col == 1:
                return (os.path.basename(f[1].rstrip("\\/")) or f[1]) + ("\\" if f[5] else "")
            if col == 2:
                return fmt_bytes(f[2])
            return os.path.dirname(f[1].rstrip("\\/"))
        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 0:
                return QBrush({"run": self.c_run, "ok": self.c_ok, "skip": self.c_warn}.get(f[3], self.c_sub))
            return QBrush(self.c_sub) if col in (2, 3) else None
        if role == Qt.ItemDataRole.TextAlignmentRole and col == 2:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role == Qt.ItemDataRole.ToolTipRole:
            return f[1] + (("\n" + f[4]) if f[4] else "")
        return None


class YtGlassDialog(QDialog):
    """Frameless, themed floating dialog that matches Synapse's translucent glass shell."""
    def __init__(self, theme, opacity, backdrop=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.theme = dict(theme)
        self.glass_opacity = max(0.0, min(1.0, float(opacity)))
        self.backdrop = backdrop                       # paints the launcher's blurred snapshot: no live acrylic, no layered window
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.backdrop is None:                      # no snapshot available: plain rounded window shape instead
            self.setMask(rounded_region(self.width(), self.height(), 18))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.backdrop is not None:
            self.backdrop(painter, self.width(), self.height(), self.x(), self.y(), 18)
        else:
            painter.fillRect(self.rect(), QColor(14, 16, 24))
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 18, 18)
        bg = QColor(*self.theme["bg"])
        bg.setAlpha(int(255 * self.glass_opacity))
        painter.fillPath(path, bg)
        tint_parts = [int(v) for v in re.findall(r"\d+", self.theme["tint"])[:3]]
        if len(tint_parts) == 3:
            tint = QColor(*tint_parts, 18)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tint)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 17, 17)
        outline = QColor(*self.theme["outline"])
        outline.setAlpha(max(outline.alpha(), 70))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(outline, 1))
        painter.drawPath(path)
        painter.end()


def _blur_image(img, radius):
    """Smooth gaussian-style blur (Qt's own blur effect, run offscreen). The edges are replicated first so the
    borders do not fade to transparent / go dark the way a plain blur does."""
    if radius <= 0:
        return img
    try:
        fmt = QImage.Format.Format_ARGB32_Premultiplied
        pad = int(radius * 3) + 2
        w, h = img.width(), img.height()
        src = img.convertToFormat(fmt)
        ext = QImage(w + 2 * pad, h + 2 * pad, fmt)
        ext.fill(0)
        q = QPainter(ext)
        q.drawImage(pad, pad, src)
        q.drawImage(QRect(0, pad, pad, h), src, QRect(0, 0, 1, h))
        q.drawImage(QRect(pad + w, pad, pad, h), src, QRect(w - 1, 0, 1, h))
        q.end()
        top = ext.copy(0, pad, ext.width(), 1)
        bot = ext.copy(0, pad + h - 1, ext.width(), 1)
        q = QPainter(ext)
        q.drawImage(QRect(0, 0, ext.width(), pad), top)
        q.drawImage(QRect(0, pad + h, ext.width(), pad), bot)
        q.end()
        scene = QGraphicsScene()
        item = scene.addPixmap(QPixmap.fromImage(ext))
        fx = QGraphicsBlurEffect()
        fx.setBlurRadius(radius)
        fx.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
        item.setGraphicsEffect(fx)
        out = QImage(ext.size(), fmt)
        out.fill(0)
        q = QPainter(out)
        scene.render(q, QRectF(out.rect()), QRectF(0, 0, ext.width(), ext.height()))
        q.end()
        del scene
        return out.copy(pad, pad, w, h)
    except Exception:  # noqa: BLE001
        log("blur failed, using the unblurred image:\n" + traceback.format_exc())
        return img


def _grain_tile(dpr):
    """Tiny tile of faint monochrome noise: real acrylic has it, and it hides any banding in the soft blur."""
    n = 128
    noise = os.urandom(n * n)
    raw = bytearray(n * n * 4)
    raw[0::4] = noise
    raw[1::4] = noise
    raw[2::4] = noise
    raw[3::4] = bytes([11]) * (n * n)
    pm = QPixmap.fromImage(QImage(bytes(raw), n, n, n * 4, QImage.Format.Format_ARGB32).copy())
    pm.setDevicePixelRatio(dpr)
    return pm


class Launcher(QWidget):
    hotkey = Signal()
    key_hist = Signal(bool)             # Alt+Up (True) / Alt+Down (False) caught by KeyGrab
    yt_event = Signal(str, float, str)  # status text, percentage (-1 if unknown), state
    yt_detail = Signal(object)          # title / thumbnail link / speed text from the download thread
    yt_thumb = Signal(object)           # the downloaded thumbnail picture (QImage)
    apps_ready = Signal(list)
    files_ready = Signal(list)
    weather_ready = Signal(dict)
    wm_done = Signal(str)
    custom_done = Signal(str)
    vapor_done = Signal(bool, str)      # (ok, text) from a vaporctl command that ran in a thread
    temps_ready = Signal(dict)
    ocr_done = Signal(str, str)        # (text, error) from the OCR thread
    clean_event = Signal(object)       # progress from the cache-clearing thread

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        # A normal opaque window. The glass look comes from a screenshot of what is behind the launcher, blurred + tinted
        # by us, so there is no see-through (layered) window and no live acrylic blur for dwm.exe to keep re-rendering.
        self._shot = self._glass = self._blur = None
        self._shot_org = QPoint(0, 0)
        self._shot_scr, self._regrabbing, self._blur_scale, self._shot_scale, self._grain = None, False, 0.5, 1.0, None
        self._shot_lsize = (1, 1)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._h = H                                    # current window height (shrinks in zen mode)
        self.setMinimumSize(COLLAPSED_W, ZEN_BAR_H)    # the window really resizes when the right side retracts
        self.setMaximumSize(W, H)
        self.resize(W, H)
        self.cfg = _CFG_REF                              # one shared settings dict: helpers outside this class read it too
        self.cfg.update(load_settings())
        try:                                             # Harmony found on its own -> write the path into the config line
            cz = self.cfg.get("customizations")
            if isinstance(cz, dict) and not (cz.get("harmony") or cz.get("wallpaper_picker")):
                found_h = picker_path(self.cfg)
                if found_h:
                    cz["harmony"] = found_h.replace("\\", "/")
                    save_settings(self.cfg)
        except Exception:  # noqa: BLE001
            pass
        refresh_base()
        self.hue_deg = saved_hue()
        self.t = themed(self.hue_deg)
        self.cfg.setdefault("editor", "notepad.exe")
        self._k = self._k_target = 0.0 if (self.cfg.get("collapsed") or self.cfg.get("zen")) else 1.0     # 1 = right side out, 0 = retracted
        self._vis_w = W if self._k else COLLAPSED_W
        self._cx = self._y = None
        self._wd = None                                # window drag: (mouse start, window start)
        self._dialog_open = False                      # keep launcher alive while a native/modal dialog is active
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.toggle_panel)
        self.col_anim = QVariantAnimation(self)
        self.col_anim.valueChanged.connect(lambda v: self._apply_k(float(v)))
        self.col_anim.finished.connect(lambda: (self._apply_glass(), self._media_run(self._k_target > 0.5 and self.isVisible())))
        self.zen_anim = QVariantAnimation(self)
        self.zen_anim.setDuration(180)
        self.zen_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.zen_anim.valueChanged.connect(self._on_zen_height)
        bg = clean_path(self.cfg.get("background") or "")
        self.src, self._covs = shrink(QPixmap(bg), W, H) if bg and os.path.isfile(bg) else QPixmap(), {}
        self._movie = self._player = self._sink = self._media_obj = None
        self._media_kind, self._media_cached = "", False
        self._media_crop, self._cropwin = None, None
        self._cpu_prev = None
        qp = clean_path(self.cfg.get("quote") or "")
        self.qsrc = (shrink(crop_pm(QPixmap(qp), self.cfg.get("quote_crop")), QUOTE_R.width(), QUOTE_R.height())
                     if qp and os.path.isfile(qp) else QPixmap())
        self.apps, self.usage, self.show_all = [], self._load_usage(), False
        self.files, self._files_at, self._files_busy = [], 0.0, False
        self._ready = self._closing = self._down = self._drag = self._rb = False
        self._t, self._hidden_at, self._scanned, self._warm_i = 0.0, 0.0, 0.0, 0
        self._weather_at = 0.0
        self._count = ""
        self._yt_status = ""
        self._yt_progress = -1.0
        self.yt_event.connect(self._on_yt_event)
        self.yt_detail.connect(self._on_yt_detail)
        self.yt_thumb.connect(self._on_yt_thumb)
        self._yt_state, self._yt_d, self._yt_shown = "", {}, 0.0
        self._yt_thumb_url, self._yt_thumb_small = "", None
        self._yt_anim = QTimer(self)
        self._yt_anim.setInterval(50)
        self._yt_anim.timeout.connect(self._tick_yt)
        self._yt_clear_timer = QTimer(self)
        self._yt_clear_timer.setSingleShot(True)
        self._yt_clear_timer.timeout.connect(self._clear_yt_status)
        self.stats = dict(bat=None, plug=False, charging=False, life=None)
        self.weather, self.temps = None, dict(cpu=None, gpu=None)
        self.wm_state, self._wm_busy, self._wm_n = {k: False for k in WM}, None, 2
        self.hist = dict(cpu=deque(maxlen=32), gpu=deque(maxlen=32))

        self.color_editor_open = False
        self.color_editor = AdvancedColorEditor(QColor(*rot_rgb((76, 194, 255), self.hue_deg)), self)
        self.color_editor.setGeometry(EDITOR_AREA)
        self.color_editor.setVisible(False)
        self.color_editor.setTheme(self.t)
        self.color_editor.currentColorChanged.connect(self._advanced_color_changed)
        self._editing_advanced = False

        self.command_history = []
        self.command_history_index = 0
        self._history_draft = ""
        self.edit = QLineEdit(self)
        self.edit.setGeometry(LEFT_X + 52, SEARCH_Y + 4, LEFT_W - 104, SEARCH_H - 8)
        self.edit.setPlaceholderText("Search apps, files, commands...")
        self.edit.textChanged.connect(self.refresh)
        self.edit.installEventFilter(self)
        self.list = ResultList(self.t, self)
        self.list.setGeometry(LEFT_X, LIST_Y, LEFT_W, MAX_VIS * ROW_H)
        self.list.picked.connect(self.activate)
        self.setStyleSheet(make_qss(self.t))
        self._build_cache()

        self.fade = QVariantAnimation(self)
        self.fade.valueChanged.connect(self._on_fade)
        self.fade.finished.connect(self._fade_done)
        self.apps_ready.connect(self._got_apps)
        self.vapor_done.connect(self._vapor_result)
        self.files_ready.connect(self._got_files)
        self.clean_event.connect(self._on_clean_event)
        self.ocr_done.connect(self._on_ocr_done)
        self.weather_ready.connect(self._got_weather)
        self.wm_done.connect(self._wm_finished)
        self.custom_done.connect(self._custom_finished)
        self._custom_busy = False
        self.temps_ready.connect(self._got_temps)
        self.gpu_mon = GpuMonitor(lambda v: self.temps_ready.emit(dict(gpu=None if v is None else max(0.0, min(100.0, float(v))))))
        self.warm = QTimer(self)                     # loads app icons a few at a time so typing never stalls
        self.warm.setInterval(12)
        self.warm.timeout.connect(self._warm_step)
        self.poll = QTimer(self)                     # closes on a click anywhere outside the box
        self.poll.setInterval(50)
        self.poll.timeout.connect(self._poll_mouse)
        self.stat_timer = QTimer(self)
        self.stat_timer.setInterval(1000)
        self.stat_timer.timeout.connect(self._tick)
        self.save_timer = QTimer(self, singleShot=True, interval=450)    # write the theme once you stop dragging
        self.save_timer.timeout.connect(self._save_theme)
        self._theme_mtime = self._mtime()
        if self.cfg.get("zen"):
            self._fit_zen()
        self.watch = QTimer(self)
        self.watch.setInterval(700)
        self.watch.timeout.connect(self._check_theme)
        self.watch.start()
        self.keygrab = KeyGrab(lambda up: self.key_hist.emit(bool(up)))
        self.key_hist.connect(self._history_step)
        self.tb_timer = QTimer(self)                 # keeps the taskbar hidden if Windows / Explorer brings it back
        self.tb_timer.setInterval(80)
        self.tb_timer.timeout.connect(self._taskbar_guard)
        if self.cfg.get("taskbar_always_hidden", True):       # hidden from the moment Synapse starts, and kept hidden
            self._set_taskbar(True)                           # (a leftover taskbar_hidden flag keeps the remembered original state)
        elif self.cfg.get("taskbar_hidden"):                  # left over from a crash: the taskbar starts out visible
            self._set_taskbar(False)
        media = clean_path(self.cfg.get("media") or "")
        if media and os.path.isfile(media):
            self._load_media(media)

    # ---- static glass layer, drawn once per theme change instead of every frame
    def _pick(self, which):
        if which == "quote" and not self.qsrc.isNull():
            return self.qsrc
        return self.src                                  # no quote image set -> use the background, like before

    def _cover(self, w, h, dpr, ay=0.5, which="bg"):
        key = (w, h, dpr, ay, which)
        if key not in self._covs:
            tw, th = int(w * dpr), int(h * dpr)
            s = self._pick(which).scaled(tw, th, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            self._covs[key] = s.copy((s.width() - tw) // 2, int((s.height() - th) * ay), tw, th)
        return self._covs[key]

    def _card_pixmap(self, w, h, dpr, ay, dark, tint, which="bg"):
        pm = QPixmap(int(w * dpr), int(h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        cp = QPainterPath()
        cp.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 14, 14)
        q.setClipPath(cp)
        if self._pick(which).isNull():
            q.fillPath(cp, tint(30))
        else:
            q.drawPixmap(0, 0, w, h, self._cover(w, h, dpr, ay, which))
        if dark:
            q.fillRect(QRectF(0, 0, w, h), QColor(0, 0, 0, dark))
        return pm, q, cp

    def _build_cache(self):
        self._card_layer = self._anim_parts = None
        t, dpr = self.t, self.devicePixelRatioF()
        accent, sub, white = qc(t["accent"]), qc(t["sub"]), QColor("white")
        tint = lambda a: qc("rgb(%s)" % t["tint"], a)           # noqa: E731
        pm = QPixmap(int(W * dpr), int(H * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, W - 1, H - 1), R, R)
        p.setClipPath(path)
        if not self.src.isNull():
            p.setOpacity(BG_OPACITY)
            p.drawPixmap(0, 0, W, H, self._cover(W, H, dpr))
            p.setOpacity(1.0)
        bgc = QColor(*t["bg"])
        bgc.setAlpha(int(255 * self._opacity()))
        p.fillPath(path, bgc)
        p.setClipping(False)
        p.setBrush(tint(20))
        p.setPen(QPen(tint(55), 1))
        theme_panel = QRect(THEME) if not self.color_editor_open else QRect(THEME.x(), THEME.y(), THEME.width(), 294)
        panels = [QRect(LEFT_X, SEARCH_Y, LEFT_W, SEARCH_H), theme_panel]
        if not self.color_editor_open:
            panels.append(CLOCK)
        for r in panels:
            p.drawRoundedRect(QRectF(r).adjusted(.5, .5, -.5, -.5), 14, 14)
        # search glyph + sparkle
        p.setFont(_font(18, icon=True))
        p.setPen(white)
        p.drawText(QRectF(LEFT_X + 14, SEARCH_Y, 30, SEARCH_H), Qt.AlignmentFlag.AlignCenter, "\uE721")
        p.setPen(tint(70))
        p.drawLine(LEFT_X + 48, SEARCH_Y + 12, LEFT_X + 48, SEARCH_Y + SEARCH_H - 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(white)
        p.drawPolygon(sparkle(LEFT_X + LEFT_W - 26, SEARCH_Y + SEARCH_H / 2, 9))
        # window controls
        _line_pen(p, white, 1.8)
        p.drawLine(MIN_BTN.center().x() - 7, MIN_BTN.center().y(), MIN_BTN.center().x() + 7, MIN_BTN.center().y())
        c = CLOSE_BTN.center()
        p.drawLine(c.x() - 6, c.y() - 6, c.x() + 6, c.y() + 6)
        p.drawLine(c.x() - 6, c.y() + 6, c.x() + 6, c.y() - 6)
        p.setPen(QPen(tint(55), 1))
        p.drawLine(RIGHT_X + 8, 32, MIN_BTN.x() - 12, 32)
        # Collapsed state uses the original slider in the card header; expanded state
        # relocates that same control into the embedded editor below the SV square.
        track_y = TRACK_Y
        if not self.color_editor_open:
            g = QLinearGradient(TRACK_X0, 0, TRACK_X1, 0)
            for i in range(13):
                g.setColorAt(i / 12.0, QColor(*rot_rgb((76, 194, 255), i / 12.0 * 359)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawRoundedRect(QRectF(TRACK_X0, track_y - 5, TRACK_X1 - TRACK_X0, 10), 5, 5)
        # Clock separators are part of the hidden dashboard card while the
        # advanced editor is expanded, so don't cache them underneath it.
        if not self.color_editor_open:
            p.setPen(QPen(tint(55), 1))
            for dx in (250,):
                p.drawLine(CLOCK.x() + dx, CLOCK.y() + 12, CLOCK.x() + dx, CLOCK.bottom() - 12)
        # footer hints
        p.setFont(_font(14, icon=True))
        p.setPen(white)
        p.drawText(QRectF(LEFT_X + 4, FOOT_Y, 22, 22), Qt.AlignmentFlag.AlignCenter, "\uE76C")
        p.setFont(_font(10, mono=True))
        p.setPen(accent)
        p.drawText(QRectF(LEFT_X + 30, FOOT_Y, 520, 22), Qt.AlignmentFlag.AlignVCenter, HINTS)
        p.end()
        self._static = pm

        w, h = QUOTE_R.width(), QUOTE_R.height()                                                      # quote card
        self._quote, q, cp = self._card_pixmap(w, h, dpr, 0.8, 150, tint, "quote")
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(white)
        for cx, cy, r in ((16, 16, 4), (58, 40, 2.5), (w - 28, 30, 7), (w - 70, 12, 2.5), (w - 100, 44, 2)):
            q.drawPolygon(sparkle(cx, cy, r))
        q.setPen(white)
        qfont, qlines, qlh = fit_quote(quote_text(self.cfg), w - 28, h - 8)
        q.setFont(qfont)
        y0 = (h - qlh * len(qlines)) / 2
        for i, ln in enumerate(qlines):
            q.drawText(QRectF(14, y0 + i * qlh, w - 28, qlh), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, ln)
        q.setClipping(False)
        q.setPen(QPen(tint(70), 1))
        q.setBrush(Qt.BrushStyle.NoBrush)
        q.drawPath(cp)
        q.end()

    # ---- theme: follows cc_theme.json (Vapor's theme card), and the slider on the right writes to it
    def _mtime(self):
        try:
            return os.path.getmtime(theme_file())
        except OSError:
            return 0

    def _check_theme(self):
        m = self._mtime()
        if m != self._theme_mtime:
            self._theme_mtime = m
            refresh_base()
            self.hue_deg = saved_hue()
            self.t = themed(self.hue_deg)
            self._restyle()

    def _restyle(self):
        self.list.t = self.t
        self.color_editor.setTheme(self.t)
        self.setStyleSheet(make_qss(self.t))
        self._build_cache()
        if self.isVisible():
            self._apply_glass()
        self.update()
        self.list.update()

    def _set_hue(self, deg):
        self.hue_deg = max(0, min(359, int(deg)))
        self.t = themed(self.hue_deg)
        self.list.t = self.t
        self.color_editor.setTheme(self.t)
        if self.color_editor_open and not self._editing_advanced:
            self.color_editor.setHue(self.hue_deg)
        if not self._rb:                                         # rebuild at most every ~30 ms while dragging
            self._rb = True
            QTimer.singleShot(30, self._do_rebuild)
        self.save_timer.start()

    def _do_rebuild(self):
        self._rb = False
        self._build_cache()
        self.update()
        self.list.update()

    def _save_theme(self):                                       # cc_theme.json is shared with Vapor, which re-reads it
        write_hue_file(self.hue_deg)
        self._theme_mtime = self._mtime()
        self.setStyleSheet(make_qss(self.t))
        self._apply_glass()

    def _reset_theme(self):
        self.hue_deg = 0
        write_theme_state(color_sat=100, color_light=88, hue=0, theme=None)
        refresh_base()
        self.t = themed(0)
        self.list.t = self.t
        # Keep the embedded advanced editor (hex field, SV square, hue strip) in sync with the reset theme.
        self._editing_advanced = True
        try:
            self.color_editor.setTheme(self.t)
            self.color_editor.setCurrentColor(QColor(self.t["accent"]))
        finally:
            self._editing_advanced = False
        self._do_rebuild()
        self.save_timer.start()

    def _slide_to(self, x):
        self._set_hue(round(max(0.0, min(1.0, (x - TRACK_X0) / float(TRACK_X1 - TRACK_X0))) * 359))
        self.update(THEME)

    def _advanced_color_changed(self, color):
        if not color.isValid():
            return
        hue = color.hue()
        self._editing_advanced = True
        try:
            if hue >= 0:
                self.hue_deg = max(0, min(359, int(hue)))
            sat = round(color.saturationF() * 100)
            light = round(color.valueF() * 100)
            write_theme_state(color_sat=sat, color_light=light, hue=self.hue_deg, theme=(self.hue_deg or None))
            # Pull the newly selected saturation/value into the palette before
            # rebuilding local widgets; previously only hue was applied locally.
            refresh_base()
            # Immediate visual feedback.
            global BASE
            BASE["accent"] = QColor.fromHsv(0, color.saturation(), color.value()).name()
            self.t = themed(self.hue_deg)
            self.t["accent"] = color.name()
            self.list.t = self.t
            self.color_editor.setTheme(self.t)
            self._restyle()
            self.save_timer.start()
        finally:
            self._editing_advanced = False

    def _toggle_color_editor(self):
        self.color_editor_open = not self.color_editor_open
        self.color_editor.setVisible(self.color_editor_open)
        if self.color_editor_open:
            self.color_editor.setGeometry(EDITOR_AREA)
            self.color_editor.setTheme(self.t)
            self.color_editor.setCurrentColor(QColor(self.t["accent"]))
            self.color_editor.raise_()
        self._build_cache()
        self.update()

    def _on_empty(self, pos):
        track_y = self.color_editor.hueTrackY() if self.color_editor_open else TRACK_Y
        slider_hit = QRect(TRACK_X0 - 8, track_y - 16, TRACK_X1 - TRACK_X0 + 16, 32)
        return not (MIN_BTN.contains(pos) or CLOSE_BTN.contains(pos) or RESET_R.contains(pos) or COLOR_BTN.contains(pos) or slider_hit.contains(pos)
                    or any(r.contains(pos) for r in WM_BTNS.values()))

    def mousePressEvent(self, e):
        pos = e.position().toPoint()
        if e.button() != Qt.MouseButton.LeftButton:
            return
        if MIN_BTN.contains(pos) or CLOSE_BTN.contains(pos):
            self.close_launcher()
        elif COLOR_BTN.contains(pos):
            self._toggle_color_editor()
        elif RESET_R.contains(pos):
            self._reset_theme()
        elif (QRect(TRACK_X0 - 8, (self.color_editor.hueTrackY() if self.color_editor_open else TRACK_Y) - 16,
                    TRACK_X1 - TRACK_X0 + 16, 32).contains(pos)):
            self._drag = True
            self._slide_to(pos.x())
        elif not self.color_editor_open and any(r.contains(pos) for r in WM_BTNS.values()):
            key = next(k for k, r in WM_BTNS.items() if r.contains(pos))
            if key == "dotfiles":
                self._open_dotfiles(bool(e.modifiers() & Qt.KeyboardModifier.AltModifier))
            else:
                self._wm_toggle(key)
        else:                                          # empty glass: drag the whole launcher
            self._wd = (e.globalPosition().toPoint(), self.pos())

    def mouseDoubleClickEvent(self, e):                # double-click empty glass = back to the default spot
        if e.button() == Qt.MouseButton.LeftButton and self._on_empty(e.position().toPoint()):
            self._wd = None
            self.cfg.pop("pos", None)
            save_settings(self.cfg)
            self._cx, self._y = self._default_pos()
            self._apply_k(self._k)
        else:
            self.mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag:
            self._slide_to(int(e.position().x()))
            return
        if self._wd is not None and not self._regrabbing:
            start, origin = self._wd
            scr = QApplication.screenAt(e.globalPosition().toPoint()) or QApplication.primaryScreen()
            g = scr.geometry()
            x = max(g.left(), min(g.right() - self.width(), origin.x() + e.globalPosition().toPoint().x() - start.x()))
            y = max(g.top(), min(g.bottom() - self._h, origin.y() + e.globalPosition().toPoint().y() - start.y()))
            self._cx, self._y = x + self.width() // 2, y
            self.move(x, y)
            if self._shot_scr is None or scr.geometry() != self._shot_scr.geometry():
                self._regrab(scr)

    def mouseReleaseEvent(self, _e):
        self._drag = False
        if self._wd is not None:
            self._wd = None
            self.cfg["pos"] = [self._cx, self._y]
            save_settings(self.cfg)

    def _opacity(self):
        try:
            tr = float(self.cfg.get("transparency", 60))
        except (TypeError, ValueError):
            tr = 60.0
        return 1.0 - max(0.0, min(100.0, tr)) / 100.0

    def _apply_glass(self):
        if not self.isVisible():
            return
        if self._make_glass():                         # rebuild our own blur/tint from the snapshot (theme, acrylic, transparency)
            self.update()

    # ---- retractable right side: the window keeps its size, a mask + position slide it open/closed around the centre
    def _apply_k(self, k):
        self._k = k
        w = int(round(COLLAPSED_W + (W - COLLAPSED_W) * k))
        self._vis_w = w
        if self._cx is not None:
            g = QRect(self._cx - w // 2, self._y, w, self._h)
            if g != self.geometry():                   # every native resize makes dwm.exe rebuild the window surface
                self.setGeometry(g)
        elif (w, self._h) != (self.width(), self.height()):
            self.resize(w, self._h)
        self.update()

    def toggle_panel(self):
        if self.cfg.get("zen"):                       # zen mode keeps the side panel hidden
            return
        self.cfg["collapsed"] = self._k_target > 0.5
        save_settings(self.cfg)
        self._slide_panel(0.0 if self._k_target > 0.5 else 1.0)

    # ---- taskbar [on|off]: off hides the Windows taskbar completely, on brings it back
    def _set_taskbar(self, hidden, save=True):
        try:
            if hidden:
                if not self.cfg.get("taskbar_hidden"):            # remember how the taskbar was set up, to restore it later
                    self.cfg["taskbar_prev_autohide"] = taskbar_autohide_state()
                taskbar_set_autohide(True)
                taskbar_show_windows(False)
                taskbar_hide_bridge()
                self.tb_timer.start()
            else:
                self.tb_timer.stop()
                taskbar_show_windows(True)
                if self.cfg.get("taskbar_hidden"):                # only undo what Synapse itself changed
                    taskbar_set_autohide(bool(self.cfg.get("taskbar_prev_autohide", False)))
        except Exception:  # noqa: BLE001
            log("taskbar change failed:\n" + traceback.format_exc())
            return False
        self.cfg["taskbar_hidden"] = bool(hidden)
        if save:
            save_settings(self.cfg)
        return True

    # ---- customizations [on|off]: taskbar + Komorebi + Harmony in one go
    def _set_customizations(self, on):
        if self._custom_busy:
            return
        self._custom_busy = True
        self.edit.clear()
        self._count = "Turning customizations " + ("on" if on else "off") + "..."
        self.update()
        self._set_taskbar(bool(on))                               # taskbar is quick, so it is done right away; on = hidden
        picker = picker_path(self.cfg)

        def work():
            errs = []
            try:
                running = wm_running()
                for key, want in (("komorebi", bool(on)),):
                    if running.get(key) != want:
                        err = wm_start(key) if want else wm_stop(key)
                        if err:
                            errs.append(err)
                if picker:
                    err = picker_start(picker) if on else picker_stop(picker)
                    if err:
                        errs.append(err)
                else:
                    cfg_h = (self.cfg.get("customizations") or {}) if isinstance(self.cfg.get("customizations"), dict) else {}
                    if cfg_h.get("harmony") or cfg_h.get("wallpaper_picker"):
                        errs.append("Harmony path in launcher_settings.json doesn't exist: %s" % (cfg_h.get("harmony") or cfg_h.get("wallpaper_picker")))
                    else:
                        errs.append('Harmony not found  -  set "customizations": {"harmony": "C:/path/harmony.pyw"} in launcher_settings.json (>config)')
            except Exception:  # noqa: BLE001
                log("customizations switch failed:\n" + traceback.format_exc())
                errs.append("Something failed  -  see >log")
            self.custom_done.emit("  \u2022  ".join(errs) if errs else "Customizations " + ("on" if on else "off"))
        threading.Thread(target=work, name="SynapseCustomizations", daemon=True).start()

    def _custom_finished(self, msg):
        self._custom_busy = False
        try:
            self.wm_state = wm_running()
        except Exception:  # noqa: BLE001
            pass
        self._count = msg
        self.update()

    # ---- lcbar [on|off]: start / close Vapor (off the UI thread, closing can take a moment)
    def _set_lcbar(self, on):
        if self._custom_busy:
            return
        if on and not vaporctl_path(self.cfg):
            self._count = 'Vapor not found on your PATH  -  start it once, or set "customizations": {"vapor": "folder"}'
            self.update()
            return
        self._custom_busy = True
        self.edit.clear()
        self._count = ("Starting" if on else "Closing") + " Vapor..."
        self.update()

        def work():
            try:
                err = wm_start("vapor") if on else wm_stop("vapor")
            except Exception:  # noqa: BLE001
                log("vapor switch failed:\n" + traceback.format_exc())
                err = "Something failed  -  see >log"
            self.custom_done.emit(err or "Vapor " + ("on" if on else "off"))
        threading.Thread(target=work, name="SynapseVapor", daemon=True).start()

    def _taskbar_guard(self):
        """While the taskbar is meant to be hidden: hide it again if it popped back (Win key, Explorer restart...)."""
        if not self.cfg.get("taskbar_hidden"):
            self.tb_timer.stop()
            return
        try:
            if not taskbar_autohide_state():
                taskbar_set_autohide(True)
            taskbar_show_windows(False)
            taskbar_hide_bridge()
        except Exception:  # noqa: BLE001
            log("taskbar guard failed:\n" + traceback.format_exc())

    def _set_zen(self, on):
        self.cfg["zen"] = bool(on)
        save_settings(self.cfg)
        self._slide_panel(0.0 if on or self.cfg.get("collapsed") else 1.0)
        self._fit_zen()

    def _place_left(self, lh, show=True):
        """Sizes the result list in the left pane."""
        self.list.setGeometry(QRect(LEFT_X, LIST_Y, LEFT_W, max(int(lh), 1)))
        self.list.setVisible(bool(show))

    def _on_zen_height(self, value):
        self._h = int(round(float(value)))
        if self.cfg.get("zen"):
            n = len(self.list.items) if self.edit.text().strip() else 0
            self._place_left(max(0, self._h - LIST_Y - 14), n > 0)
        self._apply_k(self._k)
        self._apply_glass()

    def _fit_zen(self):
        """Ease the launcher height and results drawer in/out for Zen mode."""
        if self.cfg.get("zen"):
            n = len(self.list.items) if self.edit.text().strip() else 0
            lh = min(n, MAX_VIS) * ROW_H
            target_h = LIST_Y + lh + 14 if n else ZEN_BAR_H
            self._place_left(lh, n > 0)
            self.zen_anim.stop()
            if self.cfg.get("animations", True) and self.isVisible() and target_h != self._h:
                self.zen_anim.setStartValue(float(self._h))
                self.zen_anim.setEndValue(float(target_h))
                self.zen_anim.start()
            else:
                self._on_zen_height(float(target_h))
        else:
            self.zen_anim.stop()
            self._h = H
            self._place_left(MAX_VIS * ROW_H, True)
            self._apply_k(self._k)
            self._apply_glass()

    def _slide_panel(self, target):
        self._k_target = target
        a = self.col_anim
        a.stop()
        if self.cfg.get("animations", True) and self.isVisible():
            a.setStartValue(float(self._k))
            a.setEndValue(self._k_target)
            a.setDuration(240)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            a.start()
        else:                                          # one resize instead of ~20
            self._apply_k(self._k_target)
            self._apply_glass()
            self._media_run(self._k_target > 0.5 and self.isVisible())
        if self._k_target > 0.5:
            self._media_run(self.isVisible())
            QTimer.singleShot(0, self._tick)
        self.edit.setFocus()

    # ---- apps + recents
    def _load_usage(self):
        try:
            with open(USAGE_FILE, encoding="utf-8") as f:
                raw = json.load(f)
            return {k: (v if isinstance(v, dict) else {"n": int(v), "t": 0}) for k, v in raw.items()}
        except (OSError, ValueError, TypeError):
            return {}

    def _scan(self):
        self._scanned = time.time()
        custom = list(self.cfg.get("custom_apps") or [])
        threading.Thread(target=lambda: self.apps_ready.emit(scan_apps(custom)), daemon=True).start()

    def _scan_files(self):
        if self._files_busy:
            return
        self._files_busy = True

        def work():
            try:
                self.files_ready.emit(scan_files(self.cfg.get("file_roots") or ()))
            except Exception:  # noqa: BLE001
                log("file scan failed:\n" + traceback.format_exc())
                self.files_ready.emit([])
        threading.Thread(target=work, daemon=True).start()

    def _got_files(self, files):
        self.files, self._files_at, self._files_busy = files, time.time(), False
        if self.edit.text().lstrip().startswith('"'):
            self.refresh(self.edit.text())

    def _file_items(self, q):
        term = q[1:]
        if term.endswith('"'):
            term = term[:-1]
        term = term.strip()
        use_ev = everything_ready()
        if not use_ev and (not self.files or time.time() - self._files_at > 300):
            self._scan_files()                            # no Everything: first use (or stale) -> index in the background
        if not term:
            return [dict(kind="info", title="File search", path="", glyph="\uE721",
                         sub=('Powered by Everything  \u2022  ' if use_ev else '') + 'Type a name inside quotes, e.g.  "hello"  finds hello.txt ...')]
        if not use_ev and not self.files:
            return [dict(kind="info", title="Indexing files...", path="", glyph="\uE721", sub="One moment, results appear when it finishes")]
        fm = QFontMetrics(_font(11))
        items = []
        hits = everything_search(term) if use_ev else None
        if hits is None:                                  # Everything missing or its query failed -> built-in index
            if not self.files:
                self._scan_files()
                return [dict(kind="info", title="Indexing files...", path="", glyph="\uE721",
                             sub="Everything isn't answering, so the built-in index is being built")]
            hits = match_files(self.files, term)
        for path in hits:
            isdir = os.path.isdir(path)
            folder = fm.elidedText(os.path.dirname(path), Qt.TextElideMode.ElideMiddle, 420)
            items.append(dict(kind="file", title=os.path.basename(path) or path, sub=("Folder  \u2022  " if isdir else "") + folder,
                              path=path, glyph="\uE8B7" if isdir else "\uE8A5"))
        return items or [dict(kind="info", title="No files found", path="", glyph="\uE721", sub='Nothing matches "%s"' % term)]

    def _got_apps(self, apps):
        key = lambda L: [(a["title"], a["path"]) for a in L]       # noqa: E731
        report, self._scan_report = getattr(self, "_scan_report", False), False
        if report:
            old = {a["path"] for a in self.apps}
            new = [a for a in apps if a["path"] not in old]
            self._count = ("Scan done  \u2022  %d new: %s" % (len(new), ", ".join(a["title"] for a in new[:3]))) if new \
                else "Scan done  \u2022  no new apps (%d total)" % len(apps)
            self.update(QRect(LEFT_X, FOOT_Y, LEFT_W, 24))
        if key(apps) == key(self.apps):
            return
        self.apps = apps
        if not getattr(self, "_clean_hold", False):       # don't replace the cache-clearing progress rows
            self.refresh(self.edit.text())
        self._warm_i = 0
        self.warm.start()

    def _warm_step(self):
        for _ in range(3):
            if self._warm_i >= len(self.apps):
                self.warm.stop()
                return
            self.list.icon_for(self.apps[self._warm_i]["path"])
            self._warm_i += 1

    def refresh(self, q):
        self._clean_hold = False
        q = q.strip()
        if q.startswith(">"):
            self.list.empty_text = ""
            self._count = "command"
            self.list.set_items(self._cmd_items(q))
            self._fit_zen()
            self.update(QRect(LEFT_X, FOOT_Y, LEFT_W, 24))
            return
        if not q:
            by_title = {a["title"]: a for a in self.apps}
            rec = sorted(((u.get("n", 0), u.get("t", 0), n) for n, u in self.usage.items()
                          if u.get("n", 0) and n in by_title), reverse=True)[:8]
            if self.show_all or not rec:                  # "More..." (or no history yet) shows every app
                items = [dict(a, sub="Application") for a in self.apps][:300]
                self._count = "%d apps" % len(items) if items else ""
            else:                                         # default view = the apps you opened most recently
                items = [dict(by_title[n], sub="Opened %d time%s" % (count, "" if count == 1 else "s"))
                         for count, _ts, n in rec]
                items.append(dict(kind="more", title="More...", sub="Show all apps", path="", glyph="\uE710"))
                self._count = "%d most opened" % len(rec)
            self.list.empty_text = "" if self.apps else "Indexing apps..."
        elif q.startswith('"'):                           # "hello" -> search files instead of apps
            items = self._file_items(q)
            self.list.empty_text = ""
            self._count = "%d file%s" % (len(items), "" if len(items) == 1 else "s") if items and items[0]["kind"] == "file" else "files"
        elif q.startswith("="):                           # calculator mode: =3*3, =sqrt(16)+2^3, =sin(pi/2)
            c = calc(q, True)
            if not q[1:].strip():
                items = [dict(kind="info", title="Calculator", path="", glyph="\uE8EF",
                              sub="Type a sum, e.g. =3*3   =2^10   =sqrt(144)   =sin(pi/2)")]
            elif c is None:
                items = [dict(kind="info", title="= ?", path="", glyph="\uE8EF", sub="Can't calculate that")]
            else:
                items = [dict(kind="calc", title="= " + c, sub="Press Enter to copy", path=c, glyph="\uE8EF")]
            self.list.empty_text = ""
            self._count = "calculator"
        else:
            items = []
            c = calc(q)
            if c is not None:
                items.append(dict(kind="calc", title="= " + c, sub="Press Enter to copy", path=c, glyph="\uE8EF"))
            ql, scored = q.lower(), []
            for a in self.apps:
                sc = fuzzy(ql, a["title"])
                for w_ in (a.get("alias") or "").split():           # "mspaint" -> Paint
                    s2 = fuzzy(ql, w_)
                    if s2 is not None and (sc is None or s2 - 30 > sc):
                        sc = s2 - 30
                if sc is not None:
                    scored.append((sc + min(self.usage.get(a["title"], {}).get("n", 0), 20) * 8, a))
            items += [a for _s, a in sorted(scored, key=lambda x: -x[0])[:30]]
            items.append(dict(kind="web", title="Search the web for \u201c%s\u201d" % q, sub="Opens in your browser",
                              path=q, glyph="\uE774"))
            self.list.empty_text = ""
            self._count = "%d result%s" % (len(items), "" if len(items) == 1 else "s")
        self.list.set_items(items)
        self._fit_zen()
        self.update(QRect(LEFT_X, FOOT_Y, LEFT_W, 24))

    def _restart_frozen(self):
        """Synapse.exe: start a fresh copy, then close this one (the new one needs a moment to unpack, so the single-instance
        server is gone by the time it starts)."""
        try:
            env = dict(os.environ)
            env.pop("_MEIPASS2", None)
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"               # a onefile build must unpack its own fresh copy
            subprocess.Popen([sys.executable], env=env, cwd=HERE, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=0x00000008 | 0x00000200, close_fds=True)
        except OSError:
            log("restart failed:\n" + traceback.format_exc())
            return
        self.quit_app()

    def _history_step(self, up):
        """Alt+Up / Alt+Down: step through the earlier >commands."""
        if not self.command_history:
            return
        if self.command_history_index >= len(self.command_history):
            self._history_draft = self.edit.text()
        if up:
            self.command_history_index = max(0, self.command_history_index - 1)
        else:
            self.command_history_index = min(len(self.command_history), self.command_history_index + 1)
        value = self.command_history[self.command_history_index] if self.command_history_index < len(self.command_history) else self._history_draft
        self.edit.setText(value)
        self.edit.setCursorPosition(len(value))

    def _note_usage(self, title):
        u = self.usage.get(title, {"n": 0, "t": 0})
        self.usage[title] = {"n": u.get("n", 0) + 1, "t": time.time()}
        try:
            with open(USAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.usage, f)
        except OSError:
            pass

    def _activate_special(self, it, mode):
        """Shift+Enter (mode "reveal"): show the item in Explorer, selected.  Ctrl+Shift+Enter (mode "admin"): run as administrator."""
        path = it["path"]
        if mode == "reveal":
            target = ""
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]+:(?![\\/])", path):      # ms-paint: and other protocol "paths" have no file
                target = ""
            elif path.lower().endswith(".lnk"):                              # a shortcut: show what it points at (else the shortcut)
                t = QFileInfo(path).symLinkTarget()
                target = t if t and os.path.lexists(t) else path
            elif os.path.lexists(path):
                target = path
            if not target:
                self._count = "No file on disk to show in Explorer for this one"
                self.update()
                return
            try:
                subprocess.Popen('explorer.exe /select,"%s"' % os.path.normpath(target), creationflags=0x08000000)
            except OSError:
                self._count = "Couldn't open Explorer"
                self.update()
                return
            self.close_launcher()
            return
        if os.path.isdir(path):
            self._count = "A folder can't be opened as administrator"
            self.update()
            return
        try:
            sh = ctypes.WinDLL("shell32", use_last_error=True)
            sh.ShellExecuteW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]
            sh.ShellExecuteW.restype = ctypes.c_void_p
            r = sh.ShellExecuteW(None, "runas", path, None, os.path.dirname(path) or None, 1) or 0
        except Exception:  # noqa: BLE001
            log("run as administrator failed:\n" + traceback.format_exc())
            r = 0
        if r <= 32:
            self._count = "Cancelled" if r == 5 else "Couldn't run it as administrator"     # 5 = the UAC prompt was declined
            self.update()
            return
        if it["kind"] == "app":
            self._note_usage(it["title"])
        self.close_launcher()

    def activate(self, mode=None):
        mode = mode if mode in ("reveal", "admin") else None
        it = self.list.current()
        if not it:
            return
        if it["kind"] == "info":
            return
        if mode and it["kind"] in ("app", "file"):
            self._activate_special(it, mode)
            return
        if it["kind"] == "hint":                       # picked ">setmedia" from the suggestions -> fill it in
            self.edit.setText(it["fill"])
            self.edit.setFocus()
            return
        if it["kind"] == "cmd":
            self._run_cmd(it)
            return
        if it["kind"] == "more":
            self.show_all = True
            self.refresh(self.edit.text())
            return
        if it["kind"] == "app":
            try:
                os.startfile(it["path"])
            except OSError:
                return
            u = self.usage.get(it["title"], {"n": 0, "t": 0})
            self.usage[it["title"]] = {"n": u.get("n", 0) + 1, "t": time.time()}
            try:
                with open(USAGE_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.usage, f)
            except OSError:
                pass
        elif it["kind"] == "file":
            try:
                os.startfile(it["path"])
            except OSError:
                return
        elif it["kind"] == "calc":
            QApplication.clipboard().setText(it["path"])
        else:
            webbrowser.open("https://www.google.com/search?q=" + quote(it["path"]))
        self.close_launcher()

    # ---- commands: >setbackground "path" and >setmedia "path"
    def _cmd_items(self, q):
        m = re.match(r">\s*([A-Za-z]*)\s*(.*)", q, re.S)
        word, arg = m.group(1).lower(), m.group(2).strip()
        word = CMD_ALIAS.get(word, word)
        if word == "vapor":
            return self._vapor_items(arg)
        if word == "add":
            custom = self.cfg.get("custom_apps") or []
            if re.match(r"(?:remove|delete|rm)\b", arg, re.I):
                name = re.sub(r"^\w+\s*", "", arg).strip().strip('"').lower()
                hit = next((c for c in custom if str(c.get("title", "")).lower() == name), None)
                sub_ = ("Press Enter to remove \u201c%s\u201d from the list" % hit["title"]) if hit else \
                    ("No added app called \u201c%s\u201d" % name if name else "Type the name of an app you added")
                return [dict(kind="cmd", cmd="add", mode="remove", arg=arg, path="", val=hit, glyph="\uE74D",
                             title="Remove added app", sub=sub_)]
            if not arg:
                return [dict(kind="cmd", cmd="add", mode="browse", arg="", path="", val=True, glyph="\uE710", title="Add an app",
                             sub='Press Enter to browse for it  \u2022  or type  >add "C:\\path\\app.exe" [name]')]
            m2 = re.match(r'\s*(?:"([^"]+)"|(.+?\.(?:exe|lnk|bat|cmd|url|msi|ps1|py|pyw|jar))(?=\s|$))\s*(.*)$', arg, re.I)
            raw, name = (m2.group(1) or m2.group(2), m2.group(3).strip().strip('"')) if m2 else (arg.strip('"'), "")
            path = os.path.abspath(clean_path(raw))
            ok = os.path.exists(path)
            name = name or os.path.splitext(os.path.basename(path.rstrip("\\/")) or path)[0]
            return [dict(kind="cmd", cmd="add", mode="path", arg=arg, path=path, val=name if ok else None, glyph="\uE710",
                         title="Add \u201c%s\u201d" % name if ok else "Add an app",
                         sub=("Press Enter to add  \u2022  " + path) if ok else "That path doesn't exist")]
        if word == "customizations":
            try:
                running = wm_running()
            except Exception:  # noqa: BLE001
                running = {}
            active = bool(self.cfg.get("taskbar_hidden")) or bool(running.get("komorebi"))
            val = {"": not active, "toggle": not active, "on": True, "off": False}.get(arg.lower())
            if val is None:
                sub_ = "Use on or off, or leave it empty to toggle"
            elif val:
                sub_ = "Press Enter  \u2022  hide the taskbar, open Komorebi and Harmony"
            else:
                sub_ = "Press Enter  \u2022  close Komorebi and Harmony, show the taskbar"
            return [dict(kind="cmd", cmd="customizations", arg=arg, path="", val=val, glyph="\uE771", sub=sub_,
                         title="Customizations are " + ("on" if active else "off"))]
        if word == "taskbar":
            shown = not self.cfg.get("taskbar_hidden")
            val = {"": not shown, "toggle": not shown, "on": True, "show": True, "off": False, "hide": False}.get(arg.lower())
            sub_ = ("Press Enter to " + ("show" if val else "hide completely") + " the Windows taskbar") if val is not None \
                else "Use on or off, or leave it empty to toggle"
            return [dict(kind="cmd", cmd="taskbar", arg=arg, path="", val=val, glyph="\uE7C4", sub=sub_,
                         title="Taskbar is " + ("on" if shown else "off"))]
        if word == "lcbar":
            running = vapor_running()
            val = {"": not running, "toggle": not running, "on": True, "off": False}.get(arg.lower())
            if val is None:
                sub_ = "Use on or off, or leave it empty to toggle"
            elif val and not vaporctl_path(self.cfg):
                sub_ = 'Vapor not found on your PATH  -  start it once, or set "customizations": {"vapor": "folder"}'
            elif val:
                sub_ = "Press Enter  \u2022  start Vapor" + ("  (already running)" if running else "")
            else:
                sub_ = "Press Enter  \u2022  close Vapor" + ("" if running else "  (not running)")
            return [dict(kind="cmd", cmd="lcbar", arg=arg, path="", val=val, glyph="\uE700", sub=sub_,
                         title="Vapor is " + ("on" if running else "off"))]
        if word == "zen":
            cur = bool(self.cfg.get("zen"))
            val = {"": not cur, "toggle": not cur, "on": True, "off": False}.get(arg.lower())
            sub_ = ("Press Enter to turn zen mode " + ("on" if val else "off")) if val is not None \
                else "Use on or off, or leave it empty to toggle"
            return [dict(kind="cmd", cmd="zen", arg=arg, path="", val=val, glyph="\uE9E9", sub=sub_,
                         title="Zen mode is " + ("on" if cur else "off"))]
        if word == "cmd":
            return [dict(kind="cmd", cmd="cmd", arg=arg, path="", glyph="\uE756",
                         title="Open Command Prompt" if not arg else "Run in Command Prompt",
                         sub="Press Enter to open an interactive Windows CMD window" if not arg else "Press Enter to run this command in a new CMD window")]
        if word in ("config", "editor"):
            if word == "editor" and arg:
                candidate = clean_path(arg)
                valid = os.path.isfile(candidate)
                return [dict(kind="cmd", cmd="editor", arg=arg, path=candidate, val=candidate if valid else None,
                             glyph="\uE70F", title="Set file editor", sub=("Press Enter to use " + os.path.basename(candidate)) if valid else "Editor executable not found")]
            if word == "editor":
                return [dict(kind="cmd", cmd="editor", arg="", path="", val=None, glyph="\uE70F", title="Choose file editor",
                             sub="Press Enter to browse for an editor executable; default is Notepad")]
            return [dict(kind="cmd", cmd="config", arg="", path="", glyph="\uE713", title="Open launcher config",
                         sub="Press Enter to edit launcher_settings.json")]
        if word == "clearcache":
            adv = arg.strip().lower() in ("-a", "advanced", "adv")
            return [dict(kind="cmd", cmd="clearcache", arg=arg, advanced=adv, path="", glyph="\uE74D",
                         title="Clear cache  \u2022  advanced display" if adv else "Clear cache",
                         sub=("Press Enter to clear the caches and watch every file in the advanced window" if adv else
                              "Press Enter to clear Vapor, Harmony, Synapse and temp file caches  (add -a for the file list)"))]
        if word == "scan":
            return [dict(kind="cmd", cmd="scan", arg="", path="", glyph="\uE72C", title="Scan for new apps",
                         sub="Press Enter to re-read the Start Menu and your added apps")]
        if word == "reload":
            return [dict(kind="cmd", cmd="reload", arg="", path="", glyph="\uE72C", title="Reload Synapse",
                         sub="Press Enter to refresh app and file indexes, weather, cached images and launcher display")]
        if word == "exit":
            return [dict(kind="cmd", cmd="exit", arg="", path="", title="Exit launcher", glyph="\uE7E8",
                         sub="Press Enter to quit it completely  \u2022  it starts again next time you launch it")]
        if word == "animations":
            cur = bool(self.cfg.get("animations", True))
            val = {"": not cur, "toggle": not cur, "on": True, "off": False}.get(arg.lower())
            sub_ = ("Press Enter to turn animations " + ("on" if val else "off")) if val is not None \
                else "Use on or off, or leave it empty to toggle"
            return [dict(kind="cmd", cmd="animations", arg=arg, path="", val=val, glyph="\uE916", sub=sub_,
                         title="Animations are " + ("on" if cur else "off"))]
        if word == "acrylic":
            cur = bool(self.cfg.get("acrylic", True))
            val = {"": not cur, "toggle": not cur, "on": True, "off": False}.get(arg.lower())
            sub_ = ("Press Enter to turn the blur " + ("on" if val else "off")) if val is not None \
                else "Use on or off, or leave it empty to toggle"
            return [dict(kind="cmd", cmd="acrylic", arg=arg, path="", val=val, glyph="\uE790", sub=sub_,
                         title="Acrylic blur is " + ("on" if cur else "off"))]
        if word == "transparency":
            cur = int(self.cfg.get("transparency", 60))
            m2 = re.fullmatch(r"(\d{1,3})\s*%?", arg)
            val = int(m2.group(1)) if m2 and int(m2.group(1)) <= 100 else None
            sub_ = ("Press Enter to set it to %d%%" % val) if val is not None \
                else ("Type 0 (solid) to 100 (clear)  \u2022  now %d%%" % cur)
            return [dict(kind="cmd", cmd="transparency", arg=arg, path="", val=val, glyph="\uE706", sub=sub_,
                         title="Transparency")]
        if word == "pathdownload":
            path = clean_path(arg) if arg else ""
            current = clean_path(self.cfg.get("download_path") or os.path.join(os.path.expanduser("~"), "Downloads"))
            if not arg:
                sub_ = "Press Enter to choose a download folder  \u2022  current: " + current
            elif arg.lower() in CLEAR_WORDS:
                sub_ = "Press Enter to reset to the default Downloads folder"
            else:
                sub_ = "Press Enter to set the download folder to " + path
            return [dict(kind="cmd", cmd="pathdownload", arg=arg, path=path, glyph="\uE8B7",
                         title="Download folder", sub=sub_)]
        if word == "yt":
            # Normal mode is deliberately simple: >yt <URL> immediately downloads MP4.
            # -a opens the advanced menu, where format and quality/bitrate are chosen.
            advanced = bool(re.search(r"(?:^|\s)-a(?:\s|$)", arg, re.I))
            clean_arg = re.sub(r"(?:^|\s)-a(?=\s|$)", " ", arg, flags=re.I).strip()
            url_match = re.search(r"https?://[^\s]+", clean_arg, re.I)
            url = url_match.group(0).rstrip(".,;)]") if url_match else ""
            output_dir = clean_path(self.cfg.get("download_path") or os.path.join(os.path.expanduser("~"), "Downloads"))
            if url:
                sub_ = ("Press Enter for the advanced window  \u2022  thumbnail, format, quality, folder" if advanced else
                        "Press Enter to download MP4  \u2022  " + output_dir)
            else:
                sub_ = "Enter a video URL, e.g. >yt https://youtu.be/...  (add -a for advanced options)"
            return [dict(kind="cmd", cmd="yt", arg=arg, url=url, fmt="mp4", advanced=advanced,
                         path="", glyph="\uE896", title="Advanced YouTube download" if advanced else "YouTube download", sub=sub_)]
        if word == "log":
            folder_ = arg.strip().lower() in ("folder", "dir", "explorer", "show")
            return [dict(kind="cmd", cmd="log", mode="folder" if folder_ else "open", arg=arg, path=LOG, glyph="\uE8A5",
                         title="Show log in Explorer" if folder_ else "Open log file",
                         sub="Press Enter  \u2022  " + LOG)]
        if word == "ocr":
            a_, path_ = arg.strip(), ""
            if a_.lower() in ("clip", "clipboard"):
                mode_, sub_ = "clip", "Press Enter to read the picture on your clipboard"
            elif a_:
                path_ = clean_path(a_)
                mode_ = "file"
                sub_ = ("Press Enter to read the text in " + os.path.basename(path_)) if os.path.isfile(path_) else "File not found"
            else:
                mode_, sub_ = "snip", "Press Enter, then drag over the text on screen  \u2022  it is copied to the clipboard"
            return [dict(kind="cmd", cmd="ocr", arg=arg, path=path_, mode=mode_, glyph="\uE722", title="Screen OCR", sub=sub_)]
        if word == "setquote":
            a_ = arg.strip()
            if len(a_) > 1 and a_[0] == a_[-1] and a_[0] in "\"'":
                a_ = a_[1:-1].strip()
            if not a_:
                sub_ = 'Type the new quote  (\\n = new line, "reset" = default)  \u2022  now: ' + quote_text(self.cfg).replace("\n", " / ")
            elif a_.lower() in CLEAR_WORDS + ("default",):
                sub_ = "Press Enter to go back to  " + DEFAULT_QUOTE
            else:
                sub_ = "Press Enter to apply  \u2022  " + a_[:90]
            return [dict(kind="cmd", cmd="setquote", arg=a_, path="", title="Set quote", sub=sub_, glyph=COMMANDS["setquote"][1])]
        if word in COMMANDS:
            title, glyph, _desc = COMMANDS[word]
            crop = False
            if word in ("setmedia", "setcard"):
                arg, crop = split_crop(arg)
            path = clean_path(arg)
            if crop and not arg:
                path = clean_path(self.cfg.get(CMD_KEYS[word]) or "")
            what = CMD_KEYS[word] + (" image" if word == "setcard" else "")
            if crop and not arg and not os.path.isfile(path):
                sub_ = "Nothing is set yet  -  give a file path first"
            elif crop and os.path.isfile(path):
                sub_ = "Press Enter to choose the area  \u2022  " + os.path.basename(path)
            elif not arg:
                sub_ = 'Type or paste a file path  (or "none" to remove it)'
            elif arg.lower() in CLEAR_WORDS:
                sub_ = "Press Enter to remove the current " + what
            elif os.path.isfile(path):
                sub_ = "Press Enter to apply  \u2022  " + os.path.basename(path)
            else:
                sub_ = "File not found"
            return [dict(kind="cmd", cmd=word, arg=arg, path=path, crop=crop, title=title, sub=sub_, glyph=glyph)]
        items = [dict(kind="hint", title=HINT_TITLES.get(n, '>%s "path"' % n), sub=d, path="", glyph=g, fill=">%s " % n)
                 for n, (_t, g, d) in COMMANDS.items() if n.startswith(word)]
        return items or [dict(kind="info", title="Unknown command", sub="Try >setbackground, >cmd, or >config", path="",
                              glyph="\uE783")]

    def _glass_css(self):
        """Stylesheet shared by the floating glass option windows (YouTube download, cache details)."""
        t = self.t
        accent, tint, sub, on = t["accent"], t["tint"], t["sub"], t["on"]
        font_stack = ", ".join("'%s'" % f for f in [TEXT_FONT] + FALLBACKS)
        return f"""
            * {{ font-family: {font_stack}; font-size: 12px; color: white; }}
            QLabel {{ background: transparent; }}
            QLabel#eyebrow {{ color: {accent}; font-family: '{MONO_FONT}'; font-size: 10px; font-weight: 700; }}
            QLabel#heading {{ font-size: 19px; font-weight: 700; }}
            QLabel#sectionLabel {{ color: {sub}; font-family: '{MONO_FONT}'; font-size: 10px; font-weight: 600; }}
            QLabel#title {{ font-size: 15px; font-weight: 700; }}
            QLabel#meta {{ color: {sub}; font-size: 12px; }}
            QLabel#hint {{ color: {sub}; font-size: 11px; }}
            QLabel#chip {{ color: {accent}; background: rgba({tint}, 22); border: 1px solid rgba({tint}, 70);
                           border-radius: 8px; padding: 3px 9px; font-family: '{MONO_FONT}'; font-size: 10px; font-weight: 700; }}
            QComboBox, QLineEdit {{ background: rgba({tint}, 18); border: 1px solid rgba({tint}, 55);
                                   border-radius: 9px; padding: 9px 10px; min-height: 20px; }}
            QComboBox:hover, QLineEdit:hover {{ border-color: rgba({tint}, 105); }}
            QComboBox:focus, QLineEdit:focus {{ border: 1px solid {accent}; }}
            QComboBox::drop-down {{ border: none; width: 26px; }}
            QComboBox QAbstractItemView {{ background: #10131d; color: white; border: 1px solid rgba({tint}, 80);
                                           selection-background-color: {accent}; selection-color: {on}; outline: 0; }}
            QPushButton {{ background: rgba({tint}, 18); border: 1px solid rgba({tint}, 55);
                           border-radius: 9px; padding: 9px 14px; }}
            QPushButton:hover {{ background: rgba({tint}, 38); border-color: rgba({tint}, 110); }}
            QPushButton#primary {{ background: {accent}; color: {on}; border: 1px solid {accent}; font-weight: 700; }}
            QPushButton#primary:hover {{ background: rgba({tint}, 210); }}
            QPushButton#closeButton {{ padding: 2px; min-width: 30px; max-width: 30px; min-height: 28px; max-height: 28px;
                                       font-size: 17px; border: 1px solid rgba({tint}, 40); }}
            QPushButton#seg {{ padding: 9px 12px; }}
            QPushButton#seg:checked {{ background: {accent}; color: {on}; border: 1px solid {accent}; font-weight: 700; }}
            QPushButton#tab {{ padding: 5px 10px; font-size: 11px; border-radius: 8px; }}
            QPushButton#tab:checked {{ background: rgba({tint}, 70); border: 1px solid {accent}; font-weight: 700; }}
            QCheckBox {{ spacing: 9px; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid rgba({tint}, 120);
                                    background: rgba({tint}, 18); }}
            QCheckBox::indicator:checked {{ background: {accent}; border: 1px solid {accent}; }}
            QTableView {{ background: rgba({tint}, 10); border: 1px solid rgba({tint}, 45); border-radius: 10px; outline: 0;
                          selection-background-color: rgba({tint}, 62); }}
            QTableView::item {{ padding: 0 8px; border: none; }}
            QHeaderView {{ background: transparent; }}
            QHeaderView::section {{ background: transparent; color: {sub}; border: none; border-bottom: 1px solid rgba({tint}, 45);
                                    padding: 6px 8px; font-family: '{MONO_FONT}'; font-size: 10px; font-weight: 600; }}
            QScrollBar:vertical {{ background: transparent; width: 9px; margin: 3px 2px; }}
            QScrollBar::handle:vertical {{ background: rgba({tint}, 100); border-radius: 3px; min-height: 30px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """

    def _glass_dialog(self, w, h):
        """A themed floating glass window (same look as the launcher), sized w x h and not shown yet."""
        if self._shot is None and not self.isVisible():                   # launcher already hidden: take a snapshot for the glass
            try:
                self._grab_screen(QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen())
            except Exception:  # noqa: BLE001
                log("screen snapshot failed:\n" + traceback.format_exc())
        dlg = YtGlassDialog(self.t, self._opacity(), self._paint_backdrop_at if self._shot is not None else None)
        dlg.setModal(True)
        dlg.resize(w, h)
        dlg.setStyleSheet(self._glass_css())
        return dlg

    def _exec_glass(self, dlg):
        """Centre, show and run a glass window as a floating tool window.  True when it was accepted."""
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        area = screen.availableGeometry() if screen else self.geometry()
        dlg.move(area.center().x() - dlg.width() // 2, area.center().y() - dlg.height() // 2)
        self._dialog_open = True
        try:
            dlg.show()
            # Explicit Windows extended styles reinforce Qt.Tool's tool-window behavior, preventing taskbar grouping
            # and normal Komorebi tiling treatment.
            try:
                hwnd = int(dlg.winId())
                user32 = ctypes.windll.user32
                GWL_EXSTYLE, WS_EX_TOOLWINDOW, WS_EX_APPWINDOW = -20, 0x00000080, 0x00040000
                get_long = getattr(user32, "GetWindowLongPtrW", None)
                set_long = getattr(user32, "SetWindowLongPtrW", None)
                if get_long and set_long:
                    get_long.argtypes = [wintypes.HWND, ctypes.c_int]
                    get_long.restype = ctypes.c_ssize_t
                    set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
                    set_long.restype = ctypes.c_ssize_t
                else:
                    get_long, set_long = user32.GetWindowLongW, user32.SetWindowLongW
                    get_long.argtypes = [wintypes.HWND, ctypes.c_int]
                    get_long.restype = ctypes.c_long
                    set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
                    set_long.restype = ctypes.c_long
                exstyle = get_long(hwnd, GWL_EXSTYLE)
                set_long(hwnd, GWL_EXSTYLE, (exstyle | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)
            except Exception:  # noqa: BLE001
                pass
            dlg.raise_()
            dlg.activateWindow()
            return dlg.exec() == QDialog.DialogCode.Accepted
        finally:
            self._dialog_open = False
            if not self.isVisible():                                      # give the snapshot back if the launcher is hidden
                self._shot = self._glass = self._blur = self._glass_key = self._grain = self._shot_scr = None

    def _advanced_yt_options(self, url, initial_format="mp4"):
        """Floating glass window for >yt -a: the video's thumbnail and details, then format, quality, folder and extras.
        Returns a dict (fmt, quality, output_dir, embed, single) or None when cancelled."""
        if "music.youtube.com" in url.lower():
            initial_format = "mp3"
        dlg = self._glass_dialog(620, 556)
        dlg.setWindowTitle("Synapse \u00b7 YouTube download")
        t = self.t

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        heading_col = QVBoxLayout()
        heading_col.setSpacing(3)
        eyebrow = QLabel("SYNAPSE  /  MEDIA TOOL", dlg)
        eyebrow.setObjectName("eyebrow")
        heading = QLabel("Download options", dlg)
        heading.setObjectName("heading")
        heading_col.addWidget(eyebrow)
        heading_col.addWidget(heading)
        header.addLayout(heading_col, 1)
        close_btn = QPushButton("\u00d7", dlg)
        close_btn.setObjectName("closeButton")
        close_btn.setToolTip("Close advanced options")
        close_btn.clicked.connect(dlg.reject)
        header.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        # ---- preview: thumbnail + what yt-dlp says about the link
        preview = QHBoxLayout()
        preview.setSpacing(16)
        thumb = ThumbCard(t, dlg)
        preview.addWidget(thumb, 0, Qt.AlignmentFlag.AlignTop)
        info_col = QVBoxLayout()
        info_col.setSpacing(6)
        chip_row = QHBoxLayout()
        kind_chip = QLabel("LOADING", dlg)
        kind_chip.setObjectName("chip")
        chip_row.addWidget(kind_chip)
        chip_row.addStretch(1)
        title_lbl = QLabel("Reading video details...", dlg)
        title_lbl.setObjectName("title")
        title_lbl.setWordWrap(True)
        title_lbl.setMaximumHeight(60)
        meta_lbl = QLabel("", dlg)
        meta_lbl.setObjectName("meta")
        meta_lbl.setWordWrap(True)
        url_lbl = QLabel(QFontMetrics(dlg.font()).elidedText(url, Qt.TextElideMode.ElideMiddle, 330), dlg)
        url_lbl.setObjectName("hint")
        url_lbl.setToolTip(url)
        info_col.addLayout(chip_row)
        info_col.addWidget(title_lbl)
        info_col.addWidget(meta_lbl)
        info_col.addStretch(1)
        info_col.addWidget(url_lbl)
        preview.addLayout(info_col, 1)
        layout.addLayout(preview)

        # ---- format (segmented) + quality
        controls = QHBoxLayout()
        controls.setSpacing(12)
        format_col = QVBoxLayout()
        format_col.setSpacing(6)
        format_label = QLabel("FORMAT", dlg)
        format_label.setObjectName("sectionLabel")
        seg_row = QHBoxLayout()
        seg_row.setSpacing(6)
        btn_mp4 = QPushButton("MP4  \u00b7  Video", dlg)
        btn_mp3 = QPushButton("MP3  \u00b7  Audio", dlg)
        seg_group = QButtonGroup(dlg)
        for b in (btn_mp4, btn_mp3):
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            seg_group.addButton(b)
            seg_row.addWidget(b, 1)
        (btn_mp4 if initial_format == "mp4" else btn_mp3).setChecked(True)
        format_col.addWidget(format_label)
        format_col.addLayout(seg_row)
        controls.addLayout(format_col, 3)

        quality_col = QVBoxLayout()
        quality_col.setSpacing(6)
        quality_label = QLabel("QUALITY / BITRATE", dlg)
        quality_label.setObjectName("sectionLabel")
        quality_box = QComboBox(dlg)
        quality_col.addWidget(quality_label)
        quality_col.addWidget(quality_box)
        controls.addLayout(quality_col, 2)
        layout.addLayout(controls)

        # ---- folder
        path_label = QLabel("DOWNLOAD FOLDER", dlg)
        path_label.setObjectName("sectionLabel")
        layout.addWidget(path_label)
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_edit = QLineEdit(clean_path(self.cfg.get("download_path") or os.path.join(os.path.expanduser("~"), "Downloads")), dlg)
        path_edit.setPlaceholderText("Choose where downloads are saved")
        browse = QPushButton("Browse...", dlg)
        path_row.addWidget(path_edit, 1)
        path_row.addWidget(browse)
        layout.addLayout(path_row)

        # ---- extras
        embed_cb = QCheckBox("Embed the thumbnail and tags in the file  (cover art for music)", dlg)
        embed_cb.setChecked(initial_format == "mp3")
        embed_touched = [False]
        embed_cb.clicked.connect(lambda *_: embed_touched.__setitem__(0, True))
        layout.addWidget(embed_cb)
        has_list = bool(re.search(r"[?&]list=", url)) and bool(re.search(r"[?&]v=|youtu\.be/", url))
        single_cb = QCheckBox("Single video only  (skip the rest of the playlist in this link)", dlg)
        single_cb.setChecked(has_list)
        single_cb.setVisible(has_list)
        layout.addWidget(single_cb)
        layout.addStretch(1)

        # ---- footer
        footer = QHBoxLayout()
        footer.setSpacing(8)
        est_lbl = QLabel("", dlg)
        est_lbl.setObjectName("hint")
        footer.addWidget(est_lbl, 1)
        cancel = QPushButton("Cancel", dlg)
        start = QPushButton("Start download", dlg)
        start.setObjectName("primary")
        cancel.clicked.connect(dlg.reject)
        start.clicked.connect(dlg.accept)
        footer.addWidget(cancel)
        footer.addWidget(start)
        layout.addLayout(footer)

        quality_sets = {
            "mp4": [("Best available", "best"), ("2160p \u00b7 4K maximum", "2160"),
                    ("1440p \u00b7 2K maximum", "1440"), ("1080p maximum", "1080"),
                    ("720p maximum", "720"), ("480p maximum", "480"), ("360p maximum", "360")],
            "mp3": [("320 kbps", "320K"), ("256 kbps", "256K"), ("192 kbps", "192K"),
                    ("128 kbps", "128K"), ("96 kbps", "96K")],
        }
        meta_state = {"info": None}

        def current_fmt():
            return "mp3" if btn_mp3.isChecked() else "mp4"

        def update_estimate(*_):
            info = meta_state["info"]
            est_lbl.setText("")
            if not info:
                return
            if info.get("is_playlist"):
                n = info.get("count") or 0
                est_lbl.setText("Playlist  \u2022  %s will be downloaded" % (("%d videos" % n) if n else "every video"))
                return
            size = 0
            q = quality_box.currentData()
            try:
                if current_fmt() == "mp3":
                    size = (info.get("duration") or 0) * int(str(q or "192K").rstrip("Kk")) * 125
                else:
                    vid = info.get("vid") or {}
                    if vid:
                        cap = max(vid) if q == "best" else int(q)
                        fit = [h for h in vid if h <= cap]
                        h = max(fit) if fit else min(vid)
                        if vid[h]:
                            size = vid[h] + (info.get("aud") or 0)
            except (TypeError, ValueError):
                size = 0
            if size:
                est_lbl.setText("Estimated size  \u2248  " + fmt_bytes(size))

        def refill_quality(*_):
            fmt = current_fmt()
            selected = quality_box.currentData()
            max_h = (meta_state["info"] or {}).get("max_h") or 0
            quality_box.blockSignals(True)
            quality_box.clear()
            for label, value in quality_sets[fmt]:
                if fmt == "mp4" and value != "best" and max_h and int(value) > max_h:
                    continue                                              # not offered by this video
                quality_box.addItem(label, value)
            preferred = "best" if fmt == "mp4" else "192K"
            ix = quality_box.findData(selected if quality_box.findData(selected) >= 0 else preferred)
            quality_box.setCurrentIndex(ix if ix >= 0 else 0)
            quality_box.blockSignals(False)
            update_estimate()

        def on_format_changed(*_):
            if not embed_touched[0]:
                embed_cb.setChecked(current_fmt() == "mp3")
            refill_quality()

        btn_mp4.clicked.connect(on_format_changed)
        btn_mp3.clicked.connect(on_format_changed)
        quality_box.currentIndexChanged.connect(update_estimate)
        refill_quality()

        def pick_folder():
            start_dir = clean_path(path_edit.text()) or os.path.expanduser("~")
            was_open = self._dialog_open
            self._dialog_open = True
            try:
                chosen = QFileDialog.getExistingDirectory(dlg, "Choose download folder", start_dir)
            finally:
                self._dialog_open = was_open
            if chosen:
                path_edit.setText(chosen)

        browse.clicked.connect(pick_folder)

        # ---- details + thumbnail arrive from worker threads
        quick_seen = [False]

        def on_info(meta):
            meta_state["info"] = meta
            if not meta:
                kind_chip.setText("VIDEO" if quick_seen[0] else "NO DETAILS")
                if not quick_seen[0]:
                    title_lbl.setText("Couldn't read the video details")
                meta_lbl.setText("Couldn't read the quality list, so it downloads at the best quality.  (Why: type >log)")
                return
            kind_chip.setText("PLAYLIST" if meta["is_playlist"] else ("MUSIC" if meta["music"] else "VIDEO"))
            title_lbl.setText(meta["title"] or "Untitled")
            if meta["is_playlist"]:
                bits = [meta["uploader"], ("%d videos" % meta["count"]) if meta["count"] else ""]
            else:
                bits = [meta["uploader"], fmt_duration(meta["duration"]), ("up to %dp" % meta["max_h"]) if meta["max_h"] else ""]
                thumb.set_badge(fmt_duration(meta["duration"]))
            meta_lbl.setText("  \u2022  ".join(b for b in bits if b))
            refill_quality()

        def on_thumb(img):
            if img is not None and not img.isNull():
                thumb.set_image(QPixmap.fromImage(img))
            elif thumb.state != "ready":
                thumb.set_none()

        def on_quick(d):
            if not d or meta_state["info"] is not None:
                return
            quick_seen[0] = True
            kind_chip.setText("VIDEO")
            title_lbl.setText(d.get("title") or "Untitled")
            meta_lbl.setText("  \u2022  ".join(b for b in (d.get("author", ""), "reading the quality list...") if b))

        bridge = MediaBridge(dlg)
        bridge.info.connect(on_info)
        bridge.thumb.connect(on_thumb)
        bridge.quick.connect(on_quick)
        alive, got_thumb = [True], [False]
        dlg.finished.connect(lambda *_: alive.__setitem__(0, False))
        yid = re.search(r"(?:[?&]v=|youtu\.be/|/shorts/|/embed/|/live/)([\w-]{11})", url)

        def quick_thumb():                       # a YouTube link needs no yt-dlp for the picture, so it shows up at once
            img = fetch_image("https://i.ytimg.com/vi/%s/hqdefault.jpg" % yid.group(1))
            if img is not None and alive[0]:
                got_thumb[0] = True
                try:
                    bridge.thumb.emit(img)
                except RuntimeError:
                    pass

        def load_info():
            meta = fetch_media_info(url)
            if not alive[0]:
                return
            try:
                bridge.info.emit(meta)
            except RuntimeError:
                return
            if got_thumb[0]:
                return
            for u in (meta or {}).get("thumbs", []):
                img = fetch_image(u)
                if img is not None and alive[0]:
                    try:
                        bridge.thumb.emit(img)
                    except RuntimeError:
                        pass
                    return
            if alive[0]:
                try:
                    bridge.thumb.emit(None)
                except RuntimeError:
                    pass

        def quick_details():
            d = fetch_oembed(url)
            if d and alive[0]:
                try:
                    bridge.quick.emit(d)
                except RuntimeError:
                    pass

        if yid:
            threading.Thread(target=quick_thumb, name="SynapseYtThumb", daemon=True).start()
            threading.Thread(target=quick_details, name="SynapseYtQuick", daemon=True).start()
        threading.Thread(target=load_info, name="SynapseYtInfo", daemon=True).start()

        accepted = self._exec_glass(dlg)
        alive[0] = False
        if not accepted:
            return None
        output_dir = clean_path(path_edit.text())
        if not output_dir:
            return None
        return dict(fmt=current_fmt(), quality=str(quality_box.currentData()), output_dir=output_dir,
                    embed=embed_cb.isChecked(), single=single_cb.isChecked())

    def _on_yt_event(self, status, percent, state):
        """Receive downloader updates on the GUI thread and redraw Synapse's footer."""
        self._yt_status = str(status or "")
        try:
            self._yt_progress = float(percent)
        except (TypeError, ValueError):
            self._yt_progress = -1.0
        self._yt_state = state
        self._yt_clear_timer.stop()
        if state in ("done", "error"):
            self._yt_clear_timer.start(12000 if state == "error" else 8000)
        self._yt_anim_sync()
        self.update()

    def _clear_yt_status(self):
        self._yt_status = ""
        self._yt_progress = -1.0
        self._yt_state, self._yt_d, self._yt_shown = "", {}, 0.0
        self._yt_thumb_url, self._yt_thumb_small = "", None
        self._yt_anim.stop()
        self.update()

    def _yt_region(self):
        return QRect(LEFT_X - 2, FOOT_Y - 48, LEFT_W + 4, max(1, self.height() - (FOOT_Y - 48)))

    def _yt_anim_sync(self):
        """Run the progress-bar animation only while a download is running and the launcher is on screen."""
        if self._yt_state == "running" and self.isVisible():
            if not self._yt_anim.isActive():
                self._yt_anim.start()
        else:
            self._yt_anim.stop()

    def _tick_yt(self):
        if self._yt_state != "running" or not self.isVisible():
            self._yt_anim.stop()
            return
        target = max(0.0, self._yt_progress)
        gap = target - self._yt_shown
        self._yt_shown = target if (gap < 0 or gap < 0.05) else self._yt_shown + gap * 0.18
        self.update(self._yt_region())

    def _on_yt_detail(self, d):
        """Title / thumbnail / speed text from the download thread."""
        if not isinstance(d, dict):
            return
        self._yt_d.update({k: v for k, v in d.items() if v not in (None, "")})
        url = d.get("thumb")
        if url and url != self._yt_thumb_url:
            self._yt_thumb_url = url

            def work(u=url):
                for cand in thumb_urls_for(u):
                    img = fetch_image(cand)
                    if img is not None:
                        try:
                            self.yt_thumb.emit(img)
                        except RuntimeError:
                            pass
                        return
            threading.Thread(target=work, name="SynapseYtFooterThumb", daemon=True).start()
        self.update(self._yt_region())

    def _on_yt_thumb(self, img):
        if img is None or img.isNull():
            return
        dpr = max(1.0, self.devicePixelRatioF())
        w, h = int(52 * dpr), int(29 * dpr)
        pm = QPixmap.fromImage(img).scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        pm = pm.copy(QRect(max(0, (pm.width() - w) // 2), max(0, (pm.height() - h) // 2), w, h))
        pm.setDevicePixelRatio(dpr)
        self._yt_thumb_small = pm
        self.update(self._yt_region())

    def _paint_yt_footer(self, p, rect, accent, white):
        """Footer line while a download runs: thumbnail + title on the left, stream / percent / speed / ETA on the right."""
        d = self._yt_d
        running = self._yt_state == "running"
        AL = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        AR = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        x = rect.left()
        th = self._yt_thumb_small
        if th is not None and not th.isNull():
            tr = QRectF(x, rect.center().y() - 14.5, 52, 29)
            clip = QPainterPath()
            clip.addRoundedRect(tr, 5, 5)
            p.save()
            p.setClipPath(clip)
            p.drawPixmap(tr.topLeft(), th)
            p.restore()
            x += 62
        p.setFont(_font(10, mono=True))
        right = d.get("right") or ""
        fm = QFontMetrics(p.font())
        rw = min(fm.horizontalAdvance(right) + 2, int(rect.width() * 0.62))
        p.setPen(accent if running else PROGRESS_DONE)
        p.drawText(QRectF(rect.right() - rw, rect.top(), rw, rect.height()), AR, fm.elidedText(right, Qt.TextElideMode.ElideMiddle, rw))
        p.setPen(white)
        p.setFont(_font(11, QFont.Weight.DemiBold))
        tw = max(40, int(rect.right() - rw - 14 - x))
        title = QFontMetrics(p.font()).elidedText(d.get("title", ""), Qt.TextElideMode.ElideRight, tw)
        p.drawText(QRectF(x, rect.top(), tw, rect.height()), AL, title)

    def _start_yt_download(self, url, fmt, quality="best", output_dir=None, embed=False, single=False):
        """Run yt-dlp invisibly and stream its progress into the launcher UI."""
        if not url or not re.match(r"^https?://", url, re.I):
            self._count = "Enter a valid http(s) video URL"
            self.update()
            return
        output_dir = clean_path(output_dir or self.cfg.get("download_path") or os.path.join(os.path.expanduser("~"), "Downloads"))
        if not output_dir:
            self._count = "Set a download folder with >pathdownload"
            self.update()
            return
        try:
            os.makedirs(output_dir, exist_ok=True)
            if not os.path.isdir(output_dir):
                raise OSError("The selected path is not a folder")
        except OSError as exc:
            self._count = "Download folder error: " + str(exc)
            self.update()
            return

        command = ytdlp_command()
        if not command:
            self._yt_status = "yt-dlp isn't installed   \u2022   run: py -m pip install -U yt-dlp"
            self._yt_progress = -1.0
            self._yt_state = "error"
            self.update()
            self._yt_clear_timer.start(12000)
            return

        if fmt == "mp3":
            command += ["-x", "--audio-format", "mp3", "--audio-quality", str(quality or "192K")]
        else:
            if quality and quality != "best":
                command += ["-f", "bv*[height<=" + str(int(quality)) + "]+ba/b[height<=" + str(int(quality)) + "]"]
            else:
                command += ["-f", "bv*+ba/b"]
            command += ["--merge-output-format", "mp4", "--remux-video", "mp4"]

        if single:
            command += ["--no-playlist"]
        if embed:
            command += ["--embed-thumbnail", "--embed-metadata", "--convert-thumbnails", "jpg"]

        # A tagged progress line is easy to parse and is emitted by yt-dlp for each update.
        # fields: percent | speed | eta | downloaded | total | estimate | vcodec | acodec | file | thumbnail | title (last, may hold "|")
        progress_template = (
            "download:SYNAPSE_PROGRESS|%(progress._percent_str)s|%(progress._speed_str)s|%(progress._eta_str)s|"
            "%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|"
            "%(info.vcodec)s|%(info.acodec)s|%(progress.filename)s|%(info.thumbnail)s|%(info.title)s"
        )
        command += [
            "--newline", "--no-colors", "--progress-template", progress_template,
            "-o", os.path.join(output_dir, "%(title)s.%(ext)s"), url,
        ]

        try:
            # CREATE_NO_WINDOW prevents a console flash/window; stdout and stderr are
            # captured so every progress event can be rendered in Synapse instead.
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            process = subprocess.Popen(
                command,
                cwd=output_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creation_flags,
            )
        except (OSError, ValueError) as exc:
            self._yt_status = "Couldn't start yt-dlp: " + str(exc)
            self._yt_progress = -1.0
            self.update()
            self._yt_clear_timer.start(12000)
            return

        self._yt_clear_timer.stop()
        self._yt_status = "Starting %s download •  %s" % (fmt.upper(), os.path.basename(url.rstrip("/"))[:72])
        self._yt_progress = 0.0
        self._yt_state, self._yt_d, self._yt_shown = "running", {}, 0.0
        self._yt_thumb_url, self._yt_thumb_small = "", None
        self._yt_anim_sync()
        self.cfg["download_path"] = output_dir
        save_settings(self.cfg)
        self.edit.clear()
        self.update()

        def monitor_download():
            error_line = ""
            first_total = 1 if fmt == "mp3" else 2          # a video download normally fetches video + audio separately
            total_streams = first_total
            done_w, cur_name, cur_w, stream_no, cur_kind, seen_title = 0.0, None, 1.0, 0, "", ""

            def num(text):
                try:
                    return float(text)
                except (TypeError, ValueError):
                    return None

            def usable(text):
                return bool(text) and text not in ("NA", "N/A", "None") and "nknown" not in text

            def stage(text):
                self.yt_detail.emit(dict(right=text))
                self.yt_event.emit(text, -1.0, "running")

            try:
                if process.stdout is not None:
                    for raw_line in process.stdout:
                        line = raw_line.strip()
                        if not line:
                            continue
                        if line.startswith("SYNAPSE_PROGRESS|"):
                            f = line.split("|", 11)
                            if len(f) < 12:
                                continue
                            pct = num(f[1].replace("%", "").strip())
                            speed, eta = f[2].strip(), f[3].strip()
                            vcodec, acodec, fname = f[7].strip(), f[8].strip(), f[9].strip()
                            thumb, title = f[10].strip(), f[11].strip()
                            if usable(title) and title != seen_title:
                                if seen_title:                      # next video of a playlist: start the stream counting over
                                    done_w, cur_name, stream_no, total_streams = 0.0, None, 0, first_total
                                seen_title = title
                            if fname != cur_name:                   # a new stream (video part, then audio part)
                                if cur_name is not None:
                                    done_w += cur_w
                                cur_name = fname
                                stream_no += 1
                                cur_kind = "Audio" if vcodec == "none" else ("Video" if acodec == "none" else "Video + audio")
                                if fmt == "mp3" or cur_kind == "Video + audio":
                                    total_streams = 1
                                cur_w = 1.0 if total_streams == 1 else (0.9 if cur_kind == "Video" else 0.1)
                            overall = None
                            if pct is not None:
                                overall = min(99.9, (done_w + cur_w * max(0.0, min(100.0, pct)) / 100.0) * 100.0)
                            label = cur_kind if total_streams == 1 else "%s %d/%d" % (cur_kind, min(stream_no, total_streams), total_streams)
                            parts = [label]
                            if overall is not None:
                                parts.append("%.1f%%" % overall)
                            if usable(speed):
                                parts.append(speed)
                            if usable(eta):
                                parts.append("ETA " + eta)
                            self.yt_detail.emit(dict(title=title if usable(title) else "",
                                                     thumb=thumb if thumb.startswith("http") else "",
                                                     right="  \u00b7  ".join(parts)))
                            self.yt_event.emit(("Downloading %.1f%%" % overall) if overall is not None else "Downloading",
                                               overall if overall is not None else -1.0, "running")
                        elif line.startswith("ERROR:"):
                            error_line = line[6:].strip()
                        elif "[ExtractAudio]" in line:
                            stage("Converting to MP3...")
                        elif "[Merger]" in line or "Merging formats" in line:
                            stage("Merging video + audio...")
                        elif "[VideoRemuxer]" in line or "Remuxing" in line:
                            stage("Finalizing video...")
                        elif "[EmbedThumbnail]" in line or "[ThumbnailsConvertor]" in line:
                            stage("Embedding thumbnail...")
                        elif "[Metadata]" in line:
                            stage("Writing tags...")
                return_code = process.wait()
                if return_code == 0:
                    self.yt_detail.emit(dict(right="Saved to " + output_dir))
                    self.yt_event.emit("Download complete \u2022 saved to " + output_dir, 100.0, "done")
                else:
                    message = "Download failed"
                    if error_line:
                        message += ": " + error_line
                    else:
                        message += " (yt-dlp exit code %s)" % return_code
                    self.yt_event.emit(message, -1.0, "error")
            except Exception as exc:  # noqa: BLE001
                log("yt-dlp progress monitor failed:\n" + traceback.format_exc())
                self.yt_event.emit("Download monitor error: " + str(exc), -1.0, "error")
            finally:
                try:
                    if process.stdout:
                        process.stdout.close()
                except OSError:
                    pass

        threading.Thread(target=monitor_download, name="SynapseYtDlpMonitor", daemon=True).start()

    # ---- >log
    def _open_log(self, it):
        if not os.path.isfile(LOG):
            self._count = "No log yet  \u2022  nothing has been written"
        elif it.get("mode") == "folder":
            try:
                subprocess.Popen(["explorer.exe", "/select,", LOG])
                self.edit.clear()
                self._count = "Showing the log in Explorer"
            except OSError:
                self._count = "Couldn't open Explorer"
        else:
            editor = clean_path(self.cfg.get("editor") or "notepad.exe")
            try:
                subprocess.Popen([editor, LOG])
                self.edit.clear()
                self._count = "Opened the log"
            except (OSError, ValueError):
                self._count = "Couldn't launch editor; use >editor to choose one"
        self.update()

    # ---- >ocr: read text from a screen area, the clipboard picture or an image file
    def _start_ocr(self, it):
        if getattr(self, "_ocr_busy", False):
            self._count = "OCR is already running"
            self.update()
            return
        mode = it.get("mode", "snip")
        if mode == "file":
            path = it.get("path", "")
            if not os.path.isfile(path):
                self._count = "File not found"
                self.update()
                return
            self._ocr_run(path, False)
        elif mode == "clip":
            img = QApplication.clipboard().image()
            if img.isNull():
                self._count = "There is no picture on the clipboard"
                self.update()
                return
            self._ocr_run_image(img)
        else:
            self._ocr_scr = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
            self.edit.clear()
            self.close_launcher()                           # get out of the way so it isn't in the picture
            QTimer.singleShot(320, self._ocr_grab)

    def _ocr_grab(self):
        try:
            full = self._ocr_scr.grabWindow(0)
            full.setDevicePixelRatio(1.0)                   # real pixels; OcrSnip maps them to the logical screen itself
            snip = OcrSnip(full, self._ocr_scr, self.t["accent"])
            snip.done.connect(self._ocr_picked)
            self._ocr_snip = snip
            snip.show()
            snip.raise_()
            snip.activateWindow()
            snip.setFocus()
        except Exception:  # noqa: BLE001
            log("ocr screen grab failed:\n" + traceback.format_exc())
            self._on_ocr_done("", "Couldn't capture the screen")

    def _ocr_picked(self, img):
        self._ocr_snip = None
        if img is not None and not img.isNull():
            self._ocr_run_image(img)

    def _ocr_run_image(self, img):
        if img.height() < 400 and img.width() * 2 <= 8000:    # small text reads much better when enlarged
            img = img.scaled(img.width() * 2, img.height() * 2, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        path = os.path.join(tempfile.gettempdir(), "synapse_ocr_%d.png" % os.getpid())
        if not img.save(path, "PNG"):
            self._on_ocr_done("", "Couldn't save the picture for reading")
            return
        self._ocr_run(path, True)

    def _ocr_run(self, path, cleanup):
        self._ocr_busy = True
        if self.isVisible():
            self._count = "Reading text..."
            self.update()

        def work():
            text, err = "", ""
            try:
                text = run_ocr(path)
            except Exception as exc:  # noqa: BLE001
                log("ocr failed:\n" + traceback.format_exc())
                err = str(exc) or type(exc).__name__
            finally:
                if cleanup:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            try:
                self.ocr_done.emit(text, err)
            except RuntimeError:
                pass
        threading.Thread(target=work, name="SynapseOcr", daemon=True).start()

    def _on_ocr_done(self, text, err):
        self._ocr_busy = False
        text = (text or "").strip()
        if err:
            ok, title, sub = False, "OCR failed", err
        elif not text:
            ok, title, sub = False, "No text found", "Try a bigger area or a sharper picture"
        else:
            QApplication.clipboard().setText(text)
            ok, title, sub = True, "Copied %d characters" % len(text), text.splitlines()[0][:110]
        if not self.isVisible() or getattr(self, "_closing", False):
            self.open_launcher()                            # bring the launcher back to show the result
        QTimer.singleShot(120, lambda: self._ocr_show(ok, title, sub))

    def _ocr_show(self, ok, title, sub):
        self._count = title
        self.list.empty_text = ""
        self.list.set_items([dict(kind="info", path="", glyph=self.G_OK if ok else self.G_WARN, title=title, sub=sub)])
        self.update()

    def _run_cmd(self, it):
        cmd = it["cmd"]
        if cmd == "add":
            self._run_add(it)
            return
        if cmd == "vapor":
            self._run_vapor(it)
            return
        if cmd == "pathdownload":
            arg = (it.get("arg") or "").strip()
            if arg and arg.lower() in CLEAR_WORDS:
                chosen = os.path.join(os.path.expanduser("~"), "Downloads")
            elif arg:
                chosen = clean_path(arg)
            else:
                start = clean_path(self.cfg.get("download_path") or os.path.join(os.path.expanduser("~"), "Downloads"))
                self._dialog_open = True
                try:
                    chosen = QFileDialog.getExistingDirectory(self, "Choose download folder", start)
                finally:
                    self._dialog_open = False
            if chosen:
                try:
                    os.makedirs(chosen, exist_ok=True)
                    if not os.path.isdir(chosen):
                        raise OSError("The selected path is not a folder")
                    self.cfg["download_path"] = chosen
                    save_settings(self.cfg)
                    self._count = "Download folder set to " + chosen
                    self.edit.clear()
                except OSError as exc:
                    self._count = "Couldn't set download folder: " + str(exc)
            else:
                self._count = "Download folder unchanged"
            self.update()
            return
        if cmd == "yt":
            url = it.get("url", "")
            if not url:
                self._count = "Usage: >yt <video URL> [-a]"
                self.update()
                return
            # Keep the one-line command fast and predictable: MP4 at best available quality.
            fmt = "mp4"
            quality = "best"
            extras = {}
            output_dir = clean_path(self.cfg.get("download_path") or os.path.join(os.path.expanduser("~"), "Downloads"))
            if it.get("advanced"):
                options = self._advanced_yt_options(url, "mp4")
                if not options:
                    self._count = "Download cancelled"
                    self.update()
                    return
                fmt, quality, output_dir = options["fmt"], options["quality"], options["output_dir"]
                extras = dict(embed=options["embed"], single=options["single"])
            self._start_yt_download(url, fmt, quality, output_dir, **extras)
            return
        if cmd == "log":
            self._open_log(it)
            return
        if cmd == "ocr":
            self._start_ocr(it)
            return
        if cmd == "exit":
            self.quit_app()
            return
        if cmd == "cmd":
            command = (it.get("arg") or "").strip()
            try:
                if command:
                    subprocess.Popen([os.environ.get("COMSPEC", "cmd.exe"), "/k", command],
                                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
                else:
                    subprocess.Popen([os.environ.get("COMSPEC", "cmd.exe")],
                                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
                self.edit.clear()
                self._count = "Opened Command Prompt"
            except (OSError, ValueError) as exc:
                self._count = "Couldn't open Command Prompt: " + str(exc)
            self.update()
            return
        if cmd == "config":
            cfg_path = SETTINGS_FILE
            if not os.path.exists(cfg_path):
                save_settings(self.cfg)
            editor = clean_path(self.cfg.get("editor") or "notepad.exe")
            try:
                subprocess.Popen([editor, cfg_path])
                self.edit.clear()
                self._count = "Opened launcher config"
            except (OSError, ValueError):
                self._count = "Couldn't launch editor; use >editor to choose one"
            self.update()
            return
        if cmd == "editor":
            chosen = it.get("val")
            if not chosen:
                chosen, _ = QFileDialog.getOpenFileName(self, "Choose native file editor", "", "Applications (*.exe);;All files (*)")
                chosen = clean_path(chosen) if chosen else ""
            if chosen and os.path.isfile(chosen):
                self.cfg["editor"] = chosen
                save_settings(self.cfg)
                self._count = "File editor set to " + os.path.basename(chosen)
                self.edit.clear()
            else:
                self._count = "Editor selection cancelled or file not found"
            self.update()
            return
        if cmd == "scan":
            self._scan_report = True
            self.edit.clear()
            self._count = "Scanning apps..."
            self._scan()
            self.update()
            return
        if cmd == "reload":
            # Replace the running Python process with a fresh instance of this script.
            # Delaying briefly lets the current command handler return cleanly; omit
            # --hidden so the restarted launcher opens visibly even if preloaded hidden.
            save_settings(self.cfg)
            if FROZEN:
                QTimer.singleShot(150, self._restart_frozen)
            else:
                script_path = os.path.abspath(__file__)
                QTimer.singleShot(150, lambda: os.execl(sys.executable, sys.executable, script_path))
            self._count = "Restarting Synapse..."
            self.update()
            return
        if cmd == "clearcache":
            self._clear_cache(advanced=bool(it.get("advanced")))
            return
        if cmd == "cachedetails":
            self._open_cache_details()
            return
        if cmd == "animations":
            if it.get("val") is None:
                self._count = it["sub"]
            else:
                self.cfg["animations"] = it["val"]
                save_settings(self.cfg)
                self.edit.clear()
                self._count = "Animations " + ("on" if it["val"] else "off")
            self.update()
            return
        if cmd == "customizations":
            if it.get("val") is None:
                self._count = it["sub"]
                self.update()
            else:
                self._set_customizations(it["val"])
            return
        if cmd == "lcbar":
            if it.get("val") is None:
                self._count = it["sub"]
                self.update()
            else:
                self._set_lcbar(it["val"])
            return
        if cmd == "taskbar":
            if it.get("val") is None:
                self._count = it["sub"]
            elif self._set_taskbar(not it["val"]):
                self.edit.clear()
                self._count = "Taskbar " + ("on" if it["val"] else "off")
            else:
                self._count = "Couldn't change the taskbar  (see >log)"
            self.update()
            return
        if cmd == "setquote":
            txt = (it.get("arg") or "").strip()
            if not txt:
                self._count = it["sub"]
                self.update()
                return
            if txt.lower() in CLEAR_WORDS + ("default",):
                self.cfg.pop("quote_text", None)
                msg = "Quote reset"
            else:
                self.cfg["quote_text"] = txt[:200]
                msg = "Quote updated"
            save_settings(self.cfg)
            self._build_cache()
            self.edit.clear()
            self._count = msg
            self.update()
            return
        if cmd == "zen":
            if it.get("val") is None:
                self._count = it["sub"]
                self.update()
                return
            self.edit.clear()
            self._set_zen(it["val"])
            self._count = "Zen mode " + ("on" if it["val"] else "off")
            self.update()
            return
        if cmd in ("acrylic", "transparency"):
            val = it.get("val")
            if val is None:
                msg = it["sub"]
            else:
                if cmd == "acrylic":
                    self.cfg["acrylic"], msg = val, "Acrylic " + ("on" if val else "off")
                else:
                    self.cfg["transparency"], msg = val, "Transparency %d%%" % val
                save_settings(self.cfg)
                self._build_cache()
                self._apply_glass()
                self.edit.clear()
            self._count = msg
            self.update()
            return
        key = CMD_KEYS[cmd]
        arg, path, crop, ok = it["arg"], it["path"], it.get("crop", False), False
        if crop and not arg and key in ("media", "quote") and os.path.isfile(path):
            self._begin_crop(key, path)                    # re-crop what is already set
            return
        if not arg:
            msg = "Add a file path after the command"
        elif arg.lower() in CLEAR_WORDS:
            if key in ("background", "quote"):
                if key == "background":
                    self.src = QPixmap()
                else:
                    self.qsrc = QPixmap()
                self._covs.clear()
                self._build_cache()
            else:
                self._clear_media()
            self.cfg[key], ok, msg = "", True, "Removed " + key
            self.cfg.pop(key + "_crop", None)
        elif not os.path.isfile(path):
            msg = "File not found"
        elif key == "background":
            pm = QPixmap(path)
            if pm.isNull():
                msg = "Couldn't read that image"
            else:
                self.src = shrink(pm, W, H)
                self._covs.clear()
                self._build_cache()
                self.cfg[key], ok, msg = path, True, "Background updated"
        elif key == "quote":
            self.cfg["quote_crop"] = None
            if self._load_quote(path):
                self.cfg[key], ok, msg = path, True, "Quote image updated"
            else:
                msg = "Couldn't read that image"
        else:
            self.cfg["media_crop"] = None
            if self._load_media(path):
                self.cfg[key], ok, msg = path, True, "Media updated"
            else:
                msg = "Unsupported or unreadable media"
        if ok:
            save_settings(self.cfg)
            self.edit.clear()
            if crop and key in ("media", "quote") and arg.lower() not in CLEAR_WORDS:
                self._begin_crop(key, path)
                return
        self._count = msg
        self.update()

    def _run_add(self, it):
        custom = list(self.cfg.get("custom_apps") or [])
        mode = it.get("mode")
        if mode == "remove":
            hit = it.get("val")
            if not hit:
                self._count = it["sub"]
            else:
                custom = [c for c in custom if c is not hit and c.get("title") != hit.get("title")]
                self.cfg["custom_apps"] = custom
                save_settings(self.cfg)
                self.edit.clear()
                self._count = "Removed " + hit["title"]
                self._scan()
            self.update()
            return
        path, name = it.get("path", ""), it.get("val")
        if mode == "browse":
            self._dialog_open = True
            try:
                path, _f = QFileDialog.getOpenFileName(self, "Choose an app to add", os.path.expanduser("~"), "Programs and shortcuts (*.exe *.lnk *.bat *.cmd *.url);;All files (*.*)")
            finally:
                self._dialog_open = False
                self.activateWindow()
                self.edit.setFocus()
            if not path:
                self._count = "Nothing added"
                self.update()
                return
            path = os.path.abspath(path)
            name = os.path.splitext(os.path.basename(path))[0]
        if not name or not os.path.exists(path):
            self._count = it.get("sub", "That path doesn't exist")
            self.update()
            return
        custom = [c for c in custom if str(c.get("title", "")).lower() != name.lower()]
        custom.append(dict(title=name, path=path))
        self.cfg["custom_apps"] = custom
        save_settings(self.cfg)
        self.edit.clear()
        self._count = "Added " + name
        self._scan()
        self.update()

    # ---- clear cache: every cache, one progress row per cache
    CLEAN_ROWS = (("vapor", "Vapor"), ("harmony", "Harmony"), ("synapse", "Synapse"), ("temp", "Temp files"))
    G_WAIT, G_RUN, G_OK, G_WARN = "\uE823", "\uE895", "\uE73E", "\uE7BA"

    @staticmethod
    def _fmt_bytes(n):
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
            n /= 1024.0

    def _clear_cache(self, advanced=False):
        """Clears the Vapor, Harmony, Synapse and temp file caches, showing each one as it goes
        (settings, favourites, usage history and your theme are kept).  Every file is also logged to the advanced
        display (the last row, or >clearcache -a opens it straight away)."""
        if getattr(self, "_cleaning", False):
            if advanced:
                self._open_cache_details()
            return
        self._cleaning = True
        self.edit.clear()
        self._clean_rows, rows = {}, []
        for key, title in self.CLEAN_ROWS:
            row = dict(kind="info", path="", glyph=self.G_WAIT, title=title, sub="Waiting...")
            self._clean_rows[key] = row
            rows.append(row)
        rows.append(dict(kind="cmd", cmd="cachedetails", arg="", path="", glyph="\uE8FD", title="Advanced display",
                         sub="Open the live file list  \u2022  every path, size and result"))
        if not hasattr(self, "_clean_files"):
            self._clean_files = []
        self._clean_files.clear()                                 # shared with the worker thread and the advanced window
        self._clean_ver, self._clean_cur, self._clean_scanning = 0, -1, True
        self._clean_hold = True
        self._clean_n = 0
        self.list.empty_text = ""
        self.list.set_items(rows)
        self._count = "Clearing cache  0/%d" % len(self.CLEAN_ROWS)
        self._fit_zen()
        self.update()
        threading.Thread(target=self._clean_worker, daemon=True).start()
        if advanced:
            QTimer.singleShot(80, self._open_cache_details)

    @staticmethod
    def _why(exc):
        code = getattr(exc, "winerror", None)
        if code in (32, 33):
            return "In use by another program"
        if isinstance(exc, PermissionError) or code == 5:
            return "Access denied"
        return exc.strerror or type(exc).__name__

    def _clean_worker(self):
        emit = self.clean_event.emit
        groups = {}
        try:
            emit(("scan",))
            groups = {g["key"]: g for g in clean_groups(dict(self.cfg))}
        except Exception:  # noqa: BLE001
            log("clear cache scan failed:\n" + traceback.format_exc())
            emit(("warn", "Scan failed - see the Synapse log"))
        # Lay out every file up front so the advanced display can list the whole plan; entries are
        # [group, path, size, status, reason, is_dir] and the status is updated in place as each file is handled.
        plan = self._clean_files
        lists, offsets = {}, {}
        for key, _title in self.CLEAN_ROWS:
            lists[key] = list(groups.get(key, {}).get("items", []))
            offsets[key] = len(plan)
            for it in lists[key]:
                try:
                    is_dir = os.path.isdir(it[0]) and not os.path.islink(it[0])
                except OSError:
                    is_dir = False
                plan.append([key, it[0], it[1], "wait", "", is_dir])
        self._clean_scanning = False
        self._clean_ver += 1
        total_n = total_b = total_s = 0
        for key, _title in self.CLEAN_ROWS:
            items, base = lists[key], offsets[key]
            emit(("start", key, len(items)))
            if key == "synapse":
                emit(("mem",))                                   # in-memory caches are emptied on the UI thread
            n = b = s = 0
            pause = min(0.03, 1.2 / max(1, len(items)))
            last = 0.0
            for i, it in enumerate(items, 1):
                path, size = it[0], it[1]
                rec = plan[base + i - 1]
                rec[3] = "run"
                self._clean_cur = base + i - 1
                self._clean_ver += 1
                try:
                    if os.path.isdir(path) and not os.path.islink(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    n += 1
                    b += size
                    rec[3] = "ok"
                except FileNotFoundError:                        # e.g. it lived inside a folder that was already removed
                    rec[3] = "gone"
                except OSError as exc:
                    s += 1
                    rec[3], rec[4] = "skip", self._why(exc)
                self._clean_ver += 1
                now = time.time()
                if now - last > 0.04 or i == len(items):
                    last = now
                    emit(("item", key, i, len(items), path, b))
                time.sleep(pause)
            emit(("stage", key, n, b, s))
            total_n, total_b, total_s = total_n + n, total_b + b, total_s + s
        self._clean_cur = -1
        self._clean_ver += 1
        emit(("done", total_n, total_b, total_s))

    def _open_cache_details(self):
        """Advanced display for >clearcache."""
        if getattr(self, "_clean_files", None) is None:
            self._count = "Run >clearcache first"
            self.update()
            return
        if getattr(self, "_cache_dlg", False):
            return
        self._cache_dlg = True
        try:
            self._cache_details_dialog(self._clean_files)
        finally:
            self._cache_dlg = False

    def _cache_details_dialog(self, files):
        """Floating window listing every file the cache clean-up handles, live: result, name, size and location, with
        a progress bar, per-cache tabs, a name filter and a result filter."""
        t = self.t
        titles = dict(self.CLEAN_ROWS)
        dlg = self._glass_dialog(820, 620)
        dlg.setWindowTitle("Synapse \u00b7 Cache clean-up")
        model = CacheFilesModel(files, t, dlg)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        heading_col = QVBoxLayout()
        heading_col.setSpacing(3)
        eyebrow = QLabel("SYNAPSE  /  MAINTENANCE", dlg)
        eyebrow.setObjectName("eyebrow")
        heading = QLabel("Cache clean-up", dlg)
        heading.setObjectName("heading")
        heading_col.addWidget(eyebrow)
        heading_col.addWidget(heading)
        header.addLayout(heading_col, 1)
        close_btn = QPushButton("\u00d7", dlg)
        close_btn.setObjectName("closeButton")
        close_btn.clicked.connect(dlg.accept)
        header.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        status_row = QHBoxLayout()
        status_lbl = QLabel("Scanning caches...", dlg)
        status_lbl.setObjectName("title")
        count_lbl = QLabel("", dlg)
        count_lbl.setObjectName("meta")
        status_row.addWidget(status_lbl, 1)
        status_row.addWidget(count_lbl)
        layout.addLayout(status_row)
        bar = GlowBar(t["accent"], dlg)
        layout.addWidget(bar)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        chip_ok, chip_freed, chip_skip, chip_left = (QLabel("", dlg) for _ in range(4))
        for c in (chip_ok, chip_freed, chip_skip, chip_left):
            c.setObjectName("chip")
            chips.addWidget(c)
        chips.addStretch(1)
        follow_cb = QCheckBox("Follow live", dlg)
        follow_cb.setChecked(True)
        chips.addWidget(follow_cb)
        layout.addLayout(chips)

        tabs = QHBoxLayout()
        tabs.setSpacing(6)
        tab_btns = {}
        tab_group = QButtonGroup(dlg)
        for key, label in (("all", "All"),) + tuple(self.CLEAN_ROWS):
            b = QPushButton(label, dlg)
            b.setObjectName("tab")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            tab_group.addButton(b)
            tab_btns[key] = (b, label)
            tabs.addWidget(b)
        tab_btns["all"][0].setChecked(True)
        tabs.addStretch(1)
        layout.addLayout(tabs)

        flt = QHBoxLayout()
        flt.setSpacing(8)
        search = QLineEdit(dlg)
        search.setPlaceholderText("Filter by name or path...")
        search.setClearButtonEnabled(True)
        status_box = QComboBox(dlg)
        for label, val in (("All results", "all"), ("Deleted", "ok"), ("Skipped", "skip"), ("Waiting", "wait")):
            status_box.addItem(label, val)
        flt.addWidget(search, 1)
        flt.addWidget(status_box)
        layout.addLayout(flt)

        table = QTableView(dlg)
        table.setModel(model)
        table.viewport().setAutoFillBackground(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(26)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hh = table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setStretchLastSection(True)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(0, 116)
        table.setColumnWidth(1, 250)
        table.setColumnWidth(2, 84)
        layout.addWidget(table, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        copy_btn = QPushButton("Copy list", dlg)
        show_btn = QPushButton("Show in folder", dlg)
        hint = QLabel("Double-click a row to open its folder", dlg)
        hint.setObjectName("hint")
        done_btn = QPushButton("Close", dlg)
        done_btn.setObjectName("primary")
        done_btn.clicked.connect(dlg.accept)
        footer.addWidget(copy_btn)
        footer.addWidget(show_btn)
        footer.addWidget(hint, 1)
        footer.addWidget(done_btn)
        layout.addLayout(footer)

        def set_key(k):
            model.key = k
            model.rebuild(model.compute())

        for k, (b, _label) in tab_btns.items():
            b.clicked.connect(lambda _=False, k=k: set_key(k))

        def on_filter(*_):
            model.text = search.text().strip().lower()
            model.status = status_box.currentData() or "all"
            model.rebuild(model.compute())

        search.textChanged.connect(on_filter)
        status_box.currentIndexChanged.connect(on_filter)

        def selected_file():
            ix = table.currentIndex()
            if not ix.isValid():
                return None
            try:
                return files[model.view[ix.row()]]
            except IndexError:
                return None

        def show_folder(*_):
            f = selected_file()
            if not f:
                return
            path = os.path.normpath(f[1])
            try:
                if os.path.exists(path):
                    subprocess.Popen('explorer /select,"%s"' % path)
                elif os.path.isdir(os.path.dirname(path)):
                    os.startfile(os.path.dirname(path))
            except OSError:
                pass

        def copy_list():
            lines = ["Synapse cache clean-up  \u2022  " + time.strftime("%Y-%m-%d %H:%M:%S")]
            for f in files:
                lines.append("\t".join([model.LABEL.get(f[3], f[3]), fmt_bytes(f[2]), titles.get(f[0], f[0]), f[1]] + ([f[4]] if f[4] else [])))
            QApplication.clipboard().setText("\n".join(lines))
            copy_btn.setText("Copied")

            def restore():
                try:
                    copy_btn.setText("Copy list")
                except RuntimeError:
                    pass
            QTimer.singleShot(1500, restore)

        show_btn.clicked.connect(show_folder)
        copy_btn.clicked.connect(copy_list)
        table.doubleClicked.connect(show_folder)

        last = [None]

        def refresh():
            ver, cleaning, scanning = self._clean_ver, self._cleaning, self._clean_scanning
            if (ver, cleaning, scanning) == last[0]:
                return
            last[0] = (ver, cleaning, scanning)
            total = len(files)
            ok = skip = left = freed = 0
            per = {}
            for f in files:
                st = f[3]
                g = per.setdefault(f[0], [0, 0])
                g[0] += 1
                if st == "ok":
                    ok += 1
                    freed += f[2]
                    g[1] += f[2]
                elif st == "gone":
                    ok += 1
                elif st == "skip":
                    skip += 1
                else:
                    left += 1
            handled = ok + skip
            chip_ok.setText("DELETED  %d" % ok)
            chip_freed.setText("FREED  %s" % fmt_bytes(freed))
            chip_skip.setText("SKIPPED  %d" % skip)
            chip_skip.setStyleSheet("color: #fbbf24;" if skip else "")
            chip_left.setText("LEFT  %d" % left)
            count_lbl.setText("%d / %d" % (handled, total))
            for k, (b, label) in tab_btns.items():
                b.setText("%s  %d" % (label, total if k == "all" else per.get(k, [0, 0])[0]))
            if scanning:
                status_lbl.setText("Scanning caches...")
                bar.set_value(None)
            elif cleaning:
                cur = self._clean_cur
                name = titles.get(files[cur][0], "") if 0 <= cur < total else ""
                status_lbl.setText(("Clearing %s..." % name) if name else "Clearing...")
                bar.set_value(100.0 * handled / total if total else 100.0)
            else:
                if total == 0:
                    status_lbl.setText("Nothing to clear  \u2022  the caches are already empty")
                else:
                    status_lbl.setText("Done  \u2022  %d item%s deleted, %s freed%s" % (
                        ok, "" if ok == 1 else "s", fmt_bytes(freed), ("  \u2022  %d skipped" % skip) if skip else ""))
                bar.set_value(100.0, done=True, warn=skip > 0)
            vbar = table.verticalScrollBar()
            keep = vbar.value()
            changed = model.refresh()
            following = follow_cb.isChecked() and cleaning and not scanning
            if following and 0 <= self._clean_cur < total:
                row = bisect.bisect_left(model.view, self._clean_cur)
                if row < len(model.view) and model.view[row] == self._clean_cur:
                    table.scrollTo(model.index(row, 1), QAbstractItemView.ScrollHint.PositionAtCenter)
            elif changed:
                QTimer.singleShot(0, lambda v=keep: vbar.setValue(min(v, vbar.maximum())))

        poll = QTimer(dlg)
        poll.setInterval(120)
        poll.timeout.connect(refresh)
        poll.start()
        refresh()
        self._exec_glass(dlg)
        poll.stop()

    def _clear_memory(self):
        """What Synapse itself caches in memory."""
        self.list._icons.clear()                          # app / file icons
        self._covs.clear()                                # scaled background covers
        rounded_region.cache_clear()
        self._card_layer = None
        self.files, self._files_at = [], 0.0              # file index
        self.apps, self._scanned = [], 0.0
        self.weather, self._weather_at = None, 0.0
        self.temps = dict(cpu=None, gpu=None)
        bg = clean_path(self.cfg.get("background") or "")
        self.src = shrink(QPixmap(bg), W, H) if bg and os.path.isfile(bg) else QPixmap()
        trim_memory()

    def _on_clean_event(self, ev):
        kind, rows = ev[0], getattr(self, "_clean_rows", {})
        if kind == "scan":
            self._count = "Scanning caches..."
        elif kind == "warn":
            self._count = ev[1]
        elif kind == "start":
            row = rows.get(ev[1])
            if row:
                row["glyph"] = self.G_RUN
                row["sub"] = ("Clearing %d item%s..." % (ev[2], "" if ev[2] == 1 else "s")) if ev[2] else "Checking..."
        elif kind == "mem":
            self._clear_memory()
            row = rows.get("synapse")
            if row:
                row["sub"] = "Memory: icons, images, file index, weather"
        elif kind == "item":
            _, key, i, total, path, freed = ev
            row = rows.get(key)
            if row:
                row["sub"] = "%d/%d  \u2022  %s freed  \u2022  %s" % (i, total, self._fmt_bytes(freed), os.path.basename(path.rstrip("\\/")) or path)
        elif kind == "stage":
            _, key, n, b, s = ev
            row = rows.get(key)
            if row:
                txt = ("%d item%s deleted  \u2022  %s freed" % (n, "" if n == 1 else "s", self._fmt_bytes(b))) if n else "Nothing to delete"
                if s:
                    txt += "  \u2022  %d in use, skipped" % s
                if key == "synapse":
                    txt = "Memory cleared  \u2022  " + txt
                row["glyph"] = self.G_WARN if s else self.G_OK
                row["sub"] = txt
            self._clean_n += 1
            self._count = "Clearing cache  %d/%d" % (self._clean_n, len(self.CLEAN_ROWS))
        elif kind == "done":
            _, n, b, s = ev
            self._cleaning = False
            self._count = "Cache cleared  \u2022  %d item%s, %s freed%s" % (
                n, "" if n == 1 else "s", self._fmt_bytes(b), ("  \u2022  %d in use" % s) if s else "")
            self._build_cache()                                   # rebuild what was dropped
            self._scan()
            if not everything_ready():
                self._scan_files()
        self.list.update()
        self.update(QRect(LEFT_X, FOOT_Y, LEFT_W, 24))

    def _load_quote(self, path):
        pm = crop_pm(QPixmap(path), self.cfg.get("quote_crop"))
        if pm.isNull():
            return False
        self.qsrc = shrink(pm, QUOTE_R.width(), QUOTE_R.height())
        self._covs.clear()
        self._build_cache()
        self.update()
        return True

    # ---- crop picker flow: launcher hides, the picker opens, Enter saves the area and the launcher comes back
    def _begin_crop(self, key, path):
        if key == "media" and os.path.splitext(path)[1].lower() in VID_EXT:
            self._crop_when_ready(key, path, 0)            # needs a decoded frame to show
            return
        pm = QPixmap(path)
        if pm.isNull():
            self._count = "Couldn't read that image"
            self.update()
            return
        self._open_crop(key, path, pm)

    def _crop_when_ready(self, key, path, tries):
        img = self._media_obj
        if isinstance(img, QImage) and not img.isNull():
            self._open_crop(key, path, QPixmap.fromImage(img))
        elif tries < 25:
            QTimer.singleShot(160, lambda: self._crop_when_ready(key, path, tries + 1))
        else:
            self._count = "Couldn't grab a video frame to crop"
            self.update()

    def _open_crop(self, key, path, pm):
        if key == "media":
            aspect, label = CARD.width() / CARD.height(), "Choose the area for the image card"
        else:
            aspect, label = QUOTE_R.width() / QUOTE_R.height(), "Choose the area for the quote card"
        self.close_launcher()
        win = CropWindow(pm, aspect, self.cfg.get(key + "_crop"), self.t["accent"], label)
        win.done.connect(lambda c, k=key, p=path: self._crop_done(k, p, c))
        self._cropwin = win
        QTimer.singleShot(200, win.present)

    def _crop_done(self, key, path, crop):
        win, self._cropwin = self._cropwin, None
        if win is not None:
            QTimer.singleShot(0, lambda w=win: w.deleteLater())     # free the preview picture
        if crop is not None:
            self.cfg[key + "_crop"] = [round(float(v), 5) for v in crop]
            save_settings(self.cfg)
            if key == "media":
                self._load_media(path)
            else:
                self._load_quote(path)
        self.open_launcher()
        self._count = "Crop saved" if crop is not None else "Crop cancelled"
        self.update()

    # ---- >vapor ...: name / profile picture / any vaporctl command
    def _vapor_items(self, arg):
        al = re.sub(r"\s+", " ", arg.strip().lower())
        hints = []
        exact = any(f == al and not f.endswith(" ") for f, _u, _d, _g in VAPOR_HINTS)      # a finished command: run it, don't list longer ones
        for fill, usage, desc, glyph in ([] if exact else VAPOR_HINTS):
            core = fill.rstrip()
            if not al or (core.startswith(al) and (len(al) <= len(core) if fill.endswith(" ") else len(al) < len(core))):
                hints.append(dict(kind="hint", title=">vapor " + usage, sub=desc, path="", glyph=glyph, fill=">vapor " + fill))
        if hints:
            return hints
        base = dict(kind="cmd", cmd="vapor", arg=arg, path="", glyph="\uE77B", ok=True)
        if not vaporctl_path(self.cfg):
            return [dict(base, ok=False, plan={}, title="Vapor", sub='vaporctl.py not found on your PATH  -  start Vapor once (it adds its folder), or set "customizations": {"vapor": "folder"}')]
        plan = vapor_plan(arg)
        if plan["mode"] == "need":
            return [dict(kind="info", title="Vapor", path="", glyph="\uE77B", sub="Type " + plan["what"])]
        if plan["mode"] == "pfp":
            path, crop = plan["path"], plan["crop"]
            last = clean_path(self.cfg.get("vapor_pfp_src") or "")
            ok = True
            if path:
                if not os.path.isfile(path):
                    sub_, ok = "File not found", False
                elif crop:
                    sub_ = "Press Enter, then drag the circle over your face  \u2022  " + os.path.basename(path)
                else:
                    sub_ = "Press Enter to use it as your Vapor profile picture  \u2022  " + os.path.basename(path)
            elif crop and os.path.isfile(last):
                path, sub_ = last, "Press Enter to re-crop the last picture  \u2022  " + os.path.basename(last)
            elif crop:
                sub_ = "Press Enter to pick a picture, then crop it round"
            else:
                sub_ = 'Press Enter to pick a picture  \u2022  or type a path, add -c to crop it round'
            return [dict(base, ok=ok, plan=dict(plan, path=path), title="Vapor profile picture" + ("  \u2022  round crop" if crop else ""), sub=sub_)]
        if plan["mode"] == "update":
            if plan["check"]:
                title, sub_ = "Vapor update  \u2022  check only", "Press Enter to see whether a newer Vapor release is out"
            else:
                title = "Update Vapor" + ("  \u2022  reinstall" if plan["force"] else "")
                sub_ = "Press Enter  \u2022  checks GitHub, then opens the Vapor installer in a command window  (add --check to only look)"
            return [dict(base, plan=plan, title=title, sub=sub_)]
        va = plan["vargs"]
        return [dict(base, plan=plan, title=plan.get("title") or "Vapor  \u2022  " + " ".join(va),
                     sub="Press Enter  \u2022  vaporctl " + " ".join('"%s"' % a if " " in a else a for a in va))]

    def _run_vapor(self, it):
        plan = it.get("plan") or {}
        if not it.get("ok", True):
            self._count = it["sub"]
            self.update()
            return
        if plan.get("mode") == "pfp":
            path, crop = plan.get("path", ""), plan.get("crop", False)
            if not path:
                self._dialog_open = True
                try:
                    path, _f = QFileDialog.getOpenFileName(
                        self, "Choose a profile picture", os.path.join(os.path.expanduser("~"), "Pictures"),
                        "Pictures (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.tif *.tiff *.ico);;All files (*.*)")
                finally:
                    self._dialog_open = False
                if not path:
                    self._count = "Profile picture unchanged"
                    self.update()
                    return
                path = os.path.normpath(path)
            if crop:
                self._begin_pfp_crop(path)
            else:
                self._count = "Setting the profile picture..."
                self.update()
                self._vapor_async(["pfp", path])
            return
        if plan.get("mode") == "update":
            self._count = "Checking for a Vapor update..."
            self.update()
            if plan.get("check"):
                self._vapor_async(["update", "--check"])
            else:
                self._vapor_update(plan)
            return
        self._count = "vaporctl " + " ".join(plan.get("vargs") or []) + " ..."
        self.update()
        self._vapor_async(plan.get("vargs") or [])

    def _vapor_update(self, plan):
        """>vapor update: ask vaporctl whether a newer release exists, then open the installer in a command window."""
        cfg = dict(self.cfg)
        force, extras = bool(plan.get("force")), bool(plan.get("extras"))
        self._vapor_title = "Vapor update"

        def work():
            try:
                ok, text = run_vaporctl(cfg, ["update", "--check"])
                if ok and (force or "update available" in text):
                    ok, text = open_vapor_installer(cfg, extras, force)
                elif ok:
                    text = "Vapor is up to date  -  " + (text.split("   ")[0] or text).strip()
            except Exception:  # noqa: BLE001
                log("vapor update failed:\n" + traceback.format_exc())
                ok, text = False, "Vapor update failed  (see >log)"
            self.vapor_done.emit(ok, text)
        threading.Thread(target=work, name="SynapseVaporUpdate", daemon=True).start()

    def _vapor_async(self, argv, cleanup=""):
        cfg = dict(self.cfg)
        self._vapor_title = "Profile picture" if argv and argv[0] == "pfp" else "vaporctl " + " ".join(str(a) for a in argv[:3])

        def work():
            try:
                ok, text = run_vaporctl(cfg, argv)
            except Exception:  # noqa: BLE001
                log("vaporctl failed:\n" + traceback.format_exc())
                ok, text = False, "vaporctl failed  (see >log)"
            if cleanup:
                try:
                    os.remove(cleanup)
                except OSError:
                    pass
            self.vapor_done.emit(ok, text)
        threading.Thread(target=work, daemon=True).start()

    def _vapor_result(self, ok, text):
        if ok and self.edit.text().lstrip().lower().startswith((">vapor", ">vctl", ">vaporctl")):
            self.edit.clear()
        lines = [l.rstrip() for l in text.splitlines() if l.strip()]
        if len(lines) > 1 or len(text) > 100:                    # more than a line: show it in a window, like >yt -a / >clearcache -a
            self._count = "%s  \u2022  %d line%s" % ("Done" if ok else "Failed", len(lines), "" if len(lines) == 1 else "s")
            self.update(QRect(LEFT_X, FOOT_Y, LEFT_W, 24))
            self._show_text_window("VAPOR  /  " + ("OUTPUT" if ok else "ERROR"), getattr(self, "_vapor_title", "Vapor"), "\n".join(lines))
            return
        line = lines[0] if lines else ""
        self._count = (line[:117] + "...") if len(line) > 120 else (line or ("Done" if ok else "vaporctl failed"))
        self.update(QRect(LEFT_X, FOOT_Y, LEFT_W, 24))

    def _show_text_window(self, eyebrow, heading, text):
        """Floating glass window with some read-only text (same look as >yt -a and >clearcache -a): command output, lists ..."""
        t = self.t
        dlg = self._glass_dialog(720, 480)
        dlg.setWindowTitle("Synapse \u00b7 " + heading)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(12)
        header = QHBoxLayout()
        header.setSpacing(10)
        col = QVBoxLayout()
        col.setSpacing(3)
        eb = QLabel(eyebrow.upper(), dlg)
        eb.setObjectName("eyebrow")
        hd = QLabel(heading, dlg)
        hd.setObjectName("heading")
        col.addWidget(eb)
        col.addWidget(hd)
        header.addLayout(col, 1)
        close_btn = QPushButton("\u00d7", dlg)
        close_btn.setObjectName("closeButton")
        close_btn.clicked.connect(dlg.accept)
        header.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        view = QPlainTextEdit(dlg)
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        view.setPlainText(text)
        view.setStyleSheet("QPlainTextEdit { background: rgba(%s, 14); border: 1px solid rgba(%s, 45); border-radius: 10px; padding: 10px;"
                           " font-family: '%s', 'CaskaydiaCove Nerd Font Mono', 'Cascadia Code'; font-size: 12px; selection-background-color: %s; selection-color: %s; }"
                           % (t["tint"], t["tint"], MONO_FONT, t["accent"], t["on"]))
        layout.addWidget(view, 1)

        row = QHBoxLayout()
        row.setSpacing(8)
        meta = QLabel("%d line%s" % (text.count("\n") + 1, "" if "\n" not in text else "s"), dlg)
        meta.setObjectName("meta")
        row.addWidget(meta, 1)
        copy_btn = QPushButton("Copy", dlg)
        done_btn = QPushButton("Close", dlg)
        done_btn.setObjectName("primary")
        done_btn.setDefault(True)

        def copy():
            QApplication.clipboard().setText(text)
            copy_btn.setText("Copied")
        copy_btn.clicked.connect(copy)
        done_btn.clicked.connect(dlg.accept)
        row.addWidget(copy_btn)
        row.addWidget(done_btn)
        layout.addLayout(row)
        self._exec_glass(dlg)

    def _begin_pfp_crop(self, path):
        img = read_image(path)
        if img.isNull():
            self._count = "Couldn't read that image"
            self.update()
            return
        same = os.path.normcase(path) == os.path.normcase(clean_path(self.cfg.get("vapor_pfp_src") or ""))
        self.close_launcher()
        win = CropWindow(QPixmap.fromImage(img), 1.0, self.cfg.get("vapor_pfp_crop") if same else None, self.t["accent"],
                         "Choose your Vapor profile picture  (%d x %d px)" % (img.width(), img.height()), circle=True)
        win.done.connect(lambda c, p=path, im=img: self._pfp_crop_done(p, im, c))
        self._cropwin = win
        QTimer.singleShot(200, win.present)

    def _pfp_crop_done(self, path, img, crop):
        win, self._cropwin = self._cropwin, None
        if win is not None:
            QTimer.singleShot(0, lambda w=win: w.deleteLater())
        self.open_launcher()
        if crop is None:
            self._count = "Crop cancelled"
            self.update()
            return
        out = crop_square(img, crop)
        tmp = os.path.join(tempfile.gettempdir(), "synapse_pfp_%d.png" % int(time.time() * 1000))
        if out.isNull() or not out.save(tmp, "PNG"):
            self._count = "Couldn't save the cropped picture"
            self.update()
            return
        self.cfg["vapor_pfp_src"] = path
        self.cfg["vapor_pfp_crop"] = [round(float(v), 5) for v in crop]
        save_settings(self.cfg)
        self._count = "Setting the profile picture  (%d x %d px)..." % (out.width(), out.height())
        self.update()
        self._vapor_async(["pfp", tmp], cleanup=tmp)

    def quit_app(self):
        """Stop timers, threads' consumers, media and the single-instance server, then end the process."""
        try:
            self.keygrab.stop()
            for tm in (self.poll, self.stat_timer, self.watch, self.warm, self.save_timer, self.tb_timer):
                tm.stop()
            if self.cfg.get("taskbar_hidden") and not self.cfg.get("taskbar_always_hidden", True):     # always-hidden: leave it off
                taskbar_show_windows(True)
                taskbar_set_autohide(bool(self.cfg.get("taskbar_prev_autohide", False)))
                self.cfg["taskbar_hidden"] = False
                save_settings(self.cfg)
            self.col_anim.stop()
            self.fade.stop()
            self._clear_media()
            self.gpu_mon.stop()
            srv = getattr(self, "server", None)
            if srv is not None:
                srv.close()
            QLocalServer.removeServer(SERVER)
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            if getattr(self, "_tray", None) is not None:
                self._tray.hide()                           # remove the icon so no ghost is left in the tray
        except Exception:  # noqa: BLE001
            log("quit cleanup failed:\n" + traceback.format_exc())
        self.hide()
        QApplication.quit()

    # ---- image card media: still image, GIF (QMovie) or video (QMediaPlayer -> QVideoSink, painted by us)
    def _clear_media(self):
        if self._movie is not None:
            self._movie.stop()
            self._movie.deleteLater()
            self._movie = None
        if self._player is not None:
            try:
                self._player.stop()
                self._player.setVideoSink(None)
            except Exception:  # noqa: BLE001
                pass
            self._player.deleteLater()
            self._player = None
        if self._sink is not None:
            self._sink.deleteLater()
            self._sink = None
        self._media_obj, self._media_kind, self._media_cached = None, "", False
        self._card_layer = None
        self.update(CARD)

    def _load_media(self, path):
        ext = os.path.splitext(path)[1].lower()
        self._clear_media()
        self._media_crop = self.cfg.get("media_crop")
        try:
            if ext in IMG_EXT:
                pm = crop_pm(QPixmap(path), self._media_crop)
                if pm.isNull():
                    return False
                dpr = self.devicePixelRatioF()
                tw, th = int(CARD.width() * dpr), int(CARD.height() * dpr)
                sc = pm.scaled(tw, th, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                sc = sc.copy((sc.width() - tw) // 2, (sc.height() - th) // 2, tw, th)
                sc.setDevicePixelRatio(dpr)
                self._media_obj, self._media_cached, self._media_kind = sc, True, "image"
            elif ext in GIF_EXT:
                mv = QMovie(path)
                if not mv.isValid():
                    return False
                mv.frameChanged.connect(self._on_movie_frame)
                self._movie = mv
                mv.jumpToFrame(0)
                self._media_obj, self._media_kind = mv.currentPixmap(), "gif"
            elif ext in VID_EXT:
                if not _need_video():
                    log("QtMultimedia is not available, cannot play video")
                    return False
                self._sink = QVideoSink(self)
                self._sink.videoFrameChanged.connect(self._on_video_frame)
                self._player = QMediaPlayer(self)            # no audio output attached, so it plays silently
                self._player.setVideoSink(self._sink)
                try:
                    self._player.setLoops(QMediaPlayer.Loops.Infinite)
                except Exception:  # noqa: BLE001
                    pass
                self._player.setSource(QUrl.fromLocalFile(path))
                self._media_kind = "video"
            else:
                return False
        except Exception:  # noqa: BLE001
            log("could not load media:\n" + traceback.format_exc())
            self._clear_media()
            return False
        self._media_run(self.isVisible())
        self.update(CARD)
        return True

    def _media_due(self):
        """Cap animated media at ~24 fps: every repaint is another window flush to dwm.exe."""
        now = time.monotonic()
        if now - getattr(self, "_media_paint_at", 0.0) < 0.05:
            return False
        self._media_paint_at = now
        return True

    def _on_movie_frame(self, _n):
        if self._movie is not None and self.isVisible() and self._media_due():
            self._media_obj = self._movie.currentPixmap()
            self.update(CARD)

    def _on_video_frame(self, frame):
        if not frame.isValid() or not self.isVisible() or not self._media_due():
            return
        img = frame.toImage()
        if not img.isNull():
            self._media_obj = img
            self.update(CARD)

    def _media_run(self, on):
        """Play while the launcher is open, pause (first frame stays) while it is hidden."""
        try:
            if self._movie is not None:
                if on:
                    if self._movie.state() == QMovie.MovieState.NotRunning:
                        self._movie.start()
                    else:
                        self._movie.setPaused(False)
                elif self._movie.state() == QMovie.MovieState.Running:
                    self._movie.setPaused(True)
            if self._player is not None:
                (self._player.play if on else self._player.pause)()
        except Exception:  # noqa: BLE001
            log("media play/pause failed:\n" + traceback.format_exc())

    @staticmethod
    def _draw_cover(p, obj, rect, crop=None):
        sw, sh = obj.width(), obj.height()
        if sw <= 0 or sh <= 0:
            return
        bx, by, bw, bh = 0.0, 0.0, float(sw), float(sh)
        if crop:
            try:
                bx, by, bw, bh = crop[0] * sw, crop[1] * sh, max(1.0, crop[2] * sw), max(1.0, crop[3] * sh)
            except (TypeError, ValueError, IndexError):
                bx, by, bw, bh = 0.0, 0.0, float(sw), float(sh)
        k = max(rect.width() / bw, rect.height() / bh)
        cw, ch = rect.width() / k, rect.height() / k
        src = QRectF(bx + (bw - cw) / 2, by + (bh - ch) / 2, cw, ch)
        if isinstance(obj, QImage):
            p.drawImage(rect, obj, src)
        else:
            p.drawPixmap(rect, obj, src)

    def _build_card_layer(self, dpr):
        """Image + soft fade + anti-aliased rounded mask + gradient edge, baked into one pixmap.
        (QPainter clip paths are not anti-aliased, which is what made the corners look jagged.)"""
        t = self.t
        tint = lambda a: qc("rgb(%s)" % t["tint"], a)           # noqa: E731
        accent = qc(t["accent"])
        w, h = CARD.width(), CARD.height()
        rect = QRectF(0, 0, w, h)
        pm = QPixmap(int(w * dpr), int(h * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        obj = self._media_obj
        if obj is not None and not obj.isNull():
            if self._media_cached:
                q.drawPixmap(0, 0, obj)
            else:
                self._draw_cover(q, obj, rect, self._media_crop)
        else:
            q.fillRect(rect, tint(30))
            q.setPen(qc(t["sub"]))
            q.setFont(_font(10, mono=True))
            q.drawText(QRectF(0, 12, w, 20), Qt.AlignmentFlag.AlignCenter,
                       'Type  >setmedia "path"  for an image, GIF or video')
        g = QLinearGradient(0, 0, 0, h)                         # eased fade so the clock stays readable without a visible band
        for pos, a in ((0.0, 0), (0.30, 0), (0.50, 28), (0.68, 80), (0.84, 150), (1.0, 205)):
            g.setColorAt(pos, QColor(0, 6, 20, a))
        q.fillRect(rect, g)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)      # round the corners, smoothly
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(QColor(0, 0, 0, 255))
        q.drawRoundedRect(rect.adjusted(.5, .5, -.5, -.5), 14, 14)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        eg = QLinearGradient(0, 0, w, h)                        # thin gradient edge
        e0, e1, e2 = QColor(accent), tint(80), QColor(accent)
        e0.setAlpha(210)
        e2.setAlpha(150)
        eg.setColorAt(0.0, e0)
        eg.setColorAt(0.5, e1)
        eg.setColorAt(1.0, e2)
        q.setBrush(Qt.BrushStyle.NoBrush)
        q.setPen(QPen(QBrush(eg), 1.2))
        q.drawRoundedRect(rect.adjusted(.6, .6, -.6, -.6), 14, 14)
        q.end()
        return pm

    def _animated_layer(self, dpr):
        """GIF / video card: the fade, rounded mask and edge are baked once; only the frame itself is drawn per update."""
        t = self.t
        w, h = CARD.width(), CARD.height()
        rect = QRectF(0, 0, w, h)

        def blank():
            pm = QPixmap(int(w * dpr), int(h * dpr))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            return pm

        parts = getattr(self, "_anim_parts", None)
        if parts is None or parts[0] != dpr:
            tint = lambda a: qc("rgb(%s)" % t["tint"], a)           # noqa: E731
            accent = qc(t["accent"])
            fade = blank()
            q = QPainter(fade)
            g = QLinearGradient(0, 0, 0, h)
            for pos, a in ((0.0, 0), (0.30, 0), (0.50, 28), (0.68, 80), (0.84, 150), (1.0, 205)):
                g.setColorAt(pos, QColor(0, 6, 20, a))
            q.fillRect(rect, g)
            q.end()
            mask = blank()
            q = QPainter(mask)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.setPen(Qt.PenStyle.NoPen)
            q.setBrush(QColor(0, 0, 0, 255))
            q.drawRoundedRect(rect.adjusted(.5, .5, -.5, -.5), 14, 14)
            q.end()
            edge = blank()
            q = QPainter(edge)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            eg = QLinearGradient(0, 0, w, h)
            e0, e1, e2 = QColor(accent), tint(80), QColor(accent)
            e0.setAlpha(210)
            e2.setAlpha(150)
            eg.setColorAt(0.0, e0)
            eg.setColorAt(0.5, e1)
            eg.setColorAt(1.0, e2)
            q.setBrush(Qt.BrushStyle.NoBrush)
            q.setPen(QPen(QBrush(eg), 1.2))
            q.drawRoundedRect(rect.adjusted(.6, .6, -.6, -.6), 14, 14)
            q.end()
            parts = self._anim_parts = (dpr, fade, mask, edge)
        _d, fade, mask, edge = parts
        pm = blank()
        q = QPainter(pm)
        q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        obj = self._media_obj
        if obj is not None and not obj.isNull():
            self._draw_cover(q, obj, rect, self._media_crop)
        else:
            q.fillRect(rect, qc("rgb(%s)" % t["tint"], 30))
        q.drawPixmap(0, 0, fade)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        q.drawPixmap(0, 0, mask)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        q.drawPixmap(0, 0, edge)
        q.end()
        return pm

    def _paint_card(self, p, now):
        t = self.t
        AL = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        dpr = self.devicePixelRatioF()
        animated = self._media_kind in ("gif", "video")
        if animated:
            layer = self._animated_layer(dpr)
        else:
            layer = getattr(self, "_card_layer", None)
            if layer is None:
                layer = self._card_layer = self._build_card_layer(dpr)      # still images only rebuild when something changes
        p.drawPixmap(CARD.topLeft(), layer)

        x0, bot = CARD.x(), CARD.bottom()
        accent = qc(t["accent"])
        white = QColor("white")

        def text(rect, s, font, col):                           # text with a faint shadow so it stays crisp on any picture
            p.setFont(font)
            p.setPen(QColor(0, 0, 0, 110))
            p.drawText(rect.translated(0, 1.4), AL, s)
            p.setPen(col)
            p.drawText(rect, AL, s)

        w = self.weather
        temp = ("%d\u00b0%s" % (w["temp"], w.get("unit", "C"))) if w else "--"
        cond = " ".join(x.capitalize() for x in (w["text"] if w else (WX.get("place") or "Weather")).split())
        f_temp, f_cond = _font(16, QFont.Weight.DemiBold), _font(11)
        fm_t, fm_c = QFontMetrics(f_temp), QFontMetrics(f_cond)
        cond = fm_c.elidedText(cond, Qt.TextElideMode.ElideRight, 88)
        tw = max(fm_t.horizontalAdvance(temp), fm_c.horizontalAdvance(cond))
        gx = CARD.right() - 22 - (44 + tw)                      # weather group hugs the right edge: icon, gap, text
        divx = gx - 18

        ts = time.strftime("%I:%M %p", now).lstrip("0")
        size = 32
        while size > 22 and x0 + 22 + QFontMetrics(_font(size, QFont.Weight.DemiBold)).horizontalAdvance(ts) > divx - 14:
            size -= 1                                           # shrink the time if a long weather label needs the room
        text(QRectF(x0 + 22, bot - 90, divx - x0 - 30, 46), ts, _font(size, QFont.Weight.DemiBold), white)
        text(QRectF(x0 + 24, bot - 48, divx - x0 - 32, 20), time.strftime("%A, %B ", now) + str(now.tm_mday),
             _font(13), QColor(255, 255, 255, 225))
        p.setPen(Qt.PenStyle.NoPen)                             # short accent underline
        p.setBrush(accent)
        p.drawRoundedRect(QRectF(x0 + 24, bot - 18, 40, 2.5), 1.25, 1.25)

        div = QColor(accent)                                    # divider + weather (no location pin)
        div.setAlpha(170)
        p.setBrush(div)
        p.drawRect(QRectF(divx, bot - 64, 1.2, 46))
        draw_weather_icon(p, gx, bot - 56, w["code"] if w else 3, QColor(255, 255, 255, 235))
        text(QRectF(gx + 44, bot - 62, tw + 4, 26), temp, f_temp, white)
        text(QRectF(gx + 44, bot - 36, tw + 4, 18), cond, f_cond, accent.lighter(140))

    # ---- live data for the right pane
    def _tick(self):
        if self._k <= 0.0 and self._k_target < 0.5:        # right side retracted: nothing to refresh
            return
        st = self.stats
        try:
            pw = _PWR()
            ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(pw))
            st["bat"] = None if (pw.pct == 255 or pw.flag == 128) else int(pw.pct)
            st["plug"], st["charging"] = pw.ac == 1, bool(pw.flag != 255 and pw.flag & 8)
            st["life"] = None if pw.life == 0xFFFFFFFF else int(pw.life)
        except Exception:  # noqa: BLE001
            pass
        try:
            st["up"] = read_uptime()
            self._wm_n = (self._wm_n + 1) % 3
            if self._wm_n == 0 and not self._wm_busy:                # is Komorebi running? every 3 s is plenty
                self.wm_state = wm_running()
        except Exception:  # noqa: BLE001
            pass
        self.temps["cpu"] = self._cpu_load()
        if self.temps["cpu"] is not None:
            self.hist["cpu"].append(self.temps["cpu"])
        self._kick_data()
        mnt = time.localtime().tm_min
        if mnt != getattr(self, "_last_min", None):
            self._last_min = mnt
            self.update(CARD)                              # the time / date on the card only change once a minute
        self.update(QRect(RIGHT_X, CARD.bottom() + 1, RIGHT_W + 20, H - CARD.bottom() - 1))

    def _cpu_load(self):
        try:
            idle, total = cpu_times()
        except Exception:  # noqa: BLE001
            return None
        now, prev = time.time(), self._cpu_prev
        self._cpu_prev = (now, idle, total)
        if not prev or now - prev[0] > 5 or total <= prev[2]:    # first reading, or stale after the launcher was hidden
            return self.temps["cpu"]
        return max(0.0, min(100.0, 100.0 * (1.0 - (idle - prev[1]) / float(total - prev[2]))))

    def _kick_data(self):
        now = time.time()
        sig = vapor_location_sig(_CFG_REF)                          # `>vapor set location ...` was run: refetch now
        if sig != getattr(self, "_wx_sig", sig):
            self._weather_at = 0.0
        self._wx_sig = sig
        if now - self._weather_at > 900:
            self._weather_at = now

            def go():
                try:
                    self.weather_ready.emit(fetch_weather())
                except Exception:  # noqa: BLE001
                    self._weather_at = time.time() - 840         # offline etc.: try again in a minute
            threading.Thread(target=go, daemon=True).start()
        if time.time() - getattr(self, "_opened_at", 0) > 0.9:       # not during the open animation: the helper spawn is the heaviest bit
            self.gpu_mon.start()                       # no-op while its helper process is already running

    def _wm_toggle(self, key):
        """Click the Komorebi button: running -> stop it; stopped -> start it."""
        if self._wm_busy:
            return
        self._wm_busy = key
        self.update(CLOCK)

        def work():
            err = ""
            try:
                err = wm_stop(key) if wm_running()[key] else wm_start(key)
            except Exception:  # noqa: BLE001
                log("window manager switch failed:\n" + traceback.format_exc())
                err = "Couldn't switch Komorebi  -  see >log"
            self.wm_done.emit(err)
        threading.Thread(target=work, name="SynapseWM", daemon=True).start()

    def _open_dotfiles(self, full):
        dirs = dotfiles_dirs(self.cfg)
        path = dirs[1] if full and len(dirs) > 1 else dirs[0]
        if not os.path.isdir(path):
            self._count = "Folder not found: " + path
            self.update()
            return
        try:
            os.startfile(path)
        except OSError:
            self._count = "Couldn't open " + path
            self.update()
            return
        self.close_launcher()

    def _wm_finished(self, err):
        self._wm_busy = None
        self.wm_state = wm_running()
        if err:
            self._count = err
        self.update(CLOCK)
        self.update()

    def _got_weather(self, d):
        self.weather = d
        self.update(CARD)

    def _got_temps(self, d):
        self.temps["gpu"] = d.get("gpu")
        if self.temps["gpu"] is not None:
            self.hist["gpu"].append(self.temps["gpu"])
        self.update(QRect(RIGHT_X, TILES[0].y(), RIGHT_W, TILES[0].height()))

    # ---- keys + outside click
    def eventFilter(self, obj, e):
        if obj is self.edit and e.type() == QEvent.Type.KeyPress:
            k = e.key()
            if k in (Qt.Key.Key_Up, Qt.Key.Key_Down) and e.modifiers() & Qt.KeyboardModifier.AltModifier:
                self._history_step(k == Qt.Key.Key_Up)            # (normally KeyGrab delivers these, ahead of whkd)
            elif k == Qt.Key.Key_Tab:
                self._autocomplete()                              # Tab completes; it never moves the highlight
            elif k == Qt.Key.Key_Down:
                self.list.move_sel(1)
            elif k in (Qt.Key.Key_Up, Qt.Key.Key_Backtab):
                self.list.move_sel(-1)
            elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                value = self.edit.text().strip()
                if value.startswith(">"):
                    if not self.command_history or self.command_history[-1] != value:
                        self.command_history.append(value)
                        self.command_history = self.command_history[-100:]
                    self.command_history_index = len(self.command_history)
                    self._history_draft = ""
                mods = e.modifiers()
                ctrl, shift = bool(mods & Qt.KeyboardModifier.ControlModifier), bool(mods & Qt.KeyboardModifier.ShiftModifier)
                self.activate("admin" if ctrl and shift else "reveal" if shift else None)
            elif k == Qt.Key.Key_Escape:
                self.close_launcher()
            elif k == Qt.Key.Key_B and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.toggle_panel()
            elif k == Qt.Key.Key_K and e.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.edit.selectAll()
                self.edit.setFocus()
            else:
                return False
            return True
        return super().eventFilter(obj, e)

    def _autocomplete(self):
        """Tab: finish what is typed from the highlighted result.
        >ta   -> >taskbar        (the highlighted command suggestion)
        >zen  -> >zen            (adds the space so arguments can follow),  >zen o -> >zen on
        chr   -> Google Chrome   (the highlighted app),  "rep -> "report.docx  (the highlighted file)"""
        text, it = self.edit.text(), self.list.current()
        if not it:
            return False
        kind, new = it.get("kind"), None
        if kind == "hint":
            new = it["fill"]
        elif text.lstrip().startswith(">"):
            m = re.match(r">\s*([A-Za-z]*)(\s*)(.*)$", text.lstrip(), re.S)
            word, space, arg = m.groups()
            if word and not space:
                new = ">%s " % word
            elif arg and not arg.strip().count(" "):
                opts = ("on", "off", "toggle", "show", "hide") if CMD_ALIAS.get(word.lower(), word.lower()) == "taskbar" \
                    else ("on", "off", "toggle")
                if CMD_ALIAS.get(word.lower(), word.lower()) in ("taskbar", "customizations", "zen", "animations", "acrylic", "lcbar"):
                    new = next((">%s %s" % (word, o) for o in opts if o.startswith(arg.strip().lower()) and o != arg.strip().lower()), None)
        elif kind == "app" and not text.lstrip().startswith(("=", '"')):
            new = it["title"]
        elif kind == "file" and text.lstrip().startswith('"'):
            new = '"' + it["title"]
        if new and new != text:
            self.edit.setText(new)
            self.edit.setCursorPosition(len(new))
            return True
        return False

    def event(self, e):
        if e.type() == QEvent.Type.WindowDeactivate and self._ready and not self._drag and self._wd is None and not self._dialog_open:
            QTimer.singleShot(0, self.close_launcher)
        return super().event(e)

    def _poll_mouse(self):
        try:
            down = any(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000 for vk in VK_BUTTONS)
        except Exception:  # noqa: BLE001
            return
        if down and not self._down and self._ready and not self._closing:
            if not QRect(self.x(), self.y(), self._vis_w, self._h).contains(QCursor.pos()):
                self.close_launcher()
        self._down = down

    # ---- show / hide: the window stays put; the right-pane cards slide + fade in, the list rows stagger in
    def _on_fade(self, v):
        self._t = float(v)
        self.update(QRect(RIGHT_X - 4, 0, RIGHT_W + 28, H))

    def _fade_to(self, end, ms, curve):
        self.fade.stop()
        self.fade.setStartValue(self._t)
        self.fade.setEndValue(end)
        self.fade.setDuration(ms)
        self.fade.setEasingCurve(curve)
        self.fade.start()

    def _fade_done(self):
        if self._closing:
            self._closing = False
            self.hide()
            self.poll.stop()
            self.stat_timer.stop()
            self.watch.setInterval(3000)                   # theme file is only checked every 3 s while hidden
            self._media_run(False)
            self.gpu_mon.stop()                            # no helper processes while hidden
            self._hidden_at = time.time()
            self._shot = self._glass = self._blur = self._glass_key = self._grain = self._shot_scr = None      # give the screenshot back
            QTimer.singleShot(4000, self._release_window)    # trimming right away only made the next open page-fault everything back in

    def _release_window(self):
        """While hidden, destroy the native window (and its backing surface) so dwm.exe can free what it
        holds for it. show() recreates it on the next open. Off by default; set "release_when_hidden": true in launcher_settings.json to use it."""
        if not (self.isVisible() or self._closing) and self.cfg.get("release_when_hidden", False):
            try:
                self.destroy()
            except Exception:  # noqa: BLE001
                log("could not release the window:\n" + traceback.format_exc())
        if not (self.isVisible() or self._closing):
            trim_memory()

    def _default_pos(self):
        """(centre x, top y): the position you dragged it to (kept between runs), else top-centre of the main screen."""
        pos = self.cfg.get("pos")
        try:
            if pos:
                cx, y = int(pos[0]), int(pos[1])
                g = (QApplication.screenAt(QPoint(cx, y)) or QApplication.primaryScreen()).geometry()
                return (max(g.left() + W // 2, min(g.right() - W // 2, cx)), max(g.top(), min(g.bottom() - H, y)))
        except (TypeError, ValueError, IndexError):
            pass
        scr = QApplication.primaryScreen().geometry()
        return scr.center().x(), max(scr.top() + 8, min(scr.top() + int(scr.height() * TOP_FRACTION), scr.bottom() - H - 8))

    def open_launcher(self):
        self._opened_at = time.time()
        self._closing, self._ready, self._down, self.show_all = False, False, True, False   # _down: ignore the opening click
        self._cx, self._y = self._default_pos()
        self._apply_k(self._k)
        self.edit.clear()
        if not self._scanned:                                      # apps are indexed once at startup; use >scan for new installs
            self._scan()
        self.refresh("")
        self._tick()
        self._t = 0.0
        self._take_shot()                              # opaque mode: snapshot the screen while the launcher is still hidden
        self.show()
        self._apply_glass()
        self.raise_()
        self.activateWindow()
        try:                                          # Windows only lets the foreground app take focus; this nudges it
            u = ctypes.windll.user32
            u.keybd_event(0x12, 0, 0, 0)
            u.keybd_event(0x12, 0, 2, 0)
            u.SetForegroundWindow(int(self.winId()))
        except Exception:  # noqa: BLE001
            pass
        self.edit.setFocus()
        self.watch.setInterval(700)
        self._check_theme()                                # pick up a theme change made while it was hidden
        self.poll.start()
        self.stat_timer.start()
        self._yt_anim_sync()
        QTimer.singleShot(450, self._tick)                 # second CPU sample soon after opening
        if self.cfg.get("animations", True):
            self._fade_to(1.0, 320, QEasingCurve.Type.OutCubic)
        else:
            self.fade.stop()
            self._t = 1.0
            self.update()
        self._media_run(self._k_target > 0.5)
        QTimer.singleShot(150, lambda: setattr(self, "_ready", True))
        self.keygrab.start()                               # Alt+Up / Alt+Down ahead of whkd while we are open

    def close_launcher(self):
        if not self.isVisible() or self._closing:
            return
        self._closing = True
        self._hidden_at = time.time()
        self.keygrab.stop()                                # hand Alt+Up / Alt+Down back to whkd / Komorebi at once
        if self.cfg.get("animations", True):
            self._fade_to(0.0, 90, QEasingCurve.Type.InCubic)
        else:
            self.fade.stop()
            self._t = 0.0
            self._fade_done()

    def toggle(self):
        if self.isVisible() and not self._closing:
            self.close_launcher()
        elif time.time() - self._hidden_at > 0.35:     # the click that closed it also re-launches us
            self.open_launcher()

    # ---- opaque mode: screenshot behind the launcher, blurred + tinted by us (instead of live acrylic)
    def _take_shot(self):
        self._shot = self._glass = self._blur = self._glass_key = None
        if self._cx is None:
            return
        try:
            scr = QApplication.screenAt(QPoint(self._cx, self._y)) or QApplication.primaryScreen()
            self._grab_screen(scr)
        except Exception:  # noqa: BLE001
            log("screen snapshot failed:\n" + traceback.format_exc())
            self._shot = self._glass = self._blur = None

    def _grab_screen(self, scr):
        """Snapshot of the WHOLE screen. The launcher just slides over it when you drag it, so the glass always
        shows what is really behind it, wherever you put it."""
        self._shot_scr = scr
        sg = scr.geometry()
        full = scr.grabWindow(0)
        # Don't trust full.devicePixelRatio(): on scaled displays it can disagree with the real pixel size.
        # Work out the true pixels-per-logical-pixel from the image we actually received.
        sx = full.width() / max(1, sg.width())
        sy = full.height() / max(1, sg.height())
        d = (sx + sy) / 2.0
        full.setDevicePixelRatio(1.0)                  # the source rect in _paint_backdrop is in raw pixels
        self._shot = full
        self._shot_scale = d
        self._shot_lsize = (max(1, sg.width()), max(1, sg.height()))
        self._shot_org = QPoint(sg.x(), sg.y())
        self._blur = self._glass = self._glass_key = None
        self._make_glass()

        
    def _regrab(self, scr):
        """Dragged onto another monitor: hide for a blink, grab that screen, show again."""
        if self._regrabbing:
            return
        self._regrabbing = True
        self._shot_scr = scr
        self._park = self.pos()
        self.move(-30000, -30000)                       # off-screen for a blink (no layered window, nothing extra for dwm)
        QTimer.singleShot(90, lambda: self._regrab_done(scr))

    def _regrab_done(self, scr):
        try:
            if self.isVisible() and not self._closing:
                self._grab_screen(scr)
        except Exception:  # noqa: BLE001
            log("screen snapshot failed:\n" + traceback.format_exc())
        finally:
            self.move(self._park)
            self._regrabbing = False
            self.update()

    def moveEvent(self, e):                            # the backdrop is a slice of the snapshot: moving = repaint
        super().moveEvent(e)
        self.update()

    def _make_glass(self):
        """Blurred + tinted copy of the snapshot (same stack the live acrylic gave: blur, then a colour tint).
        Returns True when something was rebuilt (it skips the work when theme / blur / transparency are unchanged)."""
        on = bool(self.cfg.get("acrylic", True))
        key = (int(self.t["acrylic"]), round(self._opacity(), 3), on, id(self._shot))
        if key == getattr(self, "_glass_key", None):
            return False
        self._glass_key = key
        if self._shot is None or self._shot.isNull() or not on:
            self._glass = None
            return True
        ig, sm = Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
        if self._blur is None:                         # the blur itself only has to be made once per opening
            lw, lh = self._shot_lsize
            hw, hh = max(1, lw // 4), max(1, lh // 4)                          # the glass itself is kept at half size: it is blurry anyway
            img = self._shot.toImage().convertToFormat(QImage.Format.Format_RGB32)
            qw, qh = max(1, lw // 12), max(1, lh // 12)                        # same strength as before: 1/12 of the screen
            while img.width() > qw * 2 and img.height() > qh * 2:
                img = img.scaled(img.width() // 2, img.height() // 2, ig, sm)
            img = img.scaled(qw, qh, ig, sm)
            img = img.scaled(hw, hh, ig, sm)
            img = _blur_image(img, 2.6)                                        # smooths the stretch: no blocks / diamonds
            opaque = QImage(img.size(), QImage.Format.Format_RGB32)           # glass must be fully opaque, nothing sharp may show through
            opaque.fill(QColor(14, 16, 24))
            q = QPainter(opaque)
            q.drawImage(0, 0, img)
            q.end()
            self._blur, self._blur_scale = opaque, hw / lw
        pm = QPixmap.fromImage(self._blur)
        a = int(self.t["acrylic"])
        q = QPainter(pm)
        q.fillRect(pm.rect(), QColor(a & 255, (a >> 8) & 255, (a >> 16) & 255, min(255, int(0x60 * self._opacity()))))
        q.end()
        self._glass = pm
        return True

    def _paint_backdrop_at(self, p, w, h, gx, gy, r):
        """Fake glass for a w x h window whose top-left is at (gx, gy) on screen. Used by the launcher and the yt dialog."""
        shot, ss = self._shot, self._shot_scale
        ox, oy = gx - self._shot_org.x(), gy - self._shot_org.y()        # where this window sits inside the snapshot
        base = QColor(14, 16, 24)
        if shot is not None and not shot.isNull():                        # the real desktop, corners only (the rest is covered)
            for cx, cy in ((0, 0), (w - r, 0), (0, h - r), (w - r, h - r)):
                p.drawPixmap(QRectF(cx, cy, r, r), shot, QRectF((ox + cx) * ss, (oy + cy) * ss, r * ss, r * ss))
        else:
            p.fillRect(0, 0, w, h, base)
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(0, 0, w, h), r, r)
        p.setClipPath(shape)                           # everything below is drawn inside the rounded glass shape
        p.fillRect(0, 0, w, h, base)                   # solid base: the sharp screenshot can never show through
        if self._glass is not None:
            s = self._blur_scale
            p.save()
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            p.drawPixmap(QRectF(0, 0, w, h), self._glass, QRectF(ox * s, oy * s, w * s, h * s))
            p.restore()
            if self.cfg.get("grain", False):
                if self._grain is None:
                    self._grain = _grain_tile(self.devicePixelRatioF())
                p.fillRect(QRectF(0, 0, w, h), QBrush(self._grain))

    # ---- painting: one cached pixmap + text and a few shapes on top
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self._paint_backdrop_at(p, self.width(), self.height(), self.x(), self.y(), R)
        p.drawPixmap(0, 0, self._static)
        t, st = self.t, self.stats
        sub, accent, white = qc(t["sub"]), qc(t["accent"]), QColor("white")
        AL = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        AR = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        mono = lambda px, w=QFont.Weight.Normal: _font(px, w, mono=True)     # noqa: E731
        now = time.localtime()

        p.setPen(sub)
        p.setFont(mono(10))
        footer_rect = QRectF(LEFT_X, FOOT_Y - 26, LEFT_W - 8, 22)
        if self._yt_state in ("running", "done") and self._yt_d.get("title"):
            self._paint_yt_footer(p, footer_rect, accent, white)
        else:
            footer_status = QFontMetrics(p.font()).elidedText(
                self._yt_status or self._count, Qt.TextElideMode.ElideRight, int(footer_rect.width())
            )
            p.drawText(footer_rect, AR, footer_status)

        # Download progress bar along the bottom of the launcher: eased fill, shimmer, sweeping when the size is unknown.
        if self._yt_state in ("running", "done"):
            running = self._yt_state == "running"
            draw_progress_bar(p, QRectF(LEFT_X + 2, self.height() - 14, LEFT_W - 12, 6),
                              None if (running and self._yt_progress < 0) else (self._yt_shown if running else 100.0),
                              accent, done=not running)

        def lead(i):
            a = max(0.0, min(1.0, self._t * 2.3 - i * 0.24)) * self._k
            return a, (1 - a) * 12

        def begin(i):
            a, dy = lead(i)
            p.save()
            p.setOpacity(a)
            p.translate(0, dy)

        begin(0)                                              # image card (media + clock)
        self._paint_card(p, now)
        p.restore()

        tint = lambda a: qc("rgb(%s)" % t["tint"], a)         # noqa: E731

        begin(1)                                              # theme color
        p.setPen(sub)
        p.setFont(mono(11, QFont.Weight.DemiBold))
        p.drawText(QRectF(THEME.x() + 16, THEME.y() + 8, 150, 26), AL, "THEME COLOR")
        p.setPen(QPen(white, 1.5))
        p.setBrush(accent)
        p.drawEllipse(QRectF(COLOR_BTN.x() + 4, COLOR_BTN.y() + 6, 14, 14))
        p.setPen(white)
        p.setFont(mono(12))
        p.drawText(RESET_R, AR, "Reset")
        if not self.color_editor_open:
            # TRACK_Y is the collapsed hue-slider centre.  Do not rely on the
            # local `track_y` created inside _build_cache(); that local is not
            # in scope here and caused paintEvent to abort before dashboard tiles.
            cx = TRACK_X0 + self.hue_deg / 359.0 * (TRACK_X1 - TRACK_X0)
            p.setBrush(QColor(*rot_rgb((76, 194, 255), self.hue_deg)))
            p.setPen(QPen(white, 2.2))
            p.drawEllipse(QPointF(cx, TRACK_Y), 8, 8)
        p.restore()

        # The advanced color editor expands through the dashboard area. Hide
        # only these right-side dashboard widgets for the duration of editing;
        # when the color circle is clicked again they are painted normally.
        if not self.color_editor_open:
            bat = st["bat"]
            if bat is None:
                note = "No battery"
            elif st["charging"]:
                note = "Charging"
            elif st["plug"]:
                note = "Plugged in"
            elif st["life"]:
                note = "%dh %dm left" % (st["life"] // 3600, st["life"] % 3600 // 60)
            else:
                note = "On battery"
            fmt = lambda v: ("%d%%" % round(v)) if v is not None else "--"             # noqa: E731
            tiles = [("Battery", "%d%%" % bat if bat is not None else "AC", note),
                     ("CPU Load", fmt(self.temps["cpu"]), ""), ("GPU Load", fmt(self.temps["gpu"]), "")]
            cols = [C_GREEN, accent, C_PURPLE]
            for i, (r, (label, val, small)) in enumerate(zip(TILES, tiles)):
                begin(i + 2)
                col = cols[i]
                fillc, edge = QColor(col), QColor(col)
                fillc.setAlpha(22)
                edge.setAlpha(95)
                p.setBrush(fillc)
                p.setPen(QPen(edge, 1))
                p.drawRoundedRect(QRectF(r).adjusted(.5, .5, -.5, -.5), 14, 14)
                if i == 0:
                    draw_battery(p, r.x() + 9, r.y() + 6, bat if bat is not None else 100, col)
                elif i == 1:
                    draw_chip(p, r.x() + 7, r.y() + 4, col)
                else:
                    draw_gpu(p, r.x() + 7, r.y() + 4, col)
                p.setPen(white)
                p.setFont(mono(10))
                p.drawText(QRectF(r.x() + 52, r.y() + 7, r.width() - 56, 16), AL, label)
                p.setFont(mono(17, QFont.Weight.DemiBold))
                p.drawText(QRectF(r.x() + 52, r.y() + 22, r.width() - 56, 24), AL, val)
                if i == 0:                                        # progress bar + status line
                    bx, by, bw = r.x() + 12, r.y() + 52, r.width() - 24
                    p.setPen(Qt.PenStyle.NoPen)
                    trk = QColor(col)
                    trk.setAlpha(50)
                    p.setBrush(trk)
                    p.drawRoundedRect(QRectF(bx, by, bw, 5), 2.5, 2.5)
                    p.setBrush(col)
                    p.drawRoundedRect(QRectF(bx, by, bw * max(0, min(100, bat if bat is not None else 100)) / 100.0, 5), 2.5, 2.5)
                    tx = r.x() + 12
                    if st["plug"] or st["charging"]:
                        draw_bolt(p, tx, r.y() + 60, col, 0.8)
                        tx += 15
                    p.setPen(col)
                    p.setFont(mono(9))
                    p.drawText(QRectF(tx, r.y() + 58, r.right() - tx - 6, 18), AL, small)
                else:
                    draw_spark(p, QRectF(r.x() + 10, r.y() + 48, r.width() - 20, 24),
                               list(self.hist["cpu" if i == 1 else "gpu"]), col)
                p.restore()

            begin(5)                                              # quote
            p.drawPixmap(QUOTE_R.topLeft(), self._quote)
            p.restore()

            begin(6)                                              # Komorebi switch | dotfiles | uptime
            rect = WM_BTNS["komorebi"]
            on, busy = self.wm_state.get("komorebi", False), self._wm_busy == "komorebi"
            r = QRectF(rect).adjusted(.5, .5, -.5, -.5)
            p.setPen(QPen(accent if on else tint(55), 1))
            p.setBrush(qc(t["accent"], 52) if on else tint(14))
            p.drawRoundedRect(r, 11, 11)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 196, 64) if busy else (QColor(46, 230, 140) if on else QColor(255, 255, 255, 75)))
            p.drawEllipse(QPointF(rect.x() + 15, rect.y() + 14), 4, 4)
            p.setPen(white)
            p.setFont(mono(12, QFont.Weight.DemiBold))
            p.drawText(QRectF(rect.x() + 27, rect.y() + 5, rect.width() - 31, 18), AL, WM["komorebi"]["label"])
            p.setPen(sub)
            p.setFont(mono(9))
            p.drawText(QRectF(rect.x() + 13, rect.y() + 25, rect.width() - 18, 14), AL,
                       "switching..." if busy else ("running" if on else "stopped"))
            rect = WM_BTNS["dotfiles"]                            # click = ~/.config, Alt+click = the full dotfiles folder
            p.setPen(QPen(tint(55), 1))
            p.setBrush(tint(14))
            p.drawRoundedRect(QRectF(rect).adjusted(.5, .5, -.5, -.5), 11, 11)
            p.setPen(accent)
            p.setFont(_font(15, icon=True))
            p.drawText(QRectF(rect.x() + 12, rect.y() + 11, 22, 22), Qt.AlignmentFlag.AlignCenter, "\uE8B7")
            p.setPen(white)
            p.setFont(mono(12, QFont.Weight.DemiBold))
            p.drawText(QRectF(rect.x() + 40, rect.y() + 12, rect.width() - 44, 20), AL, "Dotfiles")
            up = self.stats.get("up")
            p.setPen(sub)
            p.setFont(mono(9, QFont.Weight.DemiBold))
            p.drawText(QRectF(CLOCK.x() + 264, CLOCK.y() + 12, 90, 14), AL, "UPTIME")
            p.setPen(white)
            p.setFont(mono(13, QFont.Weight.DemiBold))
            if up is not None:
                d_, rem = divmod(int(up), 86400)
                h_, m_ = divmod(rem, 3600)
                up_txt = ("%dd %dh" % (d_, h_)) if d_ else ("%dh %dm" % (h_, m_ // 60))
            else:
                up_txt = "--"
            p.drawText(QRectF(CLOCK.x() + 264, CLOCK.y() + 28, 90, 20), AL, up_txt)
            p.restore()

        p.setClipping(False)
        p.setOpacity(1.0)                                     # window outline (its right edge moves)
        op_ = QPainterPath()
        op_.addRoundedRect(QRectF(0, 0, self._vis_w - 1, self._h - 1), R, R)
        p.setPen(QPen(QColor(*t["outline"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(op_)
        p.end()


def main():
    sock = QLocalSocket()
    sock.connectToServer(SERVER)
    if sock.waitForConnected(120):                # already running -> toggle it
        sock.write(b"toggle")
        sock.flush()
        sock.waitForBytesWritten(300)
        return
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    _df = QFont()
    _df.setFamilies([TEXT_FONT] + FALLBACKS)
    _df.setPixelSize(12)
    app.setFont(_df)                      # menus, tray, file dialogs: Caskaydia too
    QLocalServer.removeServer(SERVER)
    server = QLocalServer()
    server.listen(SERVER)
    win = Launcher()
    win.server = server
    icon = QIcon(tray_pixmap())
    app.setWindowIcon(icon)
    win.setWindowIcon(icon)
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():                # tray icon: click toggles, right-click menu
        tray = QSystemTrayIcon(icon, app)
        tray.setToolTip("Synapse")
        menu = QMenu()
        act_toggle, act_quit = QAction("Open / close Synapse", menu), QAction("Exit", menu)
        act_toggle.triggered.connect(win.toggle)
        act_quit.triggered.connect(win.quit_app)
        menu.addAction(act_toggle)
        menu.addSeparator()
        menu.addAction(act_quit)
        tray.setContextMenu(menu)
        tray.activated.connect(lambda r: win.toggle() if r in (QSystemTrayIcon.ActivationReason.Trigger,
                                                              QSystemTrayIcon.ActivationReason.DoubleClick) else None)
        tray.show()
        win._tray, win._tray_menu = tray, menu                  # keep references alive
    win.hotkey.connect(win.toggle)                         # global Alt+Space, handled in its own thread
    start_hotkey_thread(win.hotkey.emit)

    def on_conn():
        conn = server.nextPendingConnection()
        if conn:
            conn.readyRead.connect(lambda c=conn: (c.readAll(), win.toggle()))
    server.newConnection.connect(on_conn)
    if "--hidden" in sys.argv:
        win._scan()
        QTimer.singleShot(5000, trim_memory)
    else:
        win.open_launcher()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        log("fatal:\n" + traceback.format_exc())
        raise