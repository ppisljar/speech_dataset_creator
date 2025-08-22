def archive_dataset(project_name):
    import os
    import shutil
    import csv
    
    # create projects/{project_name}/output
    project_dir = f"projects/{project_name}"
    output_dir = f"{project_dir}/output"
    splits_dir = f"{project_dir}/splits"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Look for metadata.csv in the splits directory
    metadata_file = None
    for root, dirs, files in os.walk(splits_dir):
        if "metadata.csv" in files:
            metadata_file = os.path.join(root, "metadata.csv")
            break
    
    if not metadata_file or not os.path.exists(metadata_file):
        print(f"Error: metadata.csv not found in {splits_dir}")
        return False
    
    # Load metadata.csv and process each line
    new_metadata = []
    
    with open(metadata_file, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            audio_id = row['id']
            audio_path = row['audio_path']
            speaker = row['speaker']
            text = row['text']
            
            # Create speaker directory in output
            speaker_dir = os.path.join(output_dir, speaker)
            os.makedirs(speaker_dir, exist_ok=True)
            
            # Copy audio file to output/{speaker}/{id}.wav
            if os.path.exists(audio_path):
                dest_audio = os.path.join(speaker_dir, f"{audio_id}.wav")
                shutil.copy2(audio_path, dest_audio)
                
                # Create corresponding text file
                dest_text = os.path.join(speaker_dir, f"{audio_id}.txt")
                with open(dest_text, 'w', encoding='utf-8') as f:
                    f.write(text)
                
                # Update metadata with new path
                new_metadata.append({
                    'id': audio_id,
                    'audio_path': f"{speaker}/{audio_id}.wav",
                    'speaker': speaker,
                    'text': text
                })
            else:
                print(f"Warning: Audio file not found: {audio_path}")
    
    # Save updated metadata.csv in output directory
    output_metadata = os.path.join(output_dir, "metadata.csv")
    with open(output_metadata, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['id', 'audio_path', 'speaker', 'text']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_metadata)
    
    print(f"Dataset archived successfully to {output_dir}")
    print(f"Processed {len(new_metadata)} audio files")
    return True

def clean(project_name, raw=False):
    import os
    import shutil
    
    project_dir = f"projects/{project_name}"
    splits_dir = f"{project_dir}/splits"
    raw_dir = f"{project_dir}/raw"
    
    # Remove all files in projects/{project_name}/splits
    if os.path.exists(splits_dir):
        for root, dirs, files in os.walk(splits_dir, topdown=False):
            dirs.sort()  # Sort directories for consistent ordering
            # Remove all files
            for file in sorted(files):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"Removed file: {file_path}")
                except OSError as e:
                    print(f"Error removing file {file_path}: {e}")
            
            # Remove all directories (except the splits dir itself)
            for dir_name in sorted(dirs):
                dir_path = os.path.join(root, dir_name)
                try:
                    os.rmdir(dir_path)
                    print(f"Removed directory: {dir_path}")
                except OSError as e:
                    print(f"Error removing directory {dir_path}: {e}")
        
        print(f"Cleaned splits directory: {splits_dir}")
    else:
        print(f"Splits directory does not exist: {splits_dir}")
    
    # Remove all files in projects/{project_name}/raw (only if raw=True)
    if raw and os.path.exists(raw_dir):
        for root, dirs, files in os.walk(raw_dir, topdown=False):
            dirs.sort()  # Sort directories for consistent ordering
            # Remove all files
            for file in sorted(files):
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"Removed raw file: {file_path}")
                except OSError as e:
                    print(f"Error removing raw file {file_path}: {e}")
            
            # Remove all directories (except the raw dir itself)
            for dir_name in sorted(dirs):
                dir_path = os.path.join(root, dir_name)
                try:
                    os.rmdir(dir_path)
                    print(f"Removed raw directory: {dir_path}")
                except OSError as e:
                    print(f"Error removing raw directory {dir_path}: {e}")
        
        print(f"Cleaned raw directory: {raw_dir}")
    elif raw:
        print(f"Raw directory does not exist: {raw_dir}")

    return True

def compress(project_name):
    import os
    import zipfile
    
    project_dir = f"projects/{project_name}"
    output_dir = f"{project_dir}/output"
    zip_file_path = f"{project_dir}/output.zip"
    
    # Check if output directory exists
    if not os.path.exists(output_dir):
        print(f"Error: Output directory does not exist: {output_dir}")
        return False
    
    # Create zip file
    try:
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Walk through all files in the output directory
            for root, dirs, files in os.walk(output_dir):
                dirs.sort()  # Sort directories for consistent ordering
                for file in sorted(files):
                    file_path = os.path.join(root, file)
                    # Calculate relative path from output directory
                    arcname = os.path.relpath(file_path, output_dir)
                    zipf.write(file_path, arcname)
                    print(f"Added to zip: {arcname}")
        
        # Get zip file size for confirmation
        zip_size = os.path.getsize(zip_file_path)
        print(f"Successfully compressed output directory to: {zip_file_path}")
        print(f"Zip file size: {zip_size / (1024*1024):.2f} MB")
        return True
        
    except Exception as e:
        print(f"Error creating zip file: {e}")
        return False