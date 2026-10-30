"""

Vapor - a Caelestia-style bar for Windows.

Run:      pythonw vapor.pyw           (or `python vapor.pyw` if you want to see errors in the console)
          or the built Vapor.exe (see build.ps1 / vapor.spec)
Needs:    run install_deps.bat (pyside6 pillow pycaw comtypes numpy winrt-* pyaudiowpatch)
          only pyside6 is required. pycaw = volume, winrt = media widget, pillow = wallpaper colour + media art,
          numpy + pyaudiowpatch = audio visualizer. a missing one just turns off its own widget.
Won't start? run launch_vapor.bat, it shows errors in a console. Startup errors also pop up as a
message box and go into the log.
Log:      %LOCALAPPDATA%\vapor\vapor.log   (QML errors end up here too)
Flags:    --no-appbar   don't reserve screen space (handy while testing)
Hotkey:   Alt+W hides / shows the bar with a slide. Change HIDE_HOTKEY below.
"""

import asyncio
import codecs
import ctypes
import gc
import hashlib
import io
import json
import logging
import math
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import traceback
import winreg
from ctypes import wintypes
from pathlib import Path

# logging + the error dialog have to come before the Qt imports, otherwise a broken PySide6 dies
# silently when started with pythonw
FROZEN = bool(getattr(sys, "frozen", False))      # True when running as the PyInstaller Vapor.exe
if FROZEN:
    HERE = Path(getattr(sys, "_MEIPASS", "") or Path(sys.executable).resolve().parent)   # bundled files: Vapor.qml, cc_backend ...
    APPDIR = Path(sys.executable).resolve().parent                                        # next to Vapor.exe: config.json, files/, vaporctl.exe
else:
    HERE = APPDIR = Path(__file__).resolve().parent
DATA = Path(os.environ.get("LOCALAPPDATA", str(APPDIR))) / "vapor"
DATA.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(DATA / "vapor.log"), level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8",
)
log = logging.getLogger("vapor")
sys.excepthook = lambda *a: log.error("unhandled", exc_info=a)


def _fatal(msg, code=1):
    log.error(msg)
    try:
        ctypes.windll.user32.MessageBoxW(None, str(msg)[:1500], "Vapor", 0x10)
    except Exception:
        pass
    sys.exit(code)


try:
    from PySide6.QtCore import (
        QAbstractListModel, QFileInfo, QModelIndex, QObject, QSize, Qt, QTimer, QUrl,
        Property, Signal, Slot, qInstallMessageHandler,
    )
    from PySide6.QtGui import QGuiApplication, QImage, QPainter, QFont, QColor
    from PySide6.QtQml import QQmlApplicationEngine
    try:
        from PySide6 import QtQuick  # noqa: F401  (makes sure the QML window type is registered)
    except ImportError:
        pass
    try:
        from PySide6.QtGui import QFileIconProvider
    except ImportError:  # older layouts
        from PySide6.QtWidgets import QFileIconProvider
except Exception:
    _fatal("Could not load PySide6:\n\n" + traceback.format_exc()[-900:]
           + "\nFix:  py -m pip install pyside6")

# ---- settings ----
PILL_H = 36              # bar height, keep in sync with barH in Vapor.qml
RESERVE_H = 36           # screen space the app bar reserves at the top
CLAMP_MAXIMIZED = True    # without komorebi: keep maximized windows inside the glass frame ourselves (works even if Windows ignores the app bars)
# padding like YASB's `padding: {top, left, bottom, right}`, only used when komorebi is offline (logical px). It's added
# on top of the bar / frame to get the space the app bars reserve, so maximize + snap keep that gap.
# with komorebi online this is ignored, it uses RESERVE_H / FRAME_W through global-work-area-offset.
OFFLINE_PAD = {"top": 1, "left": 0, "right": 0, "bottom": 0}
APP_TOP_PAD = OFFLINE_PAD["top"]
# the glass frame around the other three edges (frameW) and the inner corner radius (frameR) live in
# Vapor.qml. an app bar window can only reserve one edge, so the thin left / right / bottom frame windows
# ("Vapor L / R / B") each reserve their own edge too. that way Windows (and komorebi, which tiles inside
# the work area) keeps every app inside the glass and not under it.
RESERVE_FRAME = True     # also reserve the side + bottom frame so apps don't poke out under it
FRAME_W = 8              # frame thickness in logical px, keep in sync with frameW in Vapor.qml
USE_APPBAR = "--no-appbar" not in sys.argv
STRIP_H = RESERVE_H + 20               # main window height in logical px: the bar plus the rounded inner corners (popups get their own window)
HIDE_HOTKEY = "alt+w"    # global hotkey to hide / show the bar, like "ctrl+alt+b" or "win+f2", "" turns it off
HIDE_RELEASES_SPACE = True   # give the reserved space back while hidden
HIDE_ON_FULLSCREEN = True
CONTROL_CENTER = str(APPDIR / "control_center.exe") if FROZEN else str(HERE / "control_center.pyw")   # old stand-alone control center next to this file, only used by B.openControlCenter
KOMOREBI_MONITOR = 0     # which komorebi monitor the workspace dots follow
AUTO_SWITCH_OUTPUT = True  # make a playback device the default as soon as it shows up (headphones, Bluetooth, USB DAC ...)
VIZ_RANGE_DB = 38.0     # how many dB under the loudest band still show (lower = more contrast, higher = flatter)
OUTLINE_MAX_SAT = 0.62    # max saturation of the wallpaper outline / icon colour (1.0 = neon, 0.5 = soft pastel)
FILL_DARKNESS = 0.8    # shell brightness: 1.0 = original, 0.6 = clearly darker, 0.4 = very dark (outline isn't affected)
VIZ_FALL = 0.82         # how fast the bars fall each frame (0.7 = snappy, 0.9 = floaty)
WIFI_POLL_S = 60         # backup re-check of the network name, every check starts a PowerShell process. normally it's re-checked as soon as Windows reports a change
PHONES_POLL_S = 2        # how often the playback devices' registry fingerprint is checked (cheap, no process). the PowerShell scan only runs when it changes
TRIM_MEMORY = True       # every 2 min hand unused memory pages back to Windows, so Task Manager shows the real working set
VIZ_ENABLED = True       # audio visualizer (pip install numpy pyaudiowpatch)
TRAY_ENABLED = True      # system tray, reads Explorer's notification-area icons (pinned ones sit right of the visualizer)
APP_NOTIFICATIONS = True   # show other apps' Windows notifications (Discord, Chrome, mail ...) in Vapor's own card at the top
NOTIF_POLL_S = 1.0        # how often Windows' notification database gets checked
TRAY_POLL_S = 2.0        # how often the tray icons are re-read
TRAY_HIDE_EXES = ("explorer.exe", "taskmgr.exe")   # programs whose tray icons stay hidden: Windows' own battery / volume / network icons, the bar has its own
AVATAR_LOGICAL = 62        # px the picture is drawn at in the profile card (Vapor.qml: 68 px ring minus 2 x 3 px margin)

ICON_DIR = DATA / "icons"
ART_DIR = DATA / "art"
for _d in (ICON_DIR, ART_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CNW = 0x08000000  # CREATE_NO_WINDOW

# ---- win32 helpers ----
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi
shell32 = ctypes.windll.shell32

user32.GetForegroundWindow.restype = wintypes.HWND
for _name, _args in {
    "IsWindowVisible": [wintypes.HWND], "IsIconic": [wintypes.HWND], "IsZoomed": [wintypes.HWND],
    "GetWindowTextLengthW": [wintypes.HWND],
    "GetWindowTextW": [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],
    "GetClassNameW": [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int],
    "GetWindow": [wintypes.HWND, wintypes.UINT],
    "GetWindowLongW": [wintypes.HWND, ctypes.c_int],
    "GetWindowThreadProcessId": [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)],
    "ShowWindow": [wintypes.HWND, ctypes.c_int],
    "SetForegroundWindow": [wintypes.HWND],
    "PostMessageW": [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM],
    "GetWindowRect": [wintypes.HWND, ctypes.POINTER(wintypes.RECT)],
}.items():
    getattr(user32, _name).argtypes = _args
user32.GetWindow.restype = wintypes.HWND
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = ctypes.c_int
kernel32.GetLastError.restype = wintypes.DWORD
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

GWL_STYLE, GWL_EXSTYLE = -16, -20
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_EX_TOOLWINDOW, WS_EX_APPWINDOW = 0x80, 0x40000
SKIP_CLASSES = {
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow",
}
EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_exe_cache = {}


def pid_of(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def exe_of(pid):
    if pid in _exe_cache:
        return _exe_cache[pid]
    if len(_exe_cache) > 800:
        _exe_cache.clear()
    path = ""
    h = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if h:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            path = buf.value
        kernel32.CloseHandle(h)
    _exe_cache[pid] = path
    return path


def class_of(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


class _PROCENTRY(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCENTRY)]
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCENTRY)]
_procs = {"t": 0.0, "list": []}


def running_processes():
    """[(exe name lower, pid)] for every running process, re-read at most every 5 s."""
    if time.time() - _procs["t"] < 5 and _procs["list"]:
        return _procs["list"]
    out = []
    snap = kernel32.CreateToolhelp32Snapshot(2, 0)      # TH32CS_SNAPPROCESS
    if snap and snap != ctypes.c_void_p(-1).value:
        try:
            pe = _PROCENTRY()
            pe.dwSize = ctypes.sizeof(pe)
            ok = kernel32.Process32FirstW(snap, ctypes.byref(pe))
            while ok:
                out.append((pe.szExeFile.lower(), pe.th32ProcessID))
                ok = kernel32.Process32NextW(snap, ctypes.byref(pe))
        finally:
            kernel32.CloseHandle(snap)
    _procs["t"], _procs["list"] = time.time(), out
    return out


# Firefox-family browsers (Zen, Firefox ...) hand Windows a hash like 308046B0AF4A39CB as their app id, which
# the media widget used to show as the app name. these are the programs we look for instead.
BROWSER_NAMES = {"zen.exe": "Zen", "firefox.exe": "Firefox", "librewolf.exe": "LibreWolf", "waterfox.exe": "Waterfox",
                 "floorp.exe": "Floorp", "mullvadbrowser.exe": "Mullvad Browser", "tor.exe": "Tor Browser"}


def media_source_name(aumid):
    """Readable app name for a media session's app id."""
    src = re.split(r"[!\\/]", aumid or "")[-1]
    src = re.sub(r"\.exe$", "", src, flags=re.I)
    if re.fullmatch(r"[0-9A-Fa-f]{8,}", src) or re.fullmatch(r"[0-9.\-]+", src):
        names = {BROWSER_NAMES[n] for n, _ in running_processes() if n in BROWSER_NAMES}
        return names.pop() if len(names) == 1 else "Browser"
    return src.replace("_", " ").title()


user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                       wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t


def uwp_owner_exe(hwnd, host_pid):
    """Settings, Calculator and friends are windows of ApplicationFrameHost.exe (one generic icon for all of them).
        The program that really owns the window is the process of the CoreWindow inside it."""
    found = []

    def cb(ch, _lp):
        try:
            if class_of(ch) == "Windows.UI.Core.CoreWindow":
                p = pid_of(ch)
                if p and p != host_pid:
                    found.append(p)
        except Exception:
            pass
        return True

    user32.EnumChildWindows(hwnd, EnumProc(cb), 0)
    return exe_of(found[0]) if found else ""


def window_hicon(hwnd):
    """The icon the window offers itself (WM_GETICON), or 0."""
    for kind in (1, 2, 0):      # ICON_BIG, ICON_SMALL2, ICON_SMALL
        res = ctypes.c_size_t(0)
        if user32.SendMessageTimeoutW(hwnd, 0x007F, kind, 0, 0x0002, 120, ctypes.byref(res)) and res.value:
            return int(res.value)
    return 0


def list_windows(own_pid):
    """Taskbar-style window list in z-order, topmost first, plus the foreground window."""
    out = []

    @EnumProc
    def cb(hwnd, _lp):
        try:
            if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, 4):  # GW_OWNER
                return True
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if (ex & WS_EX_TOOLWINDOW) and not (ex & WS_EX_APPWINDOW):
                return True
            if user32.GetWindowTextLengthW(hwnd) == 0:
                return True
            cloaked = wintypes.DWORD(0)
            dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)  # DWMWA_CLOAKED
            if cloaked.value:
                return True
            if class_of(hwnd) in SKIP_CLASSES:
                return True
            pid = pid_of(hwnd)
            if pid == own_pid:
                return True
            exe = exe_of(pid)
            if not exe:
                return True
            uwp, hicon = False, 0
            if os.path.basename(exe).lower() == "applicationframehost.exe":
                real = uwp_owner_exe(hwnd, pid)
                if real:
                    exe, uwp = real, True
                    hicon = window_hicon(hwnd)
            buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, buf, 512)
            out.append({"hwnd": int(hwnd), "exe": exe, "title": buf.value, "uwp": uwp, "hicon": hicon})
        except Exception:
            pass
        return True

    user32.EnumWindows(cb, 0)
    return out, int(user32.GetForegroundWindow() or 0)


def fullscreen_check(hwnd, pw, ph, own_pid):
    if not hwnd or pid_of(hwnd) == own_pid or class_of(hwnd) in SKIP_CLASSES:
        return False
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    if r.left > 0 or r.top > 0 or r.right < pw or r.bottom < ph:
        return False
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    if (style & WS_CAPTION) == WS_CAPTION:
        return False
    if user32.IsZoomed(hwnd) and (style & WS_THICKFRAME):
        return False          # maximized custom-titlebar app (Discord, Spotify ...), not real fullscreen
    return True


OVERLAY_EXES = {"screenclippinghost.exe", "snippingtool.exe", "screensketch.exe"}   # screenshot overlays (Win+Shift+S, Snipping Tool)


def overlay_fullscreen(own_pid, pw, ph):
    """True while a screenshot overlay (Snipping Tool / Win+Shift+S) covers the whole screen. Those windows are never the
        foreground window the normal fullscreen check looks at, so the bar stayed on top of the screenshot."""
    found = []

    @EnumProc
    def cb(hwnd, _lp):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            if r.left > 0 or r.top > 0 or r.right < pw or r.bottom < ph:
                return True
            cloaked = wintypes.DWORD(0)
            dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), 4)     # DWMWA_CLOAKED
            if cloaked.value:
                return True
            pid = pid_of(hwnd)
            if pid != own_pid and os.path.basename(exe_of(pid) or "").lower() in OVERLAY_EXES:
                found.append(hwnd)
                return False
        except Exception:
            pass
        return True

    user32.EnumWindows(cb, 0)
    return bool(found)


def activate_window(hwnd):
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.keybd_event(0x12, 0, 0, 0)  # tap Alt so Windows lets us take the foreground
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(hwnd)


class APPBARDATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uCallbackMessage", wintypes.UINT),
                ("uEdge", wintypes.UINT), ("rc", wintypes.RECT), ("lParam", wintypes.LPARAM)]


shell32.SHAppBarMessage.argtypes = [wintypes.DWORD, ctypes.POINTER(APPBARDATA)]
shell32.SHAppBarMessage.restype = ctypes.c_size_t


def appbar_register(hwnd, width_px, height_px):
    abd = APPBARDATA()
    abd.cbSize = ctypes.sizeof(abd)
    abd.hWnd = hwnd
    shell32.SHAppBarMessage(0, ctypes.byref(abd))  # ABM_NEW
    abd.uEdge = 1  # ABE_TOP
    abd.rc = wintypes.RECT(0, 0, width_px, height_px)
    shell32.SHAppBarMessage(2, ctypes.byref(abd))  # ABM_QUERYPOS
    abd.rc.bottom = abd.rc.top + height_px
    shell32.SHAppBarMessage(3, ctypes.byref(abd))  # ABM_SETPOS


def appbar_register_edge(hwnd, edge, thick_px, pw, ph):
    """Reserves a thin strip along the left (0), right (2) or bottom (3) edge of the screen for `hwnd`."""
    abd = APPBARDATA()
    abd.cbSize = ctypes.sizeof(abd)
    abd.hWnd = hwnd
    shell32.SHAppBarMessage(0, ctypes.byref(abd))  # ABM_NEW
    abd.uEdge = edge
    if edge == 0:
        abd.rc = wintypes.RECT(0, 0, thick_px, ph)
    elif edge == 2:
        abd.rc = wintypes.RECT(pw - thick_px, 0, pw, ph)
    else:
        abd.rc = wintypes.RECT(0, ph - thick_px, pw, ph)
    shell32.SHAppBarMessage(2, ctypes.byref(abd))  # ABM_QUERYPOS (steps aside for the other bars)
    if edge == 0:
        abd.rc.right = abd.rc.left + thick_px
    elif edge == 2:
        abd.rc.left = abd.rc.right - thick_px
    else:
        abd.rc.top = abd.rc.bottom - thick_px
    shell32.SHAppBarMessage(3, ctypes.byref(abd))  # ABM_SETPOS


def appbar_remove(hwnd):
    abd = APPBARDATA()
    abd.cbSize = ctypes.sizeof(abd)
    abd.hWnd = hwnd
    shell32.SHAppBarMessage(1, ctypes.byref(abd))  # ABM_REMOVE


kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.SetProcessWorkingSetSize.argtypes = [wintypes.HANDLE, ctypes.c_size_t, ctypes.c_size_t]


def trim_memory():
    """Collect garbage, then hand every page that isn't in active use back to Windows."""
    gc.collect()
    if TRIM_MEMORY:
        kernel32.SetProcessWorkingSetSize(kernel32.GetCurrentProcess(), ctypes.c_size_t(-1), ctypes.c_size_t(-1))


def memory_loop(b):
    """Every 2 minutes: collect garbage and hand unused memory pages back to Windows."""
    while True:
        time.sleep(120)
        try:
            trim_memory()
        except Exception:
            log.exception("memory trim")


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD)]


# ---- wallpaper colour: the bar is one solid colour from the wallpaper, no blur / acrylic ----
def get_wallpaper():
    import winreg
    buf = ctypes.create_unicode_buffer(520)
    user32.SystemParametersInfoW(0x0073, 520, buf, 0)  # SPI_GETDESKWALLPAPER
    style, tile = "10", "0"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as k:
            style = str(winreg.QueryValueEx(k, "WallpaperStyle")[0])
            tile = str(winreg.QueryValueEx(k, "TileWallpaper")[0])
    except OSError:
        pass
    return buf.value, style, tile


def wallpaper_colors(src):
    """Picks one colour from the wallpaper and returns (fill, outline) as '#AARRGGBB'.
        fill is a dark, solid version of the main colour (dark enough for the white text),
        outline is the most vivid colour in the wallpaper, pushed to high saturation and brightness."""
    import colorsys
    from PIL import Image
    img = Image.open(src)
    try:
        img.draft("RGB", (192, 192))        # JPEGs decode at a fraction of the size, a lot faster on a 4K wallpaper
    except Exception:
        pass
    img = img.convert("RGB")
    img.thumbnail((96, 96))
    h = s = v = None
    oh = os_ = None            # hue / saturation for the outline
    try:
        q = img.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
        pal = q.getpalette()
        best = obest = -1.0
        for count, idx in q.getcolors():
            r, g, bl = pal[idx * 3: idx * 3 + 3]
            ch, cs, cv = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, bl / 255.0)
            score = count * (0.2 + cs) * (0.25 + min(cv, 0.8))   # big, colourful, not-black areas win
            if score > best:
                best, h, s, v = score, ch, cs, cv
            if cv > 0.2:                                    # outline: the most colourful area that isn't near-black
                sc2 = (count ** 0.5) * cs
                if sc2 > obest:
                    obest, oh, os_ = sc2, ch, cs
    except Exception:
        log.warning("palette failed, using the average colour", exc_info=True)
    if h is None:
        r, g, bl = img.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0))
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, bl / 255.0)

    def argb(a, hh, ss, vv):
        r, g, bl = (round(c * 255) for c in colorsys.hsv_to_rgb(hh, max(0.0, min(1.0, ss)), max(0.0, min(1.0, vv))))
        return "#%02x%02x%02x%02x" % (round(a * 255), r, g, bl)

    if oh is None:
        oh, os_ = h, s
    # a wallpaper with real colour gets a strongly saturated outline, a grey one stays grey (no hue to boost)
    o_sat = min(OUTLINE_MAX_SAT, max(os_ * 0.9, 0.4)) if os_ >= 0.12 else os_
    return argb(1.0, h, min(0.85, s * 1.1), (0.12 + 0.18 * v) * FILL_DARKNESS), argb(1.0, oh, o_sat, 1.0)


