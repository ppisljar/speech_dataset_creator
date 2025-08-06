import os
from clearvoice import ClearVoice
# use clearvoice mossformer2 to clean up audio (remove background noise, echo, reverb, etc.)\\\


myClearVoice = ClearVoice(task='speech_enhancement', model_names=['MossFormer2_SE_48K'])

def clean_audio(input_path, output_path):
    """
    Clean the audio file using ClearVoice and save the output.
    
    :param input_path: Path to the input audio file.
    :param output_path: Path to save the cleaned audio file.
    """
    # Ensure the output directory exists
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_wav = myClearVoice(input_path=input_path, online_write=False)
    print(f"Cleaned audio saved to {output_path}")
    # remove file if it exists
    if os.path.exists(output_path):
        os.remove(output_path)

    myClearVoice.write(output_wav, output_path=str(output_path))
