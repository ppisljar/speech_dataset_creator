import wespeaker

model = wespeaker.load_model('english')
embedding1 = model.extract_embedding('audio1.wav')
embedding2 = model.extract_embedding('audio2.wav')
similarity = model.cosine_similarity(embedding1, embedding2)
diar_result = model.diarize('audio.wav')