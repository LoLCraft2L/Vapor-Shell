#!/usr/bin/env python3
"""vaporctl - command line for the running Vapor shell (stdlib only, starts instantly).

Usage:  python vaporctl.py <command> [args]      (or add this folder to PATH and use vaporctl.cmd)
Run with no arguments, or `help`, for the command list.

Works whether or not Vapor is running: `start` launches it, and volume / mute / media / notify / timer / remind / layout /
log / paths fall back to doing the job directly when the shell is down.
"""
import datetime
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("LOCALAPPDATA", str(HERE))) / "vapor"
CLI_FILE = DATA / "cli.json"

HELP = """vaporctl - control the running Vapor shell

  status                      volume, battery, wifi, media, workspace, layout, bar state
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
  start                       start Vapor (does nothing if it already runs)
  restart | quit | stop       restart or close Vapor  (stop --force kills a hung copy)

  log [N]                     last N lines of vapor.log (default 40)
  paths                       where config, files, log and settings live
  config | files              open config.json / the files folder
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
    exe = Path(sys.executable)
    pyw = exe.with_name("pythonw.exe")
    subprocess.Popen([str(pyw if pyw.exists() else exe), str(HERE / "vapor.pyw")], cwd=str(HERE),
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


def main(argv):
    raw = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if not argv or argv[0] in ("help", "-h", "--help", "/?"):
        print(HELP)
        return
    cmd, args = argv[0].lower(), argv[1:]

    # ---- commands that don't need Vapor to be running
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
