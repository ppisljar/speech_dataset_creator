from speakerlab.bin.infer_diarization import Diarization3Dspeaker
wav_path = "audio.wav"
pipeline = Diarization3Dspeaker()
print(pipeline(wav_path, wav_fs=None, speaker_num=None))