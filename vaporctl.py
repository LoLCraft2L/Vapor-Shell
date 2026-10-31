#!/usr/bin/env python3
"""vaporctl - command line for the running Vapor shell (stdlib only, starts instantly).

Usage:  python vaporctl.py <command> [args]      (or add this folder to PATH and use vaporctl.cmd)
Run with no arguments, or `help`, for the command list.  `--version` prints the version, `update` installs the newest release.

Works whether or not Vapor is running: `start` launches it, and volume / mute / media / notify / timer / remind / layout /
log / paths fall back to doing the job directly when the shell is down.
"""
import datetime
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))      # True when running as the PyInstaller vaporctl.exe
if FROZEN:
    HERE = Path(sys.executable).resolve().parent     # the install folder (next to Vapor.exe), NOT the _MEI temp folder
else:
    HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("LOCALAPPDATA", str(HERE))) / "vapor"
CLI_FILE = DATA / "cli.json"

VERSION = "0.1.2"           # keep in step with the release tag (CI can set it from the tag before building vaporctl.exe)
REPO = os.environ.get("VAPOR_REPO") or "LoLCraft2L/Vapor-Shell"
INSTALL_URL = "https://raw.githubusercontent.com/%s/main/scripts/install.ps1" % REPO

HELP = """vaporctl - control the running Vapor shell

  status                      volume, battery, wifi, media, workspace, layout, bar state
  fetch                       logo + version + live status in one coloured card
  volume [N|+N|-N]            show / set / step the volume
  mute [on|off]               toggle (or force) mute
  media [play|next|prev]      control the active player, no argument shows what is playing
  ws <N|next|prev>            switch komorebi workspace (N starts at 1)
  layout [next|prev]          cycle the komorebi layout
  hide | show | toggle        slide the bar away / back
  alert "title" ["text"]      in-bar alert card + ringtone (dismiss to stop)
  dismiss                     dismiss the current alert / stop the ringtone
  notify "title" ["text"]     normal Windows toast
  timer <5m|1h30m|90|cancel>  start the clock-page timer
  remind <when> "text"        add a reminder; <when> = 18:30, 7pm, 7:30pm, 10m, 1h30m
        [--every daily|weekly|monthly]
  reminders [list]            list reminders + the running timer      (also: reminders rm <N>)
  note ["text"] [-t "title"]  add a note (no text = list notes; also: note show <N>, note rm <N>, note - = read stdin)
  setname [name|--reset]      show / set the name on the profile card
  pfp [path|reset]            show / set the profile picture (the file is copied into files/)
  ringtone [path|test]        show / replace the alarm sound (an .mp3, copied to files/ringtone.mp3) / play it once
  set location <place|auto>   weather place: "Pokhara", "Paris, France", "27.7,85.3", or auto (from your IP)
        [--f | --c]
  set name|pfp|location ...   same as setname / pfp / location
  wallpaper [file|random]     show / set the desktop wallpaper  (also: next, prev, dir <folder>)
  reload                      re-read config.json without restarting
  autostart [on|off]          start Vapor at every login (a Startup shortcut)
  start                       start Vapor (does nothing if it already runs)
  restart | quit | stop       restart or close Vapor  (stop --force kills a hung copy)

  update [--check|--force]    install the latest release (--check only looks, --force reinstalls the same version)
  --version                   print the installed version

  log [N]                     last N lines of vapor.log (default 40)
  paths                       where config, files, log and settings live
  config | files              open config.json / the files folder
  config get|set|unset ...    read / change one config.json key   (config get = show all)
  doctor [--report]           check install, config, log and helpers (--report: + log tail and config for bug reports)
  --json                      (anywhere) print the raw reply
"""


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


class NotRunning(Exception):
    pass


def send(cmd, args):
    """Ask the running Vapor. Raises NotRunning when nothing answers (never started, closed, or crashed)."""
    try:
        info = json.loads(CLI_FILE.read_text(encoding="utf-8"))
        with socket.create_connection(("127.0.0.1", info["port"]), timeout=2) as s:
            s.settimeout(8)
            s.sendall((json.dumps({"token": info["token"], "cmd": cmd, "args": args}) + "\n").encode("utf-8"))
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(4096)
                if not chunk:
                    break
                buf += chunk
        return json.loads(buf.decode("utf-8"))
    except (OSError, ValueError, KeyError):
        raise NotRunning()


def is_running():
    try:
        return bool(send("ping", []).get("ok"))
    except NotRunning:
        return False


def _stale_pid():
    """pid from cli.json if that process is still a live python/pythonw (Vapor not answering), else 0."""
    try:
        pid = int(json.loads(CLI_FILE.read_text(encoding="utf-8")).get("pid", 0))
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             creationflags=0x08000000).stdout.lower()
        return pid if pid and "python" in out else 0
    except Exception:
        return 0


def start_vapor():
    if is_running():
        return "Vapor is already running"
    pid = _stale_pid()
    if pid:
        raise RuntimeError("a Vapor process (pid %d) is alive but not answering; try: vaporctl stop --force" % pid)
    if FROZEN:      # sys.executable is vaporctl.exe here: start Vapor.exe from the same folder
        cmd = [str(HERE / "Vapor.exe")]
    else:
        exe = Path(sys.executable)
        pyw = exe.with_name("pythonw.exe")
        cmd = [str(pyw if pyw.exists() else exe), str(HERE / "vapor.pyw")]
    subprocess.Popen(cmd, cwd=str(HERE),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
                     creationflags=0x00000008 | 0x00000200 | 0x08000000)       # detached, own group, no window
    for _ in range(60):
        time.sleep(0.25)
        if is_running():
            return "Vapor started"
    raise RuntimeError("started it, but it did not answer in 15 s (see: vaporctl log)")


# ---------------------------------------------------------------- fallbacks for when Vapor is not running
VK = {"mute": 0xAD, "down": 0xAE, "up": 0xAF, "next": 0xB0, "prev": 0xB1, "play": 0xB3}


def press(key, times=1):
    import ctypes
    for _ in range(times):
        ctypes.windll.user32.keybd_event(VK[key], 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK[key], 0, 2, 0)


def _endpoint():
    import ctypes
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    dev = AudioUtilities.GetSpeakers()
    ep = getattr(dev, "EndpointVolume", None)
    if ep is None:
        ep = ctypes.cast(dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None), ctypes.POINTER(IAudioEndpointVolume))
    return ep


