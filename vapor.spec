# PyInstaller spec for Vapor.   Build with:  pyinstaller --noconfirm --clean vapor.spec    (or just run build.ps1)
# Put this file in the same folder as vapor.pyw, Vapor.qml (+ all other .qml), cc_backend.py and vaporctl.py.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH)

# ---------------------------------------------------------------- your own files that ship inside the bundle
SKIP_DIRS = {"build", "dist", ".git", ".github", "__pycache__", "files", ".venv", "venv", "env"}
ASSET_EXT = {".qml", ".js", ".mjs", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
             ".ttf", ".otf", ".woff", ".woff2", ".mp3", ".wav", ".ogg", ".frag", ".vert", ".qsb"}
datas = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
    for fn in filenames:
        if Path(fn).suffix.lower() in ASSET_EXT or fn == "qmldir":
            src = Path(dirpath) / fn
            rel = src.parent.relative_to(ROOT)
            datas.append((str(src), "." if str(rel) == "." else str(rel)))

# ---------------------------------------------------------------- PySide6 / Qt Quick
# QML pulls in Qt modules by name (import QtQuick.Controls ...) which PyInstaller cannot see from the Python code,
# so take all of PySide6 and drop the big parts a bar never uses.
DENY = [
    "pyside6-", "webengine", "qt3d", "qt63d", "quick3d", "designer", "datavisualization", "charts", "qtgraphs",
    "qt6graphs", "pdf", "sensors", "qtnfc", "qt6nfc", "serialport", "serialbus", "remoteobjects", "scxml",
    "virtualkeyboard", "quicktest", "qmlls", "qmllint", "qmlformat", "qmlcachegen", "qmltyperegistrar",
    "linguist", "assistant", "lupdate", "lrelease", "/translations/", "/metatypes/", "/typesystems/",
    "/glue/", "/include/", ".pyi",
]
def _keep(entry):
    text = (str(entry[0]) + "|" + str(entry[1])).replace("\\", "/").lower()
    return not any(d in text for d in DENY)

ps_datas, ps_bins, _ps_hidden = collect_all("PySide6")
ps_datas = [e for e in ps_datas if _keep(e)]
ps_bins = [e for e in ps_bins if _keep(e)]

hidden = ["cc_backend",
          "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6.QtQml", "PySide6.QtQuick",
          "PySide6.QtQuickControls2", "PySide6.QtQuickWidgets", "PySide6.QtNetwork", "PySide6.QtOpenGL",
          "PySide6.QtSvg", "PySide6.QtMultimedia"]
# packages that are imported lazily / use native pieces PyInstaller can miss
for pkg in ("winrt", "winsdk", "comtypes", "pycaw", "pyaudiowpatch", "PIL"):
    try:
        hidden += collect_submodules(pkg)
    except Exception:
        pass

a = Analysis(
    ["vapor.pyw"],
    pathex=[str(ROOT)],
    binaries=ps_bins,
    datas=datas + ps_datas,
    hiddenimports=hidden,
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "matplotlib", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

ICON = str(ROOT / "vapor.ico") if (ROOT / "vapor.ico").exists() else None
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Vapor",
    console=False,          # no console window (same as pythonw)
    icon=ICON,
    upx=False,              # UPX makes antivirus false positives much more likely
)
coll = COLLECT(exe, a.binaries, a.datas, name="Vapor", upx=False)

# ---------------------------------------------------------------- vaporctl.exe (the command line tool), only if vaporctl.py exists
if (ROOT / "vaporctl.py").exists():
    b = Analysis(["vaporctl.py"], pathex=[str(ROOT)],
                 excludes=["PySide6", "PIL", "numpy", "tkinter", "PyQt5", "PyQt6"])
    bpyz = PYZ(b.pure)
    EXE(bpyz, b.scripts, b.binaries, b.datas, [], name="vaporctl", console=True, icon=ICON, upx=False)
