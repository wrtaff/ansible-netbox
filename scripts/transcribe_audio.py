#!/usr/bin/env python3
"""
================================================================================
Filename:	transcribe_audio.py
Version:	1.4
Author:		Gemini CLI
Last Modified:	2026-01-28
Context:	http://trac.home.arpa/ticket/2987

Purpose:
	Transcribes an audio file using the Gemini 2.0 Flash API.
	Outputs the transcript to a .txt file in the same directory.
	Supports providing context to improve transcription accuracy.
	Automatically chunks large files (>20m) to prevent timeouts.

Changes in 1.4:
	- Added automatic audio chunking for files longer than 20 minutes using ffmpeg.
	- Concatenates transcripts from multiple chunks.

Changes in 1.3:
	- Added filename sanitization: Replaces spaces with underscores in input file.
	- Updated output filename format: Appends "_transcription.txt".

Changes in 1.2:
	- Centralized script in ansible-netbox repository.

Usage:
	./transcribe_audio.py <audio_file_path> [--context "Context text"] [--model "model-name"]

Dependencies:
	- requests (pip install requests)
	- ffmpeg (apt install ffmpeg)
================================================================================
"""
import os
import sys
import time
import json
import base64
import requests
import argparse
import getpass
import threading
import itertools
import shutil
import subprocess
import glob

# --- Configuration ---
DEFAULT_MODEL = "gemini-2.0-flash"
API_KEY_FILE = os.path.join(os.path.dirname(__file__), "..", "gemini_key.txt")
CHUNK_THRESHOLD_SECONDS = 1200 # 20 minutes
CHUNK_SEGMENT_TIME = 1200      # 20 minutes

def get_api_key():
    """Retrieves the Gemini API key from environment or file."""
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        print("Using API key from environment variable 'GEMINI_API_KEY'.")
        return api_key
    
    if os.path.exists(API_KEY_FILE):
        with open(API_KEY_FILE, 'r') as f:
            print(f"Using API key from file: {API_KEY_FILE}")
            return f.read().strip()
    
    print("Gemini API key not found in environment or file.")
    try:
        api_key = getpass.getpass(prompt="Please enter your Gemini API key: ").strip()
        if api_key:
            return api_key
    except Exception as e:
        print(f"\nError reading input: {e}")

    print("Error: No API key provided.")
    sys.exit(1)

def get_audio_duration(file_path):
    """Returns the duration of the audio file in seconds using ffprobe."""
    try:
        cmd = [
            'ffprobe', 
            '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Warning: Could not determine audio duration: {e}")
        return 0

def split_audio(file_path, segment_time=CHUNK_SEGMENT_TIME):
    """Splits audio into segments using ffmpeg."""
    dir_name = os.path.dirname(file_path)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    # Create a pattern for segments: original_name_part000.ext
    extension = os.path.splitext(file_path)[1]
    output_pattern = os.path.join(dir_name, f"{base_name}_part%03d{extension}")
    
    print(f"Splitting audio into {segment_time}s chunks...")
    try:
        cmd = [
            'ffmpeg',
            '-i', file_path,
            '-f', 'segment',
            '-segment_time', str(segment_time),
            '-c', 'copy',
            '-reset_timestamps', '1',
            output_pattern
        ]
        # Run quietly
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
        
        # Find generated files
        search_pattern = os.path.join(dir_name, f"{base_name}_part*{extension}")
        chunks = sorted(glob.glob(search_pattern))
        print(f"Created {len(chunks)} chunks.")
        return chunks
    except subprocess.CalledProcessError as e:
        print(f"Error splitting audio: {e.stderr.decode()}")
        sys.exit(1)

def upload_file(file_path, api_key):
    """Uploads the file to Gemini Media API."""
    url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}"
    
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    # Determine MIME type
    mime_type = "audio/mpeg" # Default
    if file_path.endswith(".m4a"):
        mime_type = "audio/mp4"
    elif file_path.endswith(".wav"):
        mime_type = "audio/wav"
    elif file_path.endswith(".ogg"):
        mime_type = "audio/ogg"

    print(f"Uploading {file_name} ({mime_type})...")

    # Initial resumable upload request
    headers = {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(file_size),
        "X-Goog-Upload-Header-Content-Type": mime_type,
        "Content-Type": "application/json",
    }
    
    response = requests.post(url, headers=headers, json={"file": {"display_name": file_name}})
    response.raise_for_status()
    
    upload_url = response.headers.get("X-Goog-Upload-URL")
    
    # Perform the actual upload
    with open(file_path, 'rb') as f:
        upload_response = requests.post(
            upload_url,
            headers={
                "Content-Length": str(file_size),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize"
            },
            data=f
        )
    upload_response.raise_for_status()
    
    file_info = upload_response.json()
    file_uri = file_info['file']['uri']
    file_name_api = file_info['file']['name']
    
    print(f"File uploaded successfully. URI: {file_uri}")
    return file_uri, file_name_api