def _vol_text(ep):
    return "volume %d%%%s" % (round(ep.GetMasterVolumeLevelScalar() * 100), " (muted)" if ep.GetMute() else "")


def offline_volume(args):
    try:
        ep = _endpoint()
    except Exception:
        ep = None
    a = args[0] if args else ""
    if ep is None:                                           # no pycaw: media keys can still step it (2 % per press)
        if a[:1] in ("+", "-"):
            press("up" if a[0] == "+" else "down", max(1, round(abs(int(a)) / 2)))
            return "volume stepped (install pycaw + comtypes to see the level)"
        raise RuntimeError("needs pycaw to read or set a level:  pip install pycaw comtypes")
    if a:
        v = round(ep.GetMasterVolumeLevelScalar() * 100)
        v = v + int(a) if a[0] in "+-" else int(a)
        ep.SetMasterVolumeLevelScalar(max(0, min(100, v)) / 100.0, None)
        if v > 0 and ep.GetMute():
            ep.SetMute(0, None)
    return _vol_text(ep)


def offline_mute(args):
    a = args[0].lower() if args else ""
    try:
        ep = _endpoint()
    except Exception:
        press("mute")
        return "mute toggled"
    ep.SetMute(0 if (a == "off" or (a != "on" and ep.GetMute())) else 1, None)
    return "muted" if ep.GetMute() else "unmuted"


def offline_notify(args):
    app = "Vapor.Shell"
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\AppUserModelId\\" + app) as k:
            winreg.SetValueEx(k, "DisplayName", 0, winreg.REG_SZ, "Vapor")
            winreg.SetValueEx(k, "ShowInSettings", 0, winreg.REG_DWORD, 1)
    except Exception:
        pass
    ps = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
          "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
          "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
          "$x.LoadXml('<toast><visual><binding template=\"ToastGeneric\"><text></text><text></text></binding></visual></toast>');"
          "$n = $x.GetElementsByTagName('text');"
          "$n.Item(0).AppendChild($x.CreateTextNode($env:TOAST_T)) | Out-Null;"
          "$n.Item(1).AppendChild($x.CreateTextNode($env:TOAST_B)) | Out-Null;"
          "$t = [Windows.UI.Notifications.ToastNotification]::new($x);"
          "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:TOAST_APP).Show($t)")
    env = dict(os.environ, TOAST_T=args[0] if args else "Vapor", TOAST_B=args[1] if len(args) > 1 else "", TOAST_APP=app)
    subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps], env=env, creationflags=0x08000000)
    return "toast sent"


def _edit_clock(fn):
    """Timer / reminders live in settings.json -> clock; Vapor reads them when it starts."""
    f = DATA / "settings.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        d = d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        d = {}
    clock = d.get("clock") if isinstance(d.get("clock"), dict) else {}
    fn(clock)
    d["clock"] = clock
    DATA.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=1), encoding="utf-8")


def offline_timer(args):
    if args[0].lower() == "cancel":
        _edit_clock(lambda c: c.update(timerEnd=0, timerTotal=0, timerPausedLeft=0))
        return "timer cancelled (saved)"
    sec = int(args[0])
    _edit_clock(lambda c: c.update(timerEnd=int((time.time() + sec) * 1000), timerTotal=sec, timerPausedLeft=0))
    return "timer saved: %d s (it keeps counting; Vapor shows it when it starts)" % sec


def offline_remind(args):
    r = json.loads(args[0])

    def add(c):
        a = [x for x in (c.get("alarms") or []) if isinstance(x, dict)]
        a.append({"ts": r["ts"], "on": True, "rep": r["rep"], "t": r["t"]})
        c["alarms"] = sorted(a, key=lambda x: x.get("ts", 0))
    _edit_clock(add)
    return "reminder saved (it rings once Vapor is running)"


def offline_komorebi(cmd, args):
    a = args[0].lower() if args else ""
    if cmd == "layout":
        out = subprocess.run(["komorebic", "cycle-layout", "previous" if a in ("prev", "previous") else "next"],
                             capture_output=True, text=True, creationflags=0x08000000)
    else:
        out = subprocess.run(["komorebic", "focus-workspace", str(int(a) - 1)], capture_output=True, text=True,
                             creationflags=0x08000000)
    return (out.stderr or out.stdout).strip() or "ok"


# ---------------------------------------------------------------- settings: name, picture, place, reminders, notes
CONFIG_FILE = HERE / "config.json"
FILES = HERE / "files"
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")


def try_send(cmd, args):
    try:
        return send(cmd, args)
    except NotRunning:
        return None


def read_json(path, default):
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        return d if isinstance(d, type(default)) else default
    except (OSError, ValueError):
        return default


def config_update(**kv):
    """Edit config.json in place (other keys stay as they are); None removes a key."""
    d = read_json(CONFIG_FILE, {})
    for k, v in kv.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    for k, v in (("userName", ""), ("profilePicture", ""), ("addToPath", True)):
        d.setdefault(k, v)
    CONFIG_FILE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def apply_live(cmd):
    """Tell a running Vapor to re-read config.json (name/picture: right away; otherwise it picks it up within ~30 s)."""
    return try_send(cmd, []) is not None


def cmd_setname(args):
    cur = read_json(CONFIG_FILE, {}).get("userName", "")
    if not args:
        return "name: %s" % (cur or "%s  (Windows user name; set one with: vaporctl setname <name>)" % os.environ.get("USERNAME", "user"))
    if args[0] == "--reset":
        config_update(userName="")
        apply_live("refresh")
        return "name reset to your Windows user name"
    name = " ".join(args).strip()
    config_update(userName=name)
    live = apply_live("refresh")
    return "name set to %r%s" % (name, "" if live else "  (Vapor is not running: it shows up on the next start)")


def cmd_pfp(args):
    import shutil
    cfg = read_json(CONFIG_FILE, {}).get("profilePicture", "")
    if not args:
        return "profile picture: %s" % (cfg or "(not set: files/profile.png|jpg, else your Windows account picture)")
    if args[0].lower() == "reset":
        config_update(profilePicture="")
        apply_live("refresh")
        return "profile picture reset (files/profile.png|jpg, else your Windows account picture)"
    src = Path(os.path.expandvars(os.path.expanduser(" ".join(args).strip().strip('"'))))
    if not src.is_absolute():
        src = Path.cwd() / src
    if not src.is_file():
        raise RuntimeError("file not found: %s" % src)
    if src.suffix.lower() not in IMG_EXT:
        raise RuntimeError("not a picture (%s)" % ", ".join(IMG_EXT))
    FILES.mkdir(exist_ok=True)
    if src.parent.resolve() == FILES.resolve():
        name = src.name                                   # already in files/: use it as it is
    else:
        for old in FILES.glob("pfp_*"):                    # earlier pictures set by this command
            try:
                old.unlink()
            except OSError:
                pass
        name = "pfp_%d%s" % (int(time.time()), src.suffix.lower())   # new name each time, so the bar reloads the image
        shutil.copy2(src, FILES / name)
    config_update(profilePicture=name)
    live = apply_live("refresh")
    return "profile picture set: files/%s%s" % (name, "" if live else "  (Vapor is not running: it shows up on the next start)")