HINT_FILE = DATA / "wallpaper_next.txt"     # Harmony writes the new wallpaper's path here as soon as a change starts


def glass_loop(b):
    transcoded = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Themes/TranscodedWallpaper"
    last = None
    try:
        hint_sig = HINT_FILE.stat().st_mtime_ns          # whatever is there from an earlier session is old news
    except OSError:
        hint_sig = None
    hinted_until, tick = 0.0, 0
    while True:
        try:
            # 1) Harmony says which wallpaper is coming, recolour right away so the bar changes with the transition
            try:
                st = HINT_FILE.stat().st_mtime_ns
            except OSError:
                st = None
            if st is not None and st != hint_sig:
                hint_sig = st
                hp = HINT_FILE.read_text(encoding="utf-8", errors="ignore").strip()
                if hp and os.path.exists(hp):
                    fill, outline = wallpaper_colors(hp)
                    b.glassIn.emit((fill, outline))
                    hinted_until = time.time() + 8       # Windows' own copy shows up a moment later, don't recolour twice
            # 2) otherwise follow the wallpaper Windows is showing (about every 1.5 s)
            if tick % 6 == 0:
                path, style, tile = get_wallpaper()
                src = path if path and os.path.exists(path) else str(transcoded)
                sig = (src, os.path.getmtime(src) if os.path.exists(src) else 0,
                       os.path.getmtime(transcoded) if transcoded.exists() else 0)
                if sig != last and os.path.exists(src):
                    last = sig
                    if time.time() >= hinted_until:
                        fill, outline = wallpaper_colors(src)
                        b.glassIn.emit((fill, outline))
                        trim_memory()
        except Exception:
            log.exception("glass")
        tick += 1
        time.sleep(0.25)


# ---- background workers (they only emit signals, the Backend applies them on the UI thread) ----
def run_hidden(args, timeout=5):
    return subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout,
                          creationflags=CNW).stdout.decode("utf-8", errors="ignore")


def spawn(args):
    """Fire-and-forget child process, no console window."""
    try:
        return subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, creationflags=CNW)
    except OSError:
        log.warning("could not start %s", args[0], exc_info=True)
        return None


def _count(x):
    if isinstance(x, dict):
        x = x.get("elements", [])
    return len(x) if isinstance(x, (list, tuple)) else 0


def _layout_name(ws):
    if ws.get("monocle_container") is not None:
        return "monocle"
    if ws.get("maximized_window") is not None:
        return "maximized"
    if ws.get("tile") is False:
        return "floating"
    lay = ws.get("layout")
    if isinstance(lay, dict):  # {"Default": "BSP"} or {"Custom": [...]}
        lay = next(iter(lay.values()), "")
    if isinstance(lay, str) and lay:
        return re.sub(r"(?<=[a-z])(?=[A-Z])", "_", lay).lower()
    return "tiling" if lay else "bsp"


def parse_komorebi(raw):
    raw = raw[raw.find("{"):]
    return parse_komorebi_state(json.loads(raw))


def flatten_hwnds(node):
    """Every `hwnd` number nested inside a komorebi state element (maximized_window and so on)."""
    if isinstance(node, dict):
        out = [node["hwnd"]] if isinstance(node.get("hwnd"), int) else []
        for v in node.values():
            out += flatten_hwnds(v)
        return out
    if isinstance(node, (list, tuple)):
        out = []
        for v in node:
            out += flatten_hwnds(v)
        return out
    return []


def parse_komorebi_state(s):
    """`s` is komorebi's state as a dict, same as `komorebic state` prints and every pipe event carries."""
    mons = s["monitors"]["elements"]
    mon = mons[min(KOMOREBI_MONITOR, len(mons) - 1)]
    wss, fw = mon["workspaces"]["elements"], mon["workspaces"]["focused"]
    indices, populated, active = [], [], 0
    for i, w in enumerate(wss):
        pop = (_count(w.get("containers")) > 0 or _count(w.get("floating_windows")) > 0
               or w.get("monocle_container") is not None or w.get("maximized_window") is not None)
        if pop or i == fw:
            if i == fw:
                active = len(indices)
            indices.append(i)
            populated.append(bool(pop))
    layout = _layout_name(wss[fw]) if isinstance(fw, int) and 0 <= fw < len(wss) else "bsp"
    # hwnd(s) of the window komorebi has maximized on the focused workspace (empty = none)
    maximized = flatten_hwnds(wss[fw].get("maximized_window")) if isinstance(fw, int) and 0 <= fw < len(wss) else []
    return {"indices": indices, "populated": populated, "active": active, "layout": layout, "maximized": maximized}


KOMO_PIPE = "vapor"                 # komorebi writes its events to \\.\pipe\vapor
_komo_live = threading.Event()          # set while the event pipe is connected (the poller below stays quiet then)


def _komo_pipe_loop(b):
    """Event-driven komorebi. We own a named pipe and ask komorebi (`komorebic subscribe-pipe`) to write to it.
        Every event carries the full state, so the workspace dots follow the moment you switch (no 0.45 s polling,
        no komorebic process per tick). If komorebi stops or restarts the pipe breaks and we subscribe again."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID]
    k32.CreateNamedPipeW.restype = wintypes.HANDLE
    k32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
    k32.ConnectNamedPipe.restype = wintypes.BOOL
    k32.ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
                             ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    k32.ReadFile.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    invalid = ctypes.c_void_p(-1).value
    name = "\\\\.\\pipe\\" + KOMO_PIPE
    decoder = json.JSONDecoder()
    chunk = ctypes.create_string_buffer(65536)
    got = wintypes.DWORD(0)
    while True:
        if not shutil.which("komorebic"):
            time.sleep(10)
            continue
        # PIPE_ACCESS_INBOUND, byte mode, blocking, one instance, big buffer so komorebi never waits on us
        h = k32.CreateNamedPipeW(name, 0x1, 0x0, 1, 0, 1 << 20, 0, None)
        if not h or h == invalid:
            log.warning("komorebi pipe: could not create it (error %s)", ctypes.get_last_error())
            time.sleep(5)
            continue
        stop = threading.Event()

        def nudge(stop=stop):
            # keep asking komorebi to connect until it does, harmless while komorebi isn't running
            while not stop.is_set():
                spawn(["komorebic", "subscribe-pipe", KOMO_PIPE])
                stop.wait(4)

        threading.Thread(target=nudge, daemon=True).start()
        try:
            if not k32.ConnectNamedPipe(h, None) and ctypes.get_last_error() != 535:   # 535 = already connected
                time.sleep(2)
                continue
            stop.set()
            log.info("komorebi: event pipe connected")
            events = [0]                         # bumped per event so the initial sync can tell it's out of date
            prev = [None]

            def sync_once(seen=0):
                try:
                    d = parse_komorebi(run_hidden(["komorebic", "state"], timeout=3))
                    if events[0] == seen and d != prev[0]:
                        prev[0] = d
                        b.komoIn.emit(d)
                except Exception:
                    pass

            _komo_live.set()
            threading.Thread(target=sync_once, daemon=True).start()   # the pipe only talks on the next event
            dec = codecs.getincrementaldecoder("utf-8")(errors="replace")
            buf = ""
            while True:
                if not k32.ReadFile(h, chunk, 65536, ctypes.byref(got), None) or got.value == 0:
                    break                        # komorebi quit / restarted
                buf += dec.decode(chunk.raw[:got.value])
                last, pos = None, 0
                while True:                      # messages can arrive split or glued together, so take whole JSON objects
                    while pos < len(buf) and buf[pos] in " \r\n\t":
                        pos += 1
                    if pos >= len(buf):
                        break
                    try:
                        obj, pos = decoder.raw_decode(buf, pos)
                    except ValueError:
                        break                    # incomplete, wait for the rest
                    last = obj
                buf = buf[pos:] if len(buf) < 8_000_000 else ""
                if isinstance(last, dict) and isinstance(last.get("state"), dict):
                    events[0] += 1
                    try:
                        d = parse_komorebi_state(last["state"])
                    except Exception:
                        continue
                    if d != prev[0]:             # most events (focus, move ...) don't change the dots
                        prev[0] = d
                        b.komoIn.emit(d)
        except Exception:
            log.exception("komorebi pipe")
        finally:
            stop.set()
            _komo_live.clear()
            k32.CloseHandle(h)
        time.sleep(1)


def komorebi_loop(b):
    threading.Thread(target=_komo_pipe_loop, args=(b,), daemon=True).start()
    while True:
        if _komo_live.is_set():              # the pipe is delivering, nothing to poll
            time.sleep(1.0)
            continue
        data = None
        if not shutil.which("komorebic"):
            b.komoIn.emit(None)
            time.sleep(15)
            continue
        try:
            raw = run_hidden(["komorebic", "state"], timeout=3)
            if raw.strip():
                data = parse_komorebi(raw)
        except Exception:
            data = None
        b.komoIn.emit(data)
        time.sleep(0.45 if data is not None else 6.0)   # komorebi isn't running: only spawn komorebic every 6 s


def tasks_loop(b):
    own = os.getpid()
    last_fg, last_fs, last_sig = 0, None, None
    while True:
        try:
            wins, fg = list_windows(own)
            sig = (tuple((w["hwnd"], w["title"]) for w in wins), fg)
            if sig != last_sig:
                last_sig = sig
                b.tasksIn.emit((wins, fg))
            fs = bool(HIDE_ON_FULLSCREEN and (fullscreen_check(fg, b.pw, b.ph, own) or overlay_fullscreen(own, b.pw, b.ph)))
            if fs != last_fs:
                last_fs = fs
                b.fsIn.emit(fs)
            if fg != last_fg:
                last_fg = fg
                if fg and pid_of(fg) != own:
                    b.fgIn.emit()
        except Exception:
            log.exception("tasks")
        time.sleep(0.4)


NET_PS = (
    "$ErrorActionPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.Encoding]::UTF8; "
    "foreach ($p in Get-NetConnectionProfile) { "
    "if ($p.IPv4Connectivity -eq 'Disconnected' -and $p.IPv6Connectivity -eq 'Disconnected') { continue }; "
    "$a = Get-NetAdapter -InterfaceIndex $p.InterfaceIndex; "
    "$p.Name + '|' + $a.PhysicalMediaType }"
)


def _net_change_watcher(ev):
    """Sets `ev` whenever an IP address changes (connect, disconnect, roam). NotifyAddrChange blocks until then."""
    try:
        ip = ctypes.windll.iphlpapi
        ip.NotifyAddrChange.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        while True:
            ip.NotifyAddrChange(None, None)
            ev.set()
            time.sleep(1.0)                      # never spin, even if the call starts failing
    except Exception:
        log.exception("network watcher")


def _net_scan():
    best = ("", False, "")
    rank = {"wifi": 0, "ethernet": 1, "other": 2}
    for line in run_hidden(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", NET_PS],
                           timeout=15).splitlines():
        name, _, media = line.strip().partition("|")
        if not name:
            continue
        kind = "wifi" if "802.11" in media else "ethernet" if "802.3" in media else "other"
        if not best[1] or rank[kind] < rank[best[2]]:
            best = (name, True, kind)
    return best


def _cache_put(b, key, value):
    """Remembers a scan result in settings.json (only written when it changed) so the next start can show it at once."""
    try:
        if b._settings.get(key) != value:
            b._settings[key] = value
            save_settings(dict(b._settings))
    except Exception:
        log.exception("cache %s", key)


def wifi_loop(b):
    """Name + kind of the active connection. Works without Location permission, unlike `netsh wlan`.
        Event driven: PowerShell only runs at start, when Windows reports a network change, and as a slow fallback."""
    ev = threading.Event()
    threading.Thread(target=_net_change_watcher, args=(ev,), daemon=True).start()
    last = b._settings.get("lastNet") or {}
    if last.get("name"):             # the network from last time shows right away, the scan below confirms or fixes it
        b.wifiIn.emit((last["name"], True, last.get("kind") or "wifi"))
    while True:
        best, ok = ("", False, ""), False
        try:
            best, ok = _net_scan(), True
        except Exception:
            log.warning("network poll failed", exc_info=True)
        b.wifiIn.emit(best)
        if ok:
            _cache_put(b, "lastNet", {"name": best[0], "kind": best[2]} if best[1] else {})
        ev.wait(WIFI_POLL_S)
        if ev.is_set():
            time.sleep(2.0)                      # let the new connection settle before asking
        ev.clear()


OUTPUTS_PS = (
    "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
    "Get-PnpDevice -Class AudioEndpoint -Status OK -ErrorAction SilentlyContinue | "
    "Where-Object { $_.InstanceId -like '*{0.0.0.*' } | "
    "ForEach-Object { $_.InstanceId + '|' + $_.FriendlyName }"
)
PHONE_RE = re.compile(r"Headphone|Headset|Earphone|Earbuds|Buds|AirPods|Hands-Free", re.I)


def out_info(name):
    base = re.sub(r"\s*\(.*$", "", name).strip() or name
    if PHONE_RE.search(base):
        return "Headphones", "headphones", base
    if re.search(r"speaker", base, re.I):
        return "Speaker", "speaker", base
    return base, "speaker", base


def _audio_sig():
    """Fingerprint of the playback endpoints (id + state) read straight from the registry, no process and no WMI.
        None if the registry can't be read."""
    import winreg
    sig = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render") as k:
            i = 0
            while True:
                try:
                    name = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(k, name) as dk:
                        sig.append((name, winreg.QueryValueEx(dk, "DeviceState")[0]))
                except OSError:
                    pass
    except OSError:
        return None
    return tuple(sorted(sig))


def _scan_outputs():
    outs, phones = [], ""
    raw = run_hidden(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", OUTPUTS_PS], timeout=15)
    for line in raw.splitlines():
        iid, _, name = line.strip().partition("|")
        if not iid or not name:
            continue
        if re.search(r"hands[- ]?free", name, re.I):
            continue
        dev_id = iid.split("\\")[-1]
        label, kind, base = out_info(name)
        outs.append({"id": dev_id, "key": dev_id.lower(), "label": label, "kind": kind, "base": base})
        if not phones and kind == "headphones":
            phones = base
    labels = [o["label"] for o in outs]
    for o in outs:  # two "Speaker"s and so on: fall back to the real device name
        if labels.count(o["label"]) > 1:
            o["label"] = o["base"]
    return phones, outs


def phones_loop(b):
    """Active playback devices (for the Speaker / Headphones buttons in the volume panel) + the headphones chip.
        The registry fingerprint is checked every couple of seconds. The heavy PowerShell scan only runs when a device
        appears or disappears (twice, a few seconds apart, since Windows lists a new device a bit late) and every 10 min."""
    last_sig, last_run, again = object(), 0.0, 0
    cached, sig0 = b._settings.get("lastAudio") or {}, _audio_sig()
    if sig0 is not None and "outs" in cached and cached.get("sig") == [list(x) for x in sig0]:
        # same playback devices in the same state as last time: show the saved result at once, no PowerShell
        b.phonesIn.emit((cached.get("phones", ""), cached["outs"]))
        last_sig, last_run = sig0, time.time()
    while True:
        sig = _audio_sig()
        due = sig is None or sig != last_sig or again > 0 or time.time() - last_run > 600
        if due:
            if sig is not None and sig != last_sig:
                again = 1                                    # one more scan shortly after a change
            elif again > 0:
                again -= 1
            try:
                phones, outs = _scan_outputs()
            except Exception:
                phones, outs = "", []
            b.phonesIn.emit((phones, outs))
            if sig is not None and outs:
                _cache_put(b, "lastAudio", {"sig": [list(x) for x in sig], "phones": phones, "outs": outs})
            last_sig, last_run = sig, time.time()
            time.sleep(3.0 if again else PHONES_POLL_S)
        else:
            time.sleep(PHONES_POLL_S)


def uptime_str():
    sec = ctypes.windll.kernel32.GetTickCount64() // 1000
    d, sec = divmod(sec, 86400)
    h, sec = divmod(sec, 3600)
    m = sec // 60
    parts = []
    if d:
        parts.append(f"{d} day" + ("s" if d != 1 else ""))
    if h:
        parts.append(f"{h} hour" + ("s" if h != 1 else ""))
    if m or not (d or h):
        parts.append(f"{m} minute" + ("s" if m != 1 else ""))
    return "up " + ", ".join(parts)


CONFIG_FILE = APPDIR / "config.json"          # next to vapor.pyw: your name + profile picture
FILES = APPDIR / "files"                      # your own files: ringtone.mp3, profile picture
try:
    FILES.mkdir(exist_ok=True)
except OSError:
    pass
_CONFIG_DEFAULT = {"userName": "", "profilePicture": "", "addToPath": True}


def load_config():
    """config.json next to vapor.pyw, created on first start. Empty values mean use the Windows account's.
        profilePicture can be an absolute path or a name inside the files/ folder (like "me.png")."""
    try:
        d = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            d = {}
    except (OSError, ValueError):
        d = {}
        if not CONFIG_FILE.exists():
            try:
                CONFIG_FILE.write_text(json.dumps(_CONFIG_DEFAULT, indent=2), encoding="utf-8")
            except OSError:
                log.exception("config.json not created")
    out = dict(_CONFIG_DEFAULT)
    for k in ("userName", "profilePicture"):
        v = d.get(k, "")
        out[k] = v.strip() if isinstance(v, str) else ""
    out["addToPath"] = d.get("addToPath", True) is not False      # "addToPath": false turns the PATH update off
    loc = d.get("location")                                       # set with: vaporctl set location <place>
    try:
        out["location"] = ({"name": str(loc.get("name", "")), "lat": float(loc["lat"]), "lon": float(loc["lon"]),
                            "fahrenheit": bool(loc.get("fahrenheit", False))} if isinstance(loc, dict) else None)
    except (KeyError, TypeError, ValueError):
        out["location"] = None
    return out


def ensure_on_path():
    """Keeps this folder on your user Path (HKCU, no admin) so `vaporctl` works from any terminal. If the folder moved,
        the entry Vapor added earlier gets replaced. Terminals that were already open need reopening to see it.
        Turn it off with "addToPath": false in config.json."""
    if not load_config()["addToPath"]:
        return
    here = str(APPDIR)
    norm = lambda s: os.path.normcase(os.path.normpath(os.path.expandvars(s.strip().strip('"')))) if s.strip() else ""
    mine = DATA / "path_entry.txt"                       # the entry Vapor itself added last time
    try:
        old_entry = mine.read_text(encoding="utf-8").strip()
    except OSError:
        old_entry = ""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
        try:
            raw, typ = winreg.QueryValueEx(k, "Path")
            if typ not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                raw, typ = "", winreg.REG_EXPAND_SZ
        except FileNotFoundError:
            raw, typ = "", winreg.REG_EXPAND_SZ
        entries = [e for e in raw.split(";") if e.strip()]
        # drop the entry Vapor added earlier if the folder moved or is gone, never touch anything else
        keep = [e for e in entries if not (old_entry and norm(e) == norm(old_entry) and norm(e) != norm(here))]
        if not any(norm(e) == norm(here) for e in keep):
            keep.append(here)
        if keep == entries:
            return
        winreg.SetValueEx(k, "Path", 0, typ, ";".join(keep))
    try:
        mine.write_text(here, encoding="utf-8")
    except OSError:
        pass
    try:                                                   # tell Explorer so terminals opened from now on get the new Path
        res = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 0x0002, 5000, ctypes.byref(res))
    except Exception:
        pass
    log.info("path: %s added to the user Path", here)


