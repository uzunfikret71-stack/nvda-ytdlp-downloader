"""Build CI packages using checksum-pinned binaries from an existing release."""
import ast
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
MEDIA = ROOT.name == "nvdaMediaConverter"
# Repository checkout names may differ on runners: detect the build metadata instead.
MEDIA = (ROOT / "buildVars.py").exists()
if MEDIA:
    sys.path.insert(0, str(ROOT))
    from buildVars import addon_info
    version = addon_info["version"]
    url = "https://github.com/uzunfikret71-stack/nvdaMediaConverter/releases/download/v1.0.5/mediaConverter-1.0.5.nvda-addon"
    expected = "a06d6c93d6e6e7477929f501e602d97c07a1ba5df0a05a68a3a315700e5a21ce"
    required = {"ffmpeg.exe", "ffprobe.exe"}
else:
    manifest = (ROOT / "manifest.ini").read_text(encoding="utf-8")
    version = re.search(r"^version\s*=\s*(.+)$", manifest, re.M)[1].strip().strip('"')
    url = "https://github.com/uzunfikret71-stack/nvda-ytdlp-downloader/releases/download/v1.2.4/Video-ve-Ses-Indirici-1.2.4.nvda-addon"
    expected = "93de7c41b74346128d7da2724f231b2a0c7fe5f1713a09642977cf2f121ec9a6"
    required = {"ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe", "deno.exe"}
if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", version):
    raise ValueError("Invalid manifest version")
if os.environ.get("GITHUB_REF_TYPE") == "tag":
    if os.environ["GITHUB_REF_NAME"] != "v" + version:
        raise ValueError("Tag must match manifest version: v" + version)
for source in (ROOT / "globalPlugins").rglob("*.py"):
    ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
with tempfile.TemporaryDirectory() as temporary:
    package = Path(temporary) / "dependencies.zip"
    request = urllib.request.Request(url, headers={"User-Agent": "NVDA-addon-build"})
    with urllib.request.urlopen(request, timeout=120) as response, package.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    with package.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
            raise ValueError("Dependency package SHA-256 mismatch")
    with zipfile.ZipFile(package) as archive:
        for name in required:
            destination = ROOT / "bin" / name
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes(archive.read("bin/" + name))
if MEDIA:
    subprocess.run([sys.executable, "build.py"], check=True)
else:
    output = ROOT / "output" / f"ytdlpDownloader-{version}.nvda-addon"
    output.parent.mkdir(exist_ok=True)
    files = [ROOT / "manifest.ini", ROOT / "LICENSE.txt", ROOT / "THIRD_PARTY_NOTICES.md"]
    for directory in ("globalPlugins", "thirdPartyLicenses", "bin"):
        files.extend(p for p in (ROOT / directory).rglob("*") if p.is_file() and p.suffix in {".py", ".txt", ".exe"})
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert "manifest.ini" in archive.namelist()
    with output.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    output.with_suffix(".nvda-addon.sha256").write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(f"Built and checked: {output.name}")
