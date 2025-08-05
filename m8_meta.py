# construct metadata.txt file for entire podcast
import os
import json

def generate_metadata(podcast_dir, output_file='metadata.txt'):
    """
    Generate metadata for the podcast episodes in the specified directory.
    
    Args:
        podcast_dir (str): Path to the directory containing podcast episodes.
        output_file (str): Path to the output metadata file.
    
    Returns:
        None
    """
    with open(output_file, 'w') as f:
        for episode in os.listdir(podcast_dir):
            if episode.endswith('.json'):
                episode_path = os.path.join(podcast_dir, episode)
                f.write(f"Episode: {episode}\n")
                f.write(f"Path: {episode_path}\n")
                f.write("\n")
    
    print(f"Metadata generated and saved to {output_file}")