def _avatar_source():
    """Profile picture: config.json's "profilePicture" if that file exists, otherwise the picture set for your Windows
        account (Settings > Accounts > Your info), or "" if there's none."""
    custom = load_config()["profilePicture"]
    if custom:
        f = Path(os.path.expandvars(os.path.expanduser(custom)))
        if not f.is_absolute():
            f = FILES / f
        if f.is_file():
            return str(f)
        log.warning("config.json: profilePicture not found: %s", f)
    else:                                            # nothing configured: files/profile.png|jpg|jpeg gets picked up on its own
        for n in ("profile.png", "profile.jpg", "profile.jpeg"):
            if (FILES / n).is_file():
                return str(FILES / n)
    base = os.environ.get("APPDATA", "")
    best = ""
    for sub in ("AccountPictures", "AccountPicture"):
        dd = os.path.join(base, "Microsoft", "Windows", sub)
        try:
            names = os.listdir(dd)
        except OSError:
            continue
        for name in names:
            f = os.path.join(dd, name)
            if not os.path.isfile(f) or os.path.splitext(name)[1].lower() not in (".png", ".jpg", ".jpeg"):
                continue
            if not best or os.path.getmtime(f) > os.path.getmtime(best):
                best = f
    return best

def avatar_path():
    """The profile picture as a clean, square, right-sized PNG. Falls back to the original file if anything goes wrong."""
    src = _avatar_source()
    if not src:
        return ""
    try:
        import hashlib
        from PySide6.QtGui import QGuiApplication, QImageReader
        scr = QGuiApplication.primaryScreen()
        dpr = max(1.0, scr.devicePixelRatio()) if scr else 1.0
        px = max(96, min(512, int(AVATAR_LOGICAL * dpr * 1.5 + 0.5)))
        f = Path(src)
        st = f.stat()
        key = hashlib.md5(("%s|%d|%d|%d" % (f, st.st_mtime_ns, st.st_size, px)).encode()).hexdigest()[:12]
        out = DATA / "cache" / ("avatar_%s.png" % key)
        if out.is_file():
            return str(out)
        rd = QImageReader(str(f))
        rd.setAutoTransform(True)                      # phone photos: apply the camera rotation
        img = rd.read()
        if img.isNull():
            return src
        side = min(img.width(), img.height())
        img = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
        if side > px:                                  # only shrink, never enlarge
            img = img.scaled(px, px, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        out.parent.mkdir(parents=True, exist_ok=True)
        for old in out.parent.glob("avatar_*.png"):    # keep only the current one
            try:
                old.unlink()
            except OSError:
                pass
        if img.save(str(out), "PNG"):
            return str(out)
    except Exception:  # noqa: BLE001
        log.exception("avatar: could not prepare the picture")
    return src

def status_loop(b):
    """User card in the dock's dashboard: avatar + uptime, re-checked every 30 s."""
    def snapshot():
        return {"uptime": uptime_str(), "userAvatar": avatar_path(),
                "userName": load_config()["userName"] or os.environ.get("USERNAME", "user")}

    last = snapshot()
    b.userIn.emit(last)
    while True:
        time.sleep(30)
        try:
            data = snapshot()
            if data != last:
                last = dict(data)
                b.userIn.emit(data)
        except Exception:
            log.exception("status")


def _fmt(sec):
    sec = max(0, int(sec))
    return f"{sec // 60}:{sec % 60:02d}"


_MEDIA_API = []     # cache: [] = not tried yet, [None] = unavailable, [(Manager, DataReader)] = ready


def _media_api():
    """(SessionManager, DataReader) from `winrt` (works on new Pythons) or the old `winsdk`. None if neither works.

        Catches every Exception, not just ImportError: a half-matching winrt install (winrt-runtime older or newer than
        the winrt-Windows.* packages) fails with AttributeError "module 'winrt._winrt' has no attribute '_C_API'"."""
    if _MEDIA_API:
        return _MEDIA_API[0]
    api = None
    try:
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as M
        from winrt.windows.storage.streams import DataReader as R
        import winrt.windows.foundation  # noqa: F401  (these two register the types the calls return)
        import winrt.windows.foundation.collections  # noqa: F401
        api = (M, R)
    except Exception as e:
        log.warning("winrt unusable (%s: %s) - trying winsdk", type(e).__name__, e)
        try:
            from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as M
            from winsdk.windows.storage.streams import DataReader as R
            api = (M, R)
        except Exception:
            api = None
    _MEDIA_API.append(api)
    return api


class MediaWorker(threading.Thread):
    """Reads the Windows 'now playing' session, the same source as the volume flyout."""

    def __init__(self, b):
        super().__init__(daemon=True)
        self.b = b
        self.loop = None
        self.session = None
        self.mgr = None           # the GSMTC session manager (kept so the scroll can list sessions)
        self.sessions = []        # every app that currently has a "now playing" session
        self.cur_aumid = ""       # app id of the session we're showing
        self.pick = None          # app the user scrolled to (None = follow Windows' current session)
        self._repoll = False      # a scroll changed the session, re-read title/art on the very next tick
        self._wake = None         # set by a scroll: poll again right away instead of waiting 0.5 s

    def run(self):
        try:
            asyncio.run(self._main())
        except Exception:
            log.exception("media worker stopped")

    async def _thumb(self, props, n):
        try:
            ref = props.thumbnail
            if ref is None:
                return ""
            DataReader = _media_api()[1]
            from PIL import Image
            stream = await ref.open_read_async()
            size = stream.size
            if not size:
                return ""
            reader = DataReader(stream)
            await reader.load_async(size)
            data = bytearray(size)
            reader.read_bytes(data)
            im = Image.open(io.BytesIO(bytes(data))).convert("RGB")
            w, h = im.size
            s = min(w, h)
            l, t = (w - s) // 2, (h - s) // 2
            im = im.crop((l, t, l + s, t + s)).resize((256, 256), Image.Resampling.LANCZOS)
            path = ART_DIR / f"art_{n}.png"
            im.save(path)
            for old in ART_DIR.glob("art_*.png"):
                if old != path and time.time() - old.stat().st_mtime > 30:
                    try:
                        old.unlink()
                    except OSError:
                        pass
            return str(path)
        except Exception:
            log.warning("thumbnail failed", exc_info=True)
            return ""

    async def _main(self):
        self.loop = asyncio.get_running_loop()
        api = _media_api()
        if api is None:
            log.warning("media widget disabled: uninstall every winrt-* package, then reinstall them together: "
                        "pip install winrt-runtime winrt-Windows.Media.Control winrt-Windows.Storage.Streams "
                        "winrt-Windows.Foundation winrt-Windows.Foundation.Collections")
            return
        Manager = api[0]
        mgr = await Manager.request_async()
        self.mgr = mgr
        self._wake = asyncio.Event()
        key, art, n = None, "", 0
        pos_seen, pos_t = None, 0.0
        props, tick = None, 0
        while True:
            try:
                self.sessions = list(mgr.get_sessions())   # Spotify, Zen ...: what the scroll can jump between
                s = None
                if self.pick is not None:                  # a scroll pinned the widget to one app
                    s = next((x for x in self.sessions if (x.source_app_user_model_id or "") == self.pick), None)
                    if s is None:
                        self.pick = None                   # that app's session ended, follow Windows again
                if s is None:
                    s = mgr.get_current_session()
                self.session = s
                if s is None:
                    key, props, self.cur_aumid = None, None, ""
                    self.b.mediaIn.emit({"title": ""})
                else:
                    tick += 1
                    aumid = s.source_app_user_model_id or ""
                    if aumid != self.cur_aumid or self._repoll:   # another app took over (scroll or Windows), read it right away
                        self.cur_aumid = aumid
                        self._repoll = False
                        props = None
                    if props is None or tick % 2 == 0:   # every WinRT call allocates COM objects, so do it half as often
                        props = await s.try_get_media_properties_async()
                        k = (props.title, props.artist, aumid)
                        if k != key:
                            key = k
                            n += 1
                            art = await self._thumb(props, n)
                    playing = int(s.get_playback_info().playback_status) == 4
                    tl = s.get_timeline_properties()
                    length = (tl.end_time - tl.start_time).total_seconds()
                    pos = tl.position.total_seconds()
                    if pos != pos_seen:
                        pos_seen, pos_t = pos, time.time()
                    shown = pos + ((time.time() - pos_t) if playing else 0)
                    if length > 0:
                        shown = min(shown, length)
                    src = media_source_name(s.source_app_user_model_id or "")
                    self.b.mediaIn.emit({
                        "title": props.title or "", "artist": props.artist or "", "source": src,
                        "playing": playing, "art": art,
                        "progress": (shown / length) if length > 0 else 0.0,
                        "time": f"{_fmt(shown)} / {_fmt(length)}" if length > 0 else "",
                    })
            except Exception:
                log.warning("media poll failed", exc_info=True)
            # 0.25 s poll, fast enough that the progress bar can glide between ticks without stuttering.
            # a scroll on the media widget sets _wake so the new session shows up at once
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=0.25)
                self._wake.clear()
            except asyncio.TimeoutError:
                pass

    def act(self, what):
        if not self.loop or not self.session:
            return
        s = self.session
        call = {"toggle": s.try_toggle_play_pause_async, "next": s.try_skip_next_async,
                "prev": s.try_skip_previous_async}[what]

        async def go():
            await call()

        asyncio.run_coroutine_threadsafe(go(), self.loop)

    def seek(self, frac):
        """Click / drag on the progress bar: jump the shown track to that point. It only asks that one app to move
                inside its own track, it never switches apps or changes play state."""
        if not self.loop or not self.session:
            return
        s = self.session

        async def go():
            try:
                from datetime import timedelta
                tl = s.get_timeline_properties()
                start, end = tl.start_time.total_seconds(), tl.end_time.total_seconds()
                if end - start <= 0.1:
                    return    # no usable timeline (a live stream, say), nothing to seek
                f = min(1.0, max(0.0, frac))   # don't rebind the closure var `frac` (UnboundLocalError)
                target = timedelta(seconds=start + f * (end - start))
                try:
                    await s.try_change_playback_position_async(target)
                except TypeError:    # some winrt builds want raw 100 ns ticks instead
                    await s.try_change_playback_position_async(int(target.total_seconds() * 10_000_000))
                self._wake.set()         # re-read the timeline right away so the bar follows
            except Exception:
                log.warning("could not seek", exc_info=True)

        asyncio.run_coroutine_threadsafe(go(), self.loop)

    def cycle(self, direction=1):
        """Scroll on the media widget: show the next / previous app that can play media (wraps around).

                This only changes which app the widget shows and the control buttons talk to, it never starts, pauses or
                skips anything. The Windows bindings have no way to move their 'current session', so the choice is kept
                here: `pick` pins the widget to that app until you scroll again or its session ends (then it goes back to
                following the current session).
                """
        loop, mgr = self.loop, self.mgr
        if not loop or loop.is_closed() or mgr is None:
            return

        async def go():
            try:
                sessions = list(mgr.get_sessions())
                if len(sessions) < 2:
                    return                      # nothing to scroll to
                idx = next((i for i, x in enumerate(sessions)
                            if (x.source_app_user_model_id or "") == self.cur_aumid), 0)
                nxt = sessions[(idx + (1 if direction >= 0 else -1)) % len(sessions)]
                self.session = nxt
                self.pick = (nxt.source_app_user_model_id or "")
                self.cur_aumid = self.pick
                # _repoll makes the loop drop the previous app's title/art on its next (woken) tick
                self._repoll = True
                if self._wake:
                    self._wake.set()
            except Exception:
                log.warning("media session switch failed", exc_info=True)

        asyncio.run_coroutine_threadsafe(go(), loop)


# ---- theme: wallpaper defaults, plus the colours the control center can override ----
def css_color(txt):
    """CSS colour -> QML '#AARRGGBB', or None."""
    txt = (txt or "").strip()
    m = re.match(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)", txt)
    if m:
        r, g, bl = (max(0, min(255, round(float(m.group(i))))) for i in (1, 2, 3))
        a = float(m.group(4)) if m.group(4) is not None else 1.0
        return "#%02x%02x%02x%02x" % (round(max(0.0, min(1.0, a)) * 255), r, g, bl)
    m = re.match(r"#([0-9a-fA-F]{6})$", txt)
    if m:
        return "#ff" + m.group(1).lower()
    m = re.match(r"#([0-9a-fA-F]{3})$", txt)
    if m:
        return "#ff" + "".join(c * 2 for c in m.group(1).lower())
    return None


DEFAULT_THEME = {
    "accent": css_color("#4cc2ff"),
    "blue": css_color("rgba(150, 172, 255, 0.95)"),
    "lavender": css_color("rgba(210, 188, 255, 0.9)"),
    "hover": css_color("rgba(150, 172, 255, 0.16)"),
    "outline": css_color("rgba(150, 172, 255, 0.34)"),
}


def argb_alpha(c, a):
    """'#AARRGGBB' with a different alpha."""
    return "#%02x%s" % (round(max(0.0, min(1.0, a)) * 255), c[3:9])


ICON_VALUE = 0.74         # brightness of the icon colours that follow the wallpaper (1.0 = as bright as it gets, 0.6 = dim)


def wallpaper_icons(outline):
    """Icon colours that follow the wallpaper: same hue / saturation as the outline but toned down in brightness
        (ICON_VALUE) so icons and the control center aren't glaring. blue / lavender are softer tints of it."""
    import colorsys
    h, s, _v = colorsys.rgb_to_hsv(*(int(outline[i:i + 2], 16) / 255.0 for i in (3, 5, 7)))

    def mk(a, hh, ss, vv):
        r, g, b = (round(c * 255) for c in colorsys.hsv_to_rgb(hh % 1.0, ss, min(1.0, vv)))
        return "#%02x%02x%02x%02x" % (round(a * 255), r, g, b)
    acc = mk(1.0, h, s, ICON_VALUE)
    return {"accent": acc, "blue": mk(0.95, h, s * 0.45, ICON_VALUE + 0.14), "lavender": mk(0.9, h + 0.1, s * 0.6, ICON_VALUE + 0.1),
            "hover": argb_alpha(acc, 0.16)}


# ---- audio visualizer: WASAPI loopback -> FFT -> 6 bars (500-12000 Hz) ----
def viz_loop(b):
    if not VIZ_ENABLED:
        return
    try:
        import numpy as np
        import pyaudiowpatch as pyaudio
    except ImportError:
        log.warning("visualizer disabled (pip install numpy pyaudiowpatch)")
        return
    import queue
    N, FMIN, FMAX, FRAMES = 6, 500.0, 12000.0, 2048
    while True:
        p = stream = None
        try:
            p = pyaudio.PyAudio()
            wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            dev = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
            if not dev.get("isLoopbackDevice"):
                for lb in p.get_loopback_device_info_generator():
                    if dev["name"] in lb["name"]:
                        dev = lb
                        break
                else:
                    raise RuntimeError("no loopback device for " + dev["name"])
            rate, ch = int(dev["defaultSampleRate"]), max(1, int(dev["maxInputChannels"]))
            q = queue.Queue(maxsize=6)

            def cb(in_data, frame_count, time_info, status):
                try:
                    q.put_nowait(in_data)
                except queue.Full:
                    pass
                return (None, pyaudio.paContinue)

            stream = p.open(format=pyaudio.paInt16, channels=ch, rate=rate, input=True,
                            frames_per_buffer=FRAMES, input_device_index=dev["index"], stream_callback=cb)
            freqs = np.fft.rfftfreq(FRAMES, 1.0 / rate)
            edges = np.geomspace(FMIN, min(FMAX, rate / 2 - 1), N + 1)
            bands = [np.where((freqs >= edges[i]) & (freqs < edges[i + 1]))[0] for i in range(N)]
            win = np.hanning(FRAMES).astype(np.float32)
            level, peak_db = np.zeros(N), -40.0
            tilt = np.arange(N) * 2.0          # +2 dB per band towards the highs, music is bass-heavy
            active, quiet_since, last_emit, t0 = False, None, 0.0, time.time()
            out_id = b._v.get("defaultOutput", "")
            # reopening a loopback stream (PyAudio() + terminate()) stalls the audio stack, worst on Bluetooth
            # headphones. so only reopen when the default output changed, the stream died, or after 30 min.
            while time.time() - t0 < 1800:
                if not stream.is_active() or b._v.get("defaultOutput", "") != out_id:
                    break
                try:
                    data = q.get(timeout=0.2)
                except queue.Empty:
                    data = None  # loopback sends nothing while the PC is silent
                if data is not None:
                    x = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                    if ch > 1:
                        x = x[: len(x) // ch * ch].reshape(-1, ch).mean(axis=1)
                    if len(x) != FRAMES:
                        continue
                    mag = np.abs(np.fft.rfft(x * win)) * (4.0 / FRAMES)
                    band = np.array([mag[i].max() if len(i) else 0.0 for i in bands])
                    db = 20.0 * np.log10(band + 1e-7) + tilt
                    peak_db = max(peak_db - 0.08, float(db.max()), -55.0)       # slow auto-gain, in dB
                    norm = np.clip((db - (peak_db - VIZ_RANGE_DB)) / VIZ_RANGE_DB, 0.0, 1.0) ** 1.4
                else:
                    norm = np.zeros(N)
                level = np.maximum(norm, level * VIZ_FALL)
                now = time.time()
                if float(level.max()) > 0.03:
                    active, quiet_since = True, None
                elif quiet_since is None:
                    quiet_since = now
                elif now - quiet_since > 3.0:
                    active = False
                if now - last_emit > 1 / 20:
                    last_emit = now
                    try:
                        b.vizIn.emit((active, [round(float(v), 3) for v in level]))
                    except RuntimeError:        # window is already gone (quitting)
                        return
        except Exception:
            log.warning("visualizer error, retrying", exc_info=True)
            time.sleep(5)
        finally:
            try:
                if stream is not None:
                    stream.stop_stream()
                    stream.close()
            except Exception:
                pass
            try:
                if p is not None:
                    p.terminate()
            except Exception:
                pass


# ---- global hotkey (Alt+W): own thread with a message loop so Qt never has to know about it ----
def parse_hotkey(spec):
    mods, vk = 0, 0
    for part in spec.lower().replace(" ", "").split("+"):
        if part == "alt":
            mods |= 0x1
        elif part in ("ctrl", "control"):
            mods |= 0x2
        elif part == "shift":
            mods |= 0x4
        elif part in ("win", "super"):
            mods |= 0x8
        elif len(part) == 1:
            vk = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x6F + int(part[1:])
        else:
            raise ValueError("unknown key %r" % part)
    if not vk:
        raise ValueError("no key in %r" % spec)
    return mods, vk


def hotkey_loop(b):
    if not HIDE_HOTKEY:
        return
    try:
        mods, vk = parse_hotkey(HIDE_HOTKEY)
    except ValueError:
        log.error("bad HIDE_HOTKEY %r", HIDE_HOTKEY, exc_info=True)
        return
    # 0x4000 = MOD_NOREPEAT, holding the keys only toggles once
    if not user32.RegisterHotKey(None, 0x4642, mods | 0x4000, vk):
        log.error("could not register hotkey %s (Windows error %s): another program (whkd / AutoHotkey / an app) "
                  "already owns it. Change HIDE_HOTKEY.", HIDE_HOTKEY, kernel32.GetLastError())
        return
    log.info("hotkey %s registered", HIDE_HOTKEY)
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == 0x0312:  # WM_HOTKEY
            b.toggleIn.emit()


# ---- switch the default playback device (undocumented but long-stable IPolicyConfig, same as Sound settings) ----
_policy = None


def set_default_output(dev_id):
    global _policy
    import comtypes
    from comtypes import COMMETHOD, GUID, HRESULT, IUnknown
    if _policy is None:
        class IPolicyConfig(IUnknown):
            _iid_ = GUID("{F8679F50-850A-41CF-9C72-430F290290C8}")
            _methods_ = tuple(COMMETHOD([], HRESULT, n) for n in (
                "GetMixFormat", "GetDeviceFormat", "ResetDeviceFormat", "SetDeviceFormat",
                "GetProcessingPeriod", "SetProcessingPeriod", "GetShareMode", "SetShareMode",
                "GetPropertyValue", "SetPropertyValue")) + (
                COMMETHOD([], HRESULT, "SetDefaultEndpoint",
                          (["in"], ctypes.c_wchar_p, "wszDeviceId"), (["in"], ctypes.c_int, "role")),
                COMMETHOD([], HRESULT, "SetEndpointVisibility",
                          (["in"], ctypes.c_wchar_p, "wszDeviceId"), (["in"], ctypes.c_int, "visible")),
            )
        _policy = comtypes.CoCreateInstance(
            GUID("{870AF99C-171D-4F9E-AF0D-E63DF40C2BC9}"), IPolicyConfig, comtypes.CLSCTX_ALL)
    for role in (0, 1, 2):  # console, multimedia, communications
        _policy.SetDefaultEndpoint(dev_id, role)


gdi32 = ctypes.windll.gdi32
gdi32.CreateRectRgn.argtypes = [ctypes.c_int] * 4
gdi32.CreateRectRgn.restype = wintypes.HRGN
user32.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
gdi32.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
gdi32.CreateRoundRectRgn.restype = wintypes.HRGN
gdi32.CombineRgn.argtypes = [wintypes.HRGN, wintypes.HRGN, wintypes.HRGN, ctypes.c_int]
gdi32.CombineRgn.restype = ctypes.c_int
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
user32.MonitorFromWindow.restype = wintypes.HANDLE
user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
user32.GetMonitorInfoW.restype = wintypes.BOOL


# ---- app list model (stable rows so QML can animate items in and out) ----
class TaskModel(QAbstractListModel):
    ROLES = ["appKey", "appTitle", "isActive", "winCount", "iconUrl"]
    BASE = 0x0100  # Qt.UserRole

    def __init__(self):
        super().__init__()
        self._items = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        i = int(role) - self.BASE
        if not index.isValid() or not (0 <= i < len(self.ROLES)) or index.row() >= len(self._items):
            return None
        return self._items[index.row()][self.ROLES[i]]

    def roleNames(self):
        return {self.BASE + i: n.encode() for i, n in enumerate(self.ROLES)}

    def update(self, new_items):
        keys = {d["appKey"] for d in new_items}
        for row in range(len(self._items) - 1, -1, -1):
            if self._items[row]["appKey"] not in keys:
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._items[row]
                self.endRemoveRows()
        have = {d["appKey"]: i for i, d in enumerate(self._items)}
        for d in new_items:
            if d["appKey"] in have:
                row = have[d["appKey"]]
                if self._items[row] != d:
                    self._items[row] = d
                    idx = self.index(row)
                    self.dataChanged.emit(idx, idx)
            else:
                row = len(self._items)
                self.beginInsertRows(QModelIndex(), row, row)
                self._items.append(d)
                self.endInsertRows()
                have[d["appKey"]] = row


# ---- small settings file (pinned tray icons), theme colours are saved by cc_backend.py in cc_theme.json ----
SETTINGS_FILE = DATA / "settings.json"


def load_settings():
    try:
        d = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(d):
    try:
        SETTINGS_FILE.write_text(json.dumps(d, indent=1), encoding="utf-8")
    except OSError:
        log.exception("settings not saved")


# ---- system tray ----
# Explorer owns every notification-area icon, so we read them straight out of its hidden tray toolbars
# (same trick AutoHotkey's TrayIcon library uses) and post a click back to the icon's owner window like
# Explorer would. needs 64-bit Python. if nothing shows up, look for "tray:" in the log.
TB_BUTTONCOUNT, TB_GETBUTTON, TBSTATE_HIDDEN = 0x0418, 0x0417, 0x08
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_RBUTTONUP = 0x0201, 0x0202, 0x0204, 0x0205
gdi32 = ctypes.windll.gdi32
_vp = ctypes.c_void_p
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumProc, wintypes.LPARAM]
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.IsWindow.argtypes = [wintypes.HWND]
user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_ssize_t
user32.GetIconInfo.argtypes = [_vp, _vp]
user32.GetDC.argtypes = [_vp]
user32.GetDC.restype = _vp
user32.ReleaseDC.argtypes = [_vp, _vp]
gdi32.GetObjectW.argtypes = [_vp, ctypes.c_int, _vp]
gdi32.GetDIBits.argtypes = [_vp, _vp, wintypes.UINT, wintypes.UINT, _vp, _vp, wintypes.UINT]
gdi32.DeleteObject.argtypes = [_vp]
kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, _vp, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
kernel32.VirtualAllocEx.restype = _vp
kernel32.VirtualFreeEx.argtypes = [wintypes.HANDLE, _vp, ctypes.c_size_t, wintypes.DWORD]
kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, _vp, _vp, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.ReadProcessMemory.restype = wintypes.BOOL


