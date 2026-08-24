#!/usr/bin/env python3
import sys, os, time, threading, subprocess, io, wave
import re
from pynput import keyboard
import pyaudio

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

class PTTDaemon:
    def __init__(self):
        # Listen for both Key.alt_r and Key.alt_gr to handle all keyboard layout variants
        self.target_keys = {keyboard.Key.alt_r, getattr(keyboard.Key, 'alt_gr', keyboard.Key.alt_r)}
        self.is_recording = False
        self.frames = []
        self.pa = pyaudio.PyAudio()
        self.lock = threading.Lock()
        self.stream = None

    def start_recording(self):
        with self.lock:
            if self.is_recording:
                return
            self.is_recording = True
            self.frames = []
            subprocess.Popen(["notify-send", "-t", "800", "-i", "audio-input-microphone", "Voice Typing (PTT)", "Listening..."])
            try:
                self.stream = self.pa.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
            except Exception as e:
                print(f"Error opening audio stream: {e}", file=sys.stderr)
                self.is_recording = False
                return
            threading.Thread(target=self._record_loop, daemon=True).start()

    def _record_loop(self):
        while self.is_recording and self.stream:
            try:
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                self.frames.append(data)
            except Exception:
                break

    def stop_recording(self):
        with self.lock:
            if not self.is_recording:
                return
            self.is_recording = False
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

            if len(self.frames) < 8:  # less than ~0.5s audio
                return

            wav_path = "/tmp/ptt_input.wav"
            wf = wave.open(wav_path, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.pa.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(self.frames))
            wf.close()

            threading.Thread(target=self._transcribe_and_inject, args=(wav_path,), daemon=True).start()

    def _transcribe_and_inject(self, wav_path):
        try:
            subprocess.Popen(["notify-send", "-t", "800", "-i", "audio-input-microphone", "Voice Typing (PTT)", "Transcribing..."])
            cmd = ["/home/will/.local/bin/whisper-local", wav_path, "--model", "base.en", "--language", "en"]
            res = subprocess.check_output(cmd).decode()
            lines = [re.sub(r'^\[[0-9:.]+ --> [0-9:.]+\]\s*', '', l).strip() for l in res.strip().split('\n') if l.strip()]
            text = " ".join(lines)
            if text:
                print(f"Transcribed (CUDA): {text}")
                subprocess.run(["xdotool", "type", "--delay", "12", text + " "])
        except Exception as e:
            print(f"Transcription error: {e}", file=sys.stderr)
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def on_press(self, key):
        if key in self.target_keys:
            self.start_recording()

    def on_release(self, key):
        if key in self.target_keys:
            self.stop_recording()

    def run(self):
        print("Starting GPU PTT Daemon listening on Right Alt (Alt_R / AltGr)...")
        with keyboard.Listener(on_press=self.on_press, on_release=self.on_release) as listener:
            listener.join()

if __name__ == '__main__':
    daemon = PTTDaemon()
    daemon.run()
