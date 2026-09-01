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

    def send_motor_speeds(self, left_speed, right_speed):
        """
        Send individual motor speeds to ESP32 for PID-based smooth steering.
        
        This bypasses the discrete command system and directly controls
        both motors with independent PWM values while maintaining forward direction.
        
        Throttles sends to MOTOR_SEND_INTERVAL_S to prevent overwhelming ESP32's
        single-threaded WebServer with too many connections per second.
        
        Args:
            left_speed: int (0-255 PWM value for left motor)
            right_speed: int (0-255 PWM value for right motor)
        
        Returns:
            bool: True if successful, False on error
        """
        now = time.time()
        
        # Throttle: skip if not enough time has elapsed since last send
        if (now - self.last_sent_time) < config.MOTOR_SEND_INTERVAL_S:
            return True  # skip, treat as success/no-op
        
        try:
            # Cast to int in case PID output is float
            left_speed = int(left_speed)
            right_speed = int(right_speed)
            
            url = f"{config.BASE_URL}/set_motors?left={left_speed}&right={right_speed}"
            requests.get(url, timeout=config.REQUEST_TIMEOUT)
            self.last_sent_time = now
            # Don't update last_command since this is a different control mode
            return True
        except requests.exceptions.RequestException as e:
            print(f"[communication] Could not send motor speeds to ESP32: {e}")
            return False