class _ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD), ("yHotspot", wintypes.DWORD),
                ("hbmMask", ctypes.c_void_p), ("hbmColor", ctypes.c_void_p)]


class _BITMAP(ctypes.Structure):
    _fields_ = [("bmType", ctypes.c_long), ("bmWidth", ctypes.c_long), ("bmHeight", ctypes.c_long),
                ("bmWidthBytes", ctypes.c_long), ("bmPlanes", wintypes.WORD), ("bmBitsPixel", wintypes.WORD),
                ("bmBits", ctypes.c_void_p)]


class _BMIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


def _tray_toolbars():
    """Explorer's notification-area toolbars: the visible area and the overflow (hidden icons)."""
    found = []
    parents = {"SysPager", "TrayNotifyWnd", "NotifyIconOverflowWindow"}

    @EnumProc
    def cb(hwnd, _lp):
        try:
            if class_of(hwnd) == "ToolbarWindow32":
                p = user32.GetParent(hwnd)
                for _ in range(4):
                    if not p:
                        break
                    if class_of(p) in parents:
                        if int(hwnd) not in found:
                            found.append(int(hwnd))
                        break
                    p = user32.GetParent(p)
        except Exception:
            pass
        return True

    for root in ("Shell_TrayWnd", "NotifyIconOverflowWindow"):
        h = user32.FindWindowW(root, None)
        if h:
            user32.EnumChildWindows(h, cb, 0)
    return found


def _read_remote(proc, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    if addr and kernel32.ReadProcessMemory(proc, addr, buf, size, ctypes.byref(got)) and got.value:
        return buf.raw[:got.value]
    return None


def _tray_read_toolbar(tb):
    """[{hwnd, uid, cb, hicon, title}] for every icon button of one tray toolbar."""
    out = []
    n = user32.SendMessageW(tb, TB_BUTTONCOUNT, 0, 0)
    if n <= 0 or n > 300:
        return out
    proc = kernel32.OpenProcess(0x0438, False, pid_of(tb))      # VM_OPERATION | VM_READ | VM_WRITE | QUERY_INFORMATION
    if not proc:
        return out
    remote = kernel32.VirtualAllocEx(proc, None, 4096, 0x3000, 0x04)
    try:
        if not remote:
            return out
        for i in range(n):
            if not user32.SendMessageW(tb, TB_GETBUTTON, i, remote):
                continue
            raw = _read_remote(proc, remote, 32)                        # TBBUTTON (64-bit layout)
            if not raw or len(raw) < 32:
                continue
            _bmp, _cmd, state, _style, data, istr = struct.unpack("<iiBB6xQq", raw)
            if (state & TBSTATE_HIDDEN) or not data:
                continue
            td = _read_remote(proc, data, 32)                           # Explorer's TRAYDATA
            if not td or len(td) < 32:
                continue
            hwnd, uid, cbmsg, hicon = struct.unpack("<QII8xQ", td)
            if not hwnd or not user32.IsWindow(hwnd):
                continue
            title = ""
            if istr > 0:
                for size in (512, 192, 64):
                    tr = _read_remote(proc, istr, size)
                    if tr:
                        title = tr.decode("utf-16-le", "ignore").split("\x00", 1)[0].strip()
                        break
            out.append(dict(hwnd=int(hwnd), uid=int(uid), cb=int(cbmsg), hicon=int(hicon), title=title))
    finally:
        if remote:
            kernel32.VirtualFreeEx(proc, remote, 0, 0x8000)
        kernel32.CloseHandle(proc)
    return out


def hicon_rgba(hicon):
    """(w, h, BGRA bytes) of an HICON, or None."""
    ii = _ICONINFO()
    if not user32.GetIconInfo(hicon, ctypes.byref(ii)):
        return None
    hdc = None
    try:
        if not ii.hbmColor:
            return None
        bm = _BITMAP()
        if not gdi32.GetObjectW(ii.hbmColor, ctypes.sizeof(bm), ctypes.byref(bm)):
            return None
        w, h = bm.bmWidth, bm.bmHeight
        if w <= 0 or h <= 0 or w > 512 or h > 512:
            return None
        hdc = user32.GetDC(None)

        def bits(hbm):
            bi = _BMIH()
            bi.biSize = ctypes.sizeof(_BMIH)
            bi.biWidth, bi.biHeight, bi.biPlanes, bi.biBitCount = w, -h, 1, 32
            buf = ctypes.create_string_buffer(w * h * 4)
            return buf.raw if gdi32.GetDIBits(hdc, hbm, 0, h, buf, ctypes.byref(bi), 0) else None

        px = bits(ii.hbmColor)
        if px is None:
            return None
        data = bytearray(px)
        if not any(data[3::4]):                  # old-style icon without alpha, the 1-bit mask says what's see-through
            mk = bits(ii.hbmMask) if ii.hbmMask else None
            for i in range(w * h):
                data[i * 4 + 3] = 0 if (mk and mk[i * 4]) else 255
        return w, h, bytes(data)
    finally:
        if hdc:
            user32.ReleaseDC(None, hdc)
        if ii.hbmColor:
            gdi32.DeleteObject(ii.hbmColor)
        if ii.hbmMask:
            gdi32.DeleteObject(ii.hbmMask)


def tray_icon_url(hicon):
    r = hicon_rgba(hicon)
    if not r:
        return ""
    w, h, data = r
    p = ICON_DIR / ("tray_" + hashlib.md5(data + bytes((w & 255, h & 255))).hexdigest()[:16] + ".png")
    if not p.exists():
        img = QImage(data, w, h, w * 4, QImage.Format.Format_ARGB32).copy()
        if w > 64 or h > 64 or max(w, h) < 48:         # always ends up around 48px: big ones shrink, 16/32px ones grow smoothly
            img = img.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        if not img.save(str(p), "PNG"):
            return ""
    return QUrl.fromLocalFile(str(p)).toString()


# ---- tray "spy" window ----
# On current Windows 11 Explorer has no tray toolbars to read, so this registers a hidden window with the
# taskbar's class name (Shell_TrayWnd) and keeps it on top of the real one. every program that adds / changes /
# removes a tray icon sends its message (WM_COPYDATA) to the first Shell_TrayWnd it finds, which is ours. we note
# the icon down and pass the message on to the real taskbar untouched. a "TaskbarCreated" broadcast makes
# programs that are already running announce their icons again.
# limit: a program that ignores TaskbarCreated only shows up after it's restarted.
WM_COPYDATA, WM_TIMER, WM_CONTEXTMENU = 0x004A, 0x0113, 0x007B
_SPY = {"ok": False, "icons": {}, "lock": threading.Lock(), "real": 0, "self": 0, "proc": None}
_u32 = ctypes.WinDLL("user32", use_last_error=True)
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_k32.GetModuleHandleW.restype = wintypes.HMODULE
_SPYPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class _SPYCLASS(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", _SPYPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HMODULE), ("hIcon", wintypes.HANDLE),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class _COPYDATA(ctypes.Structure):
    _fields_ = [("dwData", ctypes.c_size_t), ("cbData", wintypes.DWORD), ("lpData", ctypes.c_void_p)]


_u32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
_u32.SystemParametersInfoW.restype = wintypes.BOOL
_u32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_u32.DefWindowProcW.restype = ctypes.c_ssize_t
_u32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_u32.SendMessageW.restype = ctypes.c_ssize_t
_u32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
_u32.IsWindow.argtypes = [wintypes.HWND]
_u32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
_u32.FindWindowExW.restype = wintypes.HWND
_u32.RegisterClassW.argtypes = [ctypes.POINTER(_SPYCLASS)]
_u32.RegisterClassW.restype = wintypes.ATOM
_u32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HANDLE,
                                 wintypes.HMODULE, ctypes.c_void_p]
_u32.CreateWindowExW.restype = wintypes.HWND
_u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                              wintypes.UINT]
_u32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
_u32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
_u32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
_u32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]


def _spy_fields(buf, lay):
    """Pulls the icon fields out of a Shell_NotifyIcon payload. Layout 0 = 32-bit handles (what Explorer sends on
        64-bit Windows), layout 1 = native 64-bit handles as a fallback."""
    if lay == 0:
        if len(buf) < 296:
            return None
        hw, uid, fl, cb, hi = struct.unpack_from("<IIIII", buf, 12)
        tip_o, st_o, ver_o = 32, 288, 808
    else:
        if len(buf) < 316:
            return None
        hw = struct.unpack_from("<Q", buf, 16)[0]
        uid, fl, cb = struct.unpack_from("<III", buf, 24)
        hi = struct.unpack_from("<Q", buf, 40)[0]
        tip_o, st_o, ver_o = 48, 304, 824
    st, mask = struct.unpack_from("<II", buf, st_o)
    ver = struct.unpack_from("<I", buf, ver_o)[0] if len(buf) >= ver_o + 4 else 0
    tip = buf[tip_o:tip_o + 256].decode("utf-16-le", "ignore").split("\0")[0]
    return dict(hw=hw, uid=uid, fl=fl, cb=cb, hi=hi, st=st, mask=mask, ver=ver, tip=tip)


def _spy_handle(buf):
    if len(buf) < 12:
        return
    sig, code = struct.unpack_from("<II", buf, 0)
    if code not in (0, 1, 2, 4):
        return
    icons, f = _SPY["icons"], None
    for lay in (0, 1):
        c = _spy_fields(buf, lay)
        if c and (_u32.IsWindow(c["hw"]) or (code == 2 and (c["hw"], c["uid"]) in icons)):
            f = c
            break
    if not f:
        return
    key = (f["hw"], f["uid"])
    with _SPY["lock"]:
        if code == 2:                                       # NIM_DELETE
            icons.pop(key, None)
            return
        ic = icons.get(key) or dict(hwnd=f["hw"], uid=f["uid"], cb=0, hicon=0, title="", ver=0)
        if code == 4:                                       # NIM_SETVERSION
            ic["ver"] = f["ver"]
        else:                                               # NIM_ADD / NIM_MODIFY: only the fields flagged valid
            if f["fl"] & 1:
                ic["cb"] = f["cb"]
            if f["fl"] & 2:
                ic["hicon"] = f["hi"]
            if f["fl"] & 4:
                ic["title"] = f["tip"]
            if (f["fl"] & 8) and (f["mask"] & 1) and (f["st"] & 1):     # NIS_HIDDEN
                icons.pop(key, None)
                return
        icons[key] = ic


def _spy_real_taskbar():
    h = None
    while True:
        h = _u32.FindWindowExW(None, h, "Shell_TrayWnd", None)
        if not h:
            return 0
        if h != _SPY["self"]:
            return h


def _spy_wndproc(hwnd, msg, wp, lp):
    try:
        if msg == WM_COPYDATA:
            cds = ctypes.cast(lp, ctypes.POINTER(_COPYDATA)).contents
            if cds.dwData in (1, 2) and cds.lpData and 0 < cds.cbData < 8192:  # Shell_NotifyIcon (1 on most builds, 2 on some)
                try:
                    _spy_handle(ctypes.string_at(cds.lpData, cds.cbData))
                except Exception:
                    log.exception("tray spy parse")
            real = _SPY["real"]
            if real and _u32.IsWindow(real):                # everything (appbar, icon positions ...) goes on to Explorer
                return _u32.SendMessageW(real, msg, wp, lp)
            return 0
        if msg == WM_TIMER:
            _u32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0013)                    # stay above the real taskbar
            if not (_SPY["real"] and _u32.IsWindow(_SPY["real"])):
                _SPY["real"] = _spy_real_taskbar()
            return 0
    except Exception:
        log.exception("tray spy")
    return _u32.DefWindowProcW(hwnd, msg, wp, lp)


def _spy_thread():
    try:
        _SPY["real"] = _u32.FindWindowExW(None, None, "Shell_TrayWnd", None) or 0
        _SPY["proc"] = _SPYPROC(_spy_wndproc)               # kept alive here
        wc = _SPYCLASS()
        wc.lpfnWndProc = _SPY["proc"]
        wc.hInstance = _k32.GetModuleHandleW(None)
        wc.lpszClassName = "Shell_TrayWnd"
        if not _u32.RegisterClassW(ctypes.byref(wc)):
            log.error("tray: could not register the spy window class (error %d)", ctypes.get_last_error())
            return
        hwnd = _u32.CreateWindowExW(0x88, "Shell_TrayWnd", "", 0x80000000, 0, 0, 0, 0, None, None, wc.hInstance, None)
        if not hwnd:
            log.error("tray: could not create the spy window (error %d)", ctypes.get_last_error())
            return
        _SPY["self"] = hwnd
        _u32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0013)
        _u32.SetTimer(hwnd, 1, 1000, None)
        _SPY["ok"] = True
        wm = _u32.RegisterWindowMessageW("TaskbarCreated")
        threading.Timer(0.5, lambda: _u32.PostMessageW(0xFFFF, wm, 0, 0)).start()     # running programs re-add their icons
        threading.Timer(4.0, lambda: _u32.PostMessageW(0xFFFF, wm, 0, 0)).start()
        msg = wintypes.MSG()
        while _u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _u32.DispatchMessageW(ctypes.byref(msg))
    except Exception:
        log.exception("tray spy thread")


def _spy_snapshot():
    with _SPY["lock"]:
        rows = [dict(v) for v in _SPY["icons"].values()]
    return [r for r in rows if user32.IsWindow(r["hwnd"])]


_TB_CACHE = {"t": 0.0, "found": []}


def _tray_toolbars_cached():
    """Explorer's tray toolbars, looked up at most once a minute (every 20 s while there are none, like on current
        Windows 11). Walking Explorer's window tree on every poll is pointless cross-process traffic."""
    now = time.monotonic()
    found = _TB_CACHE["found"]
    if found and all(user32.IsWindow(h) for h in found) and now - _TB_CACHE["t"] < 60:
        return found
    if not found and now - _TB_CACHE["t"] < 20:
        return []
    _TB_CACHE["found"] = _tray_toolbars()
    _TB_CACHE["t"] = now
    return _TB_CACHE["found"]


def _tray_sources():
    yield from _spy_snapshot()
    for tb in _tray_toolbars_cached():
        yield from _tray_read_toolbar(tb)


def read_tray_icons():
    items, seen = [], set()
    for b in _tray_sources():
        ident = (b["hwnd"], b["uid"])
        if ident in seen:
            continue
        seen.add(ident)
        b["exe"] = exe_of(pid_of(b["hwnd"]))
        if os.path.basename(b["exe"]).lower() in TRAY_HIDE_EXES:
            continue
        b["iconUrl"] = tray_icon_url(b["hicon"]) if b["hicon"] else ""
        if not b["title"]:
            b["title"] = os.path.splitext(os.path.basename(b["exe"]))[0] if b["exe"] else class_of(b["hwnd"])
        items.append(b)
    per = {}
    for b in items:
        per[b["exe"].lower()] = per.get(b["exe"].lower(), 0) + 1
    for b in items:     # the key a pin is remembered by: the program, plus the icon id if it has several
        base = (b["exe"] or class_of(b["hwnd"])).lower()
        b["key"] = base if (b["exe"] and per[b["exe"].lower()] == 1) else "%s|%d" % (base, b["uid"])
    return items


