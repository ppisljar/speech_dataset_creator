# TODO

- enhance with clearvoice [no need for audiobooks]
-- superresolution ?
- split into 1 hour segments [only needed for soniox]
- transribe (soniox, whisperx, nvidia ctc)
-- diaretization with pyannote (optional)
-- speaker validation
-- match speakers across files
- align with existing text ?
- split into 1-25s segments (single speaker) and save with transcription
-- trim silence
- phonetize and phoneme alig ()



web:
!- detect shorter silences
!- allow to configure the project (silence length, treshold)
!- align segments with pyannote/silences
- add export button which: builds the segments, constructs metadata
- add clean button (which deletes everythuing but final artifacts)
- add download button which downloads zip


next round:
- improve alignment
- handle overlapping speach
- fix pyannote across multiple files