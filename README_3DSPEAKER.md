# 3D-Speaker Diarization Module (m5_3dspeaker.py)

This module provides speaker diarization functionality using the 3D-Speaker toolkit, which is an alternative to pyannote.audio with competitive performance and easier setup.

## Features

- **High Performance**: 3D-Speaker achieves competitive or better DER (Diarization Error Rate) compared to pyannote.audio
- **No Authentication Required**: Unlike pyannote.audio, 3D-Speaker doesn't require HuggingFace tokens for basic usage
- **Fast Processing**: Optimized for speed with RTF (Real Time Factor) of 0.03 on CPU
- **Overlap Detection**: Optional support for overlapping speech detection
- **Multiple Output Formats**: Supports both RTTM and CSV output formats

## Installation

Install 3D-Speaker using pip:

```bash
pip install 3dspeaker
```

For overlap detection functionality (optional), you'll also need to accept the pyannote/segmentation-3.0 license and get a HuggingFace token:

1. Visit [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) and accept the user conditions
2. Create an access token at [hf.co/settings/tokens](https://hf.co/settings/tokens)

## Usage

### As a Module

```python
from m5_3dspeaker import threed_speaker_diarize, pyannote

# Basic diarization
segments = threed_speaker_diarize('audio.wav', output_dir='output/')

# Using the compatibility wrapper (same interface as original pyannote)
segments = pyannote('audio.wav', output_dir='output/')

# With overlap detection (requires HuggingFace token)
segments = threed_speaker_diarize('audio.wav', output_dir='output/', include_overlap=True)
```

### Command Line

```bash
# Basic diarization
python m5_3dspeaker.py audio.wav --output_dir output/

# With overlap detection
python m5_3dspeaker.py audio.wav --output_dir output/ --include_overlap --hf_token your_token_here
```

### Integration with Existing Pipeline

The module maintains compatibility with the original pyannote interface:

```python
# This works with both the original m5_pyannote.py and m5_3dspeaker.py
from m5_3dspeaker import pyannote
segments = pyannote('audio.wav', output_dir='output/')
```

## Performance Comparison

According to 3D-Speaker benchmarks:

| Dataset | 3D-Speaker DER | pyannote.audio DER |
|---------|----------------|-------------------|
| Aishell-4 | **10.30%** | 12.2% |
| VoxConverse | 11.75% | **11.3%** |
| AMI_SDM | 21.76% | 22.4% |

Computational efficiency (CPU):

| Method | RTF |
|--------|-----|
| 3D-Speaker | **0.03** |
| pyannote.audio | 0.19 |

## Output Format

The module generates two types of output files:

### RTTM File Format
```
SPEAKER filename 0 start_time duration <NA> <NA> speaker_id <NA> <NA>
```

### CSV File Format
```csv
start,end,duration,speaker,speaker_id
0.00,2.50,2.50,SPEAKER_00,0
2.50,5.75,3.25,SPEAKER_01,1
```

## Function Reference

### `threed_speaker_diarize(audio_file_path, output_dir=None, speaker_database=None, include_overlap=False)`

Main diarization function using 3D-Speaker.

**Parameters:**
- `audio_file_path` (str): Path to the audio file
- `output_dir` (str, optional): Directory to save output files
- `speaker_database` (dict, optional): Not used in this implementation but kept for compatibility
- `include_overlap` (bool): Whether to include overlapping speech detection

**Returns:**
- List of segments: `[[start_time, end_time, speaker_id], ...]`

### `pyannote(audio_file_path, output_dir=None, speaker_database=None)`

Compatibility wrapper that maintains the same interface as the original pyannote module.

**Parameters:**
- `audio_file_path` (str): Path to the audio file
- `output_dir` (str, optional): Directory to save output files
- `speaker_database` (dict, optional): Not used but kept for compatibility

**Returns:**
- List of segments: `[[start_time, end_time, speaker_id], ...]`

## Requirements

- Python 3.7+
- 3dspeaker
- pandas
- numpy
- ffmpeg (for audio format conversion)

## Notes

1. **Audio Format**: The module automatically converts non-WAV files to WAV format using ffmpeg
2. **Device Selection**: Automatically detects and uses GPU if available, falls back to CPU
3. **Speaker Database**: The speaker_database parameter is maintained for interface compatibility but not currently used by 3D-Speaker
4. **Error Handling**: Comprehensive error handling with cleanup of temporary files

## Troubleshooting

### Import Error
```
ImportError: 3D-Speaker is not available. Please install it with: pip install 3dspeaker
```
**Solution**: Install 3D-Speaker using `pip install 3dspeaker`

### Audio Conversion Error
```
Error converting audio file: ...
```
**Solution**: Ensure ffmpeg is installed and available in your PATH

### Overlap Detection Error
```
ValueError: hf_access_token is required when include_overlap is True.
```
**Solution**: Provide a valid HuggingFace access token or disable overlap detection

## License

This module follows the same license as the parent project. 3D-Speaker is licensed under Apache 2.0.