def tray_click(it, button):
    hwnd, uid, cbmsg = it["hwnd"], it["uid"], it["cb"]
    if not cbmsg or not user32.IsWindow(hwnd):
        return
    down, up = (WM_RBUTTONDOWN, WM_RBUTTONUP) if button == "right" else (WM_LBUTTONDOWN, WM_LBUTTONUP)
    try:
        user32.SetForegroundWindow(hwnd)          # its menu needs the owner in front, or it never closes again
    except Exception:
        pass
    if it.get("ver", 0) >= 4:                     # NOTIFYICON_VERSION_4: wParam = anchor point, lParam = event | uID << 16
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        wp = (pt.x & 0xFFFF) | ((pt.y & 0xFFFF) << 16)
        evs = (down, up, WM_CONTEXTMENU) if button == "right" else (down, up, 0x0400)       # 0x400 = NIN_SELECT
        for ev in evs:
            user32.PostMessageW(hwnd, cbmsg, wp, ev | ((uid & 0xFFFF) << 16))
        return
    user32.PostMessageW(hwnd, cbmsg, uid, down)
    user32.PostMessageW(hwnd, cbmsg, uid, up)


def tray_loop(b):
    if not TRAY_ENABLED:
        return
    threading.Thread(target=_spy_thread, daemon=True).start()
    try:
        for f in ICON_DIR.glob("tray_*.png"):
            f.unlink()
    except OSError:
        pass
    time.sleep(2.0)                                 # let Explorer and the bar settle first
    last, n = None, 0
    while True:
        try:
            items = read_tray_icons()
            sig = [(it["key"], it["title"], it["iconUrl"]) for it in items]
            if sig != last:
                last = sig
                b.trayIn.emit(items)
            n += 1
            if n % 200 == 0:                        # animated tray icons make lots of pictures, keep the folder small
                files = sorted(ICON_DIR.glob("tray_*.png"), key=lambda f: f.stat().st_mtime)
                for f in files[:-150] if len(files) > 400 else []:
                    f.unlink()
        except Exception:
            log.exception("tray")
        time.sleep(TRAY_POLL_S)


class TrayModel(QAbstractListModel):
    ROLES = ["trayKey", "trayTitle", "iconUrl", "pinned"]
    BASE = 0x0100  # Qt.UserRole

    def __init__(self):
        super().__init__()
        self._items = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        i = int(role) - self.BASE
        if not index.isValid() or not (0 <= i < len(self.ROLES)) or index.row() >= len(self._items):
            return None
        return self._items[index.row()][self.ROLES[i]]

    def roleNames(self):
        return {self.BASE + i: n.encode() for i, n in enumerate(self.ROLES)}

    def update(self, new_items):
        want = [d["trayKey"] for d in new_items]
        cur = [d["trayKey"] for d in self._items]
        keep = [k for k in cur if k in set(want)]
        if want[:len(keep)] != keep:                    # order changed (pinned / unpinned / dragged), rebuild the list
            self.beginResetModel()
            self._items = list(new_items)
            self.endResetModel()
            return
        keys = {d["trayKey"] for d in new_items}
        for row in range(len(self._items) - 1, -1, -1):
            if self._items[row]["trayKey"] not in keys:
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._items[row]
                self.endRemoveRows()
        have = {d["trayKey"]: i for i, d in enumerate(self._items)}
        for d in new_items:
            if d["trayKey"] in have:
                row = have[d["trayKey"]]
                if self._items[row] != d:
                    self._items[row] = d
                    idx = self.index(row)
                    self.dataChanged.emit(idx, idx)
            else:
                row = len(self._items)
                self.beginInsertRows(QModelIndex(), row, row)
                self._items.append(d)
                self.endInsertRows()
                have[d["trayKey"]] = row


