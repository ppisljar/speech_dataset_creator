import os
import soundfile as sf
import torch
from clearvoice import ClearVoice
# use clearvoice mossformer2 to clean up audio (remove background noise, echo, reverb, etc.)

# Check GPU availability for ClearVoice (it will automatically use GPU if available)
if torch.cuda.is_available():
    print(f"GPU available: {torch.cuda.get_device_name()} - ClearVoice will use it automatically")
else:
    print("WARNING: No GPU detected - ClearVoice will run on CPU (slower processing)")

myClearVoice = ClearVoice(task='speech_enhancement', model_names=['MossFormer2_SE_48K'])

def clean_audio(input_path, output_path):
    """
    Clean the audio file using ClearVoice and save the output as a proper WAV file.
    
    :param input_path: Path to the input audio file.
    :param output_path: Path to save the cleaned audio file.
    """
    # Ensure the output directory exists
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Process audio with ClearVoice
    output_wav = myClearVoice(input_path=input_path, online_write=False)
    
    print(f"Cleaned audio saved to {output_path}")
    
    # Remove file if it exists
    if os.path.exists(output_path):
        os.remove(output_path)

    # Convert to proper WAV format using soundfile
    # output_wav should contain the audio data and sample rate
    if isinstance(output_wav, tuple) and len(output_wav) == 2:
        audio_data, sample_rate = output_wav
        sf.write(output_path, audio_data, sample_rate, format='WAV')
    else:
        print("Warning: ClearVoice output is not in expected format. Attempting fallback method.")
        # Fallback: use ClearVoice's write method first, then re-read and convert
        temp_path = str(output_path) + ".temp"
        myClearVoice.write(output_wav, output_path=temp_path)
        
        # Read the temporary file and write as proper WAV
        audio_data, sample_rate = sf.read(temp_path)
        sf.write(output_path, audio_data, sample_rate, format='WAV')
        
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)
