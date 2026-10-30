"""
cc_backend.py - the engine behind ControlCenter.qml (shows up in QML as `CC`).

Wi-Fi / Bluetooth, do not disturb, dark mode, brightness, mic, the per-app mixer, CPU / RAM / GPU / network /
disk stats, the theme card, clear cache, Project / Cast and the power menu all live here.

Keep it next to vapor.pyw, vapor.pyw imports it and there is nothing else to run.
Speaker volume stays in vapor.pyw's own backend.
Log: %TEMP%\\vapor_control_center.log
"""
import asyncio
import base64
import colorsys
import ctypes
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from ctypes import wintypes
from xml.sax.saxutils import escape as xml_escape

from PySide6.QtCore import QObject, QTimer, Property, Signal, Slot

CONFIG_DIR = r"C:\Users\NITRO\.config"      # what the Configure button opens
NOWIN = 0x08000000       # CREATE_NO_WINDOW
TMP = tempfile.gettempdir()
STAMP = os.path.join(TMP, "vapor_cc_closed.txt")
LOG = os.path.join(TMP, "vapor_control_center.log")
CACHE = os.path.join(TMP, "vapor_cc_cache.json")


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
    except OSError:
        pass


# ---- theme ----
# three targets: shell (glass fill), outline (its rim) and icons (every icon / accent). each one either follows
# the wallpaper ("auto") or uses one colour from the Theme card ("custom", h / s / v from 0 to 1).
# the bar gets picked colours straight away through themeColors, the file is saved a bit after you let go.
THEME_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cc_theme.json")
_THEME_LOCK = threading.RLock()

_BASE_ACCENT = (76, 194, 255)        # the original blue, #4cc2ff


def _tclamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _hsv_rgb(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, _tclamp(s), _tclamp(v))
    return (round(r * 255), round(g * 255), round(b * 255))


def _argb(rgb, a=1.0):
    """#AARRGGBB, the colour format QML wants."""
    return "#%02x%02x%02x%02x" % (round(_tclamp(a) * 255), rgb[0], rgb[1], rgb[2])


def load_theme_state():
    try:
        with open(THEME_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_theme_state(**kw):
    with _THEME_LOCK:
        d = load_theme_state()
        d.update(kw)
        tmp = THEME_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f)
            os.replace(tmp, THEME_FILE)                      # write to a temp file and swap, so a crash can't leave a half-written json
        except OSError as ex:
            log("theme state not saved: %r" % ex)


TARGETS = ("shell", "outline", "icons")


def _auto():
    bh, bs, bv = colorsys.rgb_to_hsv(*(c / 255.0 for c in _BASE_ACCENT))
    return {"mode": "auto", "h": bh, "s": bs, "v": bv}


def clean_target(mode, h, s, v):
    """Cleans up one target into {mode: "auto" or "custom", h, s, v}."""
    d = _auto()
    try:
        h, s, v = float(h), float(s), float(v)
        if all(map(math.isfinite, (h, s, v))):
            d.update(h=_tclamp(h, 0.0, 0.9999), s=_tclamp(s), v=_tclamp(v))
    except (TypeError, ValueError):
        pass
    d["mode"] = "custom" if mode == "custom" else "auto"
    return d


def load_theme():
    """The saved theme as {shell, outline, icons}. Also picks up the single colour an older version saved."""
    st = load_theme_state()
    out = {k: (clean_target(st[k].get("mode"), st[k].get("h"), st[k].get("s"), st[k].get("v"))
               if isinstance(st.get(k), dict) else _auto()) for k in TARGETS}
    if not any(isinstance(st.get(k), dict) for k in TARGETS) and st.get("mode") == "custom":
        out["icons"] = clean_target("custom", st.get("h"), st.get("s"), st.get("v"))
    return out


def theme_bar_colors(t):
    """Only the parts you overrode, as '#AARRGGBB'. A missing key means that part follows the wallpaper."""
    out = {}
    rgb = lambda e: _hsv_rgb(e["h"], e["s"], e["v"])      # noqa: E731
    if t["shell"]["mode"] == "custom":
        out["glass"] = _argb(rgb(t["shell"]))
    if t["outline"]["mode"] == "custom":
        out["outline"] = _argb(rgb(t["outline"]))
    if t["icons"]["mode"] == "custom":
        c = rgb(t["icons"])
        out.update(accent=_argb(c), blue=_argb(c), lavender=_argb(c), hover=_argb(c, 0.16))
    return out


LOCATION_URI = "ms-settings:privacy-location"

# ---- clear cache ----
# what gets cleared, by group (>clearcache in Synapse runs this same code):
#   Vapor    icon / album art / avatar caches in %LOCALAPPDATA%\vapor, the control center's own cache + log,
#            __pycache__ folders and .log files next to the scripts
#   Harmony  thumbnails and converted wallpapers from its cache folder (the one Windows is showing stays),
#            colors.json, error.log and the wallpaper_next.txt hand-off file
#   Synapse  its cache / temp folders, stray .log / .tmp / .cache files and the launcher log
#   System   crash dumps, shader + thumbnail caches, error reports, pip cache
#   Temp     anything in the temp folder older than CLEAN_TEMP_MIN_AGE_HOURS (running programs' _MEI* folders
#            are left alone, locked files get skipped)
# never touched: cc_theme.json, config.json, settings.json, favourites, your scripts
CLEAN_TEMP_MIN_AGE_HOURS = 1
CLEAN_EXTRA = [
    # r"C:/Users/NITRO/AppData/Local/Temp/wallpaper_thumbs",       # anything else you want gone, ends up under "Other"
]

_LOCAL = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
_ROAM = os.environ.get("APPDATA") or os.path.expanduser("~")
HERE = os.path.dirname(os.path.abspath(__file__))
VAPOR_DATA_DIR = os.path.join(_LOCAL, "vapor")                 # vapor.pyw keeps its icons / art / log here
HARMONY_DIRS = [os.path.join(_LOCAL, n) for n in ("Harmony", "WallpaperPicker")]    # WallpaperPicker was the old name
SYNAPSE_DIRS = [os.path.join(_LOCAL, "Synapse"), os.path.join(_ROAM, "Synapse"),
                os.path.expanduser("~/.config/synapse"), os.path.expanduser("~/.cache/synapse")]
_CACHE_WORDS = ("cache", "thumb", "tmp", "temp")               # sub-folders with one of these words in the name count as cache
_JUNK_EXT = (".log", ".tmp", ".cache")
# stuff in Windows' own folders that is safe to drop, it gets rebuilt
SYSTEM_JUNK_DIRS = [
    os.path.join(_LOCAL, "CrashDumps"),
    os.path.join(_LOCAL, "D3DSCache"),
    os.path.join(_LOCAL, "pip", "cache"),
    os.path.join(_LOCAL, "Microsoft", "Windows", "WER"),
    os.path.join(_LOCAL, "Microsoft", "Windows", "INetCache"),
]
CLEAN_GROUPS = [("vapor", "Vapor"), ("harmony", "Harmony"), ("synapse", "Synapse"),
                ("system", "System leftovers"), ("temp", "Temp files"), ("extra", "Other")]
_CLEAN_LABELS = {}        # path -> group name from the last scan, so the log can say what each deletion was


def _path_size(path):
    try:
        if os.path.isfile(path):
            return os.path.getsize(path)
        total = 0
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total
    except OSError:
        return 0


def _wallpaper_in_use():
    """Path of the wallpaper Windows is showing right now (Harmony keeps its converted BMP in its cache folder)."""
    try:
        buf = ctypes.create_unicode_buffer(520)
        ctypes.windll.user32.SystemParametersInfoW(0x73, 520, buf, 0)
        return os.path.normcase(os.path.abspath(buf.value)) if buf.value else ""
    except Exception:  # noqa: BLE001
        return ""


def clean_groups():
    """Scans everything listed above. Returns [{"key", "label", "items": [(path, size), ...]}, ...] in display order."""
    protected = {os.path.normcase(os.path.abspath(p)) for p in (
        __file__, THEME_FILE, STAMP,
        os.path.join(HERE, "config.json"),
        os.path.join(VAPOR_DATA_DIR, "vapor.log"),            # open right now anyway
        os.path.join(VAPOR_DATA_DIR, "settings.json"),
        os.path.join(VAPOR_DATA_DIR, "cli.json"),             # vaporctl needs this while Vapor runs
        os.path.join(VAPOR_DATA_DIR, "path_entry.txt"))}
    owner, found = {}, {k: [] for k, _ in CLEAN_GROUPS}

    def add(group, p):
        key = os.path.normcase(os.path.abspath(p))
        if key in protected or key in owner or not os.path.lexists(p):
            return
        if any(pp.startswith(key + os.sep) for pp in protected):       # skip folders that have a protected file inside
            return
        owner[key] = group
        found[group].append(p)

    def add_children(group, folder, keep=""):
        """Every file inside `folder`. The folder itself stays, the app expects it to be there."""
        for root, _dirs, files in os.walk(folder):
            for f in files:
                p = os.path.join(root, f)
                if not keep or os.path.normcase(os.path.abspath(p)) != keep:
                    add(group, p)

    def scan(group, root, depth):
        try:
            entries = list(os.scandir(root))
        except OSError:
            return
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if any(w in e.name.lower() for w in _CACHE_WORDS):
                        add(group, e.path)
                    elif depth > 1:
                        scan(group, e.path, depth - 1)
                elif e.name.lower().endswith(_JUNK_EXT):
                    add(group, e.path)
            except OSError:
                pass

    # -- Vapor
    for sub in ("icons", "art", "cache", "wpn_copy"):
        add_children("vapor", os.path.join(VAPOR_DATA_DIR, sub))
    try:
        for n in os.listdir(VAPOR_DATA_DIR):
            if n.lower().endswith((".tmp", ".cache")):
                add("vapor", os.path.join(VAPOR_DATA_DIR, n))
    except OSError:
        pass
    for p in (CACHE, LOG):
        add("vapor", p)
    try:
        for n in os.listdir(HERE):
            if n.lower().endswith(".log"):
                add("vapor", os.path.join(HERE, n))
    except OSError:
        pass
    depth0 = HERE.count(os.sep)
    for root, dirs, _files in os.walk(HERE):
        if root.count(os.sep) - depth0 >= 3:
            dirs[:] = []
            continue
        if "__pycache__" in dirs:
            add("vapor", os.path.join(root, "__pycache__"))
            dirs.remove("__pycache__")

    # -- Harmony (favourites and settings aren't cache, so they stay)
    keep = _wallpaper_in_use()
    for d in HARMONY_DIRS:
        add_children("harmony", os.path.join(d, "cache"), keep)
        for n in ("colors.json", "error.log"):
            add("harmony", os.path.join(d, n))
    add("harmony", os.path.join(VAPOR_DATA_DIR, "wallpaper_next.txt"))

    # -- Synapse
    for d in SYNAPSE_DIRS:
        if os.path.isdir(d):
            scan("synapse", d, 3)
    try:
        for n in os.listdir(TMP):
            if n.lower().startswith("synapse"):
                add("synapse", os.path.join(TMP, n))
    except OSError:
        pass

    # -- system leftovers
    for d in SYSTEM_JUNK_DIRS:
        add_children("system", d)
    try:
        explorer = os.path.join(_LOCAL, "Microsoft", "Windows", "Explorer")
        for n in os.listdir(explorer):
            if n.lower().startswith(("thumbcache_", "iconcache_")):
                add("system", os.path.join(explorer, n))
    except OSError:
        pass

    # -- whatever is in CLEAN_EXTRA
    for p in CLEAN_EXTRA:
        add("extra", os.path.expanduser(p))

    # -- temp, last so everything above keeps its own group
    cutoff = time.time() - CLEAN_TEMP_MIN_AGE_HOURS * 3600
    try:
        for e in os.scandir(TMP):
            if e.name.startswith(("_MEI", "onefile_")):         # Vapor.exe unpacks itself here while it runs
                continue
            try:
                if e.stat(follow_symlinks=False).st_mtime < cutoff:
                    add("temp", e.path)
            except OSError:
                pass
    except OSError:
        pass

    return [dict(key=k, label=label, items=[(p, _path_size(p)) for p in found[k]]) for k, label in CLEAN_GROUPS]


