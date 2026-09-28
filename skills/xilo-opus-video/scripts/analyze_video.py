#!/usr/bin/env python3
"""Inspect a video: metadata, shot-change timestamps, an evenly spaced contact sheet
and optional single frames. Works for reference videos and for checking your own render.

  analyze_video.py ref.mp4 --out source/ref            # sheet + scenes + info
  analyze_video.py out/final.mp4 --out qa/final --cells 30
  analyze_video.py ref.mp4 --out source/ref --frames 1.5 4 9.2   # also export these seconds as PNG
  analyze_video.py out/final.mp4 --out qa/phone --cells 15 --cell-width 360   # phone-size readability test

Writes <out>-sheet.png, <out>-info.txt and prints the same summary.
The contact sheet is read left-to-right, top-to-bottom; cell k is at k * step seconds.
"""
import argparse, json, pathlib, re, subprocess


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video"); ap.add_argument("--out", required=True, help="output prefix, e.g. source/ref")
    ap.add_argument("--cells", type=int, default=20, help="frames in the contact sheet")
    ap.add_argument("--scene", type=float, default=0.3, help="shot-change threshold (0-1)")
    ap.add_argument("--frames", type=float, nargs="*", default=[], help="seconds to export as full-size PNG")
    ap.add_argument("--cell-width", type=int, help="width of each sheet cell; 360 = phone test")
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)

    probe = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", a.video]).stdout)
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in probe["streams"])
    dur = float(probe["format"]["duration"])
    num, den = map(int, v["r_frame_rate"].split("/"))
    fps = num / den if den else 0

    cols = 5 if a.cells > 12 else 4
    rows = -(-a.cells // cols)
    step = dur / a.cells
    width = a.cell_width or 1600 // cols
    sheet = f"{out}-sheet.png"
    run(["ffmpeg", "-v", "error", "-y", "-i", a.video, "-vf", f"fps={a.cells}/{dur},scale={width}:-2,tile={cols}x{rows}", "-frames:v", "1", sheet])

    det = run(["ffmpeg", "-v", "info", "-i", a.video, "-vf", f"select='gt(scene,{a.scene})',showinfo", "-an", "-f", "null", "-"])
    cuts = [round(float(m), 2) for m in re.findall(r"pts_time:([\d.]+)", det.stderr)]

    for t in a.frames:
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", a.video, "-frames:v", "1", f"{out}-t{t:g}.png"])

    lines = [
        f"file: {a.video}",
        f"duration: {dur:.2f}s  size: {v['width']}x{v['height']}  fps: {fps:.2f}  audio: {'yes' if has_audio else 'no'}",
        f"contact sheet: {sheet} ({cols}x{rows}, one cell every {step:.2f}s)",
        f"shot changes ({len(cuts)}): {', '.join(map(str, cuts)) or 'none detected'}",
    ]
    if cuts:
        bounds = [0.0] + cuts + [dur]
        lens = [round(b - a_, 2) for a_, b in zip(bounds, bounds[1:])]
        lines.append(f"average shot length: {sum(lens) / len(lens):.2f}s")
    if a.frames:
        lines.append("frames: " + ", ".join(f"{out}-t{t:g}.png" for t in a.frames))
    text = "\n".join(lines)
    pathlib.Path(f"{out}-info.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
