import os
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv()
 
# Retrieve the API key from environment variable (ensure SONIOX_API_KEY is set)
api_key = os.environ.get("SONIOX_API_KEY")
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


def transcribe_file(input_file, output_file="output.json"):
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
                "language_hints": ["en", "es"],
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
        print("Transcript:")
        print(data["text"])

        # ✅ Store full JSON to file
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Full transcription JSON saved to {output_file}")

        # Delete the transcription
        res = session.delete(f"{api_base}/v1/transcriptions/{transcription_id}")
        res.raise_for_status()

        # Delete the file
        res = session.delete(f"{api_base}/v1/files/{file_id}")
        res.raise_for_status()

    except requests.exceptions.RequestException as e:
        print(f"An error occurred during the HTTP request: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
 
 
if __name__ == "__main__":
    transcribe_file(file_to_transcribe, output_file="output.json")