def clean_targets():
    """Flat (path, size) list for the Clear cache button, in group order. Remembers which group each path is in."""
    _CLEAN_LABELS.clear()
    flat = []
    for g in clean_groups():
        for p, size in g["items"]:
            flat.append((p, size))
            _CLEAN_LABELS[p] = g["label"]
    return flat


def clean_run(items, progress=None):
    """Deletes the paths, skipping anything locked. Returns (removed, freed_bytes, skipped).
    progress(kind, text) gets called per item so the log window can show it."""
    removed = freed = skipped = 0
    pause = min(0.03, 1.5 / max(1, len(items)))       # tiny pause so the log window visibly scrolls (1.5 s max in total)
    last_label = None
    for p, size in items:
        label = _CLEAN_LABELS.get(p)
        if progress and label and label != last_label:
            progress("info", "-- %s --" % label)                 # heading when a new group starts
        last_label = label
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
            removed += 1
            freed += size
            if progress:
                progress("ok", "deleted: %s (%s)" % (p, _fmt_size(size)))
        except OSError as exc:
            skipped += 1
            if progress:
                progress("skip", "skipped (in use): %s [%s]" % (p, exc.strerror or exc))
        time.sleep(pause)
    return removed, freed, skipped


def _fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d %s" % (n, unit)) if unit == "B" else ("%.1f %s" % (n, unit))
        n /= 1024.0


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace", creationflags=NOWIN, **kw)


# ---- Wi-Fi / Bluetooth ----
async def _radio_winrt(kind, set_to=None):
    from winrt.windows.devices.radios import Radio, RadioKind, RadioState
    await Radio.request_access_async()
    radios = await Radio.get_radios_async()
    want = RadioKind.WI_FI if kind == "wifi" else RadioKind.BLUETOOTH
    for r in radios:
        if r.kind == want:
            if set_to is not None:
                await r.set_state_async(RadioState.ON if set_to else RadioState.OFF)
                return bool(set_to)
            return r.state == RadioState.ON
    return None