# ---- backend exposed to QML as `B` ----
class Backend(QObject):
    # -- state QML reads (each one is a change signal + a read-only property) --
    glassColorChanged = Signal(); glassColor = Property(str, lambda s: s._v["glassColor"], notify=glassColorChanged)
    glassOutlineChanged = Signal(); glassOutline = Property(str, lambda s: s._v["glassOutline"], notify=glassOutlineChanged)
    wifiNameChanged = Signal(); wifiName = Property(str, lambda s: s._v["wifiName"], notify=wifiNameChanged)
    headphonesChanged = Signal(); headphones = Property(str, lambda s: s._v["headphones"], notify=headphonesChanged)
    mediaTitleChanged = Signal(); mediaTitle = Property(str, lambda s: s._v["mediaTitle"], notify=mediaTitleChanged)
    mediaArtistChanged = Signal(); mediaArtist = Property(str, lambda s: s._v["mediaArtist"], notify=mediaArtistChanged)
    mediaSourceChanged = Signal(); mediaSource = Property(str, lambda s: s._v["mediaSource"], notify=mediaSourceChanged)
    mediaArtChanged = Signal(); mediaArt = Property(str, lambda s: s._v["mediaArt"], notify=mediaArtChanged)
    mediaTimeChanged = Signal(); mediaTime = Property(str, lambda s: s._v["mediaTime"], notify=mediaTimeChanged)
    weatherIconChanged = Signal(); weatherIcon = Property(str, lambda s: s._v["weatherIcon"], notify=weatherIconChanged)
    weatherTempChanged = Signal(); weatherTemp = Property(str, lambda s: s._v["weatherTemp"], notify=weatherTempChanged)
    weatherDescChanged = Signal(); weatherDesc = Property(str, lambda s: s._v["weatherDesc"], notify=weatherDescChanged)
    weatherRangeChanged = Signal(); weatherRange = Property(str, lambda s: s._v["weatherRange"], notify=weatherRangeChanged)
    weatherDataChanged = Signal(); weatherData = Property(str, lambda s: s._v["weatherData"], notify=weatherDataChanged)
    screenXChanged = Signal(); screenX = Property(int, lambda s: s._v["screenX"], notify=screenXChanged)
    screenYChanged = Signal(); screenY = Property(int, lambda s: s._v["screenY"], notify=screenYChanged)
    screenWChanged = Signal(); screenW = Property(int, lambda s: s._v["screenW"], notify=screenWChanged)
    screenHChanged = Signal(); screenH = Property(int, lambda s: s._v["screenH"], notify=screenHChanged)
    sideMarginChanged = Signal(); sideMargin = Property(int, lambda s: s._v["sideMargin"], notify=sideMarginChanged)
    batteryChanged = Signal(); battery = Property(int, lambda s: s._v["battery"], notify=batteryChanged)
    wsCountChanged = Signal(); wsCount = Property(int, lambda s: s._v["wsCount"], notify=wsCountChanged)
    wsActiveChanged = Signal(); wsActive = Property(int, lambda s: s._v["wsActive"], notify=wsActiveChanged)
    volumeChanged = Signal(); volume = Property(int, lambda s: s._v["volume"], notify=volumeChanged)
    fgSerialChanged = Signal(); fgSerial = Property(int, lambda s: s._v["fgSerial"], notify=fgSerialChanged)
    hasBatteryChanged = Signal(); hasBattery = Property(bool, lambda s: s._v["hasBattery"], notify=hasBatteryChanged)
    wifiConnectedChanged = Signal(); wifiConnected = Property(bool, lambda s: s._v["wifiConnected"], notify=wifiConnectedChanged)
    fullscreenChanged = Signal(); fullscreen = Property(bool, lambda s: s._v["fullscreen"], notify=fullscreenChanged)
    userHiddenChanged = Signal(); userHidden = Property(bool, lambda s: s._v["userHidden"], notify=userHiddenChanged)
    mutedChanged = Signal(); muted = Property(bool, lambda s: s._v["muted"], notify=mutedChanged)
    mediaPlayingChanged = Signal(); mediaPlaying = Property(bool, lambda s: s._v["mediaPlaying"], notify=mediaPlayingChanged)
    mediaProgressChanged = Signal(); mediaProgress = Property(float, lambda s: s._v["mediaProgress"], notify=mediaProgressChanged)
    wsPopulatedChanged = Signal(); wsPopulated = Property(list, lambda s: s._v["wsPopulated"], notify=wsPopulatedChanged)
    netKindChanged = Signal(); netKind = Property(str, lambda s: s._v["netKind"], notify=netKindChanged)
    outputsChanged = Signal(); outputs = Property(list, lambda s: s._v["outputs"], notify=outputsChanged)
    defaultOutputChanged = Signal(); defaultOutput = Property(str, lambda s: s._v["defaultOutput"], notify=defaultOutputChanged)
    komoOnlineChanged = Signal(); komoOnline = Property(bool, lambda s: s._v["komoOnline"], notify=komoOnlineChanged)
    layoutChanged = Signal(); layout = Property(str, lambda s: s._v["layout"], notify=layoutChanged)
    vizActiveChanged = Signal(); vizActive = Property(bool, lambda s: s._v["vizActive"], notify=vizActiveChanged)
    vizBarsChanged = Signal(); vizBars = Property(list, lambda s: s._v["vizBars"], notify=vizBarsChanged)
    fullHChanged = Signal(); fullH = Property(int, lambda s: s._v["fullH"], notify=fullHChanged)
    stripModeChanged = Signal(); stripMode = Property(bool, lambda s: s._v["stripMode"], notify=stripModeChanged)
    noGlassChanged = Signal(); noGlass = Property(bool, lambda s: s._v["noGlass"], notify=noGlassChanged)
    themeAccentChanged = Signal(); themeAccent = Property(str, lambda s: s._v["themeAccent"], notify=themeAccentChanged)
    themeBlueChanged = Signal(); themeBlue = Property(str, lambda s: s._v["themeBlue"], notify=themeBlueChanged)
    themeLavenderChanged = Signal(); themeLavender = Property(str, lambda s: s._v["themeLavender"], notify=themeLavenderChanged)
    themeHoverChanged = Signal(); themeHover = Property(str, lambda s: s._v["themeHover"], notify=themeHoverChanged)
    themeOutlineChanged = Signal(); themeOutline = Property(str, lambda s: s._v["themeOutline"], notify=themeOutlineChanged)
    trayCountChanged = Signal(); trayCount = Property(int, lambda s: s._v["trayCount"], notify=trayCountChanged)
    trayPinnedCountChanged = Signal(); trayPinnedCount = Property(int, lambda s: s._v["trayPinnedCount"], notify=trayPinnedCountChanged)
    uptimeChanged = Signal(); uptime = Property(str, lambda s: s._v["uptime"], notify=uptimeChanged)
    userAvatarChanged = Signal(); userAvatar = Property(str, lambda s: s._v["userAvatar"], notify=userAvatarChanged)
    userNameChanged = Signal(); userName = Property(str, lambda s: s._v["userName"], notify=userNameChanged)

    # -- worker -> UI thread hand-off --
    tasksIn = Signal(object)
    komoIn = Signal(object)
    wifiIn = Signal(object)
    phonesIn = Signal(object)
    weatherIn = Signal(object)
    mediaIn = Signal(object)
    glassIn = Signal(object)
    fsIn = Signal(object)
    fgIn = Signal()
    vizIn = Signal(object)
    toggleIn = Signal()
    trayIn = Signal(object)
    userIn = Signal(object)
    outsideIn = Signal()
    outsideClick = Signal()
    appNotice = Signal(str, str, str)     # app name, title, body of a notification from another app
    cliIn = Signal(object)                # a command from vaporctl.py (arrives on the CLI server thread)
    cliCommand = Signal(str, str)         # CLI commands QML has to carry out: alert / dismiss / timer / remind
    clockPoke = Signal()                  # once a second QML checks its timer + reminders (an OS timer, independent of Qt Quick's animation clock)

    def __init__(self, screen):
        super().__init__()
        g = screen.geometry()
        self.dpr = screen.devicePixelRatio()
        self.lw = g.width()
        self.lh = g.height()
        self.pw, self.ph = round(g.width() * self.dpr), round(g.height() * self.dpr)
        self._v = dict(
            glassColor="#ff14141f", glassOutline="#ff7a8cff", wifiName="", headphones="", mediaTitle="", mediaArtist="", mediaSource="", mediaArt="",
            mediaTime="", weatherIcon="", weatherTemp="", weatherDesc="", weatherRange="", weatherData="",
            screenX=g.x(), screenY=g.y(), screenW=g.width(), screenH=min(g.height(), STRIP_H), fullH=g.height(), sideMargin=0, battery=100, wsCount=0,
            wsActive=0, volume=0, fgSerial=0, hasBattery=False, wifiConnected=False, fullscreen=False, userHidden=False,
            muted=False, mediaPlaying=False, mediaProgress=0.0, wsPopulated=[],
            noGlass=False, stripMode=True, netKind="", outputs=[], defaultOutput="", komoOnline=False, layout="", vizActive=False, vizBars=[0.0] * 6, trayCount=0, trayPinnedCount=0,
            uptime="", userAvatar="", userName=load_config()["userName"] or os.environ.get("USERNAME", "user"),
            **{"theme" + k.capitalize(): v for k, v in DEFAULT_THEME.items()},
        )
        self.tasks = TaskModel()
        self.tray = TrayModel()
        self._settings = load_settings()
        self._tray_pin_order = list(self._settings.get("trayPins") or [])   # icons pinned to the bar, in bar order
        self._tray_pins = set(self._tray_pin_order)
        self._tray_seen = {}                                            # key -> order first seen (keeps the unpinned ones stable)
        self._tray_items = {}
        self._ov = {}                  # colours the control center's theme card overrides (glass / outline / accent ...)
        self._wall = {"glass": "#ff14141f", "outline": "#ff7a8cff"}       # what the wallpaper says
        self._ws_indices = []
        self._ws_hold = None            # (komorebi workspace index we just asked for, deadline)
        self._groups = {}
        self._order = []
        self._icons = QFileIconProvider()
        self._ep = None
        self._vol_tick = 0
        self._media = MediaWorker(self)
        self._bar_hwnd = 0
        self._clip_key = None          # last window clip, so SetWindowRgn only gets called when it actually changes
        self._reserved = False         # is the app-bar space reserved right now?
        self._edges = []               # frame windows (L / R / B) that reserve their edge at the moment
        self._komo_off = None          # the komorebi work-area offset we set last (None = never touched)
        self._maxfix = None            # {hwnd: (l, t, r, b)} of windows we pushed back inside the komorebi offset
        self._nat_fix = {}             # {hwnd: [times fixed, first time]} so we never fight an app that won't resize
        self._max_rec = {}             # same for `komorebic maximize` (komorebi online): {hwnd: [times fixed, first time]}
        self._ab_ok = False            # offline: does Windows' work area really contain our reservation? (set by _appbar_watch)
        self._ab_bad = 0               # consecutive bad checks
        self._ab_heals = []            # how many times we re-registered the app bars (rate limit)
        self._ab_quiet_until = 0.0
        self._cc_open = False          # control center open? (the click-outside watcher only runs then)
        self._rgn_warned = False
        self._out_seen = None          # output devices seen so far (id -> scans in a row it was missing)

        self.tasksIn.connect(self._on_tasks)
        self.komoIn.connect(self._on_komo)
        self.wifiIn.connect(self._on_wifi)
        self.phonesIn.connect(self._on_phones)
        self.weatherIn.connect(self._on_weather)
        self.mediaIn.connect(self._on_media)
        self.glassIn.connect(self._on_glass)
        self.fsIn.connect(self._on_fs)
        self.fgIn.connect(self._on_fg)
        self.outsideIn.connect(self.outsideClick)
        self.vizIn.connect(self._on_viz)
        self.toggleIn.connect(self._on_toggle)
        self.trayIn.connect(self._on_tray)
        self.userIn.connect(self._on_user)
        self.cliIn.connect(self._on_cli)

    def put(self, key, value):
        if self._v.get(key) == value:
            return
        self._v[key] = value
        getattr(self, key + "Changed").emit()

    def start(self):
        self._init_volume()
        self._nat_t = QTimer(self); self._nat_t.timeout.connect(self._clamp_native); self._nat_t.start(300)
        self._ab_t = QTimer(self); self._ab_t.timeout.connect(self._appbar_watch); self._ab_t.start(1500)
        self._battery_t = QTimer(self); self._battery_t.timeout.connect(self._poll_battery); self._battery_t.start(5000)
        self._volume_t = QTimer(self); self._volume_t.timeout.connect(self._poll_volume); self._volume_t.start(750)
        self._top_t = QTimer(self); self._top_t.timeout.connect(self._keep_on_top); self._top_t.start(200)
        self._poll_battery()
        self._clock_t = QTimer(self)
        self._clock_t.setTimerType(Qt.TimerType.PreciseTimer)
        self._clock_t.timeout.connect(self.clockPoke)
        self._clock_t.start(1000)
        for fn in (hotkey_loop, memory_loop, glass_loop, komorebi_loop, tasks_loop, wifi_loop, phones_loop, viz_loop, tray_loop, notif_loop, status_loop, click_outside_loop):
            threading.Thread(target=fn, args=(self,), daemon=True).start()
        self._media.start()

    # ---- UI-thread appliers ----
    def _icon(self, exe):
        if not exe:
            return ""
        key = hashlib.md5(exe.lower().encode("utf-8")).hexdigest()
        p = ICON_DIR / f"{key}.png"
        if not p.exists():
            try:
                pm = self._icons.icon(QFileInfo(exe)).pixmap(QSize(32, 32))
                if pm.isNull() or not pm.save(str(p), "PNG"):
                    return ""
            except Exception:
                return ""
        return QUrl.fromLocalFile(str(p)).toString()

    def _glyph_icon(self, name, glyph):
        """A white Segoe Fluent glyph drawn into a 48px png, for places where Windows gives no usable icon."""
        p = ICON_DIR / f"glyph_{name}.png"
        if not p.exists():
            try:
                img = QImage(48, 48, QImage.Format.Format_ARGB32)
                img.fill(0)
                pt = QPainter(img)
                pt.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                pt.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                f = QFont("Segoe Fluent Icons")
                f.setPixelSize(38)
                pt.setFont(f)
                pt.setPen(QColor(255, 255, 255))
                pt.drawText(img.rect(), int(Qt.AlignmentFlag.AlignCenter), glyph)
                pt.end()
                if not img.save(str(p), "PNG"):
                    return ""
            except Exception:
                return ""
        return QUrl.fromLocalFile(str(p)).toString()

    def _win_icon_url(self, hicon):
        r = hicon_rgba(hicon)
        if not r:
            return ""
        w, h, data = r
        p = ICON_DIR / ("win_" + hashlib.md5(data + bytes((w & 255, h & 255))).hexdigest()[:16] + ".png")
        if not p.exists():
            img = QImage(data, w, h, w * 4, QImage.Format.Format_ARGB32).copy()
            if w > 64 or h > 64 or max(w, h) < 48:
                img = img.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            if not img.save(str(p), "PNG"):
                return ""
        return QUrl.fromLocalFile(str(p)).toString()

    def _task_icon(self, g):
        exe = g["exe"]
        if g.get("uwp"):
            if os.path.basename(exe).lower() == "systemsettings.exe":
                url = self._glyph_icon("settings", "\uE713")           # the Settings gear
                if url:
                    return url
            if g.get("hicon"):
                try:
                    url = self._win_icon_url(g["hicon"])
                    if url:
                        return url
                except Exception:
                    log.exception("window icon")
        return self._icon(exe)

    @Slot(object)
    def _on_tasks(self, payload):
        wins, fg = payload
        groups = {}
        for w in wins:
            k = w["exe"].lower()
            g = groups.setdefault(k, {"exe": w["exe"], "hwnds": [], "title": w["title"],
                                      "uwp": w.get("uwp", False), "hicon": w.get("hicon", 0)})
            g["hwnds"].append(w["hwnd"])
        for k in groups:
            if k not in self._order:
                self._order.append(k)
        self._order = [k for k in self._order if k in groups]
        items = []
        for k in self._order:
            g = groups[k]
            title = next((w["title"] for w in wins if w["hwnd"] == fg and w["exe"].lower() == k), g["title"])
            items.append({"appKey": k, "appTitle": title, "isActive": fg in g["hwnds"],
                          "winCount": len(g["hwnds"]), "iconUrl": self._task_icon(g)})
        self._groups = groups
        self.tasks.update(items)

    @Slot(object)
    def _on_komo(self, d):
        was = bool(self._v["komoOnline"])
        is_online = d is not None
        changed = is_online != was

        if changed:
            self._komo_off = None
            self._ab_ok = False          # offline checks start fresh (they do nothing while komorebi is online)
            self._ab_bad = 0

        # update this first so _reserve_px() gives 36px online and 37px offline
        self.put("komoOnline", is_online)

        if changed:
            hwnd = self._bar()
            # the top reservation changes by APP_TOP_PAD between modes, so remove and register that one window again.
            # otherwise ABM_NEW / ABM_SETPOS leave a stale height behind
            if self._reserved:
                if hwnd:
                    appbar_remove(hwnd)
                self._reserved = False

            should_reserve = not (self._v["userHidden"] and HIDE_RELEASES_SPACE)
            self.set_reserve(should_reserve)

            if is_online:
                # set the komorebi work-area offset once Windows has updated its appbar area,
                # then retile after all the offsets have settled
                QTimer.singleShot(350, self.fit_apps)
                QTimer.singleShot(900, self.fit_apps)
                QTimer.singleShot(1600, self._komo_retile)
            else:
                QTimer.singleShot(900, self.fit_apps)

        if d is None:
            d = {"indices": [], "populated": [], "active": 0, "layout": ""}
        self._clamp_max(d)
        hold = self._ws_hold
        if hold is not None:
            cur = d["indices"][d["active"]] if d["indices"] and d["active"] < len(d["indices"]) else None
            if cur == hold[0] or cur is None or time.monotonic() > hold[1]:
                self._ws_hold = None
            else:
                return
        self.put("layout", d.get("layout", ""))
        self._ws_indices = d["indices"]
        self.put("wsPopulated", d["populated"])
        self.put("wsActive", d["active"])
        self.put("wsCount", len(d["indices"]))

    @Slot(object)
    def _on_user(self, d):
        self.put("uptime", d.get("uptime", ""))
        self.put("userAvatar", d.get("userAvatar", ""))
        self.put("userName", d.get("userName", ""))

    # ---- command line (vaporctl.py) ----
    @Slot(object)
    def _on_cli(self, req):
        out = req["out"]
        try:
            out["text"] = self._cli(req.get("cmd", ""), [str(a) for a in (req.get("args") or [])])
            out["ok"] = True
        except Exception as e:
            log.exception("cli: %s", req.get("cmd"))
            out["ok"] = False
            out["text"] = "error: %s" % e
        finally:
            req["ev"].set()

    def _set_hidden(self, on):
        self.put("userHidden", bool(on))
        self.set_reserve(True)

    def _cli(self, cmd, args):
        v = self._v
        a0 = args[0].lower() if args else ""
        if cmd == "ping":
            return "pong"
        if cmd == "status":
            ws = "%s/%s" % (v["wsActive"] + 1, v["wsCount"]) if v["komoOnline"] else "-"
            media = ("%s - %s" % (v["mediaTitle"], v["mediaArtist"]) if v["mediaArtist"] else v["mediaTitle"]) or "-"
            rows = [("volume", "%d%%%s" % (v["volume"], " (muted)" if v["muted"] else "")),
                    ("battery", ("%d%%" % v["battery"]) if v["hasBattery"] else "-"),
                    ("wifi", (v["wifiName"] or "connected") if v["wifiConnected"] else "off"),
                    ("media", media + (" [playing]" if v["mediaPlaying"] else "")),
                    ("workspace", ws), ("layout", v["layout"] or "-"),
                    ("bar", "hidden" if v["userHidden"] else "visible"),
                    ("fullscreen", "yes" if v["fullscreen"] else "no"), ("uptime", v["uptime"] or "-")]
            return "\n".join("%-10s %s" % r for r in rows)
        if cmd in ("hide", "show", "toggle"):
            self._set_hidden({"hide": True, "show": False}.get(cmd, not v["userHidden"]))
            return "bar hidden" if v["userHidden"] else "bar shown"
        if cmd == "volume":
            if args:
                self.setVolume(v["volume"] + int(a0) if a0[0] in "+-" else int(a0))
            return "volume %d%%%s" % (v["volume"], " (muted)" if v["muted"] else "")
        if cmd == "mute":
            if a0 not in ("on", "off") or (a0 == "on") != bool(v["muted"]):
                self.toggleMute()
            return "muted" if v["muted"] else "unmuted"
        if cmd == "media":
            if a0 in ("play", "pause", "toggle"):
                self.mediaPlayPause()
            elif a0 == "next":
                self.mediaNext()
            elif a0 in ("prev", "previous"):
                self.mediaPrev()
            elif a0:
                raise ValueError("media play|pause|next|prev")
            return ("%s - %s" % (v["mediaTitle"], v["mediaArtist"]) if v["mediaTitle"] else "nothing playing")
        if cmd == "ws":
            if a0 == "next":
                self.stepWorkspace(1)
            elif a0 in ("prev", "previous"):
                self.stepWorkspace(-1)
            else:
                self.focusWorkspaceAt(int(a0) - 1)
            return "ok"
        if cmd == "layout":
            self.cycleLayout(-1 if a0 in ("prev", "previous") else 1)
            return "ok"
        if cmd == "notify":
            self.notify(args[0] if args else "Vapor", args[1] if len(args) > 1 else "")
            return "toast sent"
        if cmd == "alert":
            self.cliCommand.emit("alert", json.dumps([args[0] if args else "Alert", args[1] if len(args) > 1 else ""]))
            return "alert shown (dismiss with: vaporctl dismiss)"
        if cmd == "dismiss":
            self.cliCommand.emit("dismiss", "")
            return "dismissed"
        if cmd == "timer":
            self.cliCommand.emit("timer-cancel" if a0 == "cancel" else "timer", "" if a0 == "cancel" else json.dumps(int(a0)))
            return "timer cancelled" if a0 == "cancel" else "timer started: %s s" % int(a0)
        if cmd == "remind":
            self.cliCommand.emit("remind", args[0])         # JSON built by vaporctl: {ts, t, rep}
            return "reminder added"
        if cmd == "clockdump":                               # reminders + timer, as saved
            return json.dumps(self._settings.get("clock") or {})
        if cmd == "notesdump":
            return json.dumps(self._settings.get("notes") or [])
        if cmd == "refresh":                                 # name / picture changed in config.json: apply now
            self._on_user({"uptime": uptime_str(), "userAvatar": avatar_path(),
                           "userName": load_config()["userName"] or os.environ.get("USERNAME", "user")})
            return "ok"
        if cmd == "location":                                # weather place changed in config.json: re-read it
            self.cliCommand.emit("location", "")
            return "ok"
        if cmd in ("note", "note-rm", "remind-rm"):
            self.cliCommand.emit(cmd, args[0])
            return "ok"
        if cmd == "restart":
            if FROZEN:      # sys.executable is Vapor.exe itself so it can't run "-c" code: wait 3 s with PowerShell, then start it again
                exe = str(Path(sys.executable).resolve()).replace("'", "''")
                ps = "Start-Sleep -Seconds 3; Start-Process -FilePath '%s' -WorkingDirectory '%s'" % (exe, str(APPDIR).replace("'", "''"))
                subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=0x08000000 | 0x00000200, close_fds=True)
            else:
                code = "import time,subprocess,sys;time.sleep(3);subprocess.Popen([sys.argv[1], sys.argv[2]], creationflags=0x08000000)"
                subprocess.Popen([sys.executable, "-c", code, sys.executable, str(HERE / "vapor.pyw")],
                                 creationflags=0x08000000 | 0x00000008, close_fds=True)
            QTimer.singleShot(150, QGuiApplication.quit)
            return "restarting"
        if cmd == "quit":
            QTimer.singleShot(150, QGuiApplication.quit)
            return "quitting"
        raise ValueError("unknown command: %s" % cmd)

    @Slot(object)
    def _on_wifi(self, d):
        self.put("wifiName", d[0])
        self.put("wifiConnected", d[1])
        self.put("netKind", d[2])

    @Slot(object)
    def _on_phones(self, d):
        self.put("headphones", d[0])
        self.put("outputs", d[1])
        self._auto_switch(d[1])

    def _auto_switch(self, outs):
        """A playback device that wasn't there in the previous scans just appeared, so make it the default."""
        if not outs:                      # a failed / empty scan says nothing about what was plugged in
            return
        cur = {o["id"]: o for o in outs}
        if self._out_seen is None:        # first scan: just remember what's already there
            self._out_seen = {i: 0 for i in cur}
            return
        new = [o for i, o in cur.items() if i not in self._out_seen]
        for i in list(self._out_seen):    # forget devices only after ~12 s away, so a flaky scan can't look like a "new" one
            if i in cur:
                self._out_seen[i] = 0
            else:
                self._out_seen[i] += 1
                if self._out_seen[i] >= 4:
                    del self._out_seen[i]
        for o in new:
            self._out_seen[o["id"]] = 0
        if new and AUTO_SWITCH_OUTPUT:
            pick = next((o for o in new if o["kind"] == "headphones"), new[0])
            if pick["key"] != self._v["defaultOutput"]:
                log.info("new output device %r -> making it the default", pick["label"])
                self.setOutput(pick["id"])

    @Slot(object)
    def _on_weather(self, d):
        self.put("weatherIcon", d["icon"])
        self.put("weatherTemp", d["temp"])
        self.put("weatherDesc", d["desc"])
        self.put("weatherRange", d["range"])
        self.put("weatherData", d.get("data", ""))

    @Slot(object)
    def _on_media(self, d):
        self.put("mediaTitle", d.get("title", ""))
        self.put("mediaArtist", d.get("artist", ""))
        self.put("mediaSource", d.get("source", ""))
        self.put("mediaPlaying", d.get("playing", False))
        art = d.get("art", "")
        self.put("mediaArt", QUrl.fromLocalFile(art).toString() if art else "")
        self.put("mediaProgress", float(d.get("progress", 0.0)))
        self.put("mediaTime", d.get("time", ""))

    @Slot(object)
    def _on_glass(self, d):
        self._wall = {"glass": d[0], "outline": d[1]}
        self._refresh_colors()

    @Slot(object)
    def _on_fs(self, on):
        self.put("fullscreen", bool(on))

    @Slot()
    def _on_toggle(self):
        log.info("hotkey: quitting Vapor")
        QGuiApplication.quit()

    def _reserve_px(self):
        """The shell stays at 36px, only Windows-normal mode gets the original 1px safety gap."""
        extra = 0 if self._v["komoOnline"] else APP_TOP_PAD
        return round((RESERVE_H + extra) * self.dpr)

    def set_reserve(self, on):
        """Keep Windows appbars for native maximize in both modes. Komorebi has its own tiling offset."""
        try:
            should_reserve = bool(on and not (self._v["userHidden"] and HIDE_RELEASES_SPACE))

            # when hiding / exiting with komorebi online, remove the live offset this shell owns.
            # that also clears a stale offset left by older Vapor versions
            if self._v["komoOnline"] and not should_reserve:
                if self._komo_off != (0, 0, 0, 0):
                    spawn(["komorebic", "global-work-area-offset", "0", "0", "0", "0"])
                    self._komo_off = (0, 0, 0, 0)

            if not USE_APPBAR:
                QTimer.singleShot(150, self.fit_apps)
                return

            hwnd = self._bar()
            if not hwnd:
                QTimer.singleShot(300, lambda: self.set_reserve(not (self._v["userHidden"] and HIDE_RELEASES_SPACE)))
                return

            if should_reserve and not self._reserved:
                appbar_register(hwnd, self.pw, self._reserve_px())
                self._reserved = True
            elif not should_reserve and self._reserved:
                appbar_remove(hwnd)
                self._reserved = False

            # keep all four Windows reservations alive, online and offline. native maximized windows
            # respect appbars, komorebi tiled windows respect global-work-area-offset
            want_frame = bool(should_reserve and RESERVE_FRAME)
            if want_frame and not self._edges:
                thick = round(FRAME_W * self.dpr)
                if self._v["komoOnline"]:
                    sizes = {0: thick, 2: thick, 3: thick}          # online: exactly as before
                else:
                    il, _it, ir, ib = self._offline_insets()        # offline: frame + YASB-style padding
                    sizes = {0: il, 2: ir, 3: ib}
                for title, edge in (("Vapor L", 0), ("Vapor R", 2), ("Vapor B", 3)):
                    eh = find_win_hwnd(title)
                    if eh:
                        appbar_register_edge(eh, edge, sizes[edge], self.pw, self.ph)
                        self._edges.append(eh)
                if len(self._edges) < 3:
                    for eh in self._edges:
                        appbar_remove(eh)
                    self._edges = []
                    QTimer.singleShot(600, lambda: self.set_reserve(not (self._v["userHidden"] and HIDE_RELEASES_SPACE)))
            elif not want_frame and self._edges:
                for eh in self._edges:
                    appbar_remove(eh)
                self._edges = []

            QTimer.singleShot(500, self.fit_apps)
        except Exception:
            log.exception("appbar")

    def _offline_insets(self):
        """(left, top, right, bottom) px reserved while komorebi is offline: the bar / glass frame plus OFFLINE_PAD.
                All the maths lives here so the app bars, the watcher and the maximize fallback can't disagree."""
        f = 0 if not RESERVE_FRAME else round(FRAME_W * self.dpr)
        p = OFFLINE_PAD
        return (f + round(p["left"] * self.dpr),
                round((RESERVE_H + p["top"]) * self.dpr),
                f + round(p["right"] * self.dpr),
                f + round(p["bottom"] * self.dpr))

    def _reregister_appbars(self):
        """Give every reservation back and register all four again in a fixed order (top first, then L / R / B)."""
        hwnd = self._bar()
        if not hwnd:
            return
        for eh in self._edges:
            appbar_remove(eh)
        self._edges = []
        if self._reserved:
            appbar_remove(hwnd)
        self._reserved = False
        self.set_reserve(True)

    def _appbar_watch(self):
        """Komorebi offline only. A proper app bar registers itself again whenever Windows says the layout changed
                (explorer restart, display change, sleep / unlock ...). We have no message hook, so we just look: if the
                monitor's work area is smaller than what we reserved, the reservation got lost and we register again.
                Rate limited, and while it's healthy the maximize fallback (_clamp_native) stays out of Windows' way."""
        if self._v["komoOnline"] or not USE_APPBAR:
            self._ab_ok, self._ab_bad = False, 0
            return
        if self._v["fullscreen"]:
            return
        if (self._v["userHidden"] and HIDE_RELEASES_SPACE) or not self._reserved:
            self._ab_ok, self._ab_bad = False, 0
            return
        try:
            hwnd = self._bar()
            if not hwnd:
                return
            mon = user32.MonitorFromWindow(hwnd, 2)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(mi)
            if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
                return
            m, w = mi.rcMonitor, mi.rcWork
            got = (w.left - m.left, w.top - m.top, m.right - w.right, m.bottom - w.bottom)
            want = self._offline_insets()
            # more is fine (a visible taskbar), less means we lost our space. a changed monitor size counts too
            ok = (all(g >= x - 1 for g, x in zip(got, want))
                  and (m.right - m.left, m.bottom - m.top) == (self.pw, self.ph))
            self._ab_ok = ok
            if ok:
                self._ab_bad = 0
                return
            self._ab_bad += 1
            if self._ab_bad < 2:                         # let Windows finish rebuilding first
                return
            now = time.monotonic()
            if now < self._ab_quiet_until:
                return
            self._ab_heals = [x for x in self._ab_heals if now - x < 60]
            if len(self._ab_heals) >= 3:
                self._ab_quiet_until = now + 60
                log.warning("appbar: work area %s still smaller than %s after 3 tries; the maximize fallback covers it", got, want)
                return
            self._ab_heals.append(now)
            self._ab_bad = 0
            log.info("appbar: work area insets %s are smaller than reserved %s (monitor %s, shell %s): registering again",
                     got, want, (m.right - m.left, m.bottom - m.top), (self.pw, self.ph))
            self.fitWindow()
            self._reregister_appbars()
        except Exception:
            log.exception("appbar watch")

    def _komo_retile(self):
        """Ask komorebi to recalculate the tiled window bounds after the work-area offset changed."""
        if self._v["komoOnline"] and not self._v["userHidden"]:
            spawn(["komorebic", "retile"])

    def _clamp_native(self):
        """No komorebi: Windows' work area isn't reliable here (the shell resets it), so we keep every maximized
                window inside the box between the bar and the glass frame ourselves. Cheap, only maximized windows get touched."""
        if not CLAMP_MAXIMIZED or self._v["komoOnline"] or self._v["fullscreen"]:
            return
        if self._v["userHidden"] and HIDE_RELEASES_SPACE:
            return
        try:
            bar = self._bar()
            if not bar:
                return
            mon = user32.MonitorFromWindow(bar, 1)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(mi)
            if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
                return
            m = mi.rcMonitor
            il, it, ir, ib = self._offline_insets()
            l, t, r, b = m.left + il, m.top + it, m.right - ir, m.bottom - ib
            own = os.getpid()
            found = []

            @EnumProc
            def cb(h, _lp):
                try:
                    if not user32.IsWindowVisible(h) or not user32.IsZoomed(h) or user32.IsIconic(h):
                        return True
                    style = user32.GetWindowLongW(h, GWL_STYLE)
                    if (style & WS_CAPTION) != WS_CAPTION and not (style & WS_THICKFRAME):
                        # truly borderless and not resizable: only skip it if it covers the monitor exactly
                        r0 = wintypes.RECT()
                        if not user32.GetWindowRect(h, ctypes.byref(r0)) or (r0.left, r0.top, r0.right, r0.bottom) == (m.left, m.top, m.right, m.bottom):
                            return True
                    if user32.MonitorFromWindow(h, 0) != mon:
                        return True
                    cloaked = wintypes.DWORD(0)
                    dwmapi.DwmGetWindowAttribute(h, 14, ctypes.byref(cloaked), 4)
                    if cloaked.value or class_of(h) in SKIP_CLASSES or pid_of(h) == own:
                        return True
                    found.append(int(h))
                except Exception:
                    pass
                return True

            user32.EnumWindows(cb, 0)
            now = time.monotonic()
            self._nat_fix = {h: v for h, v in self._nat_fix.items() if h in found}
            for h in found:
                rc = wintypes.RECT()
                if not user32.GetWindowRect(h, ctypes.byref(rc)):
                    continue
                ext = wintypes.RECT()
                if dwmapi.DwmGetWindowAttribute(h, 9, ctypes.byref(ext), ctypes.sizeof(ext)) == 0:
                    bl, bt, br, bb = ext.left - rc.left, ext.top - rc.top, rc.right - ext.right, rc.bottom - ext.bottom
                else:
                    ext, bl, bt, br, bb = rc, 0, 0, 0, 0
                if (abs(ext.left - l) <= 2 and abs(ext.top - t) <= 2
                        and abs(ext.right - r) <= 2 and abs(ext.bottom - b) <= 2):
                    continue
                rec = self._nat_fix.get(h)
                if rec is None or now - rec[1] > 5.0:
                    rec = self._nat_fix[h] = [0, now]
                if rec[0] >= 6:
                    continue                             # this window keeps undoing us, stop for a few seconds
                rec[0] += 1
                if rec[0] >= 2:
                    # it snapped back after a plain move (Chromium / Electron: Spotify, Discord, VS Code ...):
                    # leave the maximized state first, then place it, otherwise the app re-maximizes itself
                    user32.ShowWindow(h, 9)              # SW_RESTORE
                user32.SetWindowPos(h, wintypes.HWND(0), l - bl, t - bt, (r - l) + bl + br, (b - t) + bt + bb, 0x0014)
        except Exception:
            log.exception("clamp native")

    def _clamp_max(self, d):
        """Komorebi's global-work-area-offset changes what it tiles, but `komorebic maximize` still puts the window
                over the monitor's raw work area, so it slides under the bar. Every state event carries the focused
                workspace's maximized window, so whenever one is up we size it back into the box a single tiled window
                would fill (m + our offset)."""
        try:
            online = bool(d is not None and self._v.get("komoOnline")
                          and not (self._v.get("userHidden") and HIDE_RELEASES_SPACE)
                          and self._komo_off is not None
                          and isinstance(self._komo_off, (tuple, list)))
            hwnds = sorted(d.get("maximized") or []) if online else []
            if not hwnds:
                self._maxfix = None
                self._max_rec = {}
                return
            self._max_rec = {h: v for h, v in self._max_rec.items() if h in hwnds}
            hwnd = self._bar()
            mon = user32.MonitorFromWindow(hwnd or 0, 1)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(mi)
            if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
                return
            m = mi.rcMonitor
            off = self._komo_off
            # komorebi's offset: left / top move the origin, right / bottom shrink the width / height (see fit_apps)
            l = m.left + off[0]
            t = m.top + off[1]
            r = l + (m.right - m.left) - off[2]
            b = t + (m.bottom - m.top) - off[3]
            moved = False
            now = time.monotonic()
            for h in hwnds:
                if not user32.IsWindow(h):
                    continue
                rc = wintypes.RECT()
                if not user32.GetWindowRect(h, ctypes.byref(rc)):
                    continue
                # windows have an invisible DWM border, so compare / place the visible frame like komorebi does
                ext = wintypes.RECT()
                if dwmapi.DwmGetWindowAttribute(h, 9, ctypes.byref(ext), ctypes.sizeof(ext)) == 0:
                    bl, bt, br, bb = ext.left - rc.left, ext.top - rc.top, rc.right - ext.right, rc.bottom - ext.bottom
                else:
                    ext, bl, bt, br, bb = rc, 0, 0, 0, 0
                if (abs(ext.left - l) <= 2 and abs(ext.top - t) <= 2
                        and abs(ext.right - r) <= 2 and abs(ext.bottom - b) <= 2):
                    continue                      # already where it belongs
                # Chromium / Electron apps (Discord, Spotify, VS Code ...) snap a maximized window straight back to the
                # work area after a plain move. same trick as the offline clamp: leave the maximized state first, then place
                # the window. Chromium windows get it right away (no visible two-step), other apps only if they snapped back.
                # a small budget per window keeps us from fighting an app that insists
                rec = self._max_rec.get(h)
                if rec is None or now - rec[1] > 5.0:
                    rec = self._max_rec[h] = [0, now]
                if rec[0] >= 6:
                    continue                      # this window keeps undoing us, stop for a few seconds
                rec[0] += 1
                if rec[0] >= 2 or class_of(h).startswith(("Chrome_WidgetWin", "CefBrowserWindow")):
                    user32.ShowWindow(h, 9)       # SW_RESTORE
                user32.SetWindowPos(h, wintypes.HWND(0), l - bl, t - bt, (r - l) + bl + br, (b - t) + bt + bb,
                                    0x0004 | 0x0010)   # SWP_NOZORDER | SWP_NOACTIVATE
                moved = True
            self._maxfix = {h: (l, t, r, b) for h in hwnds}
            # komorebi (or the app) may move the window itself shortly after us, so check again a few times and then
            # stop (6 fixes per 5 s for each window, see _max_rec)
            if moved:
                QTimer.singleShot(250, self._assert_max)
        except Exception:
            log.exception("maximize clamp")

    def _assert_max(self):
        """One follow-up pass so a late komorebi reposition can't win. Never loops."""
        if not self._maxfix:
            return
        d = {"maximized": list(self._maxfix)}
        self._maxfix = None
        self._clamp_max(d)

    def fit_apps(self):
        """Windows appbars handle native maximize, explicit komorebi offsets handle the tiled windows."""
        try:
            hwnd = self._bar()
            if not hwnd:
                return
            mon = user32.MonitorFromWindow(hwnd, 2)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(mi)
            if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
                return
            m = mi.rcMonitor

            hidden = self._v["userHidden"] and HIDE_RELEASES_SPACE
            f = 0 if (hidden or not RESERVE_FRAME) else round(FRAME_W * self.dpr)
            t = 0 if hidden else self._reserve_px()

            if self._v["komoOnline"]:
                # komorebi's offset doesn't depend on Windows' maximize work area. left / top shift the origin, right /
                # bottom shrink the width / height, so the visible gaps come out as f at the sides / bottom and t above the shell.
                # APP_TOP_PAD is left out on purpose while komorebi is active (t = 36px)
                off = (f, t, 2 * f, t + f)
                if off != self._komo_off:
                    self._komo_off = off
                    log.info("komorebi work-area offset %s (shell top=%d, frame=%d; monitor=%s)",
                             off, t, f, (m.left, m.top, m.right, m.bottom))
                    spawn(["komorebic", "global-work-area-offset", *[str(v) for v in off]])

        except Exception:
            log.exception("fit apps")

    def _bar(self):
        if not self._bar_hwnd or not user32.IsWindow(self._bar_hwnd):
            self._bar_hwnd = find_bar_hwnd()
        return self._bar_hwnd

    MENU_CLASSES = {"#32768", "Xaml_WindowedPopupClass", "NotifyIconOverflowWindow", "TopLevelWindowForOverflowXamlIsland"}

    def _menu_above(self, hw, own):
        """True if something that must stay above the bar already sits above `hw`, so raising the bar would cover it:
            - a visible context menu / flyout (tray icon right-click menus, classes in MENU_CLASSES), or
            - one of Vapor's own full-screen overlays (the power menu), which is a separate window of this process
              and used to count as 'a foreign window above the bar' that had to be raised over."""
        try:
            me = os.getpid()
            above, n = user32.GetWindow(hw, 3), 0            # GW_HWNDPREV
            while above and n < 100:
                if above not in own and user32.IsWindowVisible(above):
                    if class_of(above) in self.MENU_CLASSES:
                        return True
                    if pid_of(above) == me:
                        r = wintypes.RECT()
                        user32.GetWindowRect(above, ctypes.byref(r))
                        if (r.right - r.left) >= self.pw and (r.bottom - r.top) >= self.ph:
                            return True
                above = user32.GetWindow(above, 3)
                n += 1
        except Exception:
            pass
        return False

    def _keep_on_top(self, force=False):
        """The bar and its popup are always-on-top windows, but other windows can take the top spot (Explorer's
                taskbar, another always-on-top app, an overlay ...) and nothing put ours back, so a hovered popup could end up
                behind an app. Every 200 ms: if a visible foreign window overlaps the bar / popup AND sits above it in the
                z-order, raise ours again (topmost, no activation, so focus and clicks are not disturbed). The bar goes first
                and the popup last so the popup always ends up on the very top."""
        if not force and (self._v["fullscreen"] or self._v["userHidden"]):
            return
        try:
            wins = {}
            for w in QGuiApplication.topLevelWindows():
                if w.title() in ("Vapor", "Vapor Popup", "Vapor L", "Vapor R", "Vapor B"):
                    wins[w.title()] = int(w.winId())
            own = set(wins.values())
            for title in ("Vapor", "Vapor Popup"):
                hw = wins.get(title)
                if not hw or not user32.IsWindow(hw) or not user32.IsWindowVisible(hw):
                    continue
                if time.time() < getattr(self, "_menu_until", 0.0) or self._menu_above(hw, own):
                    continue                           # a tray icon was just clicked / a menu or the power menu is up: leave it on top
                need = force
                if not need:
                    mine = wintypes.RECT()
                    user32.GetWindowRect(hw, ctypes.byref(mine))
                    above, n = user32.GetWindow(hw, 3), 0        # GW_HWNDPREV: the window right above this one
                    while above and n < 100 and not need:
                        if above not in own and user32.IsWindowVisible(above):
                            r = wintypes.RECT()
                            user32.GetWindowRect(above, ctypes.byref(r))
                            if (r.right > r.left and r.bottom > r.top and r.left < mine.right and r.right > mine.left
                                    and r.top < mine.bottom and r.bottom > mine.top):
                                need = True
                                cls = class_of(above)
                                seen = self.__dict__.setdefault("_cover_seen", set())
                                if cls not in seen and len(seen) < 40:
                                    seen.add(cls)
                                    log.info("keep on top: raising %s over window class %r (%s)", title, cls,
                                             os.path.basename(exe_of(pid_of(above)) or "?"))
                        above = user32.GetWindow(above, 3)
                        n += 1
                if need:
                    user32.SetWindowPos(hw, wintypes.HWND(-1), 0, 0, 0, 0, 0x0013)   # HWND_TOPMOST, NOSIZE | NOMOVE | NOACTIVATE
        except Exception:
            log.exception("keep on top")

    @Slot()
    def raiseOnTop(self):
        """Can be called from QML (e.g. when a popup opens or is hovered): put the bar and popup on top right now."""
        self._keep_on_top(True)

    @Slot(bool)
    def setControlOpen(self, on):
        self._cc_open = bool(on)

    @Slot()
    def _on_fg(self):
        self.put("fgSerial", self._v["fgSerial"] + 1)

    @Slot(object)
    def _on_viz(self, d):
        self.put("vizActive", bool(d[0]))
        self.put("vizBars", d[1])

    def _refresh_colors(self):
        """Final colours are the wallpaper's, except the parts the theme card overrides:
                shell (glass fill), outline (its rim) and icons (accent / blue / lavender / hover)."""
        try:
            ov, wall = self._ov, self._wall
            outline = ov.get("outline") or wall["outline"]
            self.put("glassColor", ov.get("glass") or wall["glass"])
            self.put("glassOutline", outline)
            self.put("themeOutline", argb_alpha(outline, 0.34))
            icons = ({k: ov[k] for k in ("accent", "blue", "lavender", "hover")} if ov.get("accent")
                     else wallpaper_icons(wall["outline"]))
            for k, val in icons.items():
                self.put("theme" + k.capitalize(), val)
        except Exception:
            log.exception("refresh colours")

    def applyThemeColors(self, d):
        """Overrides from the control center's theme card (live) and the saved ones at start. Missing keys follow
                the wallpaper, an empty dict means everything follows the wallpaper."""
        self._ov = dict(d or {})
        self._refresh_colors()

    # notification
    APP_ID = "Vapor.Shell"

    def _register_app_id(self):
        """Registers 'Vapor' as a notification sender (HKCU, no admin) so toasts say Vapor and not PowerShell."""
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\AppUserModelId" + "\\" + self.APP_ID) as k:
                winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "Vapor")
                winreg.SetValueEx(k, "ShowInSettings", 0, winreg.REG_DWORD, 1)
        except Exception:
            log.exception("could not register notification app id")

    @Slot(str, str)
    def notify(self, title, body):
        self._register_app_id()
        ps = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
            "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
            "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
            "$x.LoadXml('<toast><visual><binding template=\"ToastGeneric\"><text></text><text></text></binding></visual></toast>');"
            "$n = $x.GetElementsByTagName('text');"
            "$n.Item(0).AppendChild($x.CreateTextNode($env:TOAST_T)) | Out-Null;"
            "$n.Item(1).AppendChild($x.CreateTextNode($env:TOAST_B)) | Out-Null;"
            "$t = [Windows.UI.Notifications.ToastNotification]::new($x);"
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:TOAST_APP).Show($t)"
        )
        env = dict(os.environ, TOAST_T=title or "Vapor", TOAST_B=body or "", TOAST_APP=self.APP_ID)
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                         env=env, creationflags=0x08000000)

    # ---- system tray ----
    @Slot(object)
    def _on_tray(self, items):
        self._tray_items = {it["key"]: it for it in items}
        self._render_tray()

    def _render_tray(self):
        for k in self._tray_items:
            if k not in self._tray_seen:
                self._tray_seen[k] = len(self._tray_seen)
        order = {k: i for i, k in enumerate(self._tray_pin_order)}
        items = sorted(self._tray_items.values(),
                       key=lambda it: (0, order[it["key"]]) if it["key"] in order else (1, self._tray_seen[it["key"]]))
        rows = [dict(trayKey=it["key"], trayTitle=it["title"], iconUrl=it["iconUrl"] or self._icon(it["exe"]),
                     pinned=it["key"] in self._tray_pins) for it in items]
        self.tray.update(rows)
        self.put("trayCount", len(rows))
        self.put("trayPinnedCount", sum(1 for r in rows if r["pinned"]))

    @Slot(str, str)
    def trayClick(self, key, button):
        it = self._tray_items.get(key)
        if it:
            self._menu_until = time.time() + 10.0          # its menu opens now: don't raise the bar over it meanwhile
            try:
                tray_click(it, button)
            except Exception:
                log.exception("tray click")

    # ---- clock page: alarms + timer live in settings.json, the ring is a beep loop until dismissed ----
    @Slot(result=str)
    def weatherPlace(self):
        """The weather place from config.json (set with `vaporctl set location`), or "" for automatic."""
        loc = load_config().get("location")
        return json.dumps(loc) if loc else ""

    @Slot(result=str)
    def clockLoad(self):
        return json.dumps(self._settings.get("clock") or {})

    @Slot(str)
    def clockSave(self, data):
        try:
            self._settings["clock"] = json.loads(data)
            save_settings(self._settings)
        except Exception:
            log.exception("clock settings not saved")

    # ---- notes (right-edge side panel): kept in settings.json next to the reminders ----
    @Slot(result=str)
    def notesLoad(self):
        return json.dumps(self._settings.get("notes") or [])

    @Slot(str)
    def notesSave(self, data):
        try:
            self._settings["notes"] = json.loads(data)
            save_settings(self._settings)
        except Exception:
            log.exception("notes not saved")

    @Slot()
    def ringStart(self):
        self.ringStop()
        ev = threading.Event()
        self._ring_ev = ev
        f = FILES / "ringtone.mp3"
        if not f.is_file():
            log.warning("alarm: no sound played, file not found: %s", f)
            return

        def run():                                   # one thread owns every MCI call for this alias
            mci = ctypes.windll.winmm.mciSendStringW
            alias = "vaporring"
            buf = ctypes.create_unicode_buffer(64)
            try:
                mci(f"close {alias}", None, 0, None)
                if mci(f'open "{f}" type mpegvideo alias {alias}', None, 0, None):
                    log.error("alarm: could not open %s", f)
                    return
                mci(f"play {alias}", None, 0, None)
                while not ev.wait(0.25):
                    mci(f"status {alias} mode", buf, 63, None)
                    if buf.value != "playing":       # reached the end, start over until dismissed
                        mci(f"seek {alias} to start", None, 0, None)
                        mci(f"play {alias}", None, 0, None)
            except Exception:
                log.exception("alarm sound")
            finally:
                try:
                    mci(f"stop {alias}", None, 0, None)
                    mci(f"close {alias}", None, 0, None)
                except Exception:
                    pass
        threading.Thread(target=run, daemon=True).start()

    @Slot()
    def ringStop(self):
        ev = getattr(self, "_ring_ev", None)
        if ev is not None:
            ev.set()

    def _save_pins(self):
        self._tray_pins = set(self._tray_pin_order)
        self._settings["trayPins"] = list(self._tray_pin_order)
        save_settings(self._settings)
        self._render_tray()

    @Slot(str)
    def trayTogglePin(self, key):
        if key in self._tray_pins:
            self._tray_pin_order = [k for k in self._tray_pin_order if k != key]
        else:
            self._tray_pin_order.append(key)
        self._save_pins()

    @Slot(str, bool, int)
    def trayMove(self, key, pinned, index):
        """Drag and drop in the tray popup: put `key` in the bar at slot `index` (among the icons that are showing), or
                take it out of the bar. Pinned programs that aren't running keep their place at the end."""
        shown = [k for k in self._tray_pin_order if k in self._tray_items and k != key]
        absent = [k for k in self._tray_pin_order if k not in self._tray_items and k != key]
        if pinned:
            i = len(shown) if index < 0 else max(0, min(index, len(shown)))
            shown.insert(i, key)
        self._tray_pin_order = shown + absent
        self._save_pins()

    # ---- battery & volume ----
    def _poll_battery(self):
        st = SYSTEM_POWER_STATUS()
        if not kernel32.GetSystemPowerStatus(ctypes.byref(st)):
            return
        present = not (st.BatteryFlag & 128) and st.BatteryLifePercent != 255
        self.put("battery", int(st.BatteryLifePercent) if present else 100)
        self.put("hasBattery", bool(present and st.ACLineStatus == 0))  # only shown when unplugged

    def _init_volume(self):
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            dev = AudioUtilities.GetSpeakers()
            try:
                self.put("defaultOutput", str(getattr(dev, "id", None) or dev.GetId()).lower())
            except Exception:
                pass
            ep = getattr(dev, "EndpointVolume", None)
            if ep is None:
                iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                ep = ctypes.cast(iface, ctypes.POINTER(IAudioEndpointVolume))
            self._ep = ep
        except Exception:
            self._ep = None
            log.warning("volume unavailable (pip install pycaw comtypes)", exc_info=True)

    def _poll_volume(self):
        self._vol_tick += 1
        if self._ep is None or self._vol_tick % 100 == 0:  # re-bind now and then (about every 30 s, a device change re-binds at once, see the line below)
            self._init_volume()
        if self._ep is None:
            return
        try:
            self.put("volume", int(round(self._ep.GetMasterVolumeLevelScalar() * 100)))
            self.put("muted", bool(self._ep.GetMute()))
        except Exception:
            self._ep = None

    # ---- slots called from QML ----
    @Slot(int)
    def setVolume(self, v):
        v = max(0, min(100, v))
        if self._ep is None:
            return
        try:
            self._ep.SetMasterVolumeLevelScalar(v / 100.0, None)
            if v > 0 and self._v["muted"]:
                self._ep.SetMute(0, None)
                self.put("muted", False)
            self.put("volume", v)
        except Exception:
            log.warning("set volume failed", exc_info=True)

    @Slot(int)
    def stepVolume(self, d):
        self.setVolume(self._v["volume"] + d)

    @Slot()
    def toggleMute(self):
        if self._ep is None:
            return
        try:
            m = not bool(self._ep.GetMute())
            self._ep.SetMute(1 if m else 0, None)
            self.put("muted", m)
        except Exception:
            log.warning("mute failed", exc_info=True)

    @Slot(int)
    def focusWorkspaceAt(self, pos):
        if 0 <= pos < len(self._ws_indices):
            self.put("wsActive", pos)  # move the pill right away, komorebi's next event confirms it
            self._ws_hold = (self._ws_indices[pos], time.monotonic() + 1.2)
            spawn(["komorebic", "focus-workspace", str(self._ws_indices[pos])])

    @Slot(str)
    def setOutput(self, dev_id):
        try:
            try:
                set_default_output(dev_id)
            except Exception:
                set_default_output(dev_id.lower())
            self.put("defaultOutput", dev_id.lower())
            self._init_volume()  # follow the new device with the slider
        except Exception:
            log.warning("switching output failed", exc_info=True)

    @Slot(result=str)
    def grabScreen(self):
        """Screenshot of the monitor the bar is on, used as the power screen's backdrop (a see-through look without a
                transparent full-screen window). Saves a sharp copy and a small blurry one and returns the sharp file's URL,
                or '' if it failed (the power screen then just uses the plain glass colour). The two URLs change on every call
                so QML never shows an older cached picture."""
        try:
            scr = QGuiApplication.primaryScreen()
            g = scr.geometry()
            for sc in QGuiApplication.screens():
                if sc.geometry().x() == self._v["screenX"] and sc.geometry().y() == self._v["screenY"]:
                    scr, g = sc, sc.geometry()
                    break
            img = scr.grabWindow(0, 0, 0, g.width(), g.height()).toImage()
            if img.isNull():
                return ""
            self._grab_n = getattr(self, "_grab_n", 0) + 1
            for f in list(ICON_DIR.glob("power_bg_*.bmp")) + list(ICON_DIR.glob("power_bg_*_blur.png")):
                try:
                    f.unlink()
                except OSError:
                    pass
            a = ICON_DIR / ("power_bg_%d.bmp" % self._grab_n)      # BMP: no compression, so saving takes a few ms
            c = ICON_DIR / ("power_bg_%d_blur.png" % self._grab_n)
            small = img.scaled(max(16, img.width() // 14), max(9, img.height() // 14),
                               Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            if not (img.save(str(a), "PNG") and small.save(str(c), "PNG")):
                return ""
            return QUrl.fromLocalFile(str(a)).toString()
        except Exception:
            log.exception("grab screen")
            return ""

    @Slot(str)
    def fitFullscreen(self, title):
        """Make a full-screen overlay window (the power menu) cover its monitor exactly, in real device pixels.
                Qt can hand a frameless window a few pixels too many at fractional scaling (125 %), and a transparent window
                bigger than the screen makes dwm.exe allocate way more memory."""
        try:
            hwnd = user32.FindWindowW(None, title)
            if not hwnd:
                return
            mon = user32.MonitorFromWindow(hwnd, 2)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(mi)
            if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
                return
            m = mi.rcMonitor
            cur = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(cur))
            have = (cur.left, cur.top, cur.right, cur.bottom)
            want = (m.left, m.top, m.right, m.bottom)
            if have != want:
                user32.SetWindowPos(hwnd, wintypes.HWND(-1), m.left, m.top, want[2] - want[0], want[3] - want[1], 0x0010)
        except Exception:
            log.exception("fit fullscreen")

    @Slot()
    def fitWindow(self):
        """Make the bar window cover this monitor exactly, measured in real device pixels by Windows itself (not Qt's
                rounded logical size). If it's a few pixels too big the right / bottom part of the glass frame ends up
                off-screen and looks missing. This stops that whatever the scaling / resolution is."""
        try:
            hwnd = self._bar()
            if not hwnd:
                return
            mon = user32.MonitorFromWindow(hwnd, 2)          # MONITOR_DEFAULTTONEAREST
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(mi)
            if not mon or not user32.GetMonitorInfoW(mon, ctypes.byref(mi)):
                return
            m = mi.rcMonitor
            cur = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(cur))
            want = (m.left, m.top, m.right, m.top + round(self._v["screenH"] * self.dpr))
            have = (cur.left, cur.top, cur.right, cur.bottom)
            if have != want:
                log.info("bar window is %s but the monitor is %s (dpr %.2f): fitting it to the monitor",
                         have, want, self.dpr)
                # HWND_TOPMOST, SWP_NOACTIVATE
                user32.SetWindowPos(hwnd, wintypes.HWND(-1), m.left, m.top, want[2] - want[0], want[3] - want[1], 0x0010)
                self._clip_key = None                        # the clip is recomputed for the new size
            self.pw, self.ph = m.right - m.left, m.bottom - m.top
        except Exception:
            log.exception("fit window")

    @Slot(int, int, int, int, int, int, int, int, int)
    def setClip(self, hx, hy, hw, hh, hr, px, py, pw, ph):
        """The bar is one screen-sized window. This clips it to the glass frame: the whole screen minus the rounded
                'hole' in the middle (hx,hy,hw,hh, corner radius hr), plus the popup panel rectangle (px,py,pw,ph, empty
                when no popup is out). Anything outside that isn't part of the window, so clicks fall straight through."""
        key = (hx, hy, hw, hh, hr, px, py, pw, ph)
        if key == self._clip_key:
            return
        try:
            hwnd = self._bar()
            if not hwnd:
                return
            d = self.dpr
            wr = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(wr))     # the window's real size in device pixels
            rgn = gdi32.CreateRectRgn(0, 0, wr.right - wr.left, wr.bottom - wr.top)
            if hw > 8 and hh > 8:
                # the hole is 2 device px smaller than the drawn one so the anti-aliased edge pixels of the
                # curved glass stay inside the window (no jagged corners)
                x1, y1 = math.ceil(hx * d) + 2, math.ceil(hy * d) + 2
                x2, y2 = int((hx + hw) * d) - 2, int((hy + hh) * d) - 2
                dia = max(2, round(hr * d) * 2 - 4)
                hole = gdi32.CreateRoundRectRgn(x1, y1, x2, y2, dia, dia)
                gdi32.CombineRgn(rgn, rgn, hole, 4)         # RGN_DIFF: screen minus the hole
                gdi32.DeleteObject(hole)
            if pw > 0 and ph > 0:
                r2 = gdi32.CreateRectRgn(int(px * d), int(py * d), math.ceil((px + pw) * d), math.ceil((py + ph) * d))
                gdi32.CombineRgn(rgn, rgn, r2, 2)           # RGN_OR: add the popup panel back
                gdi32.DeleteObject(r2)
            user32.SetWindowRgn(hwnd, rgn, True)            # the window owns the region now
            self._clip_key = key
        except Exception:
            if not self._rgn_warned:
                self._rgn_warned = True
                log.warning("window clip failed", exc_info=True)

    @Slot(int)
    def cycleLayout(self, d):
        spawn(["komorebic", "cycle-layout", "next" if d >= 0 else "previous"])

    @Slot(int)
    def stepWorkspace(self, d):
        if self._ws_indices:
            self.focusWorkspaceAt(max(0, min(len(self._ws_indices) - 1, self._v["wsActive"] + d)))

    @Slot(str)
    def taskClick(self, key):
        g = self._groups.get(key)
        if not g:
            return
        hw, fg = g["hwnds"], int(user32.GetForegroundWindow() or 0)
        if fg in hw:
            if len(hw) == 1:
                user32.ShowWindow(fg, 6)  # SW_MINIMIZE
            else:
                activate_window(hw[(hw.index(fg) + 1) % len(hw)])
        else:
            activate_window(hw[0])

    @Slot(str)
    def taskClose(self, key):
        g = self._groups.get(key)
        if g:
            user32.PostMessageW(g["hwnds"][0], 0x0010, 0, 0)  # WM_CLOSE

    @Slot()
    def mediaPlayPause(self):
        self._media.act("toggle")

    @Slot()
    def mediaNext(self):
        self._media.act("next")

    @Slot()
    def mediaPrev(self):
        self._media.act("prev")

    @Slot(str, str, result=str)
    def appIcon(self, key, name):
        """Icon (file URL) of the program behind a volume-mixer row. Finds the running program whose exe name matches
                the row's key / name and takes its Windows icon. '' if nothing matches (the row then shows its letter)."""
        try:
            ck = (key or "", name or "")
            hit = self._appicon_cache.get(ck) if hasattr(self, "_appicon_cache") else None
            if hit and time.time() - hit[0] < (300 if hit[1] else 10):
                return hit[1]
            if not hasattr(self, "_appicon_cache"):
                self._appicon_cache = {}

            def norm(t):
                return re.sub(r"[^a-z0-9]", "", re.sub(r"\.exe$", "", (t or "").lower()))
            want = {norm(t) for t in re.split(r"[\\/|:#@]+", key or "") + [name or ""]}
            want.discard("")
            for t in list(want):                              # "chrome1234" -> "chrome"
                want.add(re.sub(r"\d+$", "", t))
            want.discard("")
            url, best = "", None
            for exe, pid in running_processes():
                st = norm(exe)
                if not st:
                    continue
                if st in want:
                    best = pid
                    break
                if best is None and any(len(w) >= 4 and (w in st or (len(st) >= 4 and st in w)) for w in want):
                    best = pid
            if best:
                path = exe_of(best)
                if path:
                    url = self._icon(path)
            self._appicon_cache[ck] = (time.time(), url)
            return url
        except Exception:
            log.warning("app icon lookup failed", exc_info=True)
            return ""

    @Slot(int)
    def mediaCycle(self, direction):
        """Scroll on the media widget: -1 = the app above in the list, +1 = the one below (wraps)."""
        self._media.cycle(1 if direction >= 0 else -1)

    @Slot(float)
    def mediaSeek(self, frac):
        """Progress bar in the media popup, 0..1 position inside the shown track."""
        self._media.seek(min(1.0, max(0.0, float(frac))))

    @Slot(str)
    def openUri(self, uri):
        try:
            os.startfile(uri)
        except OSError:
            log.warning("could not open %s", uri)

    @Slot()
    def openNotifications(self):
        for down in (True, False):  # Win+N
            for vk in ((0x5B, 0x4E) if down else (0x4E, 0x5B)):
                user32.keybd_event(vk, 0, 0 if down else 2, 0)

    @Slot()
    def openControlCenter(self):
        if os.path.exists(CONTROL_CENTER):
            spawn([CONTROL_CENTER] if FROZEN else [sys.executable, CONTROL_CENTER])


