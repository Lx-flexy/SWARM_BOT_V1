"""
communication.py — Wi-Fi/HTTP communication with the ESP32
----------------------------------------------------------------
Sends high-level movement commands (forward/backward/left/right/stop)
to the ESP32 over HTTP. The ESP32 itself decides motor pin states/speed.
"""

import time
import requests
import config


class ESP32Link:
    def __init__(self):
        self.last_command = None
        self.last_sent_time = 0.0

    def send(self, command, force=False):
        """
        Send a command to the ESP32.
        By default, skips sending if the same command was just sent recently
        (cooldown), to avoid flooding the ESP32 with HTTP requests.
        Use force=True for critical commands like "stop".
        """
        now = time.time()
        if not force:
            if command == self.last_command and (now - self.last_sent_time) < config.COMMAND_COOLDOWN:
                return True  # skip, nothing changed

        try:
            requests.get(f"{config.BASE_URL}/{command}", timeout=config.REQUEST_TIMEOUT)
            self.last_command = command
            self.last_sent_time = now
            return True
        except requests.exceptions.RequestException as e:
            print(f"[communication] Could not reach ESP32 at {config.BASE_URL}: {e}")
            return False
