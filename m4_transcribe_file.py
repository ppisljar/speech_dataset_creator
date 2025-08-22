#!/usr/bin/env python3
import os
import time
import json
import requests
import sys
from dotenv import load_dotenv

load_dotenv()
 
# Retrieve the API key from environment variable (ensure SONIOX_API_KEY is set)
api_key = os.environ.get("SONIOX_API_KEY")
language = os.environ.get("SONIOX_LANG", "sl")
if api_key is None:
    raise ValueError("SONIOX_API_KEY environment variable is not set.")

api_base = "https://api.soniox.com"
 
session = requests.Session()
session.headers["Authorization"] = f"Bearer {api_key}"
 
 
def poll_until_complete(transcription_id):
    while True:
        res = session.get(f"{api_base}/v1/transcriptions/{transcription_id}")
        res.raise_for_status()
        data = res.json()
        if data["status"] == "completed":
            return
        elif data["status"] == "error":
            raise Exception(
                f"Transcription failed: {data.get('error_message', 'Unknown error')}"
            )
        time.sleep(1)


def transcribe_file(input_file, output_file="output.json", skip_file_output=False, language=None):
    # Use provided language parameter or fall back to environment variable
    lang = language if language is not None else os.environ.get("SONIOX_LANG", "sl")
    
    try:
        print("Starting file upload...")

        res = session.post(
            f"{api_base}/v1/files",
            files={
                "file": open(input_file, "rb"),
            },
        )
        res.raise_for_status()
        file_id = res.json()["id"]
        print(f"File ID: {file_id}")

        print("Starting transcription...")

        res = session.post(
            f"{api_base}/v1/transcriptions",
            json={
                "file_id": file_id,
                "model": "stt-async-preview",
                "language_hints": [lang],
                "enable_speaker_diarization": True,
            },
        )
        res.raise_for_status()
        transcription_id = res.json()["id"]
        print(f"Transcription ID: {transcription_id}")

        poll_until_complete(transcription_id)

        # Get the transcript text
        res = session.get(f"{api_base}/v1/transcriptions/{transcription_id}/transcript")
        res.raise_for_status()
        data = res.json()

        # ✅ Store full JSON to file (unless skipped)
        if not skip_file_output:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"Full transcription JSON saved to {output_file}")

        # Delete the transcription
        res = session.delete(f"{api_base}/v1/transcriptions/{transcription_id}")
        res.raise_for_status()

        # Delete the file
        res = session.delete(f"{api_base}/v1/files/{file_id}")
        res.raise_for_status()

        # Return data if requested
        return data

    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the HTTP request: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None
 
 
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python m4_transcribe_file.py <input_file> [output_file]")
        print("  input_file: Path to the audio file to transcribe")
        print("  output_file: Optional output JSON file path (default: output.json)")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "output.json"
    
    transcribe_file(input_file, output_file)