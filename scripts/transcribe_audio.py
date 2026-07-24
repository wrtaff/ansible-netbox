#!/usr/bin/env python3
"""
================================================================================
Filename:       transcribe_audio.py
Version:        1.14
Author:         Gemini CLI
Last Modified:  2026-07-24
Context:        http://trac.home.arpa/ticket/2966, http://trac.home.arpa/ticket/4001

Purpose:
    Transcribes an audio file using the Gemini 3.5 Flash API.
    Falls back to ElevenLabs Scribe (diarization-capable), then an
    OpenRouter fallback chain, on Gemini errors.
    Outputs the transcript to a .txt file in the same directory.
    Supports providing context to improve transcription accuracy.
    Automatically chunks large files (>40m) to prevent timeouts.

Changes in 1.14 (#4001):
    - ROOT CAUSE FIX for silently dropped segments (2026-06-29 board meeting):
      transcribe_chunk() previously caught KeyError on a missing text part
      and RETURNED a "[No transcript generated for this segment]" placeholder.
      Because it returned normally, process_file_or_chunk()'s except block
      never ran, so the fallback chain never fired and the placeholder was
      written into the final transcript as if the segment had succeeded.
      Now raises instead, so fallback always fires; also logs finishReason/
      promptFeedback so MAX_TOKENS/SAFETY truncation is visible in the logs.
    - Added explicit generationConfig.maxOutputTokens (65536) to reduce
      MAX_TOKENS truncation on dense, long, multi-speaker segments.
    - Added a post-assembly guard in main(): if any segment's transcript is
      empty or still contains a failure placeholder after all fallbacks are
      exhausted, the script exits non-zero instead of writing a silently
      incomplete transcript.
    - Added ElevenLabs Scribe (scribe_v1, diarize=true) as the new primary
      fallback ahead of the OpenRouter chain — matches Gemini's one-call
      diarization, often better raw accuracy. openai/gpt-audio demoted to
      secondary fallback. See ticket #4001 model-decision comment.

Changes in 1.13:
    - Updated DEFAULT_MODEL from gemini-2.5-flash to gemini-3.5-flash (now GA;
      pinned explicitly rather than using the gemini-flash-latest alias).
    - Replaced dead OpenRouter fallback openai/gpt-4o-audio-preview (removed
      from OpenRouter) with openai/gpt-audio -> openai/gpt-audio-mini;
      voxtral-small remains the last-resort backstop.
    - Raised chunk threshold/segment time from 1200s to 2400s — the 20-minute
      limit guarded the HTTP timeout, not an API limit; most recordings are
      now single-chunk, avoiding overlap dedup. See trac #2966.

Changes in 1.12:
    - Updated DEFAULT_MODEL from gemini-2.0-flash to gemini-2.5-flash.
      gemini-2.0-flash is deprecated; 2.5-flash is the current stable model.
      No API changes required — same Files API and generateContent endpoint.

Changes in 1.11:
    - Replaced single OpenRouter fallback model with an ordered fallback chain.
    - Default chain: openai/gpt-4o-audio-preview -> mistralai/voxtral-small-24b-2507.
    - gpt-4o-audio-preview first: near-Gemini quality (speaker labels, clean output).
    - voxtral-small last resort only: cheaper but no speaker labels, noisy output.
    - Each model in the chain is tried in order; only exhaustion raises a fatal error.
    - CLI: --openrouter-model replaced by --fallback-chain (accepts multiple model IDs).

Changes in 1.10:
    - Corrected default OpenRouter fallback model to openai/gpt-4o-audio-preview
      (google/gemini-2.0-flash-001 routes back to Google AI Studio and shares quota).
    - Updated Context link to master tracker ticket #2966.

Changes in 1.9:
    - Added OpenRouter fallback when Gemini returns 429 or other API errors.
    - Added --openrouter-model flag (default: openai/gpt-4o-audio-preview).
    - Added get_openrouter_api_key() reading OPENROUTER_API_KEY env / file / .bashrc.
    - Added transcribe_chunk_openrouter() using base64 inline audio.
    - transcribe_chunk() now raises on error instead of sys.exit() so fallback fires cleanly.

Changes in 1.8:
    - Added robust API key extraction from ~/.bashrc using grep.

Changes in 1.7:
    - Added note that prerequisites are managed by playbooks/standard_debian_desktop_software_config.yml.
    - Updated dependencies documentation.

Changes in 1.6:
    - Fixed MIME type mismatch by dynamically detecting and passing the correct 
      type (e.g., audio/mpeg for mp3) to the Gemini API instead of hardcoding mp4.

Changes in 1.5:
    - Added 60s overlap to audio chunks to prevent data loss at boundaries.
    - Switched from 'segment' muxer to manual splitting loop.

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
    - requests (pip install requests or python3-requests apt package)
    - ffmpeg (apt install ffmpeg)
    - Note: Prereqs are managed by playbooks/standard_debian_desktop_software_config.yml
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
import math

# --- Configuration ---
DEFAULT_MODEL = "gemini-3.5-flash"
OPENROUTER_FALLBACK_CHAIN = [
    "openai/gpt-audio",
    "openai/gpt-audio-mini",
    "mistralai/voxtral-small-24b-2507",
]
API_KEY_FILE = os.path.join(os.path.dirname(__file__), "..", "gemini_key.txt")
OPENROUTER_KEY_FILE = os.path.join(os.path.dirname(__file__), "..", "openrouter_key.txt")
ELEVENLABS_KEY_FILE = os.path.join(os.path.dirname(__file__), "..", "elevenlabs_key.txt")
ELEVENLABS_MODEL = "scribe_v1"
CHUNK_THRESHOLD_SECONDS = 2400 # 40 minutes
CHUNK_SEGMENT_TIME = 2400      # 40 minutes
CHUNK_OVERLAP = 60             # 60 seconds overlap
MAX_OUTPUT_TOKENS = 65536      # generous cap to avoid MAX_TOKENS truncation on dense segments

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

    try:
        print("Checking ~/.bashrc for GEMINI_API_KEY...")
        # Grep the export line directly from .bashrc to avoid issues with early exits in non-interactive shells
        cmd = "grep 'export GEMINI_API_KEY=' ~/.bashrc | cut -d'\"' -f2"
        result = subprocess.run(['bash', '-c', cmd], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        bashrc_key = result.stdout.strip()
        if bashrc_key and bashrc_key.startswith("AIza"):
            print("Using API key from ~/.bashrc.")
            return bashrc_key
    except Exception as e:
        print(f"Warning: Could not extract key from ~/.bashrc: {e}")
    
    print("Gemini API key not found in environment, file, or ~/.bashrc.")
    try:
        api_key = getpass.getpass(prompt="Please enter your Gemini API key: ").strip()
        if api_key:
            return api_key
    except Exception as e:
        print(f"\nError reading input: {e}")

    print("Error: No API key provided.")
    sys.exit(1)

def get_openrouter_api_key():
    """Retrieves the OpenRouter API key from environment, file, or ~/.bashrc."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        print("Using OpenRouter key from environment variable.")
        return api_key

    if os.path.exists(OPENROUTER_KEY_FILE):
        with open(OPENROUTER_KEY_FILE, 'r') as f:
            print(f"Using OpenRouter key from file: {OPENROUTER_KEY_FILE}")
            return f.read().strip()

    try:
        cmd = "grep 'export OPENROUTER_API_KEY=' ~/.bashrc | cut -d'\"' -f2"
        result = subprocess.run(['bash', '-c', cmd], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        bashrc_key = result.stdout.strip()
        if bashrc_key and bashrc_key.startswith("sk-or"):
            print("Using OpenRouter key from ~/.bashrc.")
            return bashrc_key
    except Exception as e:
        print(f"Warning: Could not extract OpenRouter key from ~/.bashrc: {e}")

    return None


def get_elevenlabs_api_key():
    """Retrieves the ElevenLabs API key from environment, file, or ~/.bashrc."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if api_key:
        print("Using ElevenLabs key from environment variable.")
        return api_key

    if os.path.exists(ELEVENLABS_KEY_FILE):
        with open(ELEVENLABS_KEY_FILE, 'r') as f:
            print(f"Using ElevenLabs key from file: {ELEVENLABS_KEY_FILE}")
            return f.read().strip()

    try:
        cmd = "grep 'export ELEVENLABS_API_KEY=' ~/.bashrc | cut -d'\"' -f2"
        result = subprocess.run(['bash', '-c', cmd], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        bashrc_key = result.stdout.strip()
        if bashrc_key:
            print("Using ElevenLabs key from ~/.bashrc.")
            return bashrc_key
    except Exception as e:
        print(f"Warning: Could not extract ElevenLabs key from ~/.bashrc: {e}")

    return None


def transcribe_chunk_elevenlabs(file_path, api_key, mime_type, chunk_index=0):
    """Transcribes a single audio chunk via ElevenLabs Scribe (speech-to-text, diarized).

    Scribe has no context/prompt parameter (unlike Gemini/OpenRouter chat-completions),
    so name-spelling/context hints are lost on this path — diarization is returned as
    per-word speaker_id, not embedded speaker labels, so it's reconstructed here into
    "Speaker N: ..." lines grouped on consecutive same-speaker words.
    """
    url = "https://api.elevenlabs.io/v1/speech-to-text"
    headers = {"xi-api-key": api_key}
    data = {
        "model_id": ELEVENLABS_MODEL,
        "diarize": "true",
        "tag_audio_events": "false",
        "timestamps_granularity": "word",
    }

    print(f"Requesting transcription from ElevenLabs ({ELEVENLABS_MODEL})...")

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
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, mime_type)}
            response = requests.post(url, headers=headers, data=data, files=files, timeout=600)
        done = True
        spinner_thread.join()
        response.raise_for_status()
        result = response.json()

        words = result.get("words")
        if not words:
            text = result.get("text", "").strip()
            if not text:
                raise RuntimeError("ElevenLabs returned no text or words")
            return text

        lines = []
        current_speaker = None
        current_words = []
        for w in words:
            if w.get("type") == "spacing":
                continue
            speaker = w.get("speaker_id", "speaker_0")
            if speaker != current_speaker:
                if current_words:
                    lines.append(f"Speaker {current_speaker}: {' '.join(current_words)}")
                current_speaker = speaker
                current_words = []
            current_words.append(w.get("text", ""))
        if current_words:
            lines.append(f"Speaker {current_speaker}: {' '.join(current_words)}")

        return "\n".join(lines)
    except Exception as e:
        done = True
        spinner_thread.join()
        print(f"\nElevenLabs error: {e}")
        try:
            if 'response' in locals():
                print(json.dumps(response.json(), indent=2))
        except Exception:
            pass
        raise


def transcribe_chunk_openrouter(file_path, openrouter_key, model, context, chunk_index=0):
    """Transcribes a single audio chunk via OpenRouter using base64-encoded audio."""
    url = "https://openrouter.ai/api/v1/chat/completions"

    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    format_map = {"mp3": "mp3", "m4a": "m4a", "wav": "wav", "ogg": "ogg", "mp4": "mp4"}
    audio_format = format_map.get(ext, "mp3")

    print(f"Encoding {os.path.basename(file_path)} as base64 for OpenRouter...")
    with open(file_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    prompt_text = "Please provide a verbatim transcript of this audio file. Include speaker labels if possible and clear timestamps for major transitions."
    if chunk_index > 0:
        prompt_text += " Note: This is part of a larger recording, so context may be continuing from a previous segment."
    if context:
        prompt_text += f"\n\nContext for the conversation:\n{context}"

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text},
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": audio_format}},
            ]
        }],
        "temperature": 0.0,
    }

    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://home.arpa/pops",
        "X-Title": "Pops Audio Ingest",
    }

    print(f"Requesting transcription from OpenRouter ({model})...")

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
        response = requests.post(url, json=payload, headers=headers, timeout=600)
        done = True
        spinner_thread.join()
        response.raise_for_status()
        result = response.json()
        try:
            content = result['choices'][0]['message']['content']
        except (KeyError, IndexError):
            print("\nWarning: No transcript text found in OpenRouter response.")
            print(json.dumps(result, indent=2))
            raise RuntimeError(f"OpenRouter/{model} returned no transcript content")
        if not content or not content.strip():
            raise RuntimeError(f"OpenRouter/{model} returned empty transcript content")
        return content
    except Exception as e:
        done = True
        spinner_thread.join()
        print(f"\nOpenRouter error: {e}")
        try:
            if 'response' in locals():
                print(json.dumps(response.json(), indent=2))
        except:
            pass
        raise


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

def split_audio(file_path, segment_time=CHUNK_SEGMENT_TIME, overlap=CHUNK_OVERLAP):
    """Splits audio into segments with overlap using ffmpeg."""
    dir_name = os.path.dirname(file_path)
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    extension = os.path.splitext(file_path)[1]
    
    duration = get_audio_duration(file_path)
    if duration == 0:
        print("Error: Cannot split file with 0 duration.")
        sys.exit(1)

    print(f"Splitting audio (Duration: {duration:.2f}s) into {segment_time}s chunks with {overlap}s overlap...")
    
    chunks = []
    start_time = 0
    part_num = 0
    
    # Stride is the amount we move forward each time
    stride = segment_time - overlap
    
    while start_time < duration:
        output_filename = f"{base_name}_part{part_num:03d}{extension}"
        output_path = os.path.join(dir_name, output_filename)
        
        # Ensure we don't go past the end, though ffmpeg handles duration gracefully usually
        # But we want strict segments if possible.
        
        cmd = [
            'ffmpeg',
            '-y',               # Overwrite if exists
            '-ss', str(start_time),
            '-t', str(segment_time),
            '-i', file_path,
            '-c', 'copy',       # Try to copy stream (fast)
            '-avoid_negative_ts', 'make_zero',
            output_path
        ]
        
        # If we are near the end, the duration might be shorter than segment_time, which is fine.
        
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
            chunks.append(output_path)
            print(f"  Created chunk {part_num}: {output_filename} (Start: {start_time}s)")
        except subprocess.CalledProcessError as e:
            print(f"Error splitting audio chunk {part_num}: {e.stderr.decode()}")
            sys.exit(1)
            
        start_time += stride
        part_num += 1
        
        # Safety break if we aren't moving (shouldn't happen with positive stride)
        if stride <= 0: 
            break

    print(f"Created {len(chunks)} chunks.")
    return chunks

def _guess_mime_type(file_path):
    """Determines audio MIME type from file extension (shared by all providers)."""
    if file_path.endswith(".m4a"):
        return "audio/mp4"
    elif file_path.endswith(".wav"):
        return "audio/wav"
    elif file_path.endswith(".ogg"):
        return "audio/ogg"
    return "audio/mpeg"  # Default (mp3)

def upload_file(file_path, api_key):
    """Uploads the file to Gemini Media API."""
    url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}"

    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    mime_type = _guess_mime_type(file_path)

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
    return file_uri, file_name_api, mime_type

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

def transcribe_chunk(file_uri, mime_type, api_key, model=DEFAULT_MODEL, context=None, chunk_index=0):
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
                {"file_data": {"mime_type": mime_type, "file_uri": file_uri}}
            ]
        }],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
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
        except (KeyError, IndexError):
            candidate = (result.get('candidates') or [{}])[0]
            finish_reason = candidate.get('finishReason', 'UNKNOWN')
            prompt_feedback = result.get('promptFeedback')
            print(f"\nWarning: No transcript text in response. finishReason={finish_reason}, promptFeedback={prompt_feedback}")
            # Raise (rather than return a placeholder) so the caller's fallback
            # chain actually fires instead of silently accepting a dropped segment.
            raise RuntimeError(f"Gemini returned no transcript text (finishReason={finish_reason})")

    except requests.exceptions.Timeout:
        done = True
        spinner_thread.join()
        print("\nError: Request timed out after 600 seconds.")
        raise
    except Exception as e:
        done = True
        spinner_thread.join()
        print(f"\nError requesting transcription: {e}")
        try:
            if 'response' in locals():
                print(json.dumps(response.json(), indent=2))
        except:
            pass
        raise

def process_file_or_chunk(file_path, api_key, model, context, chunk_index=0,
                          openrouter_key=None, fallback_chain=None, elevenlabs_key=None):
    """Orchestrates upload, wait, and transcribe for a single file/chunk.
    Fallback order on Gemini failure: ElevenLabs Scribe (diarization-capable,
    primary fallback per #4001), then the OpenRouter fallback_chain in order."""
    mime_type = _guess_mime_type(file_path)
    try:
        file_uri, file_name_api, mime_type = upload_file(file_path, api_key)
        wait_for_file(file_name_api, api_key)
        return transcribe_chunk(file_uri, mime_type, api_key, model, context, chunk_index)
    except Exception as gemini_err:
        print(f"\nGemini failed ({gemini_err}).")

        if elevenlabs_key:
            print("Trying ElevenLabs Scribe fallback...")
            try:
                return transcribe_chunk_elevenlabs(file_path, elevenlabs_key, mime_type, chunk_index)
            except Exception as el_err:
                print(f"ElevenLabs Scribe failed ({el_err}). Trying OpenRouter fallback chain...")

        if not openrouter_key or not fallback_chain:
            raise

        for fallback_model in fallback_chain:
            print(f"Trying OpenRouter fallback: {fallback_model}...")
            try:
                return transcribe_chunk_openrouter(file_path, openrouter_key, fallback_model, context, chunk_index)
            except Exception as or_err:
                print(f"OpenRouter/{fallback_model} failed ({or_err}). Trying next fallback...")
        raise RuntimeError(f"All fallbacks exhausted for {os.path.basename(file_path)}")

def main():
    parser = argparse.ArgumentParser(description="Transcribe audio using Gemini, with ElevenLabs Scribe then OpenRouter fallback chain.")
    parser.add_argument("file_path", help="Path to the audio file.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--fallback-chain", nargs="+", default=OPENROUTER_FALLBACK_CHAIN,
                        metavar="MODEL",
                        help=f"Ordered OpenRouter fallback models (default: {' '.join(OPENROUTER_FALLBACK_CHAIN)})")
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
    elevenlabs_key = get_elevenlabs_api_key()
    openrouter_key = get_openrouter_api_key()
    if elevenlabs_key:
        print("ElevenLabs Scribe fallback: enabled (primary fallback on Gemini failure)")
    else:
        print("Warning: No ElevenLabs key found — falling straight through to OpenRouter chain on Gemini failure.")
    if openrouter_key:
        print(f"OpenRouter fallback chain: {' -> '.join(args.fallback_chain)}")
    else:
        print("Warning: No OpenRouter key found — Gemini errors will not be retried past ElevenLabs.")

    # Check duration
    duration = get_audio_duration(args.file_path)
    full_transcript = ""

    kwargs = dict(openrouter_key=openrouter_key, fallback_chain=args.fallback_chain, elevenlabs_key=elevenlabs_key)

    try:
        if duration > CHUNK_THRESHOLD_SECONDS:
            print(f"File duration ({duration:.2f}s) exceeds threshold ({CHUNK_THRESHOLD_SECONDS}s). Splitting...")
            chunks = split_audio(args.file_path)

            for i, chunk_path in enumerate(chunks):
                print(f"\n--- Processing Chunk {i+1}/{len(chunks)}: {os.path.basename(chunk_path)} ---")
                chunk_transcript = process_file_or_chunk(chunk_path, api_key, args.model, args.context, chunk_index=i, **kwargs)
                full_transcript += f"\n\n--- Segment {i+1} ---\n{chunk_transcript}"

                # Cleanup chunk
                os.remove(chunk_path)

            print("\nAll chunks processed.")
        else:
            full_transcript = process_file_or_chunk(args.file_path, api_key, args.model, args.context, **kwargs)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)

    # Post-assembly guard (#4001): hard-fail rather than silently write an
    # incomplete transcript if any segment's fallback chain was fully exhausted
    # but somehow returned empty/placeholder content anyway.
    if not full_transcript.strip() or "[No transcript generated" in full_transcript:
        print("\nFatal error: assembled transcript is empty or contains a failure placeholder. Not writing output.")
        sys.exit(1)

    output_path = os.path.splitext(args.file_path)[0] + "_transcription.txt"
    with open(output_path, 'w') as f:
        f.write(full_transcript)

    print(f"\nTranscription complete! Saved to: {output_path}")

if __name__ == "__main__":
    main()
