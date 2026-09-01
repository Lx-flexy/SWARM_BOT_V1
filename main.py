"""
main.py — SWARM BOT control loop (V1: one robot, one target)
------------------------------------------------------------------
Pipeline per frame:
    capture -> detect ArUco markers -> find BOT + TARGET
    -> compute navigation (angles, error, command) -> send to ESP32
    -> draw debug UI -> repeat

Usage:
    Normal mode:
        python main.py
    
    Calibration mode (no HTTP commands sent):
        python main.py --calibrate
        
        Place robot facing target manually, observe debug output.
        Tune config.BOT_MARKER_HEADING_OFFSET_DEG until:
            BOT HEADING ≈ TARGET ANGLE
            ANGLE ERROR ≈ 0°
            COMMAND == FORWARD

Setup:
    1. Install dependencies: pip install opencv-contrib-python requests
    2. Upload swarm_bot_esp32.ino to ESP32, note its IP from Serial Monitor
    3. Set ESP32_IP in config.py
    4. Print ArUco markers (DICT_4X4_50): ID=1 for robot, ID=25 for target
"""

import sys
import cv2

import config
from aruco_detection import (
    create_detector,
    detect_markers,
    draw_marker_info,
)
from navigation import compute_navigation, print_debug, reset_navigation_state
from communication import ESP32Link


def send_command(command, link, calibrate_mode):
    """
    Pluggable command sender: sends HTTP command in normal mode,
    prints to console in calibrate mode.
    
    Args:
        command: string ("FORWARD", "LEFT", "RIGHT", "STOP")
        link: ESP32Link instance
        calibrate_mode: bool, if True skip HTTP send
    """
    if calibrate_mode:
        print(f"[CALIBRATE] Would send: {command}")
    else:
        link.send(command.lower(), force=(command == "STOP"))


