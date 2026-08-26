"""
aruco_detection.py — ArUco marker detection helpers
-------------------------------------------------------
Wraps OpenCV's ArUco API and provides convenient per-marker info:
    - center (x, y)
    - angle (degrees, mathematical coordinates Y-up) of the marker's printed orientation
    - apparent size (avg side length in px) -> used as distance proxy

IMPORTANT: This module returns the marker's printed orientation angle using
mathematical coordinates (Y-axis up), NOT the robot's heading. The robot's 
actual heading = raw angle + offset (see navigation.bot_heading_deg).
"""

import math
import cv2
import config


def create_detector():
    """Create and return an OpenCV ArUco detector using the configured dictionary."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(config.ARUCO_DICT_NAME)
    aruco_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
    return detector


def detect_markers(detector, frame):
    """
    Run ArUco detection on a frame.
    Returns a dict: {marker_id (int): corners (4x2 array)}
    """
    corners, ids, _ = detector.detectMarkers(frame)
    markers = {}
    if ids is not None:
        for marker_corners, marker_id in zip(corners, ids.flatten()):
            markers[int(marker_id)] = marker_corners.reshape(4, 2)
    return markers


def marker_center(corners):
    """Return (cx, cy) center of a marker given its 4 corners."""
    cx = float(corners[:, 0].mean())
    cy = float(corners[:, 1].mean())
    return cx, cy


def marker_raw_angle_deg(corners):
    """
    Compute the marker's printed orientation angle using MATHEMATICAL COORDINATES.
    
    Convention:
        - ArUco corners order: [top-left, top-right, bottom-right, bottom-left]
          as printed on the marker.
        - "Forward" direction of the marker = from center toward midpoint of TOP edge.
        - OpenCV image coords: X-axis points RIGHT, Y-axis points DOWN
        - We convert to mathematical coords by NEGATING dy before atan2:
            * dx = x_top_mid - x_center (unchanged)
            * dy = y_top_mid - y_center (raw image coords)
            * angle = atan2(-dy, dx)  <- NEGATIVE dy for mathematical Y-up convention
    
    Returns:
        Angle in degrees, using mathematical coordinate convention (Y-axis up).
        This is the marker's printed orientation, NOT the robot's heading.
        To get robot heading, add BOT_MARKER_HEADING_OFFSET_DEG (see navigation.py).
    """
    top_left, top_right = corners[0], corners[1]
    center = corners.mean(axis=0)
    top_mid = (top_left + top_right) / 2.0

    dx = top_mid[0] - center[0]
    dy = top_mid[1] - center[1]  # Raw image coords (y increases downward)
    angle = math.degrees(math.atan2(-dy, dx))  # Negate dy for mathematical Y-up
    return angle


def marker_size(corners):
    """
    Approximate apparent size of the marker (average side length in pixels).
    Larger value = marker appears bigger = robot is closer to it.
    """
    side_lengths = []
    for i in range(4):
        p1 = corners[i]
        p2 = corners[(i + 1) % 4]
        side_lengths.append(math.hypot(p2[0] - p1[0], p2[1] - p1[1]))
    return sum(side_lengths) / len(side_lengths)


def draw_marker_info(frame, corners, marker_id, color=(0, 255, 0)):
    """Draw a marker's outline, ID, and center dot on the frame."""
    pts = corners.astype(int)
    cv2.polylines(frame, [pts], True, color, 2)
    cx, cy = marker_center(corners)
    cv2.circle(frame, (int(cx), int(cy)), 5, color, cv2.FILLED)
    cv2.putText(frame, f"ID {marker_id}", (int(cx) + 10, int(cy) - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
