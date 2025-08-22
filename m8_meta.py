# construct metadata.txt file for entire podcast
import os
import json
import csv

def generate_metadata(project_dir, output_file='metadata.txt'):
    """
    Generate metadata for the entire podcast project.
    
    Args:
        project_dir (str): Path to the project directory.
        output_file (str): Path to the output metadata file.
    
    Returns:
        None
    """
    # Call the function to generate metadata for splits
    podcast_dir = os.path.join(project_dir, 'audio')

    # for every folder inside {podcast_dir}
    metadata = []
    i = 0
    for root, dirs, files in os.walk(podcast_dir):
        dirs.sort()  # Sort directories for consistent ordering
        for dir_name in dirs:
            speakers_folder = os.path.join(root, dir_name)
            # speakers folder contains folder per speaker, walk over all of them
            for speaker_name in sorted(os.listdir(speakers_folder)):
                speaker_path = os.path.join(speakers_folder, speaker_name)
                if os.path.isdir(speaker_path):
                    # Get all text files in the speaker folder
                    text_files = sorted([f for f in os.listdir(speaker_path) if f.endswith('.txt')])
                    for text_file in text_files:
                        text_file_path = os.path.join(speaker_path, text_file)
                        wav_file_path = os.path.join(speaker_path, text_file.replace('.txt', '.wav'))
                        with open(text_file_path, 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            # Process the content as needed
                            i += 1
                            metadata.append([i, wav_file_path, speaker_name, content])
                        

    # save metadata to output_file in csv format
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Write header
        writer.writerow(['id', 'audio_path', 'speaker', 'text'])
        # Write data
        for row in metadata:
            writer.writerow(row)
    

    print(f"Metadata generated and saved to {output_file}")
 
def generate_metadata_for_splits(podcast_dir, output_file='metadata.txt'):
    """
    Generate metadata for the podcast episodes in the specified directory.
    
    Args:
        podcast_dir (str): Path to the directory containing podcast episodes. ('splits/test.mp3')
        output_file (str): Path to the output metadata file.
    
    Returns:
        None
    """

    # for every folder inside {podcast_dir}
    metadata = []
    i = 0
    for root, dirs, files in os.walk(podcast_dir):
        dirs.sort()  # Sort directories for consistent ordering
        for dir_name in dirs:
            if dir_name.endswith('_segments'):
                segments_folder = os.path.join(root, dir_name)
                # Look for speakers folder inside segments folder
                speakers_folder = os.path.join(segments_folder, 'speakers')
                if os.path.exists(speakers_folder):
                    # speakers folder contains folder per speaker, walk over all of them
                    for speaker_name in sorted(os.listdir(speakers_folder)):
                        speaker_path = os.path.join(speakers_folder, speaker_name)
                        if os.path.isdir(speaker_path):
                            # Get all text files in the speaker folder
                            text_files = sorted([f for f in os.listdir(speaker_path) if f.endswith('.txt')])
                            for text_file in text_files:
                                text_file_path = os.path.join(speaker_path, text_file)
                                wav_file_path = os.path.join(speaker_path, text_file.replace('.txt', '.wav'))
                                with open(text_file_path, 'r', encoding='utf-8') as f:
                                    content = f.read().strip()
                                    # Process the content as needed
                                    i += 1
                                    metadata.append([i, wav_file_path, speaker_name, content])
                        

    # save metadata to output_file in csv format
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        # Write header
        writer.writerow(['id', 'audio_path', 'speaker', 'text'])
        # Write data
        for row in metadata:
            writer.writerow(row)
    

    print(f"Metadata generated and saved to {output_file}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python m8_meta.py <podcast_directory>")
        print("Example: python m8_meta.py output/test.mp3")
        sys.exit(1)
    
    podcast_dir = sys.argv[1]
    output_file = os.path.join(podcast_dir, "metadata.csv")
    
    if not os.path.exists(podcast_dir):
        print(f"Error: Directory {podcast_dir} does not exist")
        sys.exit(1)
    
    generate_metadata(podcast_dir, output_file)