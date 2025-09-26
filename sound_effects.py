# sound_effects.py
import pygame
import threading
import time
import os

class SoundEffects:
    def __init__(self, sound_folder="arena_sounds"):
        pygame.mixer.init()
        self.sound_folder = sound_folder
        self.sounds = {}

        # Preload common sound effects
        self.load_sound("countdown", "3sec_countdown.wav")
        self.load_sound("chase_seq", "chase_seq.wav")

    def load_sound(self, name, filename):
        path = os.path.join(self.sound_folder, filename)
        if os.path.exists(path):
            self.sounds[name] = pygame.mixer.Sound(path)
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
        self.play_sound("chase_seq")

    