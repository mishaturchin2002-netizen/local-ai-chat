"""Create a self-contained Python runtime for Local AI Chat inside .\\runtime."""
import os
import pathlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
RUNTIME = ROOT / "runtime"
TMP = ROOT / ".downloads"
TMP.mkdir(exist_ok=True)

ZIP_URL = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
GETPIP_URL = "https://bootstrap.pypa.io/get-pip.py"


def download(url: str, dest: pathlib.Path) -> pathlib.Path:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"cached: {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
        return dest
    print(f"downloading {url} ...")
    with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    print(f"  -> {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
    return dest


def main() -> int:
    zip_path = download(ZIP_URL, TMP / "python-embed.zip")
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)
    RUNTIME.mkdir(parents=True)
    print("extracting runtime ...")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(RUNTIME)

    # enable site-packages in the embeddable distribution
    pth = next(RUNTIME.glob("python*._pth"))
    pth.write_text(
        "python312.zip\n.\nLib\\site-packages\nimport site\n", encoding="utf-8"
    )
    (RUNTIME / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)
    print(f"patched {pth.name}")

    getpip = download(GETPIP_URL, TMP / "get-pip.py")
    py = RUNTIME / "python.exe"
    print("installing pip ...")
    rc = subprocess.call([str(py), str(getpip), "--no-warn-script-location"])
    print(f"get-pip exit: {rc}")
    print("pip check:", subprocess.call([str(py), "-m", "pip", "--version"]))

    print("version:", subprocess.run([str(py), "-c", "import sys;print(sys.version)"],
                                     capture_output=True, text=True).stdout.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