PS_RADIO = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) { $t = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
[Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Radios.RadioAccessStatus,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
Await ([Windows.Devices.Radios.Radio]::RequestAccessAsync()) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null
$radios = Await ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
$r = $radios | Where-Object { $_.Kind -eq '__KIND__' } | Select-Object -First 1
if (-not $r) { 'NONE'; exit 0 }
__SET__
$r.State
"""


def _radio_ps(kind, set_to=None):
    script = PS_RADIO.replace("__KIND__", "WiFi" if kind == "wifi" else "Bluetooth")
    if set_to is None:
        script = script.replace("__SET__", "")
    else:
        state = "On" if set_to else "Off"
        script = script.replace(
            "__SET__",
            "Await ($r.SetStateAsync('%s')) ([Windows.Devices.Radios.RadioAccessStatus]) | Out-Null" % state)
    enc = base64.b64encode(script.encode("utf-16le")).decode()
    res = run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-EncodedCommand", enc], timeout=25)
    out = (res.stdout or "").strip().splitlines()
    last = out[-1].strip() if out else ""
    if res.returncode != 0 or not last:
        raise RuntimeError((res.stderr or "PowerShell returned nothing").strip()[:300])
    if last == "NONE":
        return None
    if last == "On":
        return True
    if last == "Off":
        return False
    raise RuntimeError("Radio state: " + last)


def radio(kind, set_to=None):
    try:
        return asyncio.run(_radio_winrt(kind, set_to))
    except Exception as ex:  # noqa: BLE001  (winrt missing or failing -> PowerShell)
        log("winrt radio failed (%s): %r -> PowerShell" % (kind, ex))
    return _radio_ps(kind, set_to)


# ---- registry toggles ----
def _reg():
    import winreg
    return winreg


NOTIF_KEY = r"Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
THEME_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"


def _get_dword(path, name, default):
    w = _reg()
    try:
        with w.OpenKey(w.HKEY_CURRENT_USER, path) as k:
            return w.QueryValueEx(k, name)[0]
    except FileNotFoundError:
        return default


def _set_dword(path, name, value):
    w = _reg()
    with w.CreateKey(w.HKEY_CURRENT_USER, path) as k:
        w.SetValueEx(k, name, 0, w.REG_DWORD, int(value))


def dnd_get():
    return _get_dword(NOTIF_KEY, "NOC_GLOBAL_SETTING_TOASTS_ENABLED", 1) == 0


def dnd_set(on):
    _set_dword(NOTIF_KEY, "NOC_GLOBAL_SETTING_TOASTS_ENABLED", 0 if on else 1)
    return bool(on)


def dark_get():
    return _get_dword(THEME_KEY, "AppsUseLightTheme", 1) == 0


def dark_set(on):
    v = 0 if on else 1
    _set_dword(THEME_KEY, "AppsUseLightTheme", v)
    _set_dword(THEME_KEY, "SystemUsesLightTheme", v)
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "ImmersiveColorSet",
                                             0x0002, 2000, ctypes.byref(ctypes.c_size_t()))
    return bool(on)


# ---- project ----
def project_open(_=None):
    os.startfile("ms-settings-displays-topology:projection")     # Win+P flyout
    return False


def cast_open(_=None):
    os.startfile("ms-settings-connectabledevices:devicediscovery")
    return False


# ---- volume / mic / brightness ----
_CLSID_MMDEVENUM = "bcde0395-e52f-467c-8e3d-c4579291692e"
_IID_MMDEVENUM = "a95664d2-9614-4f35-a746-de8db63617e6"
_IID_ENDPOINTVOL = "5cdf2c82-841e-4546-9722-0cf74078229a"


def _vcall(obj, idx, *argtypes):
    """Calls method number `idx` on a raw COM pointer, so no comtypes needed."""
    vt = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vt[idx])


class _Endpoint:
    """Volume + mute of the default speaker or mic through IAudioEndpointVolume."""

    def __init__(self, capture=False):
        ole = ctypes.windll.ole32
        ole.CoInitializeEx(None, 0)                     # fine if the thread was already initialised
        ole.CoCreateInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                                         ctypes.c_void_p, ctypes.c_void_p]
        ole.CoCreateInstance.restype = ctypes.c_long
        self._ptrs = []
        enum = ctypes.c_void_p()
        hr = ole.CoCreateInstance(ctypes.byref(self._g(_CLSID_MMDEVENUM)), None, 23,
                                  ctypes.byref(self._g(_IID_MMDEVENUM)), ctypes.byref(enum))
        self._chk(hr, "CoCreateInstance")
        self._ptrs.append(enum.value)
        dev = ctypes.c_void_p()
        hr = _vcall(enum.value, 4, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p)(
            enum.value, 1 if capture else 0, 0, ctypes.byref(dev))   # eCapture / eRender, eConsole
        self._chk(hr, "GetDefaultAudioEndpoint")          # fails when there's no such device
        self._ptrs.append(dev.value)
        vol = ctypes.c_void_p()
        hr = _vcall(dev.value, 3, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p)(
            dev.value, ctypes.byref(self._g(_IID_ENDPOINTVOL)), 23, None, ctypes.byref(vol))
        self._chk(hr, "Activate")
        self.vol = vol.value
        self._ptrs.append(vol.value)

    @staticmethod
    def _g(s):
        return GUID.from_buffer_copy(uuid.UUID(s).bytes_le)

    @staticmethod
    def _chk(hr, what):
        if hr < 0:
            raise OSError("%s failed (0x%08X)" % (what, hr & 0xFFFFFFFF))

    def GetMasterVolumeLevelScalar(self):
        f = ctypes.c_float()
        self._chk(_vcall(self.vol, 9, ctypes.c_void_p)(self.vol, ctypes.byref(f)), "GetVolume")
        return f.value

    def SetMasterVolumeLevelScalar(self, v, _ctx=None):
        self._chk(_vcall(self.vol, 7, ctypes.c_float, ctypes.c_void_p)(self.vol, float(v), None), "SetVolume")

    def GetMute(self):
        b = ctypes.c_int()
        self._chk(_vcall(self.vol, 15, ctypes.c_void_p)(self.vol, ctypes.byref(b)), "GetMute")
        return bool(b.value)

    def SetMute(self, m, _ctx=None):
        self._chk(_vcall(self.vol, 14, ctypes.c_int, ctypes.c_void_p)(self.vol, int(bool(m)), None), "SetMute")

    def __del__(self):
        for ptr in reversed(getattr(self, "_ptrs", [])):
            try:
                _vcall(ptr, 2)(ptr)                        # IUnknown::Release
            except Exception:  # noqa: BLE001
                pass


def _endpoint(capture=False):
    return _Endpoint(capture)


# ---- per-app volume (audio sessions, plain ctypes) ----
_IID_SESSMGR2 = "77aa99a0-1bd6-484f-8bc7-2c654c9a9b6f"      # IAudioSessionManager2
_IID_SESSCTRL2 = "bfb7ff88-7239-4fc9-8fa2-07c950be9c6d"     # IAudioSessionControl2
_IID_SIMPLEVOL = "87ce5498-68d6-44e5-9215-6da47ef883d8"     # ISimpleAudioVolume
_APP_NAMES = {"msedge": "Microsoft Edge", "wmplayer": "Windows Media Player", "explorer": "File Explorer",
              "vlc": "VLC", "obs64": "OBS Studio", "code": "VS Code", "applicationframehost": "Windows app"}
_K32 = None


def _k32():
    global _K32
    if _K32 is None:
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        _K32 = k
    return _K32


def _proc_path(pid):
    k = _k32()
    h = k.OpenProcess(0x1000, False, pid)                     # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1040)
        n = wintypes.DWORD(1040)
        return buf.value if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ""
    finally:
        k.CloseHandle(h)


def _qi(p, iid):
    out = ctypes.c_void_p()
    hr = _vcall(p, 0, ctypes.c_void_p, ctypes.c_void_p)(p, ctypes.byref(_Endpoint._g(iid)), ctypes.byref(out))
    return out.value if hr >= 0 and out.value else None


def _release(p):
    try:
        _vcall(p, 2)(p)
    except Exception:  # noqa: BLE001
        pass


def _session_enumerator(held):
    """IAudioSessionEnumerator for the default speaker. Every pointer we grab goes into `held` so it can be released."""
    ole = ctypes.windll.ole32
    ole.CoCreateInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
    ole.CoCreateInstance.restype = ctypes.c_long
    chk = _Endpoint._chk
    enum = ctypes.c_void_p()
    chk(ole.CoCreateInstance(ctypes.byref(_Endpoint._g(_CLSID_MMDEVENUM)), None, 23,
                             ctypes.byref(_Endpoint._g(_IID_MMDEVENUM)), ctypes.byref(enum)), "CoCreateInstance")
    held.append(enum.value)
    dev = ctypes.c_void_p()
    chk(_vcall(enum.value, 4, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p)(enum.value, 0, 0, ctypes.byref(dev)),
        "GetDefaultAudioEndpoint")
    held.append(dev.value)
    mgr = ctypes.c_void_p()
    chk(_vcall(dev.value, 3, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p)(
        dev.value, ctypes.byref(_Endpoint._g(_IID_SESSMGR2)), 23, None, ctypes.byref(mgr)), "Activate(session manager)")
    held.append(mgr.value)
    en = ctypes.c_void_p()
    chk(_vcall(mgr.value, 5, ctypes.c_void_p)(mgr.value, ctypes.byref(en)), "GetSessionEnumerator")
    held.append(en.value)
    return en.value


def _walk_sessions(fn):
    """Calls fn(info) for each audio session on the default speaker. info has key, name, state (0 idle, 1 playing,
    2 expired), level (0-1), muted and vol_p (ISimpleAudioVolume pointer, only good during the call, can be None)."""
    ctypes.windll.ole32.CoInitializeEx(None, 0)
    held = []
    try:
        en = _session_enumerator(held)
        count = ctypes.c_int()
        _Endpoint._chk(_vcall(en, 3, ctypes.c_void_p)(en, ctypes.byref(count)), "GetCount")
        for i in range(count.value):
            ctl = ctypes.c_void_p()
            if _vcall(en, 4, ctypes.c_int, ctypes.c_void_p)(en, i, ctypes.byref(ctl)) < 0 or not ctl.value:
                continue
            mine = [ctl.value]
            try:
                c2 = _qi(ctl.value, _IID_SESSCTRL2)
                if c2:
                    mine.append(c2)
                vp = _qi(ctl.value, _IID_SIMPLEVOL)
                if vp:
                    mine.append(vp)
                st = ctypes.c_int(0)
                _vcall(ctl.value, 3, ctypes.c_void_p)(ctl.value, ctypes.byref(st))
                pid, system = wintypes.DWORD(0), False
                if c2:
                    _vcall(c2, 14, ctypes.c_void_p)(c2, ctypes.byref(pid))
                    system = _vcall(c2, 15)(c2) == 0                      # S_OK = the "system sounds" session
                level, muted = 1.0, False
                if vp:
                    f, b = ctypes.c_float(), ctypes.c_int()
                    _vcall(vp, 4, ctypes.c_void_p)(vp, ctypes.byref(f))
                    _vcall(vp, 6, ctypes.c_void_p)(vp, ctypes.byref(b))
                    level, muted = float(f.value), bool(b.value)
                path = _proc_path(pid.value) if pid.value else ""
                if system:
                    key, name = "system", "System sounds"
                elif path:
                    key = path.lower()
                    stem = os.path.splitext(os.path.basename(path))[0]
                    name = _APP_NAMES.get(stem.lower()) or (stem[:1].upper() + stem[1:])
                else:
                    key, name = "pid%d" % pid.value, "Unknown app"
                fn(dict(key=key, name=name, state=st.value, level=level, muted=muted, vol_p=vp))
            finally:
                for p in reversed(mine):
                    _release(p)
    finally:
        for p in reversed(held):
            _release(p)


def audio_sessions():
    """One entry per app that has an audio session, [{key, name, vol (0-1), muted, active}], playing ones first."""
    apps = {}

    def see(s):
        if s["state"] == 2:                                   # expired, the app is gone
            return
        a = apps.setdefault(s["key"], dict(key=s["key"], name=s["name"], vol=0.0, muted=True, active=False))
        a["vol"] = max(a["vol"], s["level"])
        a["muted"] = a["muted"] and s["muted"]
        a["active"] = a["active"] or s["state"] == 1
    _walk_sessions(see)
    return sorted(apps.values(), key=lambda a: (not a["active"], a["name"].lower()))


def set_app_audio(key, level=None, mute=None):
    """Sets volume (0-1) and/or mute on every session of the app `key`."""
    def apply(s):
        if s["key"] != key or not s["vol_p"]:
            return
        vp = s["vol_p"]
        if level is not None:
            _vcall(vp, 3, ctypes.c_float, ctypes.c_void_p)(vp, float(max(0.0, min(1.0, level))), None)
        if mute is not None:
            _vcall(vp, 5, ctypes.c_int, ctypes.c_void_p)(vp, int(bool(mute)), None)
    _walk_sessions(apply)


def _ps(cmd, timeout=20):
    return run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd], timeout=timeout)


def get_brightness():
    try:
        import screen_brightness_control as sbc          # optional, only used if installed
        v = sbc.get_brightness()
        return int(v[0]) if v else None
    except ImportError:
        pass
    r = _ps("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness "
            "| Select-Object -First 1).CurrentBrightness")
    s = (r.stdout or "").strip()
    return int(s) if s.isdigit() else None               # None = external monitor, no WMI brightness


def set_brightness(value):
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(int(value))
        return
    except ImportError:
        pass
    _ps("Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods "
        "| Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{Timeout=1; Brightness=%d} | Out-Null"
        % int(value))


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]


# ---- Wi-Fi networks (netsh) / Bluetooth devices ----
def _netsh(*args):
    return run(["netsh", "wlan", *args]).stdout or ""


_LOGGED = set()


def _log_once(msg):
    if msg not in _LOGGED:
        _LOGGED.add(msg)
        log(msg)


def _wlan_raw(opcode):
    """Asks the WLAN service about every Wi-Fi interface (a few ms, no netsh or PowerShell).
    Gives back a list of (rc, bytes), raises if wlanapi isn't there."""
    import ctypes.wintypes as wt
    wlan = ctypes.WinDLL("wlanapi.dll")
    wlan.WlanOpenHandle.argtypes = [wt.DWORD, ctypes.c_void_p, ctypes.POINTER(wt.DWORD), ctypes.POINTER(wt.HANDLE)]
    wlan.WlanCloseHandle.argtypes = [wt.HANDLE, ctypes.c_void_p]
    wlan.WlanEnumInterfaces.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    wlan.WlanQueryInterface.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p,
                                        ctypes.POINTER(wt.DWORD), ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    wlan.WlanFreeMemory.argtypes = [ctypes.c_void_p]
    ver, h = wt.DWORD(), wt.HANDLE()
    if wlan.WlanOpenHandle(2, None, ctypes.byref(ver), ctypes.byref(h)) != 0:
        raise OSError("WlanOpenHandle failed")
    res = []
    try:
        lst = ctypes.c_void_p()
        if wlan.WlanEnumInterfaces(h, None, ctypes.byref(lst)) != 0:
            raise OSError("WlanEnumInterfaces failed")
        try:
            for i in range(ctypes.c_uint32.from_address(lst.value).value):
                guid = ctypes.string_at(lst.value + 8 + i * 532, 16)      # WLAN_INTERFACE_INFO is 532 bytes
                data, size = ctypes.c_void_p(), wt.DWORD()
                rc = wlan.WlanQueryInterface(h, guid, opcode, None, ctypes.byref(size), ctypes.byref(data), None)
                raw = b""
                if rc == 0:
                    try:
                        raw = ctypes.string_at(data.value, size.value)
                    finally:
                        wlan.WlanFreeMemory(data)
                res.append((rc, raw))
        finally:
            wlan.WlanFreeMemory(lst)
    finally:
        wlan.WlanCloseHandle(h, None)
    return res


WLAN_CONNECTED = 1


def _wlan_state():
    """Interface state without the SSID (1 connected, 4 disconnected, 5/7 connecting), None if unknown.
    Unlike the SSID this still works with Location off."""
    try:
        for rc, raw in _wlan_raw(6):                      # wlan_intf_opcode_interface_state
            if rc == 0 and len(raw) >= 4:
                return int.from_bytes(raw[:4], "little")
            _log_once("wlan state rc=%s" % rc)
    except Exception:  # noqa: BLE001
        _log_once("wlan state failed:\n" + traceback.format_exc())
    return None


def _wlan_current():
    """(ok, name). ok=False means Windows wouldn't say (Location off), so the caller needs another way."""
    for rc, raw in _wlan_raw(7):                          # wlan_intf_opcode_current_connection
        if rc == 5023:                                    # ERROR_INVALID_STATE, not connected
            continue
        if rc != 0:
            _log_once("wlan query rc=%s" % rc)            # 5 = access denied (Location is off)
            return False, None
        if int.from_bytes(raw[0:4], "little") != WLAN_CONNECTED:
            continue
        prof = raw[8:520].decode("utf-16-le", "ignore").split("\x00")[0]
        n = int.from_bytes(raw[520:524], "little")
        ssid = raw[524:524 + min(n, 32)].decode("utf-8", "ignore") if n else ""
        if ssid or prof:
            return True, ssid or prof
        return False, None
    return True, None


_LAST_CUR = {"t": 0.0, "v": None}


def _wifi_current(out=None):
    st = _wlan_state()
    if st is not None and st != WLAN_CONNECTED and st not in (3,):
        return None                                       # obviously not connected, skip the slow lookups
    try:
        ok, name = _wlan_current()
        if ok:
            return name or None
    except Exception:  # noqa: BLE001
        _log_once("native wlan query failed:\n" + traceback.format_exc())
    if time.time() - _LAST_CUR["t"] < 4 and st == WLAN_CONNECTED:
        return _LAST_CUR["v"]                             # the PowerShell lookup takes seconds, reuse a fresh answer if there is one
    out = _netsh("show", "interfaces") if out is None else out
    if re.search(r"location permission|requires elevation", out, re.I):
        val = _wifi_ssid_fallback()                       # netsh is blocked, ask the network profile instead
        _LAST_CUR.update(t=time.time(), v=val)
        return val
    cur, state = None, ""
    for line in out.splitlines():
        m = re.match(r"\s*State\s*:\s*(.+)$", line)
        if m:
            state = m.group(1).strip().lower()
        m = re.match(r"\s*SSID\s*:\s*(.+)$", line)
        if m:
            cur = m.group(1).strip()
    if state != "connected":
        return None
    return cur or _wifi_ssid_fallback()


def _wifi_ssid_fallback():
    """Newer Windows hides the SSID from netsh when Location is off, but the network profile name still works."""
    try:
        r = _ps("(Get-NetConnectionProfile | Where-Object { $_.InterfaceAlias -match 'Wi-?Fi|WLAN|Wireless' } "
                "| Select-Object -First 1).Name", timeout=12)           # one cmdlet is a lot quicker than asking for the adapters too
        name = (r.stdout or "").strip()
        if name:
            return name
        r = _ps("$a = @(Get-NetAdapter | Where-Object { $_.NdisPhysicalMedium -eq 9 -and $_.Status -eq 'Up' } "
                "| ForEach-Object { $_.InterfaceAlias }); "
                "(Get-NetConnectionProfile | Where-Object { $a -contains $_.InterfaceAlias } "
                "| Select-Object -First 1).Name", timeout=12)
        return (r.stdout or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


_SCAN_BLOCKED = False      # set once Windows refuses to list networks (Location off), then we show saved ones instead


def _same_net(cur, ssid):
    if not cur or not ssid:
        return False
    c, n = cur.strip().lower(), ssid.strip().lower()
    return c == n or (c.startswith(n + " ") and c[len(n):].strip().isdigit())


def wifi_scan(hint=None):
    global _SCAN_BLOCKED
    from concurrent.futures import ThreadPoolExecutor
    if _SCAN_BLOCKED:                                    # no point calling netsh when we know it gets refused
        prof, ifc, raw = _netsh("show", "profiles"), "", ""
    else:
        with ThreadPoolExecutor(3) as ex:
            f_if = ex.submit(_netsh, "show", "interfaces")
            f_pr = ex.submit(_netsh, "show", "profiles")
            f_nw = ex.submit(_netsh, "show", "networks", "mode=bssid")
            ifc, prof, raw = f_if.result(), f_pr.result(), f_nw.result()
    if re.search(r"Software\s+Off|Hardware\s+Off", ifc):
        return {"nets": [], "note": "", "off": True}
    if hint and _wlan_state() == WLAN_CONNECTED:
        cur = hint                                        # show the last known network right away, it's checked afterwards
    else:
        cur = _wifi_current(ifc or None)
    known = {m.strip() for m in re.findall(r"(?:All User Profile|User Profile)\s*:\s*(.+)", prof)}
    nets, ssid = {}, None
    for line in raw.splitlines():
        m = re.match(r"\s*SSID\s+\d+\s*:\s*(.*)$", line)
        if m:
            ssid = m.group(1).strip()
            if ssid:
                nets.setdefault(ssid, {"ssid": ssid, "auth": "", "signal": 0})
            continue
        if not ssid or ssid not in nets:
            continue
        m = re.match(r"\s*Authentication\s*:\s*(.+)$", line)
        if m and not nets[ssid]["auth"]:
            nets[ssid]["auth"] = m.group(1).strip()
        m = re.match(r"\s*Signal\s*:\s*(\d+)\s*%", line)
        if m:
            nets[ssid]["signal"] = max(nets[ssid]["signal"], int(m.group(1)))
    note = ""
    if not nets and (_SCAN_BLOCKED or re.search(r"location|elevation|permission", raw + ifc, re.I)):
        if not _SCAN_BLOCKED:
            log("nearby scan blocked by Windows (Location off); using saved networks")
        _SCAN_BLOCKED = True
        note = "location"
        for name in known:                               # can't scan, so list the saved networks
            nets[name] = {"ssid": name, "auth": "WPA2-Personal", "signal": 0}
    if cur:
        cur = next((k for k in nets if _same_net(cur, k)), cur)      # map the profile name back to a listed SSID
    if cur and cur not in nets:
        nets[cur] = {"ssid": cur, "auth": "WPA2-Personal", "signal": 0}
    out = []
    for n in nets.values():
        n["known"] = n["ssid"] in known
        n["connected"] = n["ssid"] == cur
        out.append(n)
    out.sort(key=lambda n: (not n["connected"], not n["known"], -n["signal"], n["ssid"].lower()))
    return {"nets": out, "note": note, "off": False}


def _wlan_do(fn):
    """Opens the WLAN service and runs fn(wlan, handle, interface_guid_bytes) on the first Wi-Fi interface. Returns its code."""
    import ctypes.wintypes as wt
    wlan = ctypes.WinDLL("wlanapi.dll")
    wlan.WlanOpenHandle.argtypes = [wt.DWORD, ctypes.c_void_p, ctypes.POINTER(wt.DWORD), ctypes.POINTER(wt.HANDLE)]
    wlan.WlanCloseHandle.argtypes = [wt.HANDLE, ctypes.c_void_p]
    wlan.WlanEnumInterfaces.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    wlan.WlanFreeMemory.argtypes = [ctypes.c_void_p]
    wlan.WlanConnect.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    wlan.WlanDisconnect.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p]
    wlan.WlanSetProfile.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                    wt.BOOL, ctypes.c_void_p, ctypes.POINTER(wt.DWORD)]
    wlan.WlanDeleteProfile.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_void_p]
    ver, h = wt.DWORD(), wt.HANDLE()
    if wlan.WlanOpenHandle(2, None, ctypes.byref(ver), ctypes.byref(h)) != 0:
        return -1
    try:
        lst = ctypes.c_void_p()
        if wlan.WlanEnumInterfaces(h, None, ctypes.byref(lst)) != 0:
            return -1
        try:
            if ctypes.c_uint32.from_address(lst.value).value < 1:
                return -2                                  # no Wi-Fi adapter
            guid = ctypes.create_string_buffer(ctypes.string_at(lst.value + 8, 16), 16)
            return fn(wlan, h, guid)
        finally:
            wlan.WlanFreeMemory(lst)
    finally:
        wlan.WlanCloseHandle(h, None)


