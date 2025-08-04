import os
import time
import json
import requests
 
# Retrieve the API key from environment variable (ensure SONIOX_API_KEY is set)
api_key = os.environ.get("SONIOX_API_KEY")
api_base = "https://api.soniox.com"
audio_url = "https://traffic.libsyn.com/secure/aidea/179.mp3?dest-id=1173629"
 
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
 
 
def main():
    print("Starting transcription...")
 
    res = session.post(
        f"{api_base}/v1/transcriptions",
        json={
            "audio_url": audio_url,
            "model": "stt-async-preview",
            "language_hints": ["sl"],
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
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Full transcription JSON saved to output.json")

    # TODO: store full json to file

 
    # Delete the transcription
    res = session.delete(f"{api_base}/v1/transcriptions/{transcription_id}")
    res.raise_for_status()
 
 
if __name__ == "__main__":
    main()