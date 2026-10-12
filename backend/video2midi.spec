# Build from backend/:  pyinstaller video2midi.spec   (needs frontend/dist built first)
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("../frontend/dist", "frontend_dist")]
binaries, hiddenimports = [], collect_submodules("uvicorn") + ["multipart", "python_multipart"]
for pkg in ("yt_dlp", "cv2"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(["launcher.py"], pathex=["."], datas=datas, binaries=binaries, hiddenimports=hiddenimports)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="video2midi", console=True, upx=False)