class _WLAN_CONNECTION_PARAMETERS(ctypes.Structure):
    _fields_ = [("mode", ctypes.c_uint32), ("profile", ctypes.c_wchar_p), ("ssid", ctypes.c_void_p),
                ("bssids", ctypes.c_void_p), ("bss_type", ctypes.c_uint32), ("flags", ctypes.c_uint32)]


def _wlan_connect_native(profile):
    def go(wlan, h, guid):
        cp = _WLAN_CONNECTION_PARAMETERS(0, profile, None, None, 1, 0)     # profile mode, infrastructure
        return wlan.WlanConnect(h, guid, ctypes.byref(cp), None)
    return _wlan_do(go)


def _wlan_set_profile_native(xml):
    import ctypes.wintypes as wt

    def go(wlan, h, guid):
        reason = wt.DWORD()
        return wlan.WlanSetProfile(h, guid, 2, xml, None, True, None, ctypes.byref(reason))   # 2 = this user only
    return _wlan_do(go)


def _wlan_delete_profile_native(name):
    return _wlan_do(lambda wlan, h, guid: wlan.WlanDeleteProfile(h, guid, name, None))


def _wlan_disconnect_native():
    return _wlan_do(lambda wlan, h, guid: wlan.WlanDisconnect(h, guid, None))


def wifi_disconnect():
    try:
        rc = _wlan_disconnect_native()
    except Exception:  # noqa: BLE001
        log("native disconnect failed:\n" + traceback.format_exc())
        rc = -1
    if rc != 0:
        log("native disconnect rc=%s, trying netsh" % rc)
        run(["netsh", "wlan", "disconnect"], timeout=10)
    _LAST_CUR.update(t=0.0, v=None)
    deadline = time.time() + 4
    while time.time() < deadline:
        st = _wlan_state()
        if st is None:
            time.sleep(1.0)                              # no state yet, give Windows a moment
            return
        if st != WLAN_CONNECTED:
            return
        time.sleep(0.15)


def _save_profile_netsh(doc):
    path = os.path.join(TMP, "vapor_cc_wifi_%s.xml" % uuid.uuid4().hex)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
        return run(["netsh", "wlan", "add", "profile", "filename=" + path, "user=current"])
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _delete_profile(name):
    try:
        if _wlan_delete_profile_native(name) == 0:
            return
    except Exception:  # noqa: BLE001
        pass
    run(["netsh", "wlan", "delete", "profile", "name=" + name])


