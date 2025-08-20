#!/usr/bin/env python3
"""
Simple test to verify that settings are being read correctly from projects
"""

import os
import json
import sys

def test_settings_loading():
    """Test that settings are loaded correctly from the test project"""
    projects_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects')
    project_dir = os.path.join(projects_dir, 'test')
    settings_file = os.path.join(project_dir, 'settings.json')
    
    print(f"Looking for settings file: {settings_file}")
    
    if not os.path.exists(settings_file):
        print("❌ Settings file does not exist")
        return False
    
    try:
        with open(settings_file, 'r') as f:
            settings = json.load(f)
        
        print("✅ Settings loaded successfully:")
        for key, value in settings.items():
            print(f"  {key}: {value}")
        
        # Check that all expected settings are present
        expected_settings = ['silenceThreshold', 'minSilenceLength', 'maxSpeakers']
        missing_settings = []
        
        for expected in expected_settings:
            if expected not in settings:
                missing_settings.append(expected)
        
        if missing_settings:
            print(f"❌ Missing settings: {missing_settings}")
            return False
        
        # Check types and values
        if not isinstance(settings['silenceThreshold'], (int, float)):
            print("❌ silenceThreshold should be a number")
            return False
        
        if not isinstance(settings['minSilenceLength'], int):
            print("❌ minSilenceLength should be an integer")
            return False
        
        if not isinstance(settings['maxSpeakers'], int):
            print("❌ maxSpeakers should be an integer")
            return False
        
        if settings['maxSpeakers'] < 0:
            print("❌ maxSpeakers should be >= 0")
            return False
        
        print("✅ All settings are valid")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing settings JSON: {e}")
        return False
    except Exception as e:
        print(f"❌ Error loading settings: {e}")
        return False

def test_settings_usage():
    """Test that settings are used correctly in the processing pipeline"""
    # Simulate the settings loading logic from run_all.py
    projects_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'projects')
    project_dir = os.path.join(projects_dir, 'test')
    settings_file = os.path.join(project_dir, 'settings.json')
    settings = {}
    
    if os.path.exists(settings_file):
        try:
            with open(settings_file, 'r') as f:
                settings = json.load(f)
            print("✅ Settings loaded from run_all.py logic")
        except Exception as e:
            print(f"❌ Error in run_all.py settings loading logic: {e}")
            return False
    else:
        print("❌ Settings file not found in run_all.py logic")
        return False
    
    # Simulate the settings usage logic from run.py
    silence_thresh = settings.get('silenceThreshold', -30)
    min_silence_len = settings.get('minSilenceLength', 100)
    max_speakers = settings.get('maxSpeakers', 0)
    
    print("✅ Settings extracted for run.py:")
    print(f"  Silence threshold: {silence_thresh}dB")
    print(f"  Min silence length: {min_silence_len}ms")
    print(f"  Max speakers: {max_speakers if max_speakers > 0 else 'auto-detect'}")
    
    # Test max_speakers parameter logic
    max_speakers_param = max_speakers if max_speakers > 0 else None
    print(f"  Max speakers param for diarization: {max_speakers_param}")
    
    return True

if __name__ == "__main__":
    print("Testing settings loading and usage...")
    print("=" * 50)
    
    success1 = test_settings_loading()
    print()
    success2 = test_settings_usage()
    
    print()
    print("=" * 50)
    if success1 and success2:
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed!")
        sys.exit(1)