CLI_FILE = DATA / "cli.json"


def start_cli_server(b):
    """Local command channel for vaporctl.py: 127.0.0.1 only, random port + token kept in cli.json (in your own
        AppData folder), one JSON line in and one out. Commands run on the Qt main thread."""
    token = secrets.token_hex(16)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(4)
    CLI_FILE.write_text(json.dumps({"port": srv.getsockname()[1], "token": token, "pid": os.getpid()}), encoding="utf-8")

    def handle(conn):
        try:
            conn.settimeout(3)
            data = b""
            while not data.endswith(b"\n") and len(data) < 65536:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            req = json.loads(data.decode("utf-8"))
            if not secrets.compare_digest(str(req.get("token", "")), token):
                resp = {"ok": False, "text": "bad token"}
            else:
                ev, out = threading.Event(), {}
                b.cliIn.emit({"cmd": str(req.get("cmd", "")), "args": req.get("args") or [], "ev": ev, "out": out})
                resp = out if ev.wait(5) and out else {"ok": False, "text": "no answer from Vapor"}
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
        except Exception:
            log.exception("cli connection")
        finally:
            conn.close()

    def serve():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            threading.Thread(target=handle, args=(conn,), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()
    log.info("cli: listening on 127.0.0.1:%d", srv.getsockname()[1])


# ---- qt warnings ----
def qt_log(mode, ctx, msg):
    """Only QML / Qt warnings and errors (QtDebugMsg = 0 and QtInfoMsg = 4 are dropped)."""
    if int(mode.value if hasattr(mode, "value") else mode) in (0, 4):
        return
    log.warning("qt: %s (%s:%s)", msg, ctx.file, ctx.line)


def _notif_app_name(pid):
    """'com.squirrel.Discord.Discord' -> 'Discord', '5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App' -> 'WhatsAppDesktop',
        '{GUID}/Google/Chrome/Application/chrome.exe' -> 'chrome'."""
    n = str(pid or "").strip()
    n = n.split("!")[0].split("\\")[-1]
    if n.lower().endswith(".exe"):
        n = n[:-4]
    n = n.split("_")[0].split(".")[-1] if ("." in n or "_" in n) else n
    return n or "App"


def _notif_read(db, after):
    """New rows (id, payload, app id) from Windows' notification database. The service keeps the file open, so it's
        opened read-only first. If that fails, the file (+ its -wal / -shm) is copied and the copy is read."""
    import sqlite3
    sql = ("SELECT n.Id, n.Payload, h.PrimaryId FROM Notification n "
           "LEFT JOIN NotificationHandler h ON h.RecordId = n.HandlerId WHERE n.Id > ? ORDER BY n.Id")
    try:
        con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=1.0)
        try:
            top = con.execute("SELECT MAX(Id) FROM Notification").fetchone()[0] or 0
            return top, con.execute(sql, (after,)).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        tmp = DATA / "wpn_copy"
        tmp.mkdir(exist_ok=True)
        for ext in ("", "-wal", "-shm"):
            src = db.with_name(db.name + ext)
            if src.exists():
                shutil.copyfile(str(src), str(tmp / (db.name + ext)))
        con = sqlite3.connect(str(tmp / db.name), timeout=1.0)
        try:
            top = con.execute("SELECT MAX(Id) FROM Notification").fetchone()[0] or 0
            return top, con.execute(sql, (after,)).fetchall()
        finally:
            con.close()