def wifi_connect(ssid, auth, known, password="", hidden=False, keep=False):
    """Returns (ok, message). A secured network we don't know yet gets a profile made from the password."""
    added = False
    if not known:
        a = (auth or "").lower()
        if a == "open":
            am, enc, keyed = "open", "none", False
        elif "enterprise" in a:
            return False, "Set up in Windows settings"
        elif "wpa3" in a:
            am, enc, keyed = "WPA3SAE", "AES", True
        elif "wpa2" in a:
            am, enc, keyed = "WPA2PSK", "AES", True
        elif "wpa" in a:
            am, enc, keyed = "WPAPSK", "TKIP", True
        else:
            return False, "Unsupported security type"
        if keyed and not password:
            return False, "Password needed"
        key_xml = ("<sharedKey><keyType>passphrase</keyType><protected>false</protected>"
                   "<keyMaterial>%s</keyMaterial></sharedKey>" % xml_escape(password)) if keyed else ""
        name = xml_escape(ssid)
        doc = ('<?xml version="1.0"?>'
               '<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">'
               "<name>%s</name><SSIDConfig><SSID><name>%s</name></SSID>%s</SSIDConfig>"
               "<connectionType>ESS</connectionType><connectionMode>auto</connectionMode>"
               "<MSM><security><authEncryption><authentication>%s</authentication>"
               "<encryption>%s</encryption><useOneX>false</useOneX></authEncryption>%s"
               "</security></MSM></WLANProfile>") % (name, name, "<nonBroadcast>true</nonBroadcast>" if hidden else "",
                                              am, enc, key_xml)
        try:
            rc = _wlan_set_profile_native(doc)
        except Exception:  # noqa: BLE001
            log("native save profile failed:\n" + traceback.format_exc())
            rc = -1
        log("save profile %r -> native rc=%s" % (ssid, rc))
        if rc != 0:
            res = _save_profile_netsh(doc)
            if res.returncode != 0:
                log("add profile failed: %s %s" % (res.stdout, res.stderr))
                return False, "Couldn't save network"
        added = True
    _LAST_CUR.update(t=0.0, v=None)
    try:
        rc = _wlan_connect_native(ssid)                   # netsh won't connect while Location is off, the API does
    except Exception:  # noqa: BLE001
        log("native connect failed:\n" + traceback.format_exc())
        rc = -1
    log("connect %r -> native rc=%s" % (ssid, rc))
    if rc != 0:
        res = run(["netsh", "wlan", "connect", "name=" + ssid, "ssid=" + ssid], timeout=15)
        log("connect %r -> netsh rc=%s %s" % (ssid, res.returncode, (res.stdout or "").strip()[:80]))
        if res.returncode != 0:
            if added and not keep:
                _delete_profile(ssid)
            return False, "Windows blocked the request (code %s)" % rc
    ok = True
    if ok:
        left, t0 = False, time.time()
        while time.time() - t0 < 14:
            st = _wlan_state()
            if st is None:                                # no fast state, fall back to the slow lookup
                time.sleep(1.5)
                if _same_net(_wifi_current(), ssid):
                    return True, ""
                continue
            if st != WLAN_CONNECTED:
                left = True                               # Windows dropped the old link and is joining the new one
            elif left:
                if added:                                 # new network, make sure Windows didn't fall back to the old one
                    good = False
                    for _ in range(4):
                        _LAST_CUR.update(t=0.0, v=None)
                        if _same_net(_wifi_current(), ssid):
                            good = True
                            break
                        time.sleep(1.0)
                    if not good:
                        break
                log("connected to %r in %.1fs" % (ssid, time.time() - t0))
                return True, ""                           # connected again after the switch
            elif time.time() - t0 > 1.5:                  # never left "connected": already on it, or the request got ignored
                if _same_net(_wifi_current(), ssid):
                    return True, ""
                if time.time() - t0 > 6:
                    break
            time.sleep(0.08)
    if added and not keep:                                # keep a saved network whose password was just re-typed
        _delete_profile(ssid)
    return False, "Couldn't connect" + (" - check the password" if added and password else "")


class _SYSTEMTIME(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ushort) for n in ("y", "mo", "dow", "d", "h", "mi", "s", "ms")]


class _BTH_INFO(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("Address", ctypes.c_ulonglong), ("cls", wintypes.ULONG),
                ("fConnected", wintypes.BOOL), ("fRemembered", wintypes.BOOL),
                ("fAuthenticated", wintypes.BOOL), ("seen", _SYSTEMTIME), ("used", _SYSTEMTIME),
                ("szName", ctypes.c_wchar * 248)]


class _BTH_SEARCH(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("fAuth", wintypes.BOOL), ("fRemembered", wintypes.BOOL),
                ("fUnknown", wintypes.BOOL), ("fConnected", wintypes.BOOL), ("fInquiry", wintypes.BOOL),
                ("timeout", ctypes.c_ubyte), ("hRadio", ctypes.c_void_p)]


# audio sink, hands-free, headset, HID: switching these services connects / disconnects the device
BT_SERVICES = ["0000110b-0000-1000-8000-00805f9b34fb", "0000111e-0000-1000-8000-00805f9b34fb",
               "00001108-0000-1000-8000-00805f9b34fb", "00001124-0000-1000-8000-00805f9b34fb"]


def _bth():
    d = ctypes.WinDLL("bthprops.cpl")
    d.BluetoothFindFirstDevice.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    d.BluetoothFindFirstDevice.restype = ctypes.c_void_p
    d.BluetoothFindNextDevice.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    d.BluetoothFindNextDevice.restype = wintypes.BOOL
    d.BluetoothFindDeviceClose.argtypes = [ctypes.c_void_p]
    d.BluetoothSetServiceState.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD]
    d.BluetoothSetServiceState.restype = wintypes.DWORD
    return d


def bt_list():
    d = _bth()
    sp = _BTH_SEARCH()
    sp.dwSize = ctypes.sizeof(sp)
    sp.fAuth = sp.fRemembered = sp.fConnected = 1
    sp.fUnknown = sp.fInquiry = 0
    info = _BTH_INFO()
    info.dwSize = ctypes.sizeof(info)
    devs, seen = [], set()
    h = d.BluetoothFindFirstDevice(ctypes.byref(sp), ctypes.byref(info))
    if h:
        try:
            while True:
                if info.Address not in seen:
                    seen.add(info.Address)
                    devs.append({"addr": int(info.Address), "name": info.szName or "Unknown device",
                                 "connected": bool(info.fConnected), "cls": int(info.cls)})
                if not d.BluetoothFindNextDevice(h, ctypes.byref(info)):
                    break
        finally:
            d.BluetoothFindDeviceClose(h)
    devs.sort(key=lambda x: (not x["connected"], x["name"].lower()))
    return devs


def _bt_services(addr, flag):
    """Turns every audio + input service of a device on (1) or off (0) in one go."""
    d = _bth()

    def one(g):
        info = _BTH_INFO()
        info.dwSize = ctypes.sizeof(info)
        info.Address = addr
        guid = GUID.from_buffer_copy(uuid.UUID(g).bytes_le)
        r = d.BluetoothSetServiceState(None, ctypes.byref(info), ctypes.byref(guid), flag)
        log("bt %s %s %s -> %s" % ("enable" if flag else "disable", addr, g[:8], r))
    ts = [threading.Thread(target=one, args=(g,), daemon=True) for g in BT_SERVICES]
    for t in ts:
        t.start()
    for t in ts:
        t.join(25)


def bt_set(addr, connect):
    if not connect:
        _bt_services(addr, 0)
        return
    _bt_services(addr, 1)                       # works if we disconnected it earlier
    for _ in range(10):
        time.sleep(0.3)
        if any(x["addr"] == addr and x["connected"] for x in bt_list()):
            return
    _bt_services(addr, 0)                       # device dropped on its own, cycle the services
    _bt_services(addr, 1)


def bt_title(names):
    if not names:
        return None
    return names[0] + (" +%d" % (len(names) - 1) if len(names) > 1 else "")


MM_RENDER = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
PK_FORM = "{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},0"    # endpoint form factor, 3 = headphones, 5 = headset
PK_DESC = "{a45c254e-df1c-4efd-8020-67d146a850e0},2"
PK_NAME = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"


def _mm_val(key, name):
    w = _reg()
    try:
        return w.QueryValueEx(key, name)[0]
    except OSError:
        return None


def wired_headphones(debug=False):
    """True if a wired (non-Bluetooth) headphone / headset output is plugged in and active."""
    w = _reg()
    seen, found = [], False
    try:
        root = w.OpenKey(w.HKEY_LOCAL_MACHINE, MM_RENDER)
    except OSError:
        return False
    with root:
        i = 0
        while True:
            try:
                guid = w.EnumKey(root, i)
            except OSError:
                break
            i += 1
            try:
                with w.OpenKey(root, guid) as k:
                    state = _mm_val(k, "DeviceState")
                with w.OpenKey(root, guid + "\\Properties") as pk:
                    ff, desc, name = _mm_val(pk, PK_FORM), _mm_val(pk, PK_DESC), _mm_val(pk, PK_NAME)
            except OSError:
                continue
            text = ("%s %s" % (desc or "", name or "")).lower()
            seen.append("state=%s form=%s %s / %s" % (state, ff, desc, name))
            if state != 1 or "bluetooth" in text:
                continue
            by_name = "headphone" in text or "headset" in text
            if ff in (3, 5) or (ff in (None, 10) and by_name):
                found = True
    if debug and not found:
        log("no wired headphones. render endpoints: " + " | ".join(seen))
    return found


def bt_label(names, wired):
    """A connected Bluetooth device wins, wired headphones only show up when there isn't one."""
    if names:
        return bt_title(names)
    return "Wired Headphone" if wired else None


def bt_icon(cls):
    major = (cls >> 8) & 0x1F
    if major == 4:
        return "\uE7F6"
    if major == 5:
        return "\uE765" if cls & 0x40 else "\uE962"
    if major == 2:
        return "\uE8EA"
    if major == 1:
        return "\uE7F8"
    return "\uE702"


ADD_KEY = "__add__"
SECURITY = [("WPA2", "WPA2-Personal"), ("WPA3", "WPA3-Personal"), ("Open", "Open")]


class _MEMSTATUS(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class _FILETIME(ctypes.Structure):
    _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]


class _IFROW(ctypes.Structure):                      # MIB_IFROW (860 bytes)
    _fields_ = [("wszName", ctypes.c_wchar * 256), ("dwIndex", wintypes.DWORD), ("dwType", wintypes.DWORD),
                ("dwMtu", wintypes.DWORD), ("dwSpeed", wintypes.DWORD), ("dwPhysAddrLen", wintypes.DWORD),
                ("bPhysAddr", ctypes.c_ubyte * 8), ("dwAdminStatus", wintypes.DWORD),
                ("dwOperStatus", wintypes.DWORD), ("dwLastChange", wintypes.DWORD),
                ("dwInOctets", wintypes.DWORD), ("dwInUcastPkts", wintypes.DWORD),
                ("dwInNUcastPkts", wintypes.DWORD), ("dwInDiscards", wintypes.DWORD),
                ("dwInErrors", wintypes.DWORD), ("dwInUnknownProtos", wintypes.DWORD),
                ("dwOutOctets", wintypes.DWORD), ("dwOutUcastPkts", wintypes.DWORD),
                ("dwOutNUcastPkts", wintypes.DWORD), ("dwOutDiscards", wintypes.DWORD),
                ("dwOutErrors", wintypes.DWORD), ("dwOutQLen", wintypes.DWORD),
                ("dwDescrLen", wintypes.DWORD), ("bDescr", ctypes.c_ubyte * 256)]


