# WeSeaker Diarization Module

This module (`m5_wespeaker.py`) is a conversion of the pyannote-based diarization code to use the wespeaker toolkit instead.

## Key Differences from pyannote version

1. **Simpler API**: WeSeaker provides a simpler, more straightforward diarization API
2. **No HuggingFace token required**: Unlike pyannote, wespeaker doesn't require authentication tokens
3. **Better performance**: WeSeaker is optimized for production use and typically faster
4. **Less GPU memory usage**: More efficient memory utilization

## Installation

```bash
pip install git+https://github.com/wenet-e2e/wespeaker.git
```

## Usage

### Command Line
```bash
python m5_wespeaker.py input_audio.wav --output results
```

### As a Module
```python
from m5_wespeaker import wespeaker_diarize

# Basic usage
result = wespeaker_diarize("audio.wav", "output_prefix")

# With speaker database
result = wespeaker_diarize("audio.wav", "output", speaker_db="speakers.npy")
```

## Compatibility

The module provides a `pyannote()` function for backward compatibility with existing code that imports from the original pyannote module.

## Features

- **Audio format support**: WAV, MP3, M4A, FLAC (auto-converts to 16kHz mono WAV)
- **Output formats**: 
  - CSV file with speaker segments
  - RTTM file (standard diarization format)
- **Speaker database**: Optional speaker matching using embeddings
- **FFmpeg integration**: Automatic audio conversion when needed

## Parameters

- `input_file`: Path to audio file
- `output_file`: Base name for output files
- `min_speakers`: Minimum speakers (not used by wespeaker)
- `max_speakers`: Maximum speakers (not used by wespeaker)  
- `speaker_db`: Path to speaker database file
- `speaker_threshold`: Similarity threshold for speaker matching (default: 0.75)

## Output Format

The function returns a dictionary with:
- `segments`: List of speaker segments with timing information
- `rttm_file`: Path to generated RTTM file
- `csv_file`: Path to generated CSV file

Each segment contains:
- `speaker`: Speaker identifier
- `start`: Start time in seconds
- `end`: End time in seconds  
- `duration`: Duration in seconds

## Notes

- WeSeaker uses its own pre-trained models (no additional model downloads required)
- Speaker labels are automatically generated as `spk_0`, `spk_1`, etc.
- The module handles audio conversion automatically using FFmpeg
- Compatible with existing pipeline that expects pyannote output format