def geocode(query):
    import urllib.parse
    import urllib.request
    parts = [x.strip() for x in query.split(",") if x.strip()]
    url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": parts[0], "count": 20, "language": "en", "format": "json"})
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            res = json.loads(r.read().decode("utf-8")).get("results") or []
    except (OSError, ValueError):
        raise RuntimeError("could not look the place up (no internet?). You can pass coordinates instead: set location 27.7,85.3")
    for t in (x.lower() for x in parts[1:]):                  # "Paris, France" / "Springfield, Illinois": narrow by the rest
        res = [r for r in res if t in " ".join(str(r.get(k, "")) for k in ("country", "country_code", "admin1", "admin2")).lower()]
    if not res:
        raise RuntimeError("no place found for %r (try 'City, Country')" % query)
    r = res[0]
    label = ", ".join(x for x in (r.get("name"), r.get("admin1"), r.get("country")) if x)
    return label, float(r["latitude"]), float(r["longitude"]), r.get("country_code") == "US"


def cmd_location(args):
    loc = read_json(CONFIG_FILE, {}).get("location")
    if not args:
        if isinstance(loc, dict):
            return "weather place: %s (%s, %s)  %s" % (loc.get("name", "?"), loc.get("lat"), loc.get("lon"),
                                                       "Fahrenheit" if loc.get("fahrenheit") else "Celsius")
        return "weather place: automatic (found from your IP)"
    flag_f, flag_c = "--f" in args, "--c" in args
    args = [a for a in args if a not in ("--f", "--c")]
    q = " ".join(args).strip()
    if q.lower() in ("auto", "reset", "ip"):
        config_update(location=None)
        live = apply_live("location")
        return "weather place: automatic" + ("" if live else "  (Vapor is not running: applied on the next start)")
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)", q)
    if m:
        lat, lon, fahr = float(m.group(1)), float(m.group(2)), False
        label = "%s, %s" % (lat, lon)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise RuntimeError("latitude is -90..90 and longitude -180..180")
    else:
        label, lat, lon, fahr = geocode(q)
    if flag_f or flag_c:
        fahr = flag_f
    config_update(location={"name": label, "lat": lat, "lon": lon, "fahrenheit": fahr})
    live = apply_live("location")
    return "weather place: %s (%s, %s)  %s%s" % (label, lat, lon, "Fahrenheit" if fahr else "Celsius",
                                                 "" if live else "  (Vapor is not running: applied on the next start)")


def get_clock():
    r = try_send("clockdump", [])
    if r is not None and r.get("ok"):
        try:
            d = json.loads(r["text"])
            return d if isinstance(d, dict) else {}, True
        except ValueError:
            pass
    d = read_json(DATA / "settings.json", {}).get("clock")
    return (d if isinstance(d, dict) else {}), False


def get_notes():
    r = try_send("notesdump", [])
    if r is not None and r.get("ok"):
        try:
            d = json.loads(r["text"])
            return (d if isinstance(d, list) else []), True
        except ValueError:
            pass
    d = read_json(DATA / "settings.json", {}).get("notes")
    return (d if isinstance(d, list) else []), False


def fmt_ts(ms):
    return datetime.datetime.fromtimestamp(ms / 1000).strftime("%a %b %d, %I:%M %p").replace(", 0", ", ")


def _index(args, n, what):
    if not args or not args[0].isdigit() or not 1 <= int(args[0]) <= n:
        raise RuntimeError("%s: pick a number from 1 to %d" % (what, n) if n else "no %ss" % what)
    return int(args[0]) - 1


def cmd_reminders(args):
    sub = args[0].lower() if args else "list"
    clock, live = get_clock()
    alarms = [a for a in (clock.get("alarms") or []) if isinstance(a, dict)]
    if sub in ("add", "new"):
        raise RuntimeError('add one with: vaporctl remind <when> "text"')
    if sub in ("rm", "remove", "del", "delete"):
        i = _index(args[1:], len(alarms), "reminder")
        what = alarms[i].get("t") or "Reminder"
        if live:
            try_send("remind-rm", [json.dumps(i)])
        else:
            _edit_clock(lambda c: c.update(alarms=[a for k, a in enumerate(c.get("alarms") or []) if k != i]))
        return "removed reminder %d (%s)" % (i + 1, what)
    if sub not in ("list", "ls"):
        raise RuntimeError("reminders [list] | reminders rm <N>")
    now = time.time() * 1000
    rows = []
    for n, a in enumerate(alarms, 1):
        ts = a.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        rep = {"daily": "daily", "weekly": "weekly", "monthly": "monthly"}.get(a.get("rep"), "once")
        flag = "" if a.get("on", True) else "  (off)"
        rows.append("%2d  %-20s %-8s %s%s" % (n, fmt_ts(ts), rep, a.get("t") or "Reminder", flag))
    out = "\n".join(rows) if rows else "no reminders"
    end, paused = clock.get("timerEnd") or 0, clock.get("timerPausedLeft") or 0
    if end and end > now:
        left = int((end - now) / 1000)
        out += "\ntimer: %d:%02d:%02d left" % (left // 3600, left % 3600 // 60, left % 60)
    elif paused:
        out += "\ntimer: paused, %d:%02d left" % (paused // 60, paused % 60)
    return out


def cmd_note(args):
    notes, live = get_notes()
    sub = args[0].lower() if args else "list"
    if sub in ("list", "ls"):
        if not notes:
            return "no notes"
        rows = []
        for n, x in enumerate(notes, 1):
            title, body = (x.get("title") or "").strip(), " ".join((x.get("t") or "").split())
            head = title or (body[:60] + ("..." if len(body) > 60 else ""))
            rows.append("%2d  %s%s" % (n, head, ("   - " + body[:50]) if title and body else ""))
        return "\n".join(rows)
    if sub == "show":
        x = notes[_index(args[1:], len(notes), "note")]
        return ((x.get("title") + "\n") if x.get("title") else "") + (x.get("t") or "")
    if sub in ("rm", "remove", "del", "delete"):
        i = _index(args[1:], len(notes), "note")
        if live:
            try_send("note-rm", [json.dumps(i)])
        else:
            def drop(lst):
                return [x for k, x in enumerate(lst) if k != i]
            _edit_list("notes", drop)
        return "removed note %d" % (i + 1)
    # anything else is the text of a new note
    title = ""
    for flag in ("-t", "--title"):
        if flag in args:
            k = args.index(flag)
            title = args[k + 1] if k + 1 < len(args) else ""
            del args[k:k + 2]
    text = sys.stdin.read().strip() if args == ["-"] else " ".join(args).strip()
    if not text and not title:
        raise RuntimeError('usage: note "text" [-t "title"]')
    if live:
        try_send("note", [json.dumps({"title": title, "t": text})])
    else:
        _edit_list("notes", lambda lst: [{"title": title, "t": text, "ts": int(time.time() * 1000)}] + lst)
    return "note added" + ("" if live else "  (saved; Vapor shows it when it starts)")


def _edit_list(key, fn):
    f = DATA / "settings.json"
    d = read_json(f, {})
    cur = d.get(key) if isinstance(d.get(key), list) else []
    d[key] = fn(cur)
    DATA.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=1), encoding="utf-8")



def cmd_ringtone(args):
    """files/ringtone.mp3 is what the alarm plays. No argument shows it, a path replaces it, `test` plays it once."""
    import shutil
    f = FILES / "ringtone.mp3"
    a = " ".join(args).strip().strip('"')
    if not a:
        return ("ringtone: %s  (%.1f MB)" % (f, f.stat().st_size / 1048576)) if f.is_file() else \
               "ringtone: none yet. Set one with: vaporctl ringtone C:\\path\\to\\sound.mp3   (expected at %s)" % f
    if a.lower() == "test":
        if not f.is_file():
            raise RuntimeError("no ringtone yet: %s" % f)
        import ctypes
        mci = ctypes.windll.winmm.mciSendStringW
        buf = ctypes.create_unicode_buffer(64)
        mci("close vaporctltest", None, 0, None)
        if mci('open "%s" type mpegvideo alias vaporctltest' % f, None, 0, None):
            raise RuntimeError("could not open %s" % f)
        try:
            mci("play vaporctltest", None, 0, None)
            end = time.time() + 12                           # plays once, at most 12 s
            time.sleep(0.3)
            while time.time() < end:
                mci("status vaporctltest mode", buf, 63, None)
                if buf.value != "playing":
                    break
                time.sleep(0.2)
        finally:
            mci("stop vaporctltest", None, 0, None)
            mci("close vaporctltest", None, 0, None)
        return "played once"
    src = Path(os.path.expandvars(os.path.expanduser(a)))
    if not src.is_absolute():
        src = Path.cwd() / src
    if not src.is_file():
        raise RuntimeError("file not found: %s" % src)
    if src.suffix.lower() != ".mp3":
        raise RuntimeError("the ringtone has to be an .mp3")
    FILES.mkdir(exist_ok=True)
    if src.resolve() != f.resolve():
        try:
            shutil.copy2(src, f)
        except PermissionError:
            raise RuntimeError("ringtone.mp3 is in use (an alarm is ringing?). Run: vaporctl dismiss   then try again")
    return "ringtone set: %s   (test it: vaporctl ringtone test)" % f


def offline(cmd, args):
    """What each command does when Vapor is down. Returns the text to print; raises RuntimeError with a hint otherwise."""
    a = args[0].lower() if args else ""
    if cmd == "status":
        return "vapor      not running  (start it with: vaporctl start)"
    if cmd == "volume":
        return offline_volume(args)
    if cmd == "mute":
        return offline_mute(args)
    if cmd == "media":
        keys = {"play": "play", "pause": "play", "toggle": "play", "next": "next", "prev": "prev", "previous": "prev"}
        if a not in keys:
            raise RuntimeError("media play|pause|next|prev  (showing what is playing needs Vapor)")
        press(keys[a])
        return "sent media key: %s" % a
    if cmd == "notify":
        return offline_notify(args)
    if cmd == "timer":
        return offline_timer(args)
    if cmd == "remind":
        return offline_remind(args)
    if cmd == "layout" or (cmd == "ws" and a.isdigit()):
        return offline_komorebi(cmd, args)
    if cmd in ("quit", "stop"):
        return "Vapor is not running"
    if cmd == "restart":
        return start_vapor()
    raise RuntimeError("'%s' needs Vapor running. Start it with:  vaporctl start" % cmd)


def stop_vapor(force):
    try:
        resp = send("quit", [])
        return resp.get("text", "quitting")
    except NotRunning:
        pid = _stale_pid()
        if pid and force:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, creationflags=0x08000000)
            CLI_FILE.unlink(missing_ok=True)
            return "killed pid %d" % pid
        if pid:
            raise RuntimeError("a Vapor process (pid %d) is alive but not answering; use: vaporctl stop --force" % pid)
        CLI_FILE.unlink(missing_ok=True)
        return "Vapor is not running"


def parse_duration(s):
    """'90' -> 90 s, '5m', '1h30m', '45s'"""
    s = s.strip().lower().lstrip("+")
    if s.isdigit():
        return int(s)
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", s)
    if not s or not m or not any(m.groups()):
        raise ValueError("bad duration: %r (try 90, 5m, 1h30m)" % s)
    h, mi, sec = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + sec


def parse_when(s):
    """-> epoch milliseconds. Clock time (18:30, 7pm, 7:30pm) = next time it occurs; duration (10m, 1h30m) = from now."""
    t = s.strip().lower()
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", t)
    if m and (":" in t or m.group(3)):
        h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
        if ap:
            h = h % 12 + (12 if ap == "pm" else 0)
        if h > 23 or mi > 59:
            raise ValueError("bad time: %r" % s)
        now = datetime.datetime.now()
        at = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        if at <= now:
            at += datetime.timedelta(days=1)
        return int(at.timestamp() * 1000)
    return int((time.time() + parse_duration(t)) * 1000)


# ---------------------------------------------------------------- version + update
def _ver(s):
    return tuple(int(x) for x in re.findall(r"\d+", s or "")[:4])


def latest_release():
    """Tag of the newest GitHub release (e.g. v0.1.3)."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request("https://api.github.com/repos/%s/releases/latest" % REPO,
                                 headers={"User-Agent": "vaporctl", "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            tag = json.loads(r.read().decode("utf-8")).get("tag_name", "")
    except urllib.error.HTTPError as e:
        raise RuntimeError("GitHub answered %s (%s): %s" % (e.code, e.reason, "no release published yet" if e.code == 404 else "try again later"))
    except (OSError, ValueError):
        raise RuntimeError("could not reach GitHub (no internet?)")
    if not tag:
        raise RuntimeError("the latest release has no tag")
    return tag


def cmd_update(args):
    """update: install the newest release. --check only reports, --force reinstalls even when up to date.
        The real work is done by install.ps1 (same one-liner as the first install, same folder, config.json and files/
        are kept). It runs in its own window and stops this vaporctl.exe, so we start it and leave straight away."""
    check, force = "--check" in args, "--force" in args
    tag = latest_release()
    cur, new = _ver(VERSION), _ver(tag)
    newer = (new > cur) if (new and cur) else (tag.lstrip("vV") != VERSION)
    line = "installed v%s, latest %s" % (VERSION, tag)
    if check:
        return line + ("   update available: run  vaporctl update" if newer else "   (up to date)")
    if not newer and not force:
        return "already up to date (v%s)" % VERSION
    if not FROZEN:
        raise RuntimeError("running from source, so there is no install to replace (latest is %s): update with git pull" % tag)
    import tempfile
    ps = "& ([scriptblock]::Create((irm '%s'))) -Repo '%s' -Dir '%s'; Start-Sleep -Seconds 4" % (
        INSTALL_URL, REPO, str(HERE).replace("'", "''"))
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                     cwd=tempfile.gettempdir(),                      # never inside the folder it is about to replace
                     stdin=subprocess.DEVNULL, close_fds=True, creationflags=0x00000010)      # CREATE_NEW_CONSOLE
    return "updating v%s -> %s: an installer window opens, Vapor restarts when it is done" % (VERSION, tag.lstrip("vV"))


# ---------------------------------------------------------------- fetch: logo + system card

# logo art + palette indices (hex digit per character) come from scripts/install.ps1

LOGO_PALETTE = [(244, 235, 250), (221, 202, 244), (208, 173, 245), (192, 152, 245), (190, 158, 215), (175, 136, 245), (178, 119, 247), (181, 126, 234), (164, 111, 245), (180, 99, 240), (167, 122, 215), (161, 110, 232), (149, 98, 236), (145, 94, 212), (146, 106, 178), (110, 69, 150)]

LOGO_BIG = [
    '                                                :**++.',
    '                                            .*%%*:',
    '                                     .:    :%@%',
    '                #.         .:   .+#%#+.   :*%#:',
    '              +#@%+.       +* :#@@@@@%%%#**:  +*#%%#',
    '             +*%@@*+.        *#*: :#@#*.  .+*#*++#+',
    '                #:    :***+.+.:*##+:   .++#*+ :+**#%%%@@@%#:',
    '                .  .*%#+   .*%@%: +*#%@@%*+ .++.      .#@@@*',
    '              +:  +@#:   +#@@@@@@@@%#%#.              +@@@#',
    '              *+  *+  *#***@@@@@@%+*@+              +%@@#:',
    '                +.   :+ .*@@@@@@%  @%+++.  .%+   .*%@%*.',
    '            +**+.  :*##%@@@@@@@@%  :%@@@#     .*#@%#+',
    '         +##*.  +##%@@@@@@@@@@@%+ :*@@@#.  :*%@%*:',
    '      +#%*:   +%##%@@@%#****####%%%%#+..+#%%#+.',
    '    *%%*   **%@@@@@@%+ :****++.    .+#%%#*:    +*',
    '  *%@#.  :%%@@@@@@@@%*##.      +*#%%#+.  *.   +##+',
    '.%@@#    %@@@@@@@%%@@#+  .+*#%%#*:     .*@%+    .',
    '*@@@%+   *%%%%#+.  ++*#%%%#*:         +*%@@#*.',
    '.#@@@@@%%####%%%%%%#**+ :**+.            %+',
    '   :***###***++       *#*:               .',
]

LOGO_BIG_COLORS = [
    '                                                6bbdde',
    '                                            d6666f',
    '                                     7e    eb66',
    '                14         77   43335a7   b886b',
    '              111227       a9 222335566888be  999999',
    '             e12223e4        4234 77657e  ddd99dfd9',
    '                77    cccddee443337f   aa5aaa dddccccc888888',
    '                f  ccccc   42223a a5555555a ffdf      cdc888',
    '              9d  cccd   4222223333556bb              dc888',
    '              99  cc  1112422123355d8b              dc8888',
    '                ef   11 e32112555  b6bdbd  242   8d88888',
    '            77aae  41111111235555  dc8888     7d88888',
    '         7777a  11111122235555668 db8888b  8d88888',
    '      7677a   1012111233555bbbb8888888bdeb8888b',
    '    6667   d1002101233 dddbbbbb    8fb88888    e4',
    '  6667b  c70000001223a5bc      8db88888  44   f412',
    'b666b    20000001223335  b8db88888     22213    e',
    '6666b6   00000012  5adb888888         e222237a',
    '66666668bbbbbbb88688888 ddddf            33',
    '   666666666688       cccc               a',
]

LOGO_SMALL = [
    '                              .+*++',
    '                        .:   #@+',
    '          +#      *..*#@#++**#+.+*:',
    '        .*%@*:     +#**#%#+.:+**##:.+:',
    '          .+ .***+ *##+:+*##*++*+*###@@#',
    '         +: *#+ :#%@@%%%%#+         #@%+',
    '         :. : +*+*@@@@+##    +:  .*%%*',
    '       :**+.+*#%@@@@@% :%@@. ::*%%*:',
    '    :##*..*#%@@@%%%%%*#%%#:+#%#*.',
    '  +%#:.*#@@@@%++++*+++.+###*:  **',
    ':%@+  %@@@@@%@#+ :+*###+. .#*  ::',
    '#@@#++*###*+*####**.     :*%%*.',
    ' +##%%%###*++ .**+         +.',
]

LOGO_SMALL_COLORS = [
    '                              666bd',
    '                        7a   b66',
    '          12      7a2233568bb8d9999',
    '        e122a7     4245765dffdb9edccc8',
    '          aa cccdf 223a555555afddcccc888',
    '         99 ccc 222223555bb         c888',
    '         de d 114321355b8    a2  fc888',
    '       77aae1111112555 d8888 44b8888',
    '    7777a111112355568b88888fb8888',
    '  666ad40111123ddbbb88bdb8888  42',
    '666d  200012235b bfb88888 d42  42',
    '66bde100001335b88888     e2223a',
    ' 666666688888 8dcd         77',
]


def _ansi_ok():
    """True when stdout is a terminal that understands colour (switches ANSI on in old Windows consoles)."""
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.GetStdHandle(-11)
            m = ctypes.c_uint32()
            if not k.GetConsoleMode(h, ctypes.byref(m)):
                return False
            return bool(k.SetConsoleMode(h, m.value | 4))       # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        except Exception:
            return False
    return True


def _logo_rows(art, cols, color):
    """Colour the art: every character takes the palette entry named by the same spot in the colour map."""
    rows = []
    for y, line in enumerate(art):
        crow = cols[y] if y < len(cols) else ""
        out, last = [], None
        for x, ch in enumerate(line):
            if ch == " " or not color:
                out.append(ch)
                continue
            idx = int(crow[x], 16) if x < len(crow) and crow[x] != " " else 0
            if idx != last:
                out.append("\x1b[38;2;%d;%d;%dm" % LOGO_PALETTE[idx])
                last = idx
            out.append(ch)
        if color:
            out.append("\x1b[0m")
        rows.append("".join(out))
    return rows


def _fetch_info(color):
    """The text next to the logo, as (plain, styled) pairs (plain is only used for measuring the width)."""
    rows = []

    def c(txt, rgb, bold=False):
        return "\x1b[%s38;2;%d;%d;%dm%s\x1b[0m" % ("1;" if bold else "", rgb[0], rgb[1], rgb[2], txt) if color else txt

    def add(plain, styled=None):
        rows.append((plain, styled if (color and styled is not None) else plain))

    def kv(k, v):
        add("%-9s %s" % (k, v), c("%-9s" % k, (192, 132, 252)) + " " + c(v, (215, 200, 245)))

    title = "V  A  P  O  R"
    grad = "".join("\x1b[1;38;2;%d;%d;255m%s" % (int(250 + (160 - 250) * i / (len(title) - 1)),
                                                  int(244 + (110 - 244) * i / (len(title) - 1)), ch)
                   for i, ch in enumerate(title)) + "\x1b[0m"
    add(title, grad)
    add("fluid shell for Windows", c("fluid shell for Windows", (120, 100, 170)))
    add("-" * 26, c("-" * 26, (58, 40, 96)))
    name = read_json(CONFIG_FILE, {}).get("userName") or os.environ.get("USERNAME", "")
    if name:
        kv("user", name)
    kv("version", "v" + VERSION)
    resp = try_send("status", [])
    if resp is None:
        kv("vapor", "not running")
    else:
        for line in str(resp.get("text", "")).splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                kv(parts[0], parts[1].strip())
            elif line.strip():
                add(line.strip())
    if color:
        add("", "")
        add("", "".join("\x1b[48;2;%d;%d;%dm  " % p for p in LOGO_PALETTE) + "\x1b[0m")
    return rows


def cmd_fetch(logo=True, color=True, width=None):
    """neofetch-style card: the Vapor logo on the left, version and live status on the right."""
    info = _fetch_info(color)
    if not logo:
        return "\n".join(p for _, p in info)
    cols = width or shutil.get_terminal_size((100, 30)).columns
    info_w = max(len(p) for p, _ in info)
    art, amap = None, None
    for a, m in ((LOGO_BIG, LOGO_BIG_COLORS), (LOGO_SMALL, LOGO_SMALL_COLORS)):
        if max(len(l) for l in a) + 3 + info_w <= cols - 1:
            art, amap = a, m
            break
    if art is None:                                          # too narrow for any logo
        return "\n".join(p for _, p in info)
    lw = max(len(l) for l in art)
    left = _logo_rows(art, amap, color)
    top = max(0, (len(left) - len(info)) // 2)               # centre the text next to the art
    out = []
    for i in range(max(len(left), top + len(info))):
        l = left[i] if i < len(left) else ""
        lplain = art[i] if i < len(art) else ""
        r = info[i - top][1] if 0 <= i - top < len(info) else ""
        out.append(l + " " * (lw - len(lplain) + 3) + r)
    return "\n".join(out)


# ---------------------------------------------------------------- doctor, autostart, reload, wallpaper, config keys
def cmd_doctor(args):
    """Check the install. Returns (text, ok); ok is False when something is broken (warnings do not count)."""
    import platform
    rows = []

    def add(level, name, detail):
        rows.append((level, name, detail))

    add("ok", "vaporctl", "v%s  (%s, %s)" % (VERSION, "exe" if FROZEN else "python " + sys.version.split()[0], platform.platform()))
    info = read_json(CLI_FILE, {})
    if is_running():
        add("ok", "vapor", "answering on port %s" % info.get("port", "?"))
    else:
        pid = _stale_pid()
        if pid:
            add("fail", "vapor", "pid %d is alive but not answering  (vaporctl stop --force)" % pid)
        else:
            add("warn", "vapor", "not running  (vaporctl start)")

    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if not isinstance(cfg, dict):
                raise ValueError("the top level is not an object")
            add("ok", "config", "%s  (%d keys)" % (CONFIG_FILE, len(cfg)))
            pfp = cfg.get("profilePicture")
            if isinstance(pfp, str) and pfp and not any(p.exists() for p in (Path(pfp), FILES / pfp, HERE / pfp)):
                add("warn", "picture", "profilePicture points at a missing file: %s" % pfp)
        except (OSError, ValueError) as e:
            add("fail", "config", "%s is not valid JSON: %s" % (CONFIG_FILE.name, e))
    else:
        add("warn", "config", "%s is missing  (vaporctl setname creates it)" % CONFIG_FILE)

    sf = DATA / "settings.json"
    if sf.exists():
        try:
            json.loads(sf.read_text(encoding="utf-8"))
            add("ok", "settings", str(sf))
        except (OSError, ValueError) as e:
            add("fail", "settings", "%s is not valid JSON: %s" % (sf.name, e))
    else:
        add("ok", "settings", "not created yet (Vapor writes it on first run)")

    ring = FILES / "ringtone.mp3"
    add("ok" if ring.exists() else "warn", "ringtone", str(ring) if ring.exists() else "missing: alarms will be silent  (vaporctl ringtone <file.mp3>)")

    logf = DATA / "vapor.log"
    if logf.exists():
        tail = logf.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
        bad = [l for l in tail if re.search(r"traceback|error|exception", l, re.I)]
        if bad:
            add("warn", "log", "%d error line(s) in the last 200  (vaporctl log 200)" % len(bad))
        else:
            add("ok", "log", "no errors in the last 200 lines")
    else:
        add("warn", "log", "no log yet: %s" % logf)

    add("ok" if shutil.which("komorebic") else "warn", "komorebi", "found" if shutil.which("komorebic") else "komorebic is not on PATH  (ws / layout need it)")
    try:
        import pycaw, comtypes                                # noqa: F401
        add("ok", "pycaw", "found  (volume / mute work without Vapor)")
    except ImportError:
        add("warn", "pycaw", "missing: volume / mute need Vapor running  (pip install pycaw comtypes)")
    add("ok", "autostart", "on" if _startup_lnk().exists() else "off  (vaporctl autostart on)")

    tag = {"ok": "ok  ", "warn": "warn", "fail": "FAIL"}
    lines = ["%s  %-9s %s" % (tag[l], n, d) for l, n, d in rows]
    fails = sum(1 for r in rows if r[0] == "fail")
    warns = sum(1 for r in rows if r[0] == "warn")
    lines += ["", "%d problem(s), %d warning(s)" % (fails, warns) if fails or warns else "all good"]

    if "--report" in args:
        lines += ["", "---- last 40 log lines ----"]
        try:
            lines += logf.read_text(encoding="utf-8", errors="replace").splitlines()[-40:] or ["(empty)"]
        except OSError:
            lines.append("(no log)")
        lines += ["", "---- config.json ----", json.dumps(read_json(CONFIG_FILE, {}), indent=2),
                  "", "(paths under your home folder are shown as ~; read it over before you post it)"]
    text = "\n".join(lines)
    if "--report" in args:
        text = text.replace(str(Path.home()), "~")
    return text, fails == 0


def _startup_lnk():
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "Vapor.lnk"


def cmd_autostart(args):
    lnk = _startup_lnk()
    a = args[0].lower() if args else "status"
    if a == "status":
        return "autostart %s" % ("on  (Vapor starts at every login)" if lnk.exists() else "off  (turn on with: vaporctl autostart on)")
    if a in ("off", "disable", "remove"):
        lnk.unlink(missing_ok=True)
        return "autostart off"
    if a not in ("on", "enable"):
        raise RuntimeError("autostart [on|off]")
    if os.name != "nt":
        raise RuntimeError("autostart is Windows only")
    if FROZEN:
        target, targs = str(HERE / "Vapor.exe"), ""
    else:
        exe = Path(sys.executable)
        pyw = exe.with_name("pythonw.exe")
        target, targs = str(pyw if pyw.exists() else exe), '"%s"' % (HERE / "vapor.pyw")
    lnk.parent.mkdir(parents=True, exist_ok=True)
    ps = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:V_LNK); $s.TargetPath = $env:V_TARGET; "
          "$s.Arguments = $env:V_ARGS; $s.WorkingDirectory = $env:V_DIR; $s.Description = 'Vapor'; $s.Save()")
    env = dict(os.environ, V_LNK=str(lnk), V_TARGET=target, V_ARGS=targs, V_DIR=str(HERE))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env, capture_output=True, timeout=20,
                   creationflags=0x08000000)
    if not lnk.exists():
        raise RuntimeError("could not create %s" % lnk)
    return "autostart on  (Vapor starts at every login)"


def cmd_reload(args):
    resp = try_send("refresh", [])
    if resp is None:
        return "Vapor is not running; it reads config.json when it starts"
    if not resp.get("ok", True):
        raise RuntimeError(resp.get("text") or "Vapor refused the reload")
    return resp.get("text") or "config re-read"


def _wall_get():
    import ctypes
    buf = ctypes.create_unicode_buffer(520)
    ctypes.windll.user32.SystemParametersInfoW(0x0073, 520, buf, 0)           # SPI_GETDESKWALLPAPER
    return buf.value


def _wall_set(path):
    import ctypes
    if not ctypes.windll.user32.SystemParametersInfoW(0x0014, 0, str(path), 3):   # SPI_SETDESKWALLPAPER, update + broadcast
        raise OSError("Windows refused the wallpaper")


def _wall_pick(folder, cur, mode):
    files = sorted(p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in IMG_EXT)
    if not files:
        raise RuntimeError("no images in %s" % folder)
    names = [str(p).lower() for p in files]
    if mode == "random":
        return random.choice([p for p in files if str(p).lower() != cur.lower()] or files)
    if cur.lower() not in names:
        return files[0] if mode == "next" else files[-1]
    return files[(names.index(cur.lower()) + (1 if mode == "next" else -1)) % len(files)]


def cmd_wallpaper(args):
    if os.name != "nt":
        raise RuntimeError("wallpaper is Windows only")
    cfgdir = read_json(CONFIG_FILE, {}).get("wallpaperDir", "")
    a = args[0].lower() if args else ""
    cur = _wall_get()
    if not a:
        return "wallpaper  %s%s" % (cur or "(none)", "\nfolder     %s" % cfgdir if cfgdir else "")
    if a == "dir":
        if len(args) < 2:
            return "wallpaper folder: %s" % (cfgdir or "not set  (vaporctl wallpaper dir <folder>)")
        f = Path(" ".join(args[1:])).expanduser()
        if not f.is_dir():
            raise RuntimeError("not a folder: %s" % f)
        config_update(wallpaperDir=str(f.resolve()))
        return "wallpaper folder set: %s" % f.resolve()
    if a in ("next", "prev", "previous", "random"):
        folder = " ".join(args[1:]) or cfgdir or (str(Path(cur).parent) if cur and Path(cur).exists() else "")
        if not folder or not Path(folder).is_dir():
            raise RuntimeError("which folder?  vaporctl wallpaper dir <folder>")
        pick = _wall_pick(folder, cur, "prev" if a.startswith("prev") else a)
    else:
        pick = Path(" ".join(args)).expanduser().resolve()
        if not pick.is_file() or pick.suffix.lower() not in IMG_EXT:
            raise RuntimeError("not an image file: %s" % pick)
    _wall_set(pick)
    apply_live("refresh")
    return "wallpaper set: %s" % pick.name


def cmd_config(args):
    """config get [key] / set <key> <value> / unset <key>: edit config.json without opening it."""
    sub = args[0].lower()
    d = read_json(CONFIG_FILE, {})
    if sub == "get":
        if len(args) == 1:
            return json.dumps(d, indent=2) if d else "{}   (config.json is empty or missing)"
        if args[1] not in d:
            raise RuntimeError("no key '%s' in config.json  (keys: %s)" % (args[1], ", ".join(sorted(d)) or "none"))
        v = d[args[1]]
        return v if isinstance(v, str) else json.dumps(v)
    if len(args) < 2:
        raise RuntimeError("config get [key] | set <key> <value> | unset <key>")
    key = args[1]
    if sub == "set":
        if len(args) < 3:
            raise RuntimeError("config set <key> <value>   (value: text, a number, true/false or JSON)")
        try:
            val = json.loads(" ".join(args[2:]))
        except ValueError:
            val = " ".join(args[2:])
        text = "%s = %s" % (key, json.dumps(val))
    else:
        val, text = None, "%s removed" % key
    config_update(**{key: val})
    return text + ("" if apply_live("refresh") else "   (saved; Vapor is not running, it reads it on the next start)")


def main(argv):
    raw = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if not argv or argv[0] in ("help", "-h", "--help", "/?"):
        print(HELP)
        return
    cmd, args = argv[0].lower(), argv[1:]

    if cmd in ("--version", "-v", "-V", "version"):
        text = "Vapor v%s" % VERSION
        print(json.dumps({"ok": True, "text": text}) if raw else text)
        return
    if cmd in ("update", "upgrade"):
        try:
            text = cmd_update(args)
        except (RuntimeError, OSError) as e:
            die(str(e))
        print(json.dumps({"ok": True, "text": text}) if raw else text)
        return

    # ---- commands that don't need Vapor to be running
    if cmd == "fetch":
        tty = sys.stdout.isatty() and not raw          # --json / pipes get the plain text card, no logo
        text = cmd_fetch(logo=tty, color=tty and _ansi_ok())
        print(json.dumps({"ok": True, "text": text}) if raw else text)
        return
    if cmd == "doctor":
        text, ok = cmd_doctor(args)
        print(json.dumps({"ok": ok, "text": text}) if raw else text)
        sys.exit(0 if ok else 1)
    if cmd == "config" and args and args[0].lower() in ("get", "set", "unset"):
        try:
            text = cmd_config(args)
        except (RuntimeError, ValueError, OSError) as e:
            die(str(e))
        print(json.dumps({"ok": True, "text": text}) if raw else text)
        return
    if cmd in ("autostart", "reload", "wallpaper"):
        try:
            text = {"autostart": cmd_autostart, "reload": cmd_reload, "wallpaper": cmd_wallpaper}[cmd](args)
        except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as e:
            die(str(e))
        print(json.dumps({"ok": True, "text": text}) if raw else text)
        return
    if cmd == "log":
        n = int(args[0]) if args else 40
        try:
            lines = (DATA / "vapor.log").read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            die("no log yet: %s" % (DATA / "vapor.log"))
        print("\n".join(lines[-n:]))
        return
    if cmd == "paths":
        for k, v in (("config", HERE / "config.json"), ("files", HERE / "files"), ("ringtone", HERE / "files" / "ringtone.mp3"),
                     ("log", DATA / "vapor.log"), ("settings", DATA / "settings.json")):
            print("%-9s %s%s" % (k, v, "" if v.exists() else "   (missing)"))
        return
    if cmd in ("config", "files"):
        target = HERE / "config.json" if cmd == "config" else HERE / "files"
        if not target.exists() and cmd == "files":
            target.mkdir(exist_ok=True)
        try:
            os.startfile(str(target))
        except (OSError, AttributeError):
            print(target)
        return

    if cmd == "start":
        try:
            print(start_vapor())
        except RuntimeError as e:
            die(str(e))
        return
    if cmd in ("stop", "quit"):
        force = "--force" in args
        try:
            print(stop_vapor(force))
        except RuntimeError as e:
            die(str(e))
        return

    if cmd in ("setname", "pfp", "set", "location", "ringtone", "reminders", "reminder", "remainders", "remainder", "reminds", "note", "notes"):
        try:
            if cmd == "set":
                what = args[0].lower() if args else ""
                fn = {"name": cmd_setname, "pfp": cmd_pfp, "picture": cmd_pfp, "location": cmd_location}.get(what)
                if not fn:
                    raise RuntimeError("set name|pfp|location ...")
                text = fn(args[1:])
            else:
                text = {"setname": cmd_setname, "pfp": cmd_pfp, "location": cmd_location, "note": cmd_note,
                        "notes": cmd_note, "ringtone": cmd_ringtone}.get(cmd, cmd_reminders)(args)
            print(json.dumps({"ok": True, "text": text}) if raw else text)
        except (RuntimeError, ValueError, OSError) as e:
            die(str(e))
        return

    # ---- client-side parsing for the time-based commands
    try:
        if cmd == "timer" and args and args[0].lower() != "cancel":
            args = [str(parse_duration(args[0]))]
        elif cmd == "remind":
            every = "none"
            if "--every" in args:
                i = args.index("--every")
                every = args[i + 1].lower() if i + 1 < len(args) else ""
                if every not in ("daily", "weekly", "monthly"):
                    raise ValueError("--every takes daily, weekly or monthly")
                del args[i:i + 2]
            if len(args) < 2:
                raise ValueError('usage: remind <when> "text" [--every daily|weekly|monthly]')
            args = [json.dumps({"ts": parse_when(args[0]), "t": " ".join(args[1:]), "rep": every})]
        elif cmd == "timer" and not args:
            raise ValueError("usage: timer <5m|1h30m|90|cancel>")
    except ValueError as e:
        die(str(e), 2)

    try:
        resp = send(cmd, args)
    except NotRunning:
        try:
            resp = {"ok": True, "text": offline(cmd, args)}
        except (RuntimeError, ValueError, OSError) as e:
            resp = {"ok": False, "text": str(e)}
        except Exception as e:                       # e.g. a COM error from the audio device
            resp = {"ok": False, "text": "%s: %s" % (type(e).__name__, e)}
    if raw:
        print(json.dumps(resp))
    else:
        print(resp.get("text", ""), file=sys.stdout if resp.get("ok") else sys.stderr)
    sys.exit(0 if resp.get("ok") else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