_cpu_prev = None


def cpu_percent():
    """Total CPU load since the last call (0 the first time)."""
    global _cpu_prev
    idle, kern, user = _FILETIME(), _FILETIME(), _FILETIME()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))
    cur = tuple((t.hi << 32) | t.lo for t in (idle, kern, user))
    prev, _cpu_prev = _cpu_prev, cur
    if prev is None:
        return 0.0
    d_idle, d_kern, d_user = (c - p for c, p in zip(cur, prev))
    total = d_kern + d_user                              # kernel time already counts idle time
    if total <= 0:
        return 0.0
    return max(0.0, min(100.0, (total - d_idle) * 100.0 / total))


def mem_stats():
    m = _MEMSTATUS()
    m.dwLength = ctypes.sizeof(m)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullTotalPhys - m.ullAvailPhys, m.ullTotalPhys


def net_counters():
    """{adapter index: (bytes in, bytes out)} for each connected adapter except loopback (32-bit counters)."""
    try:
        iph = ctypes.windll.iphlpapi
        size = wintypes.ULONG(0)
        iph.GetIfTable(None, ctypes.byref(size), False)            # first call only tells us the size we need
        buf = ctypes.create_string_buffer(size.value)
        if iph.GetIfTable(buf, ctypes.byref(size), False) != 0:
            return {}
        n = int.from_bytes(buf.raw[:4], "little")
        sz = ctypes.sizeof(_IFROW)
        out = {}
        for i in range(n):
            row = _IFROW.from_buffer_copy(buf, 4 + i * sz)
            if row.dwType == 24 or row.dwOperStatus not in (4, 5):      # loopback / not connected
                continue
            out[row.dwIndex] = (row.dwInOctets, row.dwOutOctets)
        return out
    except Exception:  # noqa: BLE001
        return {}


def fixed_drives():
    """[(letter, used_bytes, total_bytes)] for the local fixed disks."""
    res = []
    try:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if mask & (1 << i):
                root = "%s:\\" % chr(65 + i)
                if ctypes.windll.kernel32.GetDriveTypeW(root) == 3:
                    du = shutil.disk_usage(root)
                    res.append((chr(65 + i), du.used, du.total))
    except Exception:  # noqa: BLE001
        pass
    return res


_NVSMI = []


def _nvsmi_path():
    """Looked up the first time it's needed (when the stats page opens), then cached."""
    if not _NVSMI:
        _NVSMI.append(shutil.which("nvidia-smi"))
    return _NVSMI[0]


