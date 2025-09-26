import pygame
import threading
import time
import os
from pydub import AudioSegment
from pydub.playback import play
import tempfile

class SoundEffects:
    def __init__(self, sound_folder="arena_sounds"):
        pygame.mixer.init()
        self.sound_folder = sound_folder
        self.sounds = {}

        # Preload common sound effects
        self.load_sound("countdown", "3sec_countdown.wav")
        self.load_sound("chase_seq", "chase_seq.wav", volume=0.5)        # half volume

    def load_sound(self, name, filename, volume=1.0):
        """Load a sound, convert to mono, and set volume (0.0 → 1.0)."""
        path = os.path.join(self.sound_folder, filename)
        if os.path.exists(path):
            audio = AudioSegment.from_file(path)
            audio_mono = audio.set_channels(1)  # mix to mono

            temp_path = os.path.join(tempfile.gettempdir(), f"{name}_mono.wav")
            audio_mono.export(temp_path, format="wav")

            sound = pygame.mixer.Sound(temp_path)
            sound.set_volume(volume)  # volume per effect
            self.sounds[name] = sound
        else:
            print(f"[SoundEffects] Warning: Sound file not found: {path}")

    def play_sound(self, name, blocking=False):
        """Play a sound by name. If blocking=True, waits until finished."""
        if name not in self.sounds:
            print(f"[SoundEffects] Sound '{name}' not loaded!")
            return

        sound = self.sounds[name]
        if blocking:
            sound.play()
            time.sleep(sound.get_length())
        else:
            # Play in a separate thread to be non-blocking
            threading.Thread(target=lambda: sound.play(), daemon=True).start()

    # Example effects
    def countdown_3sec(self):
        self.play_sound("countdown")
    
    def chase_seq(self):
        time.sleep(1.5)
        self.play_sound("chase_seq")
