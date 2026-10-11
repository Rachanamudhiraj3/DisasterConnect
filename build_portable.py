"""Build dist/DisasterWatch.zip -- a Windows package with Python and every
library bundled. The recipient just unzips and double-clicks START.bat;
nothing needs to be installed and no internet is needed.

Run this on Windows with the same Python version you develop with:
    python build_portable.py
Leaves out .env (your API key) and your local database.
"""
import os, shutil, subprocess, sys, urllib.request, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
PKG = os.path.join(DIST, "DisasterWatch")


def find_embed_url():
    """python.org only publishes an embeddable zip for some patch releases (e.g. no 3.11.10+),
    so try this Python's exact version first, then step down through older patches of the same
    minor version. Any patch of the same minor version is compatible with the libraries."""
    major, minor, patch = sys.version_info[:3]
    for p in range(patch, -1, -1):
        url = f"https://www.python.org/ftp/python/{major}.{minor}.{p}/python-{major}.{minor}.{p}-embed-amd64.zip"
        try:
            urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20).close()
            return url
        except Exception:
            continue
    sys.exit(f"No embeddable Python found for {major}.{minor}.x on python.org")


EMBED_URL = find_embed_url()
APP_DIRS = ["agents", "alerts", "backend", "config", "database", "frontend", "network", "sensors"]
APP_FILES = ["main.py", "requirements.txt", ".env.example", "README.md"]

START_BAT = r"""@echo off
cd /d "%~dp0"
title Local Disaster Watch
if not exist .env if exist .env.example copy /y .env.example .env >nul
if not exist data mkdir data
echo Starting Local Disaster Watch at http://localhost:5000
echo Keep this window open while using the app. Close it to stop.
python\python.exe -m backend.server
pause
"""

shutil.rmtree(DIST, ignore_errors=True)
os.makedirs(PKG)

# 1. embeddable Python
zpath = os.path.join(DIST, "embed.zip")
print("Downloading", EMBED_URL)
urllib.request.urlretrieve(EMBED_URL, zpath)
with zipfile.ZipFile(zpath) as z:
    z.extractall(os.path.join(PKG, "python"))
os.remove(zpath)

# embedded Python ignores PYTHONPATH/cwd, so list the search paths explicitly
pth = [f for f in os.listdir(os.path.join(PKG, "python")) if f.endswith("._pth")][0]
stem = pth[:-5]
with open(os.path.join(PKG, "python", pth), "w") as f:
    f.write(f"{stem}.zip\n.\n..\\libs\n..\nimport site\n")

# 2. libraries (binary wheels only, installed into libs/)
subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--only-binary=:all:",
                       "--target", os.path.join(PKG, "libs"), "-r", os.path.join(ROOT, "requirements.txt")])

# 3. app code
for d in APP_DIRS:
    shutil.copytree(os.path.join(ROOT, d), os.path.join(PKG, d),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
for f in APP_FILES:
    shutil.copy(os.path.join(ROOT, f), PKG)
os.makedirs(os.path.join(PKG, "data"))
shutil.copy(os.path.join(ROOT, "data", "earthquake_catalog.json"), os.path.join(PKG, "data"))
with open(os.path.join(PKG, "START.bat"), "w", newline="\r\n") as f:
    f.write(START_BAT)

# 4. zip
out = os.path.join(DIST, "DisasterWatch.zip")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for base, _, files in os.walk(PKG):
        for f in files:
            p = os.path.join(base, f)
            z.write(p, os.path.join("DisasterWatch", os.path.relpath(p, PKG)))
print("Created", out, "(%.0f MB)" % (os.path.getsize(out) / 1e6))
 