def draw_ui(frame, nav, bot_found, target_found, status, calibrate_mode, pid_data=None):
    """
    Draw navigation debug overlay on the video frame.
    
    Args:
        frame: OpenCV image
        nav: navigation dict from compute_navigation() (or None)
        bot_found: bool
        target_found: bool
        status: string (status message)
        calibrate_mode: bool
        pid_data: dict with PID components (or None)
    """
    h, w = frame.shape[:2]
    y = 30
    line_gap = 28

    def put(text, color=(255, 255, 255)):
        nonlocal y
        cv2.putText(frame, text, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        y += line_gap

    # Header
    mode_str = " [CALIBRATE MODE]" if calibrate_mode else " [PID MODE]"
    put(f"SWARM BOT{mode_str}", (255, 255, 0))
    put(f"BOT ID: {config.BOT_MARKER_ID}   TARGET ID: {config.TARGET_MARKER_ID}")

    # Bot status
    if bot_found and nav:
        put(f"BOT CENTER:   ({nav['bot_center'][0]:.1f}, {nav['bot_center'][1]:.1f})")
        put(f"BOT HEADING:  {nav['bot_heading']:+7.2f} deg")
    else:
        put("BOT NOT FOUND", (0, 0, 255))

    # Target status
    if target_found and nav:
        put(f"TARGET CENTER: ({nav['target_center'][0]:.1f}, {nav['target_center'][1]:.1f})")
        put(f"TARGET ANGLE:  {nav['target_angle']:+7.2f} deg")
        put(f"TARGET SIZE:   {nav['target_size_px']:.1f} px")
    else:
        put("TARGET NOT FOUND", (0, 0, 255))

    # Angle error and command
    if nav:
        # Display both raw and smoothed errors
        put(f"RAW ERROR:     {nav['angle_error_raw']:+7.2f} deg", (150, 150, 150))
        
        err_color = (0, 255, 0) if abs(nav['angle_error_smoothed']) < config.TURN_EXIT_DEG else (0, 165, 255)
        put(f"SMOOTHED ERROR: {nav['angle_error_smoothed']:+7.2f} deg", err_color)
        
        # Show PID data if available
        if pid_data:
            put(f"P: {pid_data['p_term']:+6.2f}  I: {pid_data['i_term']:+6.2f}  D: {pid_data['d_term']:+6.2f}", (150, 255, 150))
            put(f"CORRECTION:    {pid_data['correction']:+7.2f}", (150, 255, 150))
            put(f"LEFT SPEED:    {pid_data['left_speed']:3d}    RIGHT SPEED: {pid_data['right_speed']:3d}", (0, 255, 255))
        else:
            # Legacy command display
            cmd = nav['command']
            cmd_color = (0, 255, 0) if cmd == "FORWARD" else \
                        (0, 165, 255) if cmd in ("LEFT", "RIGHT") else (0, 0, 255)
            put(f"COMMAND:      {cmd}", cmd_color)
    
    put(f"STATUS:       {status}", (255, 255, 255))

    # Draw visual aids if both markers found
    if nav:
        bx, by = int(nav['bot_center'][0]), int(nav['bot_center'][1])
        tx, ty = int(nav['target_center'][0]), int(nav['target_center'][1])
        
        # Line from bot to target
        cv2.line(frame, (bx, by), (tx, ty), (255, 255, 0), 2)
        
        # Bot heading arrow (50 px long) from bot center
        import math
        hd_rad = math.radians(nav['bot_heading'])
        hx = int(bx + 50 * math.cos(hd_rad))
        hy = int(by + 50 * math.sin(hd_rad))
        cv2.arrowedLine(frame, (bx, by), (hx, hy), (0, 255, 255), 3, tipLength=0.3)


def main():
    # Parse command-line args
    calibrate_mode = "--calibrate" in sys.argv
    
    if calibrate_mode:
        print("\n" + "=" * 70)
        print("CALIBRATION MODE ENABLED")
        print("=" * 70)
        print("Place the robot facing the target marker manually.")
        print("Observe the debug output below.")
        print("Tune config.BOT_MARKER_HEADING_OFFSET_DEG until:")
        print("  - BOT HEADING ≈ TARGET ANGLE")
        print("  - ANGLE ERROR ≈ 0°")
        print("  - COMMAND == FORWARD")
        print("Press 'q' to quit.")
        print("=" * 70 + "\n")
    
    detector = create_detector()
    link = ESP32Link() if not calibrate_mode else None

    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

    bot_missing_frames = 0
    target_missing_frames = 0
    
    # Reset navigation state at startup
    reset_navigation_state()

    print(f"SWARM BOT navigation started ({'CALIBRATE' if calibrate_mode else 'NORMAL'} mode). Press 'q' to quit.\n")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Camera read failed.")
            break

        markers = detect_markers(detector, frame)

        # Check for bot marker
        bot_found = config.BOT_MARKER_ID in markers
        if bot_found:
            bot_corners = markers[config.BOT_MARKER_ID]
            draw_marker_info(frame, bot_corners, config.BOT_MARKER_ID, color=(0, 255, 0))
            bot_missing_frames = 0
        else:
            bot_missing_frames += 1

        # Check for target marker
        target_found = config.TARGET_MARKER_ID in markers
        if target_found:
            target_corners = markers[config.TARGET_MARKER_ID]
            draw_marker_info(frame, target_corners, config.TARGET_MARKER_ID, color=(255, 0, 0))
            target_missing_frames = 0
        else:
            target_missing_frames += 1

        # ---------------- Navigation decision ----------------
        nav = None
        pid_data = None
        command = "STOP"
        status = "NAVIGATING"

        if bot_missing_frames >= config.MAX_MISSING_FRAMES:
            command = "STOP"
            status = "BOT NOT FOUND"
            reset_navigation_state()  # Reset smoothing when markers lost
        elif target_missing_frames >= config.MAX_MISSING_FRAMES:
            command = "STOP"
            status = "TARGET NOT FOUND"
            reset_navigation_state()  # Reset smoothing when markers lost
        elif bot_found and target_found:
            # Compute full navigation
            nav = compute_navigation(bot_corners, target_corners)
            
            if calibrate_mode:
                # In calibrate mode, use legacy command system for display
                command = nav['command']
                status = "TARGET REACHED" if command == "STOP" else "NAVIGATING"
                print_debug(nav)
            else:
                # Normal mode: use PID control for smooth steering
                from navigation import _controller
                pid_data = _controller.compute_pid(
                    nav['angle_error_smoothed'],
                    nav['target_size_px']
                )
                
                if pid_data['is_stopped']:
                    command = "STOP"
                    status = "TARGET REACHED"
                else:
                    status = "NAVIGATING (PID)"
        else:
            # One marker missing but not past threshold yet
            command = "STOP"
            status = "WAITING FOR MARKERS"

        # Send command (or print in calibrate mode)
        if not calibrate_mode and link:
            if pid_data is not None and not pid_data['is_stopped']:
                # Use PID motor control
                link.send_motor_speeds(pid_data['left_speed'], pid_data['right_speed'])
            else:
                # Send STOP for: bot/target missing, target reached, or any error case
                link.send('stop', force=True)
        elif calibrate_mode and nav:
            # In calibrate mode, only print when we have valid nav data
            pass  # already printed by print_debug above

        # Draw UI overlay
        draw_ui(frame, nav, bot_found, target_found, status, calibrate_mode, pid_data)
        cv2.imshow("SWARM BOT - ArUco Navigation", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            if not calibrate_mode and link:
                link.send("stop", force=True)
            break

    cap.release()
    cv2.destroyAllWindows()
    print("\nShutdown complete.")


if __name__ == "__main__":
    main()