def _notif_parse(payload):
    """Toast XML -> (title, body), None if it isn't a toast (tiles and badges are ignored)."""
    import xml.etree.ElementTree as ET
    raw = bytes(payload) if payload is not None else b""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16", "replace")
    else:
        text = raw.decode("utf-8-sig", "replace")
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text).replace("\x00", "")
    root = ET.fromstring(text)
    if root.tag.split("}")[-1].lower() != "toast":
        return None
    texts = [(t.text or "").strip() for t in root.iter() if t.tag.split("}")[-1] == "text"]
    texts = [t for t in texts if t]
    if not texts:
        return None
    return texts[0], " ".join(texts[1:])


def _notif_sig(db):
    """(mtime, size) of the database and its -wal file. Changes whenever Windows records a notification."""
    out = []
    for ext in ("", "-wal"):
        try:
            st = os.stat(str(db) + ext)
            out.append((st.st_mtime_ns, st.st_size))
        except OSError:
            out.append(None)
    return tuple(out)


def notif_loop(b):
    """Other apps' notifications in Vapor's own card. Windows has no simple hook for this from a plain script, so the
        notification database (%LOCALAPPDATA%/Microsoft/Windows/Notifications/wpndatabase.db) is watched for new rows.
        Windows still shows its own banner too. Turn on Do Not Disturb (they're still recorded) to see only Vapor's card."""
    if not APP_NOTIFICATIONS:
        return
    db = Path(os.environ.get("LOCALAPPDATA", str(APPDIR))) / "Microsoft" / "Windows" / "Notifications" / "wpndatabase.db"
    last = None
    last_sig = None
    last_err = ""
    while True:
        try:
            if not db.exists():
                if last_err != "missing":
                    log.warning("app notifications: %s not found", db)
                    last_err = "missing"
                time.sleep(10)
                continue
            sig = _notif_sig(db)
            if last is not None and sig == last_sig:       # nothing was written since the last look, don't open the database
                time.sleep(NOTIF_POLL_S)
                continue
            top, rows = _notif_read(db, last if last is not None else 2 ** 62)
            last_sig = sig
            if last is None:                       # first read: everything already there is old news
                last = top
            else:
                for nid, payload, pid in rows:
                    last = max(last, nid)
                    try:
                        got = _notif_parse(payload)
                    except Exception:
                        continue
                    app = _notif_app_name(pid)
                    if not got or "vapor" in str(pid or "").lower():
                        continue
                    title, body = got
                    b.appNotice.emit(app, title[:120], body.replace("\n", " ")[:220])
                last = max(last, top)
            last_err = ""
        except Exception as e:
            if str(e) != last_err:
                log.exception("app notifications")
                last_err = str(e)
            time.sleep(5)
        time.sleep(NOTIF_POLL_S)


def click_outside_loop(b):
    """While the control center is open, a click anywhere outside the bar and its popup closes it.
        (The popup never takes focus, so the usual 'another window became active' check misses clicks on the
        desktop, the taskbar or empty space.)"""
    prev = False
    while True:
        try:
            if not b._cc_open:
                prev = True                  # a button held while it opens must not count as a click outside
                time.sleep(0.25)
                continue
            down = any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x01, 0x02, 0x04))
            if down and not prev:
                pt = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                inside = False
                for title in ("Vapor Popup", "Vapor"):
                    hw = user32.FindWindowW(None, title)
                    if hw and user32.IsWindowVisible(hw):
                        r = wintypes.RECT()
                        user32.GetWindowRect(hw, ctypes.byref(r))
                        if r.left <= pt.x < r.right and r.top <= pt.y < r.bottom:
                            inside = True
                            break
                if not inside:
                    b.outsideIn.emit()
            prev = down
        except Exception:
            log.exception("click outside")
            time.sleep(1.0)
        time.sleep(0.03)


def find_win_hwnd(title):
    for w in QGuiApplication.topLevelWindows():
        if w.title() == title:
            return int(w.winId())
    return 0


def find_bar_hwnd():
    return find_win_hwnd("Vapor")


def main():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    k32.CreateMutexW.restype = wintypes.HANDLE
    _mutex = k32.CreateMutexW(None, False, "Vapor.SingleInstance")  # noqa: F841 (kept alive on purpose)
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        _fatal("Vapor is already running, or an old copy is stuck in the background.\n\n"
               + ("End 'Vapor.exe'" if FROZEN else "End 'pythonw.exe' / 'python.exe'") + " in Task Manager, then start it again.", 0)

    qInstallMessageHandler(qt_log)
    log.info("starting (python %s, appbar=%s)", sys.version.split()[0], USE_APPBAR)
    app = QGuiApplication(sys.argv)
    # crisp text: draw every Text with the OS rasteriser (hinted glyphs) instead of Qt Quick's scalable distance-field
    # glyphs, which look soft at fractional scaling like 125 %
    try:
        from PySide6.QtQuick import QQuickWindow
        QQuickWindow.setTextRenderType(QQuickWindow.TextRenderType.NativeTextRendering)
    except Exception:
        log.exception("could not switch to native text rendering")
    app.setApplicationName("Vapor")
    backend = Backend(app.primaryScreen())
    # the control center's engine (Wi-Fi, Bluetooth, mixer, stats, theme, cache, power ...), cc_backend.py next to this file
    try:
        sys.path.insert(0, str(HERE))
        from cc_backend import ControlBackend
        cc_backend = ControlBackend()
    except Exception:
        log.exception("control center backend failed to load")
        cc_backend = QObject()          # the bar still runs, the control center just has nothing to talk to

    # one theme: the control center's colour card feeds the bar live, saved colours are applied before the first frame
    try:
        if hasattr(cc_backend, "themeColors"):
            cc_backend.themeColors.connect(backend.applyThemeColors)
            saved = cc_backend.savedColors()
            if saved:
                backend.applyThemeColors(saved)
    except Exception:
        log.exception("theme hookup")

    qml_errors = []
    engine = QQmlApplicationEngine()
    # keep only the first few warnings (they're just there to explain a failed start), an unbounded list
    # grows as long as the bar runs if QML keeps warning
    engine.warnings.connect(lambda ws: qml_errors.extend(w.toString() for w in ws[:10]) if len(qml_errors) < 40 else None)
    if FROZEN:      # the Qt Quick modules (QtQuick, QtQuick.Controls ...) sit inside the bundle
        for qml_dir in (HERE / "PySide6" / "Qt" / "qml", HERE / "PySide6" / "qml"):
            if qml_dir.is_dir():
                engine.addImportPath(str(qml_dir))
    ctx = engine.rootContext()
    ctx.setContextProperty("B", backend)
    ctx.setContextProperty("CC", cc_backend)
    ctx.setContextProperty("taskModel", backend.tasks)
    ctx.setContextProperty("trayModel", backend.tray)
    engine.load(QUrl.fromLocalFile(str(HERE / "Vapor.qml")))
    if not engine.rootObjects():
        for e in qml_errors:
            log.error("qml: %s", e)
        _fatal("Vapor.qml failed to load:\n\n" + "\n".join(qml_errors[:4])
               + "\n\nFull log: " + str(DATA / "vapor.log"))

    reserve_tries = [0]

    def reserve():
        try:
            hwnd = find_bar_hwnd()
            if not hwnd:
                reserve_tries[0] += 1
                if reserve_tries[0] <= 40:                 # the window can take a moment to appear, try again (up to ~20 s)
                    QTimer.singleShot(500, reserve)
                else:
                    log.warning("bar window not found, not reserving screen space")
                return
            backend.fitWindow()
            backend.set_reserve(not backend._v["userHidden"])
        except Exception:
            log.exception("appbar")

    app.aboutToQuit.connect(lambda: backend.set_reserve(False))
    QTimer.singleShot(400, reserve)
    backend.start()
    try:
        ensure_on_path()
    except Exception:
        log.exception("could not update the user Path")
    try:
        start_cli_server(backend)
        app.aboutToQuit.connect(lambda: CLI_FILE.unlink(missing_ok=True))
    except Exception:
        log.exception("cli server did not start (vaporctl will not work)")
    if hasattr(cc_backend, "start"):
        cc_backend.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        log.exception("fatal")
        _fatal("Vapor crashed on start:\n\n" + traceback.format_exc()[-900:])