def gpu_stats():
    """NVIDIA GPU load from nvidia-smi, or None if it's missing or says nothing."""
    exe = _nvsmi_path()
    if not exe:
        return None
    try:
        r = run([exe, "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                 "--format=csv,noheader,nounits"], timeout=4)
        line = r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ""
        if not line:
            return None
        name, util, mu, mt, temp = [x.strip() for x in line.split(",")][:5]

        def num(x):
            try:
                return float(x)
            except ValueError:
                return None
        return {"name": name, "util": num(util) or 0.0, "mem_used": num(mu), "mem_total": num(mt), "temp": num(temp)}
    except Exception:  # noqa: BLE001
        return None


def _gb(n):
    return "%.1f GB" % (n / 1073741824.0)


def _rate(bps):
    for unit in ("B/s", "KB/s", "MB/s"):
        if bps < 1024 or unit == "MB/s":
            return ("%d %s" % (bps, unit)) if unit == "B/s" else ("%.1f %s" % (bps, unit))
        bps /= 1024.0


def _uptime_text():
    k = ctypes.windll.kernel32
    k.GetTickCount64.restype = ctypes.c_ulonglong
    secs = int(k.GetTickCount64() // 1000)
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return ("%dd %dh %dm" % (d, h, m)) if d else ("%dh %dm" % (h, m))



# ---- the QObject QML sees as CC ----
class _Latest:
    """Runs fn(value) on a worker thread. If new values come in while it's busy they replace the old ones, so
    dragging a slider doesn't pile up dozens of slow PowerShell / COM calls."""

    def __init__(self, fn):
        self.fn, self.want, self.busy, self.lock = fn, None, False, threading.Lock()

    def push(self, v):
        with self.lock:
            self.want = v
            if self.busy:
                return
            self.busy = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            with self.lock:
                v, self.want = self.want, None
                if v is None:
                    self.busy = False
                    return
            try:
                self.fn(v)
            except Exception:  # noqa: BLE001
                log("latest-value worker failed:\n" + traceback.format_exc())


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class ControlBackend(QObject):
    # ---- state QML reads: a <name>Changed signal plus a read-only <name> property ----
    wifiOnChanged = Signal(); wifiOn = Property(bool, lambda s: s._v["wifiOn"], notify=wifiOnChanged)
    wifiMissingChanged = Signal(); wifiMissing = Property(bool, lambda s: s._v["wifiMissing"], notify=wifiMissingChanged)
    btOnChanged = Signal(); btOn = Property(bool, lambda s: s._v["btOn"], notify=btOnChanged)
    btMissingChanged = Signal(); btMissing = Property(bool, lambda s: s._v["btMissing"], notify=btMissingChanged)
    dndOnChanged = Signal(); dndOn = Property(bool, lambda s: s._v["dndOn"], notify=dndOnChanged)
    darkOnChanged = Signal(); darkOn = Property(bool, lambda s: s._v["darkOn"], notify=darkOnChanged)
    errorsChanged = Signal(); errors = Property("QVariant", lambda s: s._v["errors"], notify=errorsChanged)
    brightnessChanged = Signal(); brightness = Property(int, lambda s: s._v["brightness"], notify=brightnessChanged)
    micVolumeChanged = Signal(); micVolume = Property(int, lambda s: s._v["micVolume"], notify=micVolumeChanged)
    micMutedChanged = Signal(); micMuted = Property(bool, lambda s: s._v["micMuted"], notify=micMutedChanged)

    wifiNetsChanged = Signal(); wifiNets = Property("QVariant", lambda s: s._v["wifiNets"], notify=wifiNetsChanged)
    wifiScanningChanged = Signal(); wifiScanning = Property(bool, lambda s: s._v["wifiScanning"], notify=wifiScanningChanged)
    wifiNoteChanged = Signal(); wifiNote = Property(str, lambda s: s._v["wifiNote"], notify=wifiNoteChanged)
    wifiBusyChanged = Signal(); wifiBusy = Property("QVariant", lambda s: s._v["wifiBusy"], notify=wifiBusyChanged)
    wifiNotesChanged = Signal(); wifiNotes = Property("QVariant", lambda s: s._v["wifiNotes"], notify=wifiNotesChanged)
    btDevicesChanged = Signal(); btDevices = Property("QVariant", lambda s: s._v["btDevices"], notify=btDevicesChanged)
    btScanningChanged = Signal(); btScanning = Property(bool, lambda s: s._v["btScanning"], notify=btScanningChanged)
    btBusyChanged = Signal(); btBusy = Property("QVariant", lambda s: s._v["btBusy"], notify=btBusyChanged)
    btNotesChanged = Signal(); btNotes = Property("QVariant", lambda s: s._v["btNotes"], notify=btNotesChanged)
    appsChanged = Signal(); apps = Property("QVariant", lambda s: s._v["apps"], notify=appsChanged)
    appsStateChanged = Signal(); appsState = Property(str, lambda s: s._v["appsState"], notify=appsStateChanged)

    cpuChanged = Signal(); cpu = Property(float, lambda s: s._v["cpu"], notify=cpuChanged)
    memUsedChanged = Signal(); memUsed = Property(float, lambda s: s._v["memUsed"], notify=memUsedChanged)
    memTotalChanged = Signal(); memTotal = Property(float, lambda s: s._v["memTotal"], notify=memTotalChanged)
    netRxChanged = Signal(); netRx = Property(float, lambda s: s._v["netRx"], notify=netRxChanged)
    netTxChanged = Signal(); netTx = Property(float, lambda s: s._v["netTx"], notify=netTxChanged)
    gpuChanged = Signal(); gpu = Property("QVariant", lambda s: s._v["gpu"], notify=gpuChanged)
    disksChanged = Signal(); disks = Property("QVariant", lambda s: s._v["disks"], notify=disksChanged)
    uptimeChanged = Signal(); uptime = Property(str, lambda s: s._v["uptime"], notify=uptimeChanged)

    themeStateChanged = Signal(); themeState = Property("QVariant", lambda s: s._v["themeState"], notify=themeStateChanged)

    cleanStateChanged = Signal(); cleanState = Property(str, lambda s: s._v["cleanState"], notify=cleanStateChanged)
    cleanCountChanged = Signal(); cleanCount = Property(int, lambda s: s._v["cleanCount"], notify=cleanCountChanged)
    cleanSizeChanged = Signal(); cleanSize = Property(str, lambda s: s._v["cleanSize"], notify=cleanSizeChanged)
    cleanPreviewChanged = Signal(); cleanPreview = Property("QVariant", lambda s: s._v["cleanPreview"], notify=cleanPreviewChanged)
    cleanSummaryChanged = Signal(); cleanSummary = Property(str, lambda s: s._v["cleanSummary"], notify=cleanSummaryChanged)

    # ---- events for QML ----
    cleanLine = Signal(str, str)        # kind (info / ok / skip / done), text
    closeRequested = Signal()           # asks the bar to close the control center popup
    ui = Signal(object)                 # worker thread -> UI thread (carries a callable)
    themeColors = Signal(object)        # colours from the theme card -> accents + icons on the bar (accent / blue / lavender dict)

    def __init__(self):
        super().__init__()
        self._theme = load_theme()
        self._v = dict(
            wifiOn=False, wifiMissing=False, btOn=False, btMissing=False, dndOn=False, darkOn=True, errors={},
            brightness=-1, micVolume=-1, micMuted=False,
            wifiNets=[], wifiScanning=False, wifiNote="", wifiBusy={}, wifiNotes={},
            btDevices=[], btScanning=False, btBusy={}, btNotes={}, apps=[], appsState="loading",
            cpu=0.0, memUsed=0.0, memTotal=1.0, netRx=0.0, netTx=0.0, gpu={}, disks=[], uptime="",
            themeState={k: dict(e) for k, e in self._theme.items()},
            cleanState="idle", cleanCount=0, cleanSize="", cleanPreview=[], cleanSummary="",
        )
        self._wifi_nets = []
        self._wifi_cur = None
        self._wifi_busy_flag = False
        self._apps_busy = False
        self._clean_items = []
        self._net_prev, self._net_t, self._ticks, self._gpu_busy = {}, None, 0, False
        self._app_level = {}
        self.ui.connect(self._run_ui)
        self._bri = _Latest(set_brightness)
        self._mic = _Latest(lambda v: _endpoint(True).SetMasterVolumeLevelScalar(v / 100.0, None))
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(450)
        self._save_timer.timeout.connect(self._save_theme)

    # ---- plumbing ----
    def put(self, key, value):
        if self._v.get(key) == value:
            return
        self._v[key] = value
        getattr(self, key + "Changed").emit()

    @Slot(object)
    def _run_ui(self, fn):
        try:
            fn()
        except Exception:  # noqa: BLE001
            log("ui callback failed:\n" + traceback.format_exc())

    def _spawn(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def _set_error(self, key, msg):
        e = dict(self._v["errors"])
        if msg:
            e[key] = msg
        else:
            e.pop(key, None)
        self.put("errors", e)

    def start(self):
        """Called once by vapor.pyw, reads the current state so the first opening already shows it."""
        self.refresh()

    # ---- read the system state ----
    @Slot()
    def refresh(self):
        def read(key, getter):
            def work():
                try:
                    val, err = getter(), ""
                except Exception as ex:  # noqa: BLE001
                    log("%s read failed:\n%s" % (key, traceback.format_exc()))
                    val, err = None, (str(ex)[:160] or ex.__class__.__name__)
                self.ui.emit(lambda: self._state(key, val, err))
            self._spawn(work)

        read("wifi", lambda: radio("wifi"))
        read("bt", lambda: radio("bluetooth"))
        read("dnd", dnd_get)
        read("dark", dark_get)

        def bri():
            try:
                v = get_brightness()
            except Exception:  # noqa: BLE001
                log("brightness failed:\n" + traceback.format_exc())
                v = None
            self.ui.emit(lambda: self.put("brightness", -1 if v is None else int(v)))
        self._spawn(bri)

        def mic():
            try:
                ep = _endpoint(True)
                vol, mute = int(round(ep.GetMasterVolumeLevelScalar() * 100)), bool(ep.GetMute())
            except Exception:  # noqa: BLE001
                vol, mute = -1, False
            self.ui.emit(lambda: (self.put("micVolume", vol), self.put("micMuted", mute)))
        self._spawn(mic)

    def _state(self, key, val, err):
        if key in ("wifi", "bt"):
            self.put(key + "Missing", err == "" and val is None)
            if err == "" and val is not None:
                self.put(key + "On", bool(val))
        elif err == "":
            self.put(key + "On", bool(val))
        self._set_error(key, err)

    # ---- simple toggles ----
    def _toggle(self, key, setter, on):
        self.put(key + "On", bool(on))                # optimistic, the tile fills up straight away

        def work():
            try:
                res = setter(on)
                err = ""
            except Exception as ex:  # noqa: BLE001
                log("%s toggle failed:\n%s" % (key, traceback.format_exc()))
                res, err = None, (str(ex)[:160] or ex.__class__.__name__)
            self.ui.emit(lambda: self._toggled(key, on, res, err))
        self._spawn(work)

    def _toggled(self, key, wanted, res, err):
        if err:
            self.put(key + "On", not wanted)           # put it back
            self._set_error(key, err)
            return
        self._set_error(key, "")
        if res is None and key in ("wifi", "bt"):
            self.put(key + "Missing", True)
            self.put(key + "On", False)
            return
        self.put(key + "On", bool(res))
        if key == "wifi" and res:
            self._later(3.5, self.scanWifi)
        if key == "bt":
            self._later(2.5 if res else 0.2, self.scanBt)

    def _later(self, secs, fn):
        def work():
            time.sleep(secs)
            self.ui.emit(fn)
        self._spawn(work)

    @Slot(bool)
    def setWifi(self, on):
        if not on:
            self.put("wifiNets", [])
        self._toggle("wifi", lambda v: radio("wifi", v), on)

    @Slot(bool)
    def setBt(self, on):
        if not on:
            self.put("btDevices", [])
        self._toggle("bt", lambda v: radio("bluetooth", v), on)

    @Slot()
    def toggleDnd(self):
        self._toggle("dnd", dnd_set, not self._v["dndOn"])

    @Slot()
    def toggleDark(self):
        self._toggle("dark", dark_set, not self._v["darkOn"])

    @Slot()
    def project(self):
        try:
            project_open()
        except OSError:
            log("project failed:\n" + traceback.format_exc())
        self.closeRequested.emit()

    @Slot()
    def cast(self):
        try:
            cast_open()
        except OSError:
            log("cast failed:\n" + traceback.format_exc())
        self.closeRequested.emit()

    @Slot()
    def openConfig(self):
        try:
            os.startfile(CONFIG_DIR)
        except OSError as exc:
            log("could not open config folder %s: %r" % (CONFIG_DIR, exc))
        self.closeRequested.emit()

    @Slot()
    def openLocationSettings(self):
        os.startfile(LOCATION_URI)
        self.closeRequested.emit()

    # ---- brightness / mic ----
    @Slot(int)
    def setBrightness(self, v):
        v = _clamp(int(v), 0, 100)
        self.put("brightness", v)
        self._bri.push(v)

    @Slot(int)
    def setMic(self, v):
        v = _clamp(int(v), 0, 100)
        self.put("micVolume", v)
        if self._v["micMuted"] and v > 0:
            self._set_mic_mute(False)
        self._mic.push(v)

    def _set_mic_mute(self, m):
        self.put("micMuted", bool(m))

        def work():
            try:
                _endpoint(True).SetMute(1 if m else 0, None)
            except Exception:  # noqa: BLE001
                log("mic mute failed:\n" + traceback.format_exc())
        self._spawn(work)

    @Slot()
    def toggleMic(self):
        self._set_mic_mute(not self._v["micMuted"])

    # ---- Wi-Fi ----
    @Slot()
    def scanWifi(self):
        if self._wifi_busy_flag:
            return
        self._wifi_busy_flag = True
        self.put("wifiScanning", True)
        hint = self._wifi_cur or _LAST_CUR["v"]

        def work():
            try:
                data = wifi_scan(hint)
                self.ui.emit(lambda: self._on_wifi(data))
                if hint and any(n["connected"] for n in data["nets"]):
                    real = _wifi_current()              # slow check, just to catch a stale hint
                    if real and not _same_net(real, hint):
                        data2 = wifi_scan()
                        self.ui.emit(lambda: self._on_wifi(data2))
            except Exception:  # noqa: BLE001
                log("wifi scan failed:\n" + traceback.format_exc())
                self.ui.emit(lambda: self._on_wifi(None))
        self._spawn(work)

    def _on_wifi(self, data):
        self._wifi_busy_flag = False
        self.put("wifiScanning", False)
        if data is None:
            self.put("wifiNets", [])
            self.put("wifiNote", "error")
            return
        nets = data["nets"]
        self._wifi_nets = nets
        self._wifi_cur = next((n["ssid"] for n in nets if n["connected"]), None)
        if data.get("off"):
            self.put("wifiOn", False)
        self.put("wifiNote", data.get("note", ""))
        self.put("wifiBusy", {})
        self.put("wifiNets", [dict(n) for n in nets])

    def _wifi_mark(self, which, ssid, text):
        d = dict(self._v[which])
        if text:
            d[ssid] = text
        else:
            d.pop(ssid, None)
        self.put(which, d)

    @Slot(str, str)
    def wifiConnect(self, ssid, password):
        net = next((n for n in self._wifi_nets if n["ssid"] == ssid), None)
        if not net:
            return
        if not net["known"] and net["auth"].lower() != "open" and not password:
            self._wifi_mark("wifiNotes", ssid, "Enter the password")
            return
        self._wifi_mark("wifiNotes", ssid, "")
        self._wifi_mark("wifiBusy", ssid, "Connecting...")
        for n in self._wifi_nets:
            if n["connected"] and n["ssid"] != ssid:
                self._wifi_mark("wifiBusy", n["ssid"], "Disconnecting...")

        def work():
            try:
                ok, msg = wifi_connect(ssid, net["auth"], net["known"], password)
            except Exception:  # noqa: BLE001
                log("wifi connect failed:\n" + traceback.format_exc())
                ok, msg = False, "Something went wrong"
            self.ui.emit(lambda: self._wifi_done(ssid, True, ok, "" if ok else msg))
        self._spawn(work)

    @Slot(str)
    def wifiDisconnect(self, ssid):
        self._wifi_mark("wifiBusy", ssid, "Disconnecting...")

        def work():
            try:
                wifi_disconnect()
                ok, msg = True, ""
            except Exception:  # noqa: BLE001
                log("wifi disconnect failed:\n" + traceback.format_exc())
                ok, msg = False, "Something went wrong"
            self.ui.emit(lambda: self._wifi_done(ssid, False, ok, msg))
        self._spawn(work)

    @Slot(str, str, str)
    def wifiAdd(self, ssid, password, auth):
        """Join a network that isn't listed or saved, using a profile built from the typed name and password."""
        ssid = (ssid or "").strip()
        auth = auth or "WPA2-Personal"
        problem = ""
        if not ssid:
            problem = "Enter the network name"
        elif auth != "Open" and not 8 <= len(password) <= 63:
            problem = "Password must be 8 to 63 characters"
        if problem:
            self._wifi_mark("wifiNotes", ADD_KEY, problem)
            return
        saved = any(n["ssid"] == ssid and n["known"] for n in self._wifi_nets)
        self._wifi_mark("wifiNotes", ADD_KEY, "")
        self._wifi_mark("wifiBusy", ADD_KEY, "Connecting to %s..." % ssid)

        def work():
            try:
                ok, msg = wifi_connect(ssid, auth, False, password, hidden=True, keep=saved)
            except Exception:  # noqa: BLE001
                log("wifi add failed:\n" + traceback.format_exc())
                ok, msg = False, "Something went wrong"
            if ok:
                nets = [dict(n, connected=False) for n in self._wifi_nets if n["ssid"] != ssid]
                nets.append({"ssid": ssid, "auth": auth, "signal": 0, "known": True, "connected": True})
                nets.sort(key=lambda n: (not n["connected"], not n["known"], -n["signal"], n["ssid"].lower()))
                self.ui.emit(lambda: (self._wifi_mark("wifiBusy", ADD_KEY, ""),
                                      self._on_wifi({"nets": nets, "note": "location" if _SCAN_BLOCKED else "",
                                                     "off": False})))
            else:
                self.ui.emit(lambda: (self._wifi_mark("wifiBusy", ADD_KEY, ""),
                                      self._wifi_mark("wifiNotes", ADD_KEY, msg or "Couldn't connect"),
                                      self.scanWifi()))
        self._spawn(work)

    def _wifi_done(self, ssid, connecting, ok, msg):
        self.put("wifiBusy", {})
        if msg:
            self._wifi_mark("wifiNotes", ssid, msg)
        if ok and _SCAN_BLOCKED:
            # a full rescan needs the slow SSID lookup here, so use the result we already know
            target = ssid if connecting else None
            nets = []
            for n in self._wifi_nets:
                n = dict(n)
                n["connected"] = n["ssid"] == target
                if n["connected"]:
                    n["known"] = True
                nets.append(n)
            nets.sort(key=lambda n: (not n["connected"], not n["known"], -n["signal"], n["ssid"].lower()))
            self._on_wifi({"nets": nets, "note": "location", "off": False})
        else:
            self.scanWifi()

    # ---- Bluetooth ----
    @Slot()
    def scanBt(self):
        self.put("btScanning", True)

        def work():
            try:
                devs = bt_list()
            except Exception:  # noqa: BLE001
                log("bt scan failed:\n" + traceback.format_exc())
                devs = None
            self.ui.emit(lambda: self._on_bt(devs))
        self._spawn(work)

    def _on_bt(self, devs):
        self.put("btScanning", False)
        self.put("btBusy", {})
        if devs is None:
            self.put("btDevices", [])
            return
        self.put("btDevices", [{"addr": str(d["addr"]), "name": d["name"], "connected": d["connected"],
                                "glyph": bt_icon(d["cls"])} for d in devs])

    @Slot(str, bool)
    def btSet(self, addr, connect):
        d = dict(self._v["btBusy"])
        d[addr] = "Connecting..." if connect else "Disconnecting..."
        self.put("btBusy", d)
        n = dict(self._v["btNotes"])
        n.pop(addr, None)
        self.put("btNotes", n)

        def work():
            note = ""
            try:
                bt_set(int(addr), connect)
                devs = bt_list()
                dv = next((x for x in devs if str(x["addr"]) == addr), None)
                if not dv or dv["connected"] != connect:
                    note = "Couldn't connect" if connect else "Couldn't disconnect"
            except Exception:  # noqa: BLE001
                log("bt action failed:\n" + traceback.format_exc())
                devs, note = None, "Something went wrong"

            def done():
                if note:
                    nn = dict(self._v["btNotes"])
                    nn[addr] = note
                    self.put("btNotes", nn)
                if devs is None:
                    self.scanBt()
                else:
                    self._on_bt(devs)
            self.ui.emit(done)
        self._spawn(work)

    # ---- volume mixer (per app) ----
    @Slot()
    def refreshApps(self):
        if self._apps_busy:
            return
        self._apps_busy = True

        def work():
            try:
                data = audio_sessions()
            except Exception:  # noqa: BLE001
                log("app volume read failed:\n" + traceback.format_exc())
                data = None
            self.ui.emit(lambda: self._on_apps(data))
        self._spawn(work)

    def _on_apps(self, data):
        self._apps_busy = False
        if data is None:
            self.put("apps", [])
            self.put("appsState", "error")
            return
        self.put("appsState", "ok" if data else "empty")
        self.put("apps", [{"key": a["key"], "name": a["name"], "vol": float(a["vol"]),
                           "muted": bool(a["muted"]), "active": bool(a["active"])} for a in data])

    @Slot(str, float)
    def setAppVolume(self, key, level):
        w = self._app_level.get(key)
        if w is None:
            w = self._app_level[key] = _Latest(lambda v, k=key: set_app_audio(k, level=v))
        w.push(_clamp(float(level), 0.0, 1.0))

    @Slot(str, bool)
    def setAppMute(self, key, muted):
        def work():
            try:
                set_app_audio(key, mute=muted)
            except Exception:  # noqa: BLE001
                log("app mute failed:\n" + traceback.format_exc())
        self._spawn(work)

    # ---- system stats ----
    @Slot()
    def startStats(self):
        cpu_percent()                                   # prime the delta so the first number shown is real
        self._net_t = None
        self._ticks = 0

    @Slot()
    def sampleStats(self):
        self._ticks += 1
        self.put("cpu", float(cpu_percent()))
        used, total = mem_stats()
        self.put("memUsed", float(used))
        self.put("memTotal", float(total or 1))
        rx, tx = self._net_rates()
        self.put("netRx", rx)
        self.put("netTx", tx)
        if self._ticks % 5 == 1 and not self._gpu_busy and _nvsmi_path():       # nvidia-smi is slow, keep it off the UI thread
            self._gpu_busy = True

            def work():
                try:
                    d = gpu_stats()
                finally:
                    self._gpu_busy = False
                self.ui.emit(lambda: self.put("gpu", d or {}))
            self._spawn(work)
        if self._ticks % 10 == 1:
            self.put("disks", [{"letter": l, "used": float(u), "total": float(t)} for l, u, t in fixed_drives()])
            self.put("uptime", _uptime_text())

    def _net_rates(self):
        now, cur = time.monotonic(), net_counters()
        rx = tx = 0.0
        if self._net_t is not None and now > self._net_t:
            dt = now - self._net_t
            for k, (i, o) in cur.items():
                if k in self._net_prev:
                    pi, po = self._net_prev[k]
                    rx += (i - pi) & 0xFFFFFFFF                # 32-bit counters wrap
                    tx += (o - po) & 0xFFFFFFFF
            rx, tx = rx / dt, tx / dt
        self._net_prev, self._net_t = cur, now
        return rx, tx

    # ---- theme colour ----
    @Slot(str, str, float, float, float)
    def setTarget(self, target, mode, h, s, v):
        """Theme card. target is shell / outline / icons, mode is "custom" (h, s, v in 0..1, used as is) or "auto"
        (follow the wallpaper). The bar changes right away, the file is written once you stop dragging."""
        log("setTarget %s %s h=%.3f s=%.3f v=%.3f" % (target, mode, h, s, v))
        if target not in TARGETS:
            return
        self._theme = dict(self._theme)
        self._theme[target] = clean_target(mode, h, s, v)
        self.put("themeState", {k: dict(e) for k, e in self._theme.items()})
        self.themeColors.emit(theme_bar_colors(self._theme))
        self._save_timer.start()

    @Slot(str)
    def resetTarget(self, target):
        if target in TARGETS:
            e = self._theme[target]
            self.setTarget(target, "auto", e["h"], e["s"], e["v"])

    @Slot()
    def resetTheme(self):
        for k in TARGETS:
            self.resetTarget(k)

    def savedColors(self):
        """The saved overrides, applied to the bar before its first frame. {} means everything follows the wallpaper."""
        return theme_bar_colors(self._theme)

    def _save_theme(self):
        def work():
            try:
                with _THEME_LOCK:
                    save_theme_state(**{k: dict(e) for k, e in self._theme.items()})
            except Exception:  # noqa: BLE001
                log("theme write failed:\n" + traceback.format_exc())
        self._spawn(work)

    # ---- clear cache ----
    @Slot()
    def cleanScan(self):
        self.put("cleanState", "scanning")
        self.put("cleanSummary", "")

        def work():
            try:
                items = clean_targets()
            except Exception:  # noqa: BLE001
                log("clean scan failed:\n" + traceback.format_exc())
                items = []
            self.ui.emit(lambda: self._clean_scanned(items))
        self._spawn(work)

    def _clean_scanned(self, items):
        self._clean_items = items
        total = sum(sz for _p, sz in items)
        self.put("cleanCount", len(items))
        self.put("cleanSize", _fmt_size(total))
        top = sorted(items, key=lambda t: -t[1])[:5]
        self.put("cleanPreview", ["%s  (%s)" % (p, _fmt_size(sz)) for p, sz in top])
        self.put("cleanState", "ready" if items else "empty")

    @Slot()
    def cleanRun(self):
        items = list(self._clean_items)
        if not items or self._v["cleanState"] == "running":
            return
        self.put("cleanState", "running")
        self.cleanLine.emit("info", "Deleting %d items (%s)..." % (len(items), self._v["cleanSize"]))

        def work():
            try:
                res = clean_run(items, lambda k, t: self.ui.emit(lambda: self.cleanLine.emit(k, t)))
            except Exception:  # noqa: BLE001
                log("clean failed:\n" + traceback.format_exc())
                self.ui.emit(lambda: self.cleanLine.emit("skip", "cleanup stopped by an error (see the log file)"))
                res = (0, 0, len(items))
            self.ui.emit(lambda: self._clean_done(res))
        self._spawn(work)

    def _clean_done(self, res):
        removed, freed, skipped = res
        self.cleanLine.emit("done", "Done: %d removed, %d skipped, %s freed" % (removed, skipped, _fmt_size(freed)))
        self.put("cleanSummary", "Cleared %s" % _fmt_size(freed))
        self.put("cleanState", "done")
        self._clean_items = []

    @Slot()
    def cleanReset(self):
        if self._v["cleanState"] != "running":
            self.put("cleanState", "idle")

    # ---- power ----
    @Slot(str)
    def power(self, what):
        cmds = {
            "shutdown": ["shutdown", "/s", "/t", "0"],
            "restart": ["shutdown", "/r", "/t", "0"],
            "signout": ["shutdown", "/l"],
            "hibernate": ["shutdown", "/h"],
            "sleep": ["powershell.exe", "-NoProfile", "-Command",
                      "Add-Type -AssemblyName System.Windows.Forms; "
                      "[System.Windows.Forms.Application]::SetSuspendState('Suspend',$false,$false)"],
        }
        cmd = cmds.get(what)
        if not cmd:
            return
        try:
            subprocess.Popen(cmd, stdin=subprocess.DEVNULL, creationflags=NOWIN)
        except OSError:
            log("power %s failed:\n%s" % (what, traceback.format_exc()))
        self.closeRequested.emit()
