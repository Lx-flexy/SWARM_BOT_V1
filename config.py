"""
config.py — SWARM BOT configuration
--------------------------------------
All tunable parameters live here so you don't have to dig through logic code.
"""

import cv2

# ---------------- ESP32 connection ----------------
ESP32_IP = "192.168.29.68"          # <-- set this to your ESP32's IP from Serial Monitor
BASE_URL = f"http://{ESP32_IP}"
COMMAND_COOLDOWN = 0.25              # min seconds between sending the SAME command again
REQUEST_TIMEOUT = 0.4                # seconds to wait for ESP32 HTTP response

# ---------------- Camera ----------------
CAMERA_INDEX = 1
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

# ---------------- ArUco setup ----------------
ARUCO_DICT_NAME = cv2.aruco.DICT_4X4_50
BOT_MARKER_ID = 1
TARGET_MARKER_ID = 25

# ============================================================================
# COORDINATE CONVENTION (CRITICAL — DO NOT MIX!)
# ============================================================================
# All angle calculations use MATHEMATICAL COORDINATES:
#   - X-axis: points RIGHT (increases left-to-right)
#   - Y-axis: points UP (standard mathematical convention)
#   - OpenCV image coords have Y increasing DOWNWARD, so we NEGATE dy:
#   - Angles computed with: math.atan2(-dy, dx) where:
#       dy = y2 - y1 (raw image coords)
#       dx = x2 - x1
#   - The negative sign on dy converts from image coords to mathematical coords
#
# Why this matters:
#   Using raw image coordinates (y down) causes angles to behave opposite to
#   navigation intuition. When the target is physically to the RIGHT, we need
#   angle_error to be POSITIVE so the system commands RIGHT turn. Mathematical
#   coordinates (y up) achieve this naturally.
#
# The marker's printed orientation (top edge) does NOT necessarily align with
# the robot's physical front. Use BOT_MARKER_HEADING_OFFSET_DEG to compensate.
# ============================================================================

# ---------------- Navigation tuning ----------------
# Offset (in degrees) between the marker's printed top edge and the robot's
# actual front direction. Positive = robot front is rotated clockwise from marker top.
# To calibrate: run `python main.py --calibrate`, manually align robot to face
# target, then adjust this offset until BOT HEADING ≈ TARGET ANGLE (angle_error ≈ 0°).
BOT_MARKER_HEADING_OFFSET_DEG = 0.0

# ============================================================================
# ANTI-OSCILLATION PARAMETERS
# ============================================================================
# These parameters prevent the robot from constantly switching between
# LEFT/RIGHT/FORWARD commands due to noisy angle measurements.

# --- Angle smoothing ---
# Exponential moving average alpha for angle smoothing (0 to 1).
# Lower values = more smoothing but slower response.
# Higher values = less smoothing but faster response.
# Recommended range: 0.2 to 0.4
ANGLE_SMOOTHING_ALPHA = 0.3

# --- Hysteresis thresholds ---
# To enter a turn (from FORWARD), angle error must exceed TURN_ENTER_DEG.
# To exit a turn (back to FORWARD), angle error must drop below TURN_EXIT_DEG.
# TURN_ENTER_DEG must be > TURN_EXIT_DEG to create hysteresis.
# Larger difference = more stable but less responsive.
TURN_ENTER_DEG = 25.0      # Start turning when |error| exceeds this
TURN_EXIT_DEG = 15.0       # Stop turning when |error| drops below this

# --- Command stability ---
# Minimum time (seconds) to hold a command before allowing a direction change.
# This prevents rapid command switching every frame.
# Too small: robot oscillates
# Too large: robot becomes unresponsive
# Recommended range: 0.1 to 0.3 seconds
MIN_COMMAND_DURATION = 0.15

# ============================================================================

# Marker "apparent size" (avg side length in pixels) used as a simple distance proxy.
# Bigger marker on screen = robot is closer to it.
# When target marker size >= this threshold, send STOP (target reached).
STOP_MARKER_SIZE_PX = 140.0   # px; tune this based on your camera height/marker size

# ---------------- Safety ----------------
# If bot or target marker is not seen for this many consecutive frames, send STOP.
MAX_MISSING_FRAMES = 5