def wait_for_file(file_name_api, api_key):
    """Waits for the file to be processed by Gemini."""
    url = f"https://generativelanguage.googleapis.com/v1beta/{file_name_api}?key={api_key}"
    
    print("Waiting for file processing", end="", flush=True)
    while True:
        response = requests.get(url)
        response.raise_for_status()
        status = response.json().get("state")
        
        if status == "ACTIVE":
            print("\nFile is active and ready.")
            break
        elif status == "FAILED":
            print("\nFile processing failed.")
            sys.exit(1)
        
        print(".", end="", flush=True)
        time.sleep(2)

def transcribe_chunk(file_uri, api_key, model=DEFAULT_MODEL, context=None, chunk_index=0):
    """Sends the transcription request to Gemini for a specific chunk."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    prompt_text = "Please provide a verbatim transcript of this audio file. Include speaker labels if possible and clear timestamps for major transitions."
    
    if chunk_index > 0:
        prompt_text += " Note: This is part of a larger recording, so context may be continuing from a previous segment."

    if context:
        prompt_text += f"\n\nContext for the conversation:\n{context}"

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt_text},
                {"file_data": {"mime_type": "audio/mp4", "file_uri": file_uri}}
            ]
        }],
        "generationConfig": {
            "temperature": 0.0,
        }
    }
    
    print(f"Requesting transcription from {model} (this may take a while)...")
    
    # Spinner logic
    done = False
    def spinner():
        for c in itertools.cycle(['|', '/', '-', '\\']):
            if done:
                break
            sys.stdout.write(f'\rProcessing... {c}')
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write('\rProcessing... Done!   \n')

    spinner_thread = threading.Thread(target=spinner)
    spinner_thread.start()

    try:
        # Increased timeout to 600 seconds (10 minutes) per chunk
        response = requests.post(url, json=payload, timeout=600)
        done = True
        spinner_thread.join()
        response.raise_for_status()
        
        result = response.json()
        try:
            transcript = result['candidates'][0]['content']['parts'][0]['text']
            return transcript
        except KeyError:
            print("\nWarning: No transcript text found in response.")
            return "[No transcript generated for this segment]"
            
    except requests.exceptions.Timeout:
        done = True
        spinner_thread.join()
        print("\nError: Request timed out after 600 seconds.")
        sys.exit(1)
    except Exception as e:
        done = True
        spinner_thread.join()
        print(f"\nError requesting transcription: {e}")
        try:
            if 'response' in locals():
                print(json.dumps(response.json(), indent=2))
        except:
            pass
        sys.exit(1)

def process_file_or_chunk(file_path, api_key, model, context, chunk_index=0):
    """Orchestrates upload, wait, and transcribe for a single file/chunk."""
    file_uri, file_name_api = upload_file(file_path, api_key)
    wait_for_file(file_name_api, api_key)
    return transcribe_chunk(file_uri, api_key, model, context, chunk_index)

def main():
    parser = argparse.ArgumentParser(description="Transcribe audio using Gemini.")
    parser.add_argument("file_path", help="Path to the audio file.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--context", help="Contextual information to aid transcription.")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file_path):
        print(f"Error: File not found: {args.file_path}")
        sys.exit(1)

    # Sanitize filename if it contains spaces
    if " " in os.path.basename(args.file_path):
        dir_name = os.path.dirname(args.file_path)
        base_name = os.path.basename(args.file_path)
        new_base_name = base_name.replace(" ", "_")
        new_file_path = os.path.join(dir_name, new_base_name)
        
        print(f"Renaming '{args.file_path}' to '{new_file_path}'...")
        shutil.move(args.file_path, new_file_path)
        args.file_path = new_file_path
        
    api_key = get_api_key()
    
    # Check duration
    duration = get_audio_duration(args.file_path)
    full_transcript = ""
    
    if duration > CHUNK_THRESHOLD_SECONDS:
        print(f"File duration ({duration:.2f}s) exceeds threshold ({CHUNK_THRESHOLD_SECONDS}s). Splitting...")
        chunks = split_audio(args.file_path)
        
        for i, chunk_path in enumerate(chunks):
            print(f"\n--- Processing Chunk {i+1}/{len(chunks)}: {os.path.basename(chunk_path)} ---")
            chunk_transcript = process_file_or_chunk(chunk_path, api_key, args.model, args.context, chunk_index=i)
            full_transcript += f"\n\n--- Segment {i+1} ---\n{chunk_transcript}"
            
            # Cleanup chunk
            os.remove(chunk_path)
            
        print("\nAll chunks processed.")
    else:
        full_transcript = process_file_or_chunk(args.file_path, api_key, args.model, args.context)
    
    output_path = os.path.splitext(args.file_path)[0] + "_transcription.txt"
    with open(output_path, 'w') as f:
        f.write(full_transcript)
        
    print(f"\nTranscription complete! Saved to: {output_path}")

if __name__ == "__main__":
    main()