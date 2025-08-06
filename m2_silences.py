# use ffmpeg to find silences in audio file and write to silences.json
import argparse
import json
import subprocess

def find_silences(audio_file, min_silence_len=1000, silence_thresh=-30):
    """
    Find silences in an audio file using ffmpeg.
    
    :param audio_file: Path to the input audio file.
    :param min_silence_len: Minimum length of silence to detect (in milliseconds).
    :param silence_thresh: Silence threshold in dB.
    :return: List of silence intervals as tuples (start, end) in milliseconds.
    """
    command = [
        "ffmpeg", "-hide_banner", "-nostats", "-i", audio_file, "-af",
        f"silencedetect=noise={silence_thresh}dB:d={min_silence_len/1000}",
        "-f", "null", "-"
    ]
    
    result = subprocess.run(command, stderr=subprocess.PIPE, text=True)
    
    silences = []
    for line in result.stderr.splitlines():
        if "silence_start" in line:
            try:
                start = float(line.split("silence_start: ")[1].strip())
            except (IndexError, ValueError):
                continue
        elif "silence_end" in line:
            try:
                # Find the part after 'silence_end: '
                end_part = line.split("silence_end: ")[1]
                # The value is the first token (could be followed by '|', etc.)
                end_str = end_part.split()[0]
                end = float(end_str)
                silences.append((start * 1000, end * 1000))  # Convert to milliseconds
            except (IndexError, ValueError, NameError):
                continue
    
    return silences

def find_silences_in_file(audio_file, output_file, min_silence_len=100, silence_thresh=-30):
    """
    Find silences in an audio file and save the results to a JSON file.
    
    :param audio_file: Path to the input audio file.
    :param min_silence_len: Minimum length of silence to detect (in milliseconds).
    :param silence_thresh: Silence threshold in dB.
    """
    silences = find_silences(audio_file, min_silence_len, silence_thresh)
    
    with open(output_file, "w") as f:
        json.dump(silences, f, indent=4)

    print(f"Found {len(silences)} silence intervals. Saved to {output_file}.")

def main():
    parser = argparse.ArgumentParser(description="Find silences in an audio file.")
    parser.add_argument("audio_file", help="Path to the input audio file.")
    parser.add_argument("--min_silence_len", type=int, default=1000, help="Minimum silence length in milliseconds.")
    parser.add_argument("--silence_thresh", type=int, default=-30, help="Silence threshold in dB.")
    args = parser.parse_args()

    silences = find_silences(args.audio_file, args.min_silence_len, args.silence_thresh)
    
    with open("silences.json", "w") as f:
        json.dump(silences, f, indent=4)
    
    print(f"Found {len(silences)} silence intervals. Saved to silences.json.")

if __name__ == "__main__":
    main()