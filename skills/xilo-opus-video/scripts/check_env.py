#!/usr/bin/env python3
"""Check the tools this skill needs and say how to install what is missing."""
import importlib.util, shutil, subprocess, sys

ok = True


def report(name, good, fix=""):
    global ok
    ok &= good
    print(f"[{'ok' if good else 'missing'}] {name}" + ("" if good else f"  ->  {fix}"))


report("python3 >= 3.9", sys.version_info >= (3, 9), "install Python 3.9+")
report("ffmpeg", bool(shutil.which("ffmpeg")), "macOS: brew install ffmpeg | Windows: winget install ffmpeg | Linux: apt install ffmpeg")
report("ffprobe", bool(shutil.which("ffprobe")), "comes with ffmpeg")
report("numpy (audio synthesis)", importlib.util.find_spec("numpy") is not None, "python3 -m pip install numpy")
has_pw = importlib.util.find_spec("playwright") is not None
report("playwright (python)", has_pw, "python3 -m pip install playwright")

if has_pw:
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
    from render import GPU_ARGS                      # same flags the renderer uses
    from playwright.sync_api import sync_playwright
    browser_ok, webgl, skipped = False, False, []
    with sync_playwright() as p:
        for kw in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
            name = kw.get("channel", "playwright chromium")
            try:
                b = p.chromium.launch(headless=True, args=GPU_ARGS, **kw)
            except Exception:
                skipped.append(name); continue
            pg = b.new_page()
            pg.set_content("<canvas id=c></canvas>")
            webgl = pg.evaluate("!!document.getElementById('c').getContext('webgl2')")
            if skipped:
                print(f"[info] not available: {', '.join(skipped)} -> using {name}")
            print(f"[ok] browser: {name} {b.version}, WebGL2: {'yes' if webgl else 'no'}")
            b.close(); browser_ok = True
            break
    report("headless browser", browser_ok, "python3 -m playwright install chromium   (or install Google Chrome)")
    if browser_ok and not webgl:
        print("  note: WebGL2 unavailable, shader and three.js plans will fall back to Canvas 2D")

try:
    subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout.index("chromakey")
    print("[ok] ffmpeg chromakey (green-screen compositing)")
except ValueError:
    print("[warn] ffmpeg has no chromakey filter; green-screen plans need a fuller ffmpeg build")

print("\nready" if ok else "\nsome tools are missing, see above")
sys.exit(0 if ok else 1)
