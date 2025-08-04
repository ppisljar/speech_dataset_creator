#!/usr/bin/env python3
import argparse
import re
import subprocess
from pathlib import Path
from typing import List, Tuple

# ----------------------------
# Parameters you might tweak
# ----------------------------
MAX_SEG_SEC = 60 * 60           # 60 minutes
MIN_SEG_SEC = 55 * 60           # 55 minutes
SILENCE_DB = -35                # threshold in dB for silencedetect (e.g., -30 to -40 is common)
SILENCE_MIN_LEN = 1           # seconds of continuous silence to count as "long"
REENCODE = True                 # True = re-encode; False = stream copy (-c copy)
LAME_QUALITY = "2"              # -q:a 2 is good VBR quality if re-encoding

# New policy parameters
MIN_CUT_SILENCE_SEC = 0.100     # require at least 100 ms silence to cut on
EXPANSION_SEC = 5 * 60          # expand the target window by +5 minutes if needed

RE_SILENCE_START = re.compile(r"silence_start:\s*([0-9.]+)")
RE_SILENCE_END = re.compile(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)")

def run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)

def ffprobe_duration(infile: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(infile)
    ]
    cp = run(cmd)
    return float(cp.stdout.strip())

def find_silences(infile: Path, silence_db: int, min_len: float) -> List[Tuple[float, float, float]]:
    af = f"silencedetect=noise={silence_db}dB:d={min_len}"
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(infile), "-af", af, "-f", "null", "-"]
    cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    silences = []
    current_start = None
    for line in cp.stderr.splitlines():
        m1 = RE_SILENCE_START.search(line)
        if m1:
            current_start = float(m1.group(1))
            continue
        m2 = RE_SILENCE_END.search(line)
        if m2 and current_start is not None:
            end = float(m2.group(1))
            duration = float(m2.group(2))
            silences.append((current_start, end, duration))
            current_start = None
    return silences

def choose_cut_points(duration: float, silences: List[Tuple[float, float, float]]) -> List[Tuple[float, float]]:
    cuts = []
    start = 0.0
    seg_idx = 1
    while start < duration:
        remaining = duration - start
        if remaining <= MAX_SEG_SEC:
            cuts.append((start, duration))
            break
        window_min = start + MIN_SEG_SEC
        window_max = start + MAX_SEG_SEC
        def best_silence(lo: float, hi: float):
            cands = [t for t in silences if lo <= t[0] <= hi and t[2] >= MIN_CUT_SILENCE_SEC]
            if not cands:
                return None
            return max(cands, key=lambda t: t[2])
        chosen = best_silence(window_min, window_max)
        if chosen is None:
            exp_hi = min(window_max + EXPANSION_SEC, duration)
            chosen = best_silence(window_min, exp_hi)
            if chosen is None:
                raise SystemExit(
                    f"No adequate silence found for segment {seg_idx} "
                    f"in window [{sec_to_hms(window_min)} – {sec_to_hms(exp_hi)}]."
                )
        cut_point = chosen[0]
        end = min(cut_point, duration)
        if end - start < 1.0:
            end = min(start + MAX_SEG_SEC, duration)
        cuts.append((start, end))
        start = end
        seg_idx += 1
    return cuts

def sec_to_hms(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec - (h * 3600 + m * 60)
    return f"{h:02d}:{m:02d}:{s:06.3f}"

def split_with_ffmpeg(infile: Path, segments: List[Tuple[float, float]], outdir: Path, ext: str):
    outdir.mkdir(parents=True, exist_ok=True)
    base = infile.stem
    for idx, (start, end) in enumerate(segments, start=1):
        outpath = outdir / f"{base}_{idx:02d}.{ext}"
        ss = sec_to_hms(start)
        to = sec_to_hms(end)
        codec = "libmp3lame" if ext == "mp3" else "pcm_s16le"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-i", str(infile),
            "-ss", ss, "-to", to,
            "-vn", "-c:a", codec,
        ]
        if ext == "mp3":
            cmd += ["-q:a", LAME_QUALITY]
        cmd.append(str(outpath))
        print(f"[ffmpeg] Writing {outpath.name}  ({ss} → {to})")
        subprocess.run(cmd, check=True)

def main():
    parser = argparse.ArgumentParser(description="Split an audio file (mp3 or wav) into 55–60 minute chunks, cutting at long silences when possible.")
    parser.add_argument("input", type=Path, help="Path to input .mp3 or .wav file")
    parser.add_argument("--outdir", type=Path, default=Path("out"), help="Output directory (default: ./out)")
    parser.add_argument("--silence-db", type=int, default=SILENCE_DB, help="Silence threshold in dB")
    parser.add_argument("--silence-min", type=float, default=SILENCE_MIN_LEN, help="Minimum silence length in seconds")
    parser.add_argument("--min-minutes", type=int, default=55, help="Minimum segment length in minutes")
    parser.add_argument("--max-minutes", type=int, default=60, help="Maximum segment length in minutes")
    args = parser.parse_args()
    infile: Path = args.input
    if not infile.exists():
        raise SystemExit(f"Input file not found: {infile}")
    global MIN_SEG_SEC, MAX_SEG_SEC
    MIN_SEG_SEC = args.min_minutes * 60
    MAX_SEG_SEC = args.max_minutes * 60
    duration = ffprobe_duration(infile)
    print(f"[info] Duration: {duration/60:.2f} minutes")
    print(f"[info] Detecting silences...")
    silences = find_silences(infile, args.silence_db, args.silence_min)
    print(f"[info] Found {len(silences)} silences")
    print(f"[info] Choosing cut points...")
    segments = choose_cut_points(duration, silences)
    print(f"[info] Splitting into {len(segments)} file(s) → {args.outdir}/")
    ext = infile.suffix.lower().lstrip('.')
    split_with_ffmpeg(infile, segments, args.outdir, ext)
    print("[done] Splitting complete.")

if __name__ == "__main__":
    main()
