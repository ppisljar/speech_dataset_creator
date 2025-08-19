#!/usr/bin/env python3
"""
Build a transcript and per-speaker clips from a Soniox-like JSON (tokens) and an input audio (.mp3 or .wav).

This script can be used in two modes:

1. Compute mode: Analyze tokens and compute segments, saving to JSON
   python m6_segment.py compute tokens.json input.wav --outfile segments.json

2. Generate mode: Generate audio files from computed segments
   python m6_segment.py generate segments.json input.wav --outdir out/

3. Legacy mode: Do both operations in sequence (backward compatibility)
   python m6_segment.py tokens.json input.wav

Outputs (in generate mode):
- out/speakers/<spk>/clipN.wav       (WAV audio for each segment)
- out/speakers/<spk>/clipN.txt       (text for the segment)

Segmentation rules:
- Segments are single-speaker, 1–25 seconds.
- Prefer to end at sentence boundaries (., !, ?), else comma, else longest silence by token gap.
- Use global audio **silence detection** once for the whole file and reuse results.
- While splitting at a sentence end or comma, locate the **longest silence** in the token gap
  (current token end → next token start). If a silence with ≥100 ms duration exists in this gap,
  set end boundary to (silence_start + 50 ms) and the next start to (silence_end - 50 ms),
  ensuring both segments have silence at their edges.
- For each segment, verify:
  - Start has ≥20 ms silence; if not, pad +50 ms at start when exporting.
  - End has ≥50 ms silence; if not, pad +50 ms at end when exporting (unless boundary shifted by the gap rule).

Confidence filename prefixes based on the **minimum** token confidence in the segment:
- < 0.5  → "___"
- < 0.8  → "__"
- < 0.9  → "_"
- ≥ 0.9 → "" (no prefix)

Requirements:
  - ffmpeg on PATH
"""

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import List, Tuple, Optional
import pandas as pd

# ----------------------------
# Tunables_PUNT 
# ----------------------------
MIN_SEG_SEC = 1.0
MAX_SEG_SEC = 25.0
SENT_PUNCT = {".", "!", "?"}
COMMA = ","

# Global silence detection
SILENCE_DB = -35                 # dB threshold for silence detection
MIN_SILENCE_SEC = 0.02           # 20 ms; we detect once for full file

# Boundary guarantees
REQUIRED_SIL_START_MS = 20       # must have ≥20 ms silence at beginning
REQUIRED_SIL_END_MS = 50         # must have ≥50 ms silence at end
GAP_SPLIT_MIN_MS = 100           # if using a gap silence, require ≥100 ms duration
EDGE_OFFSET_MS = 50              # use ±50 ms inside that gap silence for boundaries

# Optional export settings
EXPORT_RATE = 16000              # set to None to keep original

# ----------------------------
# Structures
# ----------------------------
@dataclass
class Token:
    text: str
    start_ms: int
    end_ms: int
    confidence: float
    speaker: str

@dataclass
class Sentence:
    speaker: str
    text: str
    start_ms: int
    end_ms: int

@dataclass
class Segment:
    speaker: str
    text: str
    start_ms: int
    end_ms: int
    min_conf: float
    pad_start_ms: int = 0
    pad_end_ms: int = 0

@dataclass
class PyannoteEntry:
    speaker: str
    start_ms: int
    end_ms: int
    duration_ms: int

@dataclass
class PyannoteEntry:
    speaker: str
    start_ms: int
    end_ms: int
    duration_ms: int

# ----------------------------
# Token utilities
# ----------------------------
_space_before_punct = re.compile(r"\s+([,.;:!?])")
_multi_space = re.compile(r"[ \t]+")

def load_tokens(json_path: Path) -> List[Token]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    toks: List[Token] = []
    for t in data.get("tokens", []):
        if t.get("text") is None or t.get("is_audio_event"):
            continue
        toks.append(
            Token(
                text=str(t["text"]),
                start_ms=int(t["start_ms"]),
                end_ms=int(t["end_ms"]),
                confidence=float(t.get("confidence", 1.0)),
                speaker=str(t.get("speaker") or ""),
            )
        )
    toks.sort(key=lambda x: (x.start_ms, x.end_ms))
    return toks

def detokenize_text(tokens: List[Token]) -> str:
    raw = "".join(t.text for t in tokens)
    # Remove spaces before punctuation by using a function (avoids backrefs in editor replacements)
    s = _space_before_punct.sub(lambda m: m.group(1), raw)
    s = _multi_space.sub(" ", s).strip()
    return s

def token_has_sentence_end(tok: Token) -> bool:
    return any(p in tok.text for p in SENT_PUNCT)

def token_has_comma(tok: Token) -> bool:
    return COMMA in tok.text

# ----------------------------
# ffmpeg helpers
# ----------------------------
RE_SILENCE_START = re.compile(r"silence_start:\s*([0-9.]+)")
RE_SILENCE_END = re.compile(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)")

Sil = Tuple[int, int, int]  # start_ms, end_ms, dur_ms


def detect_silences_full(audio: Path, noise_db: int = SILENCE_DB, min_sil_sec: float = MIN_SILENCE_SEC) -> List[Sil]:
    """Run a single global silencedetect over the entire file."""
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats",
        "-i", str(audio),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_sil_sec}",
        "-f", "null", "-",
    ]
    cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    sils: List[Sil] = []
    cur: Optional[float] = None
    for line in cp.stderr.splitlines():
        m1 = RE_SILENCE_START.search(line)
        if m1:
            cur = float(m1.group(1))
            continue
        m2 = RE_SILENCE_END.search(line)
        if m2 and cur is not None:
            end = float(m2.group(1))
            dur = float(m2.group(2))
            sils.append((int(round(cur * 1000)), int(round(end * 1000)), int(round(dur * 1000))))
            cur = None
    return sils


def silences_overlapping(silences: List[Sil], start_ms: int, end_ms: int) -> List[Sil]:
    out = []
    for s, e, d in silences:
        if s < end_ms and e > start_ms:  # overlap
            out.append((max(s, start_ms), min(e, end_ms), min(d, end_ms - start_ms)))
    return out


def silence_covering_point(silences: List[Sil], t_ms: int, require_ms: int) -> bool:
    for s, e, d in silences:
        if s <= t_ms <= e and (e - s) >= require_ms:
            return True
    return False


def longest_silence_in_range(silences: List[Sil], start_ms: int, end_ms: int) -> Optional[Sil]:
    best: Optional[Sil] = None
    for s, e, d in silences_overlapping(silences, start_ms, end_ms):
        dur = min(e, end_ms) - max(s, start_ms)
        cand = (max(s, start_ms), min(e, end_ms), dur)
        if dur <= 0:
            continue
        if best is None or cand[2] > best[2]:
            best = cand
    return best


def ffmpeg_extract(in_path: Path, start_ms: int, end_ms: int, out_wav: Path, pad_start_ms: int = 0, pad_end_ms: int = 0) -> None:
    """Extract [start_ms, end_ms) to a WAV file; optionally pad start/end with silence."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    ss = f"{start_ms/1000:.3f}"
    to = f"{end_ms/1000:.3f}"
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-ss", ss, "-to", to, "-i", str(in_path),
        "-vn", "-c:a", "pcm_s16le",
    ]
    if EXPORT_RATE:
        cmd += ["-ar", str(EXPORT_RATE)]
    filters = []
    if pad_start_ms > 0:
        filters.append(f"adelay={pad_start_ms}|{pad_start_ms}")
    if pad_end_ms > 0:
        filters.append(f"apad=pad_dur={pad_end_ms/1000:.3f}")
    if filters:
        cmd += ["-af", ",".join(filters)]
    cmd.append(str(out_wav))
    subprocess.run(cmd, check=True)

# ----------------------------
# Sentence building
# ----------------------------

def build_sentences(tokens: List[Token]) -> List[Sentence]:
    sentences: List[Sentence] = []
    if not tokens:
        return sentences

    cur_speaker = tokens[0].speaker
    cur_tokens: List[Token] = []

    def flush():
        nonlocal cur_tokens
        if not cur_tokens:
            return
        text = detokenize_text(cur_tokens)
        if text:
            sentences.append(
                Sentence(
                    speaker=cur_speaker,
                    text=text,
                    start_ms=cur_tokens[0].start_ms,
                    end_ms=cur_tokens[-1].end_ms,
                )
            )
        cur_tokens = []

    for i, tok in enumerate(tokens):
        if cur_tokens and tok.speaker != cur_speaker:
            flush()
            cur_speaker = tok.speaker
        cur_tokens.append(tok)
        if token_has_sentence_end(tok):
            flush()
            if i + 1 < len(tokens):
                cur_speaker = tokens[i + 1].speaker
    flush()
    return sentences

# ----------------------------
# Segmentation using tokens + global silences
# ----------------------------

def build_segments_single_speaker(run: List[Token], silences: List[Sil]) -> List[Segment]:
    segs: List[Segment] = []
    if not run:
        return segs

    i = 0
    while i < len(run):
        # Grow candidate window up to MAX_SEG_SEC
        j = i
        while j < len(run):
            dur = (run[j].end_ms - run[i].start_ms) / 1000.0
            if dur > MAX_SEG_SEC:
                break
            j += 1
            if j > i:
                last = run[j - 1]
                if dur >= MIN_SEG_SEC and token_has_sentence_end(last):
                    # only split at sentence punctuation
                    break

        if j == i:
            j = min(i + 1, len(run))

        candidate = run[i:j]
        # Default boundary from tokens
        end_idx = len(candidate) - 1
        end_tok = candidate[end_idx]
        next_tok = run[j] if j < len(run) else None

        # If splitting on punctuation and there is a next token, align boundary using gap silence
        if next_tok is not None and token_has_sentence_end(end_tok):
            gap_start = end_tok.end_ms
            gap_end = next_tok.start_ms
            if gap_end > gap_start:
                best = longest_silence_in_range(silences, gap_start, gap_end)
                if best and best[2] >= GAP_SPLIT_MIN_MS:
                    s_ms, e_ms, _ = best
                    end_boundary = s_ms + EDGE_OFFSET_MS
                    next_start = max(end_boundary + 1, e_ms - EDGE_OFFSET_MS)  # ensure increasing
                    # enforce monotonicity and limits
                    if next_start <= next_tok.start_ms:
                        candidate_end_ms = end_boundary
                        candidate_start_ms = candidate[0].start_ms
                        if (candidate_end_ms - candidate_start_ms) / 1000.0 >= MIN_SEG_SEC:
                            end_tok_end_ms = candidate[-1].end_ms
                            custom_end_ms = min(candidate_end_ms, end_tok_end_ms)
                            seg_tokens = candidate
                            text = detokenize_text(seg_tokens)
                            seg_min_conf = min(t.confidence for t in seg_tokens)
                            seg = Segment(
                                speaker=seg_tokens[0].speaker,
                                text=text,
                                start_ms=seg_tokens[0].start_ms,
                                end_ms=custom_end_ms,
                                min_conf=seg_min_conf,
                            )
                            segs.append(seg)
                            setattr(next_tok, "_start_override_ms", next_start)
                            i = j
                            continue

        # Otherwise, we didn't align via gap silence; choose end by sentence end -> longest token gap -> hard bound
        cut_idx = None
        for k in range(len(candidate) - 1, -1, -1):
            if token_has_sentence_end(candidate[k]):
                cut_idx = k
                break
        if cut_idx is None:
            # longest token gap inside candidate
            if len(candidate) >= 2:
                best_gap = -1
                best_k = 0
                for k in range(len(candidate) - 1):
                    gap = candidate[k + 1].start_ms - candidate[k].end_ms
                    if gap > best_gap:
                        best_gap = gap
                        best_k = k
                cut_idx = best_k
            else:
                cut_idx = 0

        seg_tokens = candidate[: cut_idx + 1]
        text = detokenize_text(seg_tokens)
        seg = Segment(
            speaker=seg_tokens[0].speaker,
            text=text,
            start_ms=getattr(seg_tokens[0], "_start_override_ms", seg_tokens[0].start_ms),
            end_ms=seg_tokens[-1].end_ms,
            min_conf=min(t.confidence for t in seg_tokens),
        )

        # Boundary silence guarantees using precomputed silences
        if not silence_covering_point(silences, seg.start_ms, REQUIRED_SIL_START_MS):
            seg.pad_start_ms = EDGE_OFFSET_MS
        if not silence_covering_point(silences, seg.end_ms, REQUIRED_SIL_END_MS):
            seg.pad_end_ms = max(seg.pad_end_ms, EDGE_OFFSET_MS)

        segs.append(seg)
        i = i + cut_idx + 1

    # Enforce max length by subdividing recursively if needed
    final: List[Segment] = []
    for s in segs:
        dur = (s.end_ms - s.start_ms) / 1000.0
        if dur <= MAX_SEG_SEC:
            final.append(s)
        else:
            mid = s.start_ms + int((MAX_SEG_SEC * 1000))
            left = Segment(s.speaker, s.text, s.start_ms, mid, s.min_conf, s.pad_start_ms, EDGE_OFFSET_MS)
            right = Segment(s.speaker, s.text, mid, s.end_ms, s.min_conf, EDGE_OFFSET_MS, s.pad_end_ms)
            final.extend([left, right])
    return final


def build_segments(tokens: List[Token], silences: List[Sil]) -> List[Segment]:
    segments: List[Segment] = []
    if not tokens:
        return segments
    # Group runs by speaker
    run: List[Token] = [tokens[0]]
    for t in tokens[1:]:
        if t.speaker == run[-1].speaker:
            run.append(t)
        else:
            segments.extend(build_segments_single_speaker(run, silences))
            run = [t]
    segments.extend(build_segments_single_speaker(run, silences))
    # Now, for each segment, split by comma into subsegments
    output_segments = []  # list of dicts: {main: Segment, subs: [Segment, ...]}
    for seg in segments:
        seg_tokens = [tok for tok in tokens if tok.speaker == seg.speaker and seg.start_ms <= tok.start_ms and tok.end_ms <= seg.end_ms]
        if not seg_tokens:
            if len(seg.text) > 1:
                output_segments.append({'main': seg, 'subs': []})
            else:
                # add this to previous segment as its a single char
                output_segments[-1]['main'].text += seg.text
            continue
        current = []
        starts = []
        ends = []
        subsegments = []
        for tok in seg_tokens:
            if not current:
                starts.append(tok.start_ms)
            current.append(tok)
            if token_has_comma(tok):
                ends.append(tok.end_ms)
                subseg_tokens = current[:]
                text = detokenize_text(subseg_tokens)
                min_conf = min(t.confidence for t in subseg_tokens)
                s_start = starts[-1]
                s_end = ends[-1]
                if s_end > s_start:
                    subsegments.append(Segment(seg.speaker, text, s_start, s_end, min_conf, seg.pad_start_ms, seg.pad_end_ms))
                current = []
        # Add any remaining tokens as last subsegment
        if current:
            s_start = starts[-1]
            s_end = current[-1].end_ms
            subseg_tokens = current[:]
            text = detokenize_text(subseg_tokens)
            min_conf = min(t.confidence for t in subseg_tokens)
            if s_end > s_start:
                subsegments.append(Segment(seg.speaker, text, s_start, s_end, min_conf, seg.pad_start_ms, seg.pad_end_ms))
        # Note: Silence alignment will happen after pyannote refinement
        # Just merge subsegments with no gaps for now
        merged_subsegments = merge_subsegments_with_no_gaps(subsegments)
        
        if len(seg.text) > 1:
            output_segments.append({'main': seg, 'subs': subsegments, 'subs_merged': merged_subsegments})
        else:
            # add this to previous segment as its a single char
            output_segments[-1]['main'].text += seg.text
    return output_segments


def find_silence_for_subsegment_start(silences: List[Sil], segment_start_ms: int) -> Optional[int]:
    """
    Find the appropriate silence boundary for subsegment start.
    Returns the end of the closest silence that covers or precedes the segment start.
    """
    best_silence_end = None
    
    for s_start, s_end, s_dur in silences:
        # Case 1: Silence covers the segment start point
        if s_start <= segment_start_ms <= s_end and s_dur >= 100:  # At least 100ms silence
            # Be more conservative: use the segment start itself if it's well within the silence,
            # otherwise use a point closer to the segment start
            if segment_start_ms - s_start >= 50:  # At least 50ms into the silence
                return segment_start_ms
            else:
                return max(s_start + 25, segment_start_ms - 25)  # Stay close to segment start
        
        # Case 2: Silence ended before segment start (but close to it)
        elif s_end <= segment_start_ms and (segment_start_ms - s_end) <= 200:  # Within 200ms
            if best_silence_end is None or s_end > best_silence_end:
                best_silence_end = s_end
    
    return best_silence_end


def find_silence_for_subsegment_end(silences: List[Sil], segment_end_ms: int) -> Optional[int]:
    """
    Find the appropriate silence boundary for subsegment end.
    Returns the start of the closest silence that covers or follows the segment end.
    """
    best_silence_start = None
    
    for s_start, s_end, s_dur in silences:
        # Case 1: Silence covers the segment end point
        if s_start <= segment_end_ms <= s_end and s_dur >= 100:  # At least 100ms silence
            # Be more conservative: use the segment end itself if it's well within the silence,
            # otherwise use a point closer to the segment end
            if s_end - segment_end_ms >= 50:  # At least 50ms remaining in the silence
                return segment_end_ms
            else:
                return min(s_end - 25, segment_end_ms + 25)  # Stay close to segment end
        
        # Case 2: Silence starts after segment end (but close to it)
        elif s_start >= segment_end_ms and (s_start - segment_end_ms) <= 200:  # Within 200ms
            if best_silence_start is None or s_start < best_silence_start:
                best_silence_start = s_start
    
    return best_silence_start


def align_subsegments_with_silences(subsegments: List[Segment], silences: List[Sil]) -> List[Segment]:
    """
    Align subsegments with silence boundaries according to the specified rules.
    Ensures that adjacent subsegments don't overlap by using shared silence boundaries.
    """
    if not subsegments:
        return subsegments
    
    if len(subsegments) == 1:
        # Single subsegment, align normally
        subseg = subsegments[0]
        aligned_start = find_silence_for_subsegment_start(silences, subseg.start_ms)
        aligned_end = find_silence_for_subsegment_end(silences, subseg.end_ms)
        
        new_start_ms = aligned_start if aligned_start is not None else subseg.start_ms
        new_end_ms = aligned_end if aligned_end is not None else subseg.end_ms
        
        if new_end_ms <= new_start_ms:
            new_end_ms = new_start_ms + 100
        
        return [Segment(
            speaker=subseg.speaker,
            text=subseg.text,
            start_ms=new_start_ms,
            end_ms=new_end_ms,
            min_conf=subseg.min_conf,
            pad_start_ms=subseg.pad_start_ms,
            pad_end_ms=subseg.pad_end_ms
        )]
    
    aligned_subsegments = []
    
    # First pass: align each subsegment independently
    for i, subseg in enumerate(subsegments):
        aligned_start = find_silence_for_subsegment_start(silences, subseg.start_ms)
        aligned_end = find_silence_for_subsegment_end(silences, subseg.end_ms)
        
        new_start_ms = aligned_start if aligned_start is not None else subseg.start_ms
        new_end_ms = aligned_end if aligned_end is not None else subseg.end_ms
        
        # Ensure start comes before end
        if new_end_ms <= new_start_ms:
            new_end_ms = new_start_ms + 100
        
        aligned_subseg = Segment(
            speaker=subseg.speaker,
            text=subseg.text,
            start_ms=new_start_ms,
            end_ms=new_end_ms,
            min_conf=subseg.min_conf,
            pad_start_ms=subseg.pad_start_ms,
            pad_end_ms=subseg.pad_end_ms
        )
        
        aligned_subsegments.append(aligned_subseg)
    
    # Second pass: fix overlaps by adjusting boundaries
    for i in range(len(aligned_subsegments) - 1):
        current = aligned_subsegments[i]
        next_seg = aligned_subsegments[i + 1]
        
        # Check for overlap
        if current.end_ms > next_seg.start_ms:
            # Find the silence boundary between the original subsegments
            orig_current = subsegments[i]
            orig_next = subsegments[i + 1]
            
            gap_start = orig_current.end_ms
            gap_end = orig_next.start_ms
            
            # Find the best silence in the gap
            best_silence = longest_silence_in_range(silences, gap_start, gap_end)
            
            if best_silence and best_silence[2] >= 50:  # At least 50ms silence
                # Split at the silence midpoint
                silence_start, silence_end, silence_dur = best_silence
                split_point = silence_start + (silence_dur // 2)
                
                print(f"Fixing overlap between subsegments {i} and {i+1}: splitting at {split_point} ms")
                
                # Update current segment end
                aligned_subsegments[i] = Segment(
                    speaker=current.speaker,
                    text=current.text,
                    start_ms=current.start_ms,
                    end_ms=split_point,
                    min_conf=current.min_conf,
                    pad_start_ms=current.pad_start_ms,
                    pad_end_ms=current.pad_end_ms
                )
                
                # Update next segment start
                aligned_subsegments[i + 1] = Segment(
                    speaker=next_seg.speaker,
                    text=next_seg.text,
                    start_ms=split_point,
                    end_ms=next_seg.end_ms,
                    min_conf=next_seg.min_conf,
                    pad_start_ms=next_seg.pad_start_ms,
                    pad_end_ms=next_seg.pad_end_ms
                )
            else:
                # No silence found, just make them adjacent
                split_point = (current.end_ms + next_seg.start_ms) // 2
                print(f"No silence found for overlap fix, splitting at midpoint: {split_point} ms")
                
                aligned_subsegments[i] = Segment(
                    speaker=current.speaker,
                    text=current.text,
                    start_ms=current.start_ms,
                    end_ms=split_point,
                    min_conf=current.min_conf,
                    pad_start_ms=current.pad_start_ms,
                    pad_end_ms=current.pad_end_ms
                )
                
                aligned_subsegments[i + 1] = Segment(
                    speaker=next_seg.speaker,
                    text=next_seg.text,
                    start_ms=split_point,
                    end_ms=next_seg.end_ms,
                    min_conf=next_seg.min_conf,
                    pad_start_ms=next_seg.pad_start_ms,
                    pad_end_ms=next_seg.pad_end_ms
                )
    
    return aligned_subsegments


def split_subsegments_on_internal_silence(subsegments: List[Segment], silences: List[Sil], tokens: List[Token]) -> List[Segment]:
    """
    Split subsegments that contain significant internal silences and have gaps in transcriptions.
    This function recursively splits subsegments to handle multiple internal silences.
    
    :param subsegments: List of subsegments to potentially split
    :param silences: List of detected silences 
    :param tokens: List of all tokens for finding transcription gaps
    :return: List of subsegments with internal silences split
    """
    MIN_INTERNAL_SILENCE_MS = 100  # Minimum silence duration to consider for splitting (lowered)
    MIN_SUBSEGMENT_DURATION_MS = 600  # Minimum duration for each resulting subsegment (lowered)
    MIN_TRANSCRIPTION_GAP_MS = 150  # Minimum gap in transcriptions to consider (lowered)
    
    def split_single_subsegment(subseg: Segment) -> List[Segment]:
        """Recursively split a single subsegment on internal silences."""
        
        print(f"Checking subsegment for internal silences: {subseg.start_ms}-{subseg.end_ms} ms")
        
        # Find silences that are completely within this subsegment (with smaller margins)
        internal_silences = []
        for s_start, s_end, s_dur in silences:
            # Reduced margin to catch more internal silences
            if (s_start >= subseg.start_ms + 25 and s_end <= subseg.end_ms - 25 and 
                s_dur >= MIN_INTERNAL_SILENCE_MS):
                internal_silences.append((s_start, s_end, s_dur))
        
        print(f"Found {len(internal_silences)} internal silences: {internal_silences}")
        
        if not internal_silences:
            # No significant internal silence, keep subsegment as is
            return [subseg]
        
        # Get tokens for this subsegment - use more inclusive overlap detection
        subseg_tokens = [tok for tok in tokens if 
                        tok.speaker == subseg.speaker and 
                        not (tok.end_ms <= subseg.start_ms or tok.start_ms >= subseg.end_ms)]  # Any overlap
        
        if not subseg_tokens:
            # No tokens in this subsegment, keep as is
            print(f"No tokens found for subsegment {subseg.start_ms}-{subseg.end_ms}")
            return [subseg]
        
        print(f"Found {len(subseg_tokens)} tokens in subsegment")
        
        # Sort silences by duration (largest first) to prioritize the most significant gaps
        internal_silences.sort(key=lambda x: x[2], reverse=True)
        
        # Find the best silence to split on
        best_split_silence = None
        
        for silence in internal_silences:
            s_start, s_end, s_dur = silence
            
            print(f"Checking silence {s_start}-{s_end} (duration: {s_dur}ms)")
            
            # Find tokens before and after this silence - be more generous with overlap
            tokens_before = [tok for tok in subseg_tokens if tok.end_ms <= s_start + 150]  # Allow more overlap
            tokens_after = [tok for tok in subseg_tokens if tok.start_ms >= s_end - 150]  # Allow more overlap
            
            print(f"Tokens before silence: {len(tokens_before)}, after: {len(tokens_after)}")
            
            if tokens_before and tokens_after:
                # There are tokens both before and after this silence
                # Check the gap between last token before silence and first token after
                last_before = max(tokens_before, key=lambda t: t.end_ms)
                first_after = min(tokens_after, key=lambda t: t.start_ms)
                
                # Calculate transcription gap
                transcription_gap = first_after.start_ms - last_before.end_ms
                
                print(f"Transcription gap: {transcription_gap}ms (last_before: {last_before.end_ms}, first_after: {first_after.start_ms})")
                
                # This silence is a good candidate if there's a transcription gap OR if the silence is very long
                if transcription_gap >= MIN_TRANSCRIPTION_GAP_MS or s_dur >= 500:  # Also split on very long silences
                    # Calculate potential split points
                    split_point = s_start + (s_dur // 2)
                    first_part_end = split_point - 25
                    second_part_start = split_point + 25
                    
                    # Check if both parts would have minimum duration
                    first_duration = first_part_end - subseg.start_ms
                    second_duration = subseg.end_ms - second_part_start
                    
                    print(f"Potential split durations: first={first_duration}ms, second={second_duration}ms")
                    
                    if (first_duration >= MIN_SUBSEGMENT_DURATION_MS and 
                        second_duration >= MIN_SUBSEGMENT_DURATION_MS):
                        best_split_silence = silence
                        break  # Take the first (largest) suitable silence
        
        if best_split_silence:
            # Split the subsegment at this silence
            s_start, s_end, s_dur = best_split_silence
            
            # Calculate split points: middle of the silence
            split_point = s_start + (s_dur // 2)
            first_part_end = split_point - 25  # End first part 25ms before split point
            second_part_start = split_point + 25  # Start second part 25ms after split point
            
            # Get tokens for each part - be more careful about assignment
            first_tokens = []
            second_tokens = []
            
            for tok in subseg_tokens:
                tok_center = (tok.start_ms + tok.end_ms) / 2
                if tok_center < split_point:
                    first_tokens.append(tok)
                else:
                    second_tokens.append(tok)
            
            # Ensure we have tokens in both parts
            if first_tokens and second_tokens:
                # Create first subsegment
                first_text = detokenize_text(first_tokens)
                first_conf = min(tok.confidence for tok in first_tokens)
                first_subseg = Segment(
                    speaker=subseg.speaker,
                    text=first_text,
                    start_ms=subseg.start_ms,
                    end_ms=first_part_end,
                    min_conf=first_conf,
                    pad_start_ms=subseg.pad_start_ms,
                    pad_end_ms=0
                )
                
                # Create second subsegment  
                second_text = detokenize_text(second_tokens)
                second_conf = min(tok.confidence for tok in second_tokens)
                second_subseg = Segment(
                    speaker=subseg.speaker,
                    text=second_text,
                    start_ms=second_part_start,
                    end_ms=subseg.end_ms,
                    min_conf=second_conf,
                    pad_start_ms=0,
                    pad_end_ms=subseg.pad_end_ms
                )
                
                print(f"Split subsegment at silence gap: {subseg.start_ms}-{subseg.end_ms} -> "
                      f"{first_subseg.start_ms}-{first_subseg.end_ms} and {second_subseg.start_ms}-{second_subseg.end_ms}")
                
                # Recursively split both parts in case they have more internal silences
                result = []
                result.extend(split_single_subsegment(first_subseg))
                result.extend(split_single_subsegment(second_subseg))
                return result
        
        # If we get here, we couldn't split the subsegment, keep it as is
        print(f"Could not split subsegment {subseg.start_ms}-{subseg.end_ms}")
        return [subseg]
    
    # Process all subsegments
    result_subsegments = []
    for subseg in subsegments:
        result_subsegments.extend(split_single_subsegment(subseg))
    
    return result_subsegments


def merge_subsegments_with_no_gaps(subsegments: List[Segment]) -> List[Segment]:
    """
    Merge adjacent subsegments when there's no gap between them.
    
    :param subsegments: List of subsegments to potentially merge
    :return: List of merged subsegments
    """
    if len(subsegments) <= 1:
        return subsegments
        
    merged = []
    current_segment = subsegments[0]
    
    for i in range(1, len(subsegments)):
        next_segment = subsegments[i]
        
        # Check if there's no gap between current and next segment
        # Allow for small overlaps or very small gaps (up to 10ms)
        gap_ms = next_segment.start_ms - current_segment.end_ms
        
        if gap_ms <= 5:  # No gap or very small gap/overlap
            # Merge the segments
            merged_text = current_segment.text.rstrip() + " " + next_segment.text.lstrip()
            merged_min_conf = min(current_segment.min_conf, next_segment.min_conf)
            
            current_segment = Segment(
                speaker=current_segment.speaker,
                text=merged_text,
                start_ms=current_segment.start_ms,
                end_ms=next_segment.end_ms,
                min_conf=merged_min_conf,
                pad_start_ms=current_segment.pad_start_ms,
                pad_end_ms=next_segment.pad_end_ms
            )
        else:
            # There's a significant gap, keep current segment and start new one
            merged.append(current_segment)
            current_segment = next_segment
    
    # Add the last segment
    merged.append(current_segment)
    
    return merged

# ----------------------------
# Confidence prefix
# ----------------------------

def confidence_prefix(min_conf: float) -> str:
    if min_conf < 0.5:
        return "___"
    if min_conf < 0.8:
        return "__"
    if min_conf < 0.9:
        return "_"
    return ""

def segment_audio(audio_path, json_path, outfile, silence_db: int = SILENCE_DB, min_silence_sec: float = MIN_SILENCE_SEC, min_seg_sec: float = MIN_SEG_SEC, max_seg_sec: float = MAX_SEG_SEC) -> None:
    """
    Compute segments based on the provided JSON tokens and global silence detection.
    Stores the segment information in a JSON file.
    
    :param audio_path: Path to the input audio file.
    :param json_path: Path to the JSON file with tokens.
    :param outfile: Output JSON file path for segments.
    :param silence_db: Silence threshold in dB.
    :param min_silence_sec: Minimum silence length in seconds.
    :param min_seg_sec: Minimum segment length in seconds.
    :param max_seg_sec: Maximum segment length in seconds.
    """
    pyannote_csv_path = Path(json_path.replace('_transcription.json', '_pyannote.csv'))
    silences_json_path = Path(json_path.replace('_transcription.json', '_silences.json'))

    audio_path = Path(audio_path)
    json_path = Path(json_path)
    
    tokens = load_tokens(json_path)

    print("detecting silences ...")
    # load silences from JSON
    if silences_json_path.exists():
        silences = json.loads(silences_json_path.read_text(encoding='utf-8'))
        silences = [(s[0], s[1], s[1] - s[0]) for s in silences]
    else:
        silences = detect_silences_full(audio_path, silence_db, min_silence_sec)

    # Segments (with inline boundary checks/adjustments)
    print("building segments")
    segments = build_segments(tokens, silences)

    # Load pyannote data for segment refinement
    pyannote_entries = []
    if pyannote_csv_path.exists():
        print("loading pyannote data for segment refinement...")
        pyannote_entries = load_pyannote_entries(pyannote_csv_path)
        print(f"loaded {len(pyannote_entries)} pyannote entries")

    # Refine segments using pyannote data
    if pyannote_entries:
        print("refining segments with pyannote data...")
        segments = refine_segments_with_pyannote(segments, pyannote_entries, silences)
        print("segment refinement complete")

    for s in segments:
        s['subs'] = align_subsegments_with_silences(s['subs_merged'], silences)
        # Split subsegments that contain significant internal silences
        s['subs'] = split_subsegments_on_internal_silence(s['subs'], silences, tokens)

    # Store raw segments (before merging) for debugging
    raw_segments_data = []
    for seg_idx, segdict in enumerate(segments, 1):
        main_seg = segdict['main']
        raw_sub_segs = segdict['subs']  # These are the raw subsegments before merging
        
        # Convert main segment
        main_data = {
            'speaker': main_seg.speaker,
            'text': main_seg.text,
            'start_ms': main_seg.start_ms,
            'end_ms': main_seg.end_ms,
            'min_conf': main_seg.min_conf,
            'pad_start_ms': main_seg.pad_start_ms,
            'pad_end_ms': main_seg.pad_end_ms
        }
        
        # Convert raw subsegments
        raw_sub_data = []
        for subseg in raw_sub_segs:
            raw_sub_data.append({
                'speaker': subseg.speaker,
                'text': subseg.text,
                'start_ms': subseg.start_ms,
                'end_ms': subseg.end_ms,
                'min_conf': subseg.min_conf,
                'pad_start_ms': subseg.pad_start_ms,
                'pad_end_ms': subseg.pad_end_ms
            })
        
        raw_segments_data.append({
            'seg_idx': seg_idx,
            'main': main_data,
            'subs': raw_sub_data
        })

    # Save raw segments file
    raw_outfile = Path(str(outfile).replace('_segments.json', '_segments_raw.json'))
    raw_output_data = {
        'segments': raw_segments_data,
        'audio_path': str(audio_path),
        'total_segments': len(segments)
    }
    
    with raw_outfile.open('w', encoding='utf-8') as f:
        json.dump(raw_output_data, f, indent=2, ensure_ascii=False)
    
    print(f"[ok] Saved raw segments (before merging) to {raw_outfile}")

    # Convert segments to serializable format (processed segments)
    serializable_segments = []
    for seg_idx, segdict in enumerate(segments, 1):
        main_seg = segdict['main']
        sub_segs = segdict['subs']  # These are the final processed subsegments
        
        # Convert main segment
        main_data = {
            'speaker': main_seg.speaker,
            'text': main_seg.text,
            'start_ms': main_seg.start_ms,
            'end_ms': main_seg.end_ms,
            'min_conf': main_seg.min_conf,
            'pad_start_ms': main_seg.pad_start_ms,
            'pad_end_ms': main_seg.pad_end_ms
        }
        
        # Convert subsegments
        sub_data = []
        for subseg in sub_segs:
            sub_data.append({
                'speaker': subseg.speaker,
                'text': subseg.text,
                'start_ms': subseg.start_ms,
                'end_ms': subseg.end_ms,
                'min_conf': subseg.min_conf,
                'pad_start_ms': subseg.pad_start_ms,
                'pad_end_ms': subseg.pad_end_ms
            })
        
        serializable_segments.append({
            'seg_idx': seg_idx,
            'main': main_data,
            'subs': sub_data
        })

    # Save to JSON file
    outfile = Path(outfile)
    output_data = {
        'segments': serializable_segments,
        'audio_path': str(audio_path),
        'total_segments': len(segments)
    }
    
    with outfile.open('w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"[ok] Computed {len(segments)} segments and saved to {outfile}")


def generate_segments(segments_json_path, audio_path, outdir, export_rate: Optional[int] = EXPORT_RATE) -> None:
    """
    Generate audio segments (wav and txt files) from a segments JSON file.
    
    :param segments_json_path: Path to the JSON file with segment information.
    :param audio_path: Path to the input audio file.
    :param outdir: Output directory for segments.
    :param export_rate: Export sample rate for WAV files.
    """
    # Load segments from JSON
    
    segments_json_path = Path(segments_json_path)
    audio_path = Path(audio_path)
    outdir = Path(outdir)
    
    
    with segments_json_path.open('r', encoding='utf-8') as f:
        data = json.load(f)
    
    segments = data['segments']
    
    print("exporting segments and subsegments")
    counters = {}
    
    for segdict in segments:
        seg_idx = segdict['seg_idx']
        main_seg_data = segdict['main']
        sub_segs_data = segdict['subs']
        
        # Create Segment object from data
        main_seg = Segment(
            speaker=main_seg_data['speaker'],
            text=main_seg_data['text'],
            start_ms=main_seg_data['start_ms'],
            end_ms=main_seg_data['end_ms'],
            min_conf=main_seg_data['min_conf'],
            pad_start_ms=main_seg_data.get('pad_start_ms', 0),
            pad_end_ms=main_seg_data.get('pad_end_ms', 0)
        )
        
        spk_dir = outdir / "speakers" / str(main_seg.speaker)
        spk_dir.mkdir(parents=True, exist_ok=True)
        counters.setdefault(main_seg.speaker, 0)
        counters[main_seg.speaker] += 1

        # Write main segment as clipxx
        prefix = confidence_prefix(main_seg.min_conf)
        base = f"clip{seg_idx:02d}{prefix}"
        wav_path = spk_dir / f"{base}.wav"
        txt_path = spk_dir / f"{base}.txt"
        ffmpeg_extract(audio_path, main_seg.start_ms, main_seg.end_ms, wav_path, main_seg.pad_start_ms, main_seg.pad_end_ms)
        txt_path.write_text(main_seg.text + "\n", encoding="utf-8")

        # Write subsegments as clipxx_yy, but only if more than 1 subsegment and subsegment != main segment
        if len(sub_segs_data) > 1:
            for sub_idx, subseg_data in enumerate(sub_segs_data, 1):
                # Create Segment object from data
                subseg = Segment(
                    speaker=subseg_data['speaker'],
                    text=subseg_data['text'],
                    start_ms=subseg_data['start_ms'],
                    end_ms=subseg_data['end_ms'],
                    min_conf=subseg_data['min_conf'],
                    pad_start_ms=subseg_data.get('pad_start_ms', 0),
                    pad_end_ms=subseg_data.get('pad_end_ms', 0)
                )
                
                # skip subsegment if it is identical to main segment
                if (subseg.start_ms == main_seg.start_ms and subseg.end_ms == main_seg.end_ms):
                    continue
                sub_prefix = confidence_prefix(subseg.min_conf)
                sub_base = f"clip{seg_idx:02d}_{sub_idx:02d}{sub_prefix}"
                sub_wav_path = spk_dir / f"{sub_base}.wav"
                sub_txt_path = spk_dir / f"{sub_base}.txt"
                ffmpeg_extract(audio_path, subseg.start_ms, subseg.end_ms, sub_wav_path, subseg.pad_start_ms, subseg.pad_end_ms)
                sub_txt_path.write_text(subseg.text + "\n", encoding="utf-8")

    total = sum(counters.values())
    print(f"[ok] Generated {total} main segments across {len(counters)} speaker(s) under {outdir/'speakers'}")

# ----------------------------
# Pyannote utilities
# ----------------------------

def load_pyannote_entries(csv_path: Path) -> List[PyannoteEntry]:
    """Load pyannote speaker diarization entries from CSV file."""
    if not csv_path.exists():
        return []
    
    import pandas as pd
    df = pd.read_csv(csv_path)
    entries = []
    
    for _, row in df.iterrows():
        entries.append(PyannoteEntry(
            speaker=str(row['speaker']),
            start_ms=int(row['start'] * 1000),
            end_ms=int(row['end'] * 1000),
            duration_ms=int(row['duration'] * 1000)
        ))
    
    return entries

def find_overlapping_pyannote_entries(pyannote_entries: List[PyannoteEntry], segment: Segment) -> List[PyannoteEntry]:
    """Find pyannote entries that overlap with the given segment."""
    overlapping = []
    for entry in pyannote_entries:
        # Check if entry overlaps with segment
        if entry.start_ms < segment.end_ms and entry.end_ms > segment.start_ms:
            overlapping.append(entry)
    return overlapping

def refine_segments_with_pyannote(segments_list: List[dict], pyannote_entries: List[PyannoteEntry], silences: List[Sil]) -> List[dict]:
    """
    Refine segment boundaries using pyannote speaker diarization data.
    
    Strategy:
    1. For each pyannote annotation, find all segments that overlap with it
    2. Only extend the first segment's start to match annotation start
    3. Only extend the last segment's end to match annotation end
    4. This prevents overlapping segments while aligning to pyannote boundaries
    """
    if not pyannote_entries:
        print("[warn] No pyannote entries found, skipping refinement")
        return segments_list
    
    # Create a list of all main segments for analysis
    print(f"refining segments with pyannote data... {len(pyannote_entries)} entries found")  
    all_segments = []
    for i, segdict in enumerate(segments_list):
        main_seg = segdict['main']
        all_segments.append((i, main_seg))
    
    # Sort segments by start time
    all_segments.sort(key=lambda x: x[1].start_ms)
    
    refined_segments = [segdict.copy() for segdict in segments_list]
    
    # Process each pyannote entry
    for entry in pyannote_entries:
        # Find segments that overlap with this pyannote entry
        overlapping_segments = []
        for seg_idx, segment in all_segments:
            if (segment.start_ms < entry.end_ms and segment.end_ms > entry.start_ms):
                overlapping_segments.append((seg_idx, segment))
                segment.speaker = entry.speaker  # Update speaker to pyannote entry speaker
                # update speaker for all subsegments as well
                for subsegment in refined_segments[seg_idx]['subs']:
                    subsegment.speaker = entry.speaker
                for subsegment in refined_segments[seg_idx]['subs_merged']:
                    subsegment.speaker = entry.speaker

        if not overlapping_segments:
            continue
            
        # Sort by start time to identify first and last
        overlapping_segments.sort(key=lambda x: x[1].start_ms)
        
        # Extend first segment's start to annotation start (if annotation starts earlier)
        first_idx, first_segment = overlapping_segments[0]
        if entry.start_ms < first_segment.start_ms:
            new_start_ms = entry.start_ms
            refined_main = refined_segments[first_idx]['main']
            refined_segments[first_idx]['main'] = Segment(
                speaker=refined_main.speaker,
                text=refined_main.text,
                start_ms=new_start_ms,
                end_ms=refined_main.end_ms,
                min_conf=refined_main.min_conf,
                pad_start_ms=refined_main.pad_start_ms,
                pad_end_ms=refined_main.pad_end_ms
            )
        
        # Extend last segment's end to annotation end (if annotation ends later)
        last_idx, last_segment = overlapping_segments[-1]
        if entry.end_ms > last_segment.end_ms:
            new_end_ms = entry.end_ms
            refined_main = refined_segments[last_idx]['main']
            refined_segments[last_idx]['main'] = Segment(
                speaker=refined_main.speaker,
                text=refined_main.text,
                start_ms=refined_main.start_ms,
                end_ms=new_end_ms,
                min_conf=refined_main.min_conf,
                pad_start_ms=refined_main.pad_start_ms,
                pad_end_ms=refined_main.pad_end_ms
            )
    
    # Recheck boundary silence guarantees and update subsegments for modified segments
    for i, segdict in enumerate(refined_segments):
        original_main = segments_list[i]['main']
        refined_main = segdict['main']
        
        # If main segment changed, update silence guarantees
        if (refined_main.start_ms != original_main.start_ms or 
            refined_main.end_ms != original_main.end_ms):
            
            # Recheck boundary silence guarantees
            if not silence_covering_point(silences, refined_main.start_ms, REQUIRED_SIL_START_MS):
                refined_main.pad_start_ms = EDGE_OFFSET_MS
            if not silence_covering_point(silences, refined_main.end_ms, REQUIRED_SIL_END_MS):
                refined_main.pad_end_ms = max(refined_main.pad_end_ms, EDGE_OFFSET_MS)
            
            # Update the segment in the list
            refined_segments[i]['main'] = refined_main
            
            # Scale subsegments if main segment changed
            original_subs = segments_list[i]['subs_merged']
            if original_subs:
                refined_segments[i]['subs_merged'] = scale_subsegments(refined_main, original_main, original_subs)
    
    return refined_segments

def scale_subsegments(main_segment: Segment, original_main: Segment, subsegments: List[Segment]) -> List[Segment]:
    """
    Scale/move subsegments when main segment boundaries change.
    First subsegment starts at main segment start, last subsegment ends at main segment end.
    """
    if not subsegments:
        return []
    
    if len(subsegments) == 1:
        # Single subsegment should match main segment exactly
        return [Segment(
            speaker=subsegments[0].speaker,
            text=subsegments[0].text,
            start_ms=main_segment.start_ms,
            end_ms=main_segment.end_ms,
            min_conf=subsegments[0].min_conf,
            pad_start_ms=main_segment.pad_start_ms,
            pad_end_ms=main_segment.pad_end_ms
        )]
    
    # Calculate scaling factors
    original_duration = original_main.end_ms - original_main.start_ms
    new_duration = main_segment.end_ms - main_segment.start_ms
    
    if original_duration <= 0:
        return subsegments  # Can't scale if original has no duration
    
    scale_factor = new_duration / original_duration
    
    scaled_subsegments = []
    for i, subseg in enumerate(subsegments):
        # Calculate relative position within original main segment
        rel_start = subseg.start_ms - original_main.start_ms
        rel_end = subseg.end_ms - original_main.start_ms
        
        # Scale and translate to new main segment
        new_start = main_segment.start_ms + int(rel_start * scale_factor)
        new_end = main_segment.start_ms + int(rel_end * scale_factor)
        
        # Ensure first subsegment starts at main start and last ends at main end
        if i == 0:
            new_start = main_segment.start_ms
        if i == len(subsegments) - 1:
            new_end = main_segment.end_ms
        
        # Ensure subsegments don't overlap and are in order
        if i > 0 and new_start < scaled_subsegments[-1].end_ms:
            new_start = scaled_subsegments[-1].end_ms
        
        if new_end <= new_start:
            new_end = new_start + 100  # Minimum 100ms duration
        
        scaled_subsegments.append(Segment(
            speaker=subseg.speaker,
            text=subseg.text,
            start_ms=new_start,
            end_ms=new_end,
            min_conf=subseg.min_conf,
            pad_start_ms=subseg.pad_start_ms if i == 0 else 0,
            pad_end_ms=subseg.pad_end_ms if i == len(subsegments) - 1 else 0
        ))
    
    return scaled_subsegments

# ----------------------------
# Main
# ----------------------------

def main():
    ap = argparse.ArgumentParser(
        description=(
            "Produce sentence transcript and per-speaker segments from JSON tokens and an MP3/WAV file, "
            "using one-pass silence detection and aligning boundaries to silence."
        )
    )
    subparsers = ap.add_subparsers(dest='command', help='Available commands')
    
    # Subcommand for computing segments
    compute_parser = subparsers.add_parser('compute', help='Compute segments and save to JSON')
    compute_parser.add_argument("json_path", type=Path, help="Path to JSON file with tokens")
    compute_parser.add_argument("audio_path", type=Path, help="Path to input audio (.mp3 or .wav)")
    compute_parser.add_argument("--outfile", type=Path, default=Path("segments.json"), help="Output JSON file (default: segments.json)")
    compute_parser.add_argument("--silence-db", type=int, default=SILENCE_DB, help="Silence threshold in dB (default: -35)")
    compute_parser.add_argument("--min-sil", type=float, default=MIN_SILENCE_SEC, help="Min silence (sec) for detector (default: 0.02)")
    compute_parser.add_argument("--min-seg", type=float, default=MIN_SEG_SEC, help="Minimum segment length in seconds (default: 1.0)")
    compute_parser.add_argument("--max-seg", type=float, default=MAX_SEG_SEC, help="Maximum segment length in seconds (default: 25.0)")
    
    # Subcommand for generating audio files
    generate_parser = subparsers.add_parser('generate', help='Generate audio files from segments JSON')
    generate_parser.add_argument("segments_json", type=Path, help="Path to segments JSON file")
    generate_parser.add_argument("audio_path", type=Path, help="Path to input audio (.mp3 or .wav)")
    generate_parser.add_argument("--outdir", type=Path, default=Path("out"), help="Output directory (default: out/)")
    generate_parser.add_argument("--rate", type=int, default=EXPORT_RATE, help="Export WAV sample rate or 0 to keep original (default: 16000)")
    
    # Legacy mode (original behavior)
    ap.add_argument("json_path", type=Path, nargs='?', help="Path to JSON file with tokens (legacy mode)")
    ap.add_argument("audio_path", type=Path, nargs='?', help="Path to input audio (.mp3 or .wav) (legacy mode)")
    ap.add_argument("--outdir", type=Path, default=Path("out"), help="Output directory (default: out/) (legacy mode)")
    ap.add_argument("--silence-db", type=int, default=SILENCE_DB, help="Silence threshold in dB (default: -35)")
    ap.add_argument("--min-sil", type=float, default=MIN_SILENCE_SEC, help="Min silence (sec) for detector (default: 0.02)")
    ap.add_argument("--min-seg", type=float, default=MIN_SEG_SEC, help="Minimum segment length in seconds (default: 1.0)")
    ap.add_argument("--max-seg", type=float, default=MAX_SEG_SEC, help="Maximum segment length in seconds (default: 25.0)")
    ap.add_argument("--rate", type=int, default=EXPORT_RATE, help="Export WAV sample rate or 0 to keep original (default: 16000)")
    
    args = ap.parse_args()

    if args.command == 'compute':
        if not args.json_path.exists():
            raise SystemExit(f"JSON not found: {args.json_path}")
        if not args.audio_path.exists():
            raise SystemExit(f"Audio not found: {args.audio_path}")

        segment_audio(
            audio_path=args.audio_path,
            json_path=args.json_path,
            outfile=args.outfile,
            silence_db=args.silence_db,
            min_silence_sec=args.min_sil,
            min_seg_sec=args.min_seg,
            max_seg_sec=args.max_seg
        )
    elif args.command == 'generate':
        if not args.segments_json.exists():
            raise SystemExit(f"Segments JSON not found: {args.segments_json}")
        if not args.audio_path.exists():
            raise SystemExit(f"Audio not found: {args.audio_path}")

        generate_segments(
            segments_json_path=args.segments_json,
            audio_path=args.audio_path,
            outdir=args.outdir,
            export_rate=args.rate if args.rate and args.rate > 0 else None
        )
    else:
        # Legacy mode - original behavior
        if not args.json_path or not args.audio_path:
            ap.print_help()
            raise SystemExit("Error: json_path and audio_path are required in legacy mode")
            
        if not args.json_path.exists():
            raise SystemExit(f"JSON not found: {args.json_path}")
        if not args.audio_path.exists():
            raise SystemExit(f"Audio not found: {args.audio_path}")

        # First compute segments
        segments_file = Path("temp_segments.json")
        segment_audio(
            audio_path=args.audio_path,
            json_path=args.json_path,
            outfile=segments_file,
            silence_db=args.silence_db,
            min_silence_sec=args.min_sil,
            min_seg_sec=args.min_seg,
            max_seg_sec=args.max_seg
        )
        
        # Then generate audio files
        generate_segments(
            segments_json_path=segments_file,
            audio_path=args.audio_path,
            outdir=args.outdir,
            export_rate=args.rate if args.rate and args.rate > 0 else None
        )
        
        # Clean up temp file
        segments_file.unlink()
    


if __name__ == "__main__":
    main()
