"""
navigation.py — Navigation decision logic (SINGLE SOURCE OF TRUTH FOR ALL ANGLE MATH)
----------------------------------------------------------------------------------------
Given the bot's position/heading and the target's position/size,
decide whether to go FORWARD, LEFT, RIGHT, or STOP (target reached).

COORDINATE CONVENTION:
    All angles use MATHEMATICAL COORDINATES (x right, y UP).
    OpenCV gives us image coords (x right, y DOWN), so we NEGATE dy before atan2:
    math.atan2(-dy, dx) where dy = y2 - y1 (raw image), dx = x2 - x1.
    
WHY THE OLD RAW IMAGE COORDINATE APPROACH FAILED:
    Using raw image coords where Y increases downward causes angles to behave
    opposite to normal navigation intuition:
        - When target is visually to the RIGHT (larger x, larger y in image),
          atan2(dy, dx) with positive dy gives a positive angle
        - But if the robot is already facing downward (positive angle in image coords),
          the angle_error = target_angle - bot_heading can become NEGATIVE
        - This causes the system to command LEFT when it should command RIGHT
    
    Fix: use MATHEMATICAL coordinates (Y-up) consistently by negating dy in BOTH
    bot_heading and target_angle calculations. This makes angles behave as expected:
        - 0° = East (right)
        - 90° = North (up/toward top of image)
        - ±180° = West (left)
        - -90° = South (down/toward bottom of image)

ANTI-OSCILLATION IMPROVEMENTS:
    1. Angle smoothing: exponential moving average to reduce noise
    2. Hysteresis: separate ENTER/EXIT thresholds to prevent command flapping
    3. Command stability: minimum duration before allowing direction changes
    4. Circular angle handling: proper averaging near ±180° boundary
"""

import math
import time
import config


def normalize_angle_deg(angle):
    """
    Normalize an angle to the range (-180, 180] degrees.
    
    Examples:
        270° -> -90°
        -200° -> 160°
        180° -> 180°
        -180° -> 180°
    """
    while angle > 180:
        angle -= 360
    while angle <= -180:
        angle += 360
    return angle


def circular_lerp_deg(angle1, angle2, alpha):
    """
    Linear interpolation between two angles, handling wraparound at ±180°.
    
    This prevents incorrect averaging like:
        lerp(179°, -179°, 0.5) = 0°  (WRONG!)
    Instead gives:
        lerp(179°, -179°, 0.5) = 180° or -180°  (CORRECT)
    
    Args:
        angle1: first angle (degrees)
        angle2: second angle (degrees)
        alpha: blend factor (0 = all angle1, 1 = all angle2)
    
    Returns:
        Interpolated angle in degrees, normalized to (-180, 180].
    """
    # Compute the shortest angular difference
    diff = normalize_angle_deg(angle2 - angle1)
    # Blend along the shortest path
    result = angle1 + alpha * diff
    return normalize_angle_deg(result)


def bot_heading_deg(bot_corners):
    """
    Compute the robot's actual heading (the direction its front is facing).
    
    Steps:
        1. Get marker's raw printed orientation (top edge direction, Y-up coords)
        2. Add the mounting offset (marker may not be aligned with robot front)
        3. Normalize to (-180, 180]
    
    Args:
        bot_corners: 4x2 array of marker corners from ArUco detection
    
    Returns:
        Robot heading in degrees, mathematical coordinate convention (Y-up).
    """
    from aruco_detection import marker_raw_angle_deg
    
    raw_angle = marker_raw_angle_deg(bot_corners)
    heading = raw_angle + config.BOT_MARKER_HEADING_OFFSET_DEG
    return normalize_angle_deg(heading)


def target_angle_deg(bot_center, target_center):
    """
    Compute the angle from the bot's center to the target's center.
    
    Uses MATHEMATICAL COORDINATES (Y-axis up):
        dx = target_x - bot_x
        dy = target_y - bot_y  (raw image coords, y increases downward)
        angle = atan2(-dy, dx)  <- NEGATIVE dy for mathematical Y-up convention
    
    Args:
        bot_center: (x, y) tuple
        target_center: (x, y) tuple
    
    Returns:
        Angle in degrees, normalized to (-180, 180].
    """
    dx = target_center[0] - bot_center[0]
    dy = target_center[1] - bot_center[1]  # Raw image coords (y increases downward)
    angle = math.degrees(math.atan2(-dy, dx))  # Negate dy for mathematical Y-up
    return normalize_angle_deg(angle)


def angle_error_deg(bot_heading, target_angle):
    """
    Compute the angle error between robot heading and target direction.
    
    Formula:
        angle_error = target_angle - bot_heading
    
    Sign convention:
        - Positive error: target is to the RIGHT of bot heading -> turn RIGHT
        - Negative error: target is to the LEFT of bot heading -> turn LEFT
        - Zero error: target is straight ahead -> go FORWARD
    
    Args:
        bot_heading: robot's current heading (degrees)
        target_angle: angle from bot to target (degrees)
    
    Returns:
        Angle error in degrees, normalized to (-180, 180].
    """
    error = target_angle - bot_heading
    return normalize_angle_deg(error)


class NavigationController:
    """
    Stateful navigation controller with smoothing, hysteresis, and command stability.
    
    This class maintains state across frames to:
        1. Smooth noisy angle measurements
        2. Prevent command oscillation using hysteresis
        3. Enforce minimum command duration for stability
        4. PID control for smooth continuous steering
    """
    
    def __init__(self):
        self.smoothed_error = None  # Smoothed angle error (degrees)
        self.current_command = "STOP"
        self.last_command_change_time = 0.0
        
        # PID state
        self.previous_error = None
        self.integral = 0.0
        self.last_update_time = None
    
    def reset(self):
        """Reset all state (call when markers are lost)."""
        self.smoothed_error = None
        self.current_command = "STOP"
        self.last_command_change_time = 0.0
        
        # Reset PID state
        self.previous_error = None
        self.integral = 0.0
        self.last_update_time = None
    
    def update(self, raw_angle_error, target_marker_size_px):
        """
        Update navigation state and decide command with smoothing and hysteresis.
        
        Args:
            raw_angle_error: current angle error (degrees, unsmoothed)
            target_marker_size_px: apparent size of target marker
        
        Returns:
            tuple: (command, smoothed_error)
                command: "STOP", "FORWARD", "LEFT", or "RIGHT"
                smoothed_error: smoothed angle error for display
        """
        # Step 1: Smooth the angle error using circular interpolation
        if self.smoothed_error is None:
            # First measurement - initialize with raw value
            self.smoothed_error = raw_angle_error
        else:
            # Exponential moving average with circular angle handling
            self.smoothed_error = circular_lerp_deg(
                self.smoothed_error,
                raw_angle_error,
                config.ANGLE_SMOOTHING_ALPHA
            )
        
        # Step 2: Check if target is reached (distance check)
        if target_marker_size_px >= config.STOP_MARKER_SIZE_PX:
            self._change_command("STOP")
            return self.current_command, self.smoothed_error
        
        # Step 3: Decide command using hysteresis
        new_command = self._decide_with_hysteresis(self.smoothed_error)
        
        # Step 4: Apply command stability (minimum duration)
        current_time = time.time()
        time_since_change = current_time - self.last_command_change_time
        
        # Allow command change if:
        # - New command is STOP (safety override)
        # - Enough time has passed since last change
        # - Current command is STOP (always allow exit from stop)
        if (new_command == "STOP" or 
            time_since_change >= config.MIN_COMMAND_DURATION or
            self.current_command == "STOP"):
            self._change_command(new_command)
        
        return self.current_command, self.smoothed_error
    
    def _decide_with_hysteresis(self, smoothed_error):
        """
        Decide command using hysteresis thresholds.
        
        Hysteresis prevents oscillation:
            - To ENTER a turn: |error| must exceed TURN_ENTER_DEG
            - To EXIT a turn: |error| must drop below TURN_EXIT_DEG
        
        Args:
            smoothed_error: smoothed angle error (degrees)
        
        Returns:
            Command string: "FORWARD", "LEFT", or "RIGHT"
        """
        # Determine thresholds based on current state
        if self.current_command == "FORWARD" or self.current_command == "STOP":
            # Currently not turning - use ENTER threshold
            threshold = config.TURN_ENTER_DEG
        else:
            # Currently turning - use EXIT threshold (lower, creates hysteresis)
            threshold = config.TURN_EXIT_DEG
        
        # Decide based on smoothed error and threshold
        if smoothed_error > threshold:
            return "RIGHT"
        elif smoothed_error < -threshold:
            return "LEFT"
        else:
            return "FORWARD"
    
    def _change_command(self, new_command):
        """Update current command and timestamp."""
        if new_command != self.current_command:
            self.current_command = new_command
            self.last_command_change_time = time.time()
    
    def compute_pid(self, smoothed_error, target_marker_size_px):
        """
        Compute PID control output for smooth continuous steering.
        
        This replaces discrete LEFT/RIGHT/FORWARD commands with continuous
        motor speed adjustments: left_speed = BASE + correction, right_speed = BASE - correction.
        
        Sign convention (verified from ESP32 code):
            - Positive error (target to RIGHT) -> positive correction -> increase left motor speed
            - Negative error (target to LEFT) -> negative correction -> increase right motor speed
        
        Args:
            smoothed_error: smoothed angle error (degrees)
            target_marker_size_px: apparent size of target marker
        
        Returns:
            dict with keys:
                left_speed: int (0-255 PWM)
                right_speed: int (0-255 PWM)
                p_term: float (proportional component)
                i_term: float (integral component)
                d_term: float (derivative component)
                correction: float (total correction before clamping)
                is_stopped: bool (True if target reached)
        """
        current_time = time.time()
        
        # Check if target is reached (distance check)
        if target_marker_size_px >= config.STOP_MARKER_SIZE_PX:
            # Target reached - stop motors and reset PID state
            self.previous_error = None
            self.integral = 0.0
            self.last_update_time = None
            return {
                'left_speed': 0,
                'right_speed': 0,
                'p_term': 0.0,
                'i_term': 0.0,
                'd_term': 0.0,
                'correction': 0.0,
                'is_stopped': True
            }
        
        # Adaptive base speed: slow down when close to target
        if target_marker_size_px >= config.SLOW_DOWN_DISTANCE_PX:
            base_speed = config.SLOW_DOWN_SPEED
        else:
            base_speed = config.BASE_SPEED
        
        # --- Proportional term ---
        p_term = config.KP * smoothed_error
        
        # --- Derivative term ---
        d_term = 0.0
        if self.previous_error is not None and self.last_update_time is not None:
            dt = current_time - self.last_update_time
            if dt > 0:  # Avoid division by zero
                error_change = smoothed_error - self.previous_error
                d_term = config.KD * (error_change / dt)
        
        # --- Integral term ---
        i_term = 0.0
        if config.KI > 0 and self.last_update_time is not None:
            dt = current_time - self.last_update_time
            if dt > 0:
                self.integral += smoothed_error * dt
                # Anti-windup clamping
                self.integral = max(-config.MAX_INTEGRAL, min(config.MAX_INTEGRAL, self.integral))
                i_term = config.KI * self.integral
        
        # --- Total correction ---
        correction = p_term + i_term + d_term
        
        # Clamp correction to limits
        correction = max(-config.MAX_CORRECTION, min(config.MAX_CORRECTION, correction))
        
        # Compute motor speeds
        # Positive correction -> increase left motor (turn right to correct rightward error)
        # Negative correction -> increase right motor (turn left to correct leftward error)
        left_speed = base_speed + correction
        right_speed = base_speed - correction
        
        # Clamp motor speeds to valid range
        left_speed = int(max(config.MIN_SPEED, min(config.MAX_SPEED, left_speed)))
        right_speed = int(max(config.MIN_SPEED, min(config.MAX_SPEED, right_speed)))
        
        # Update state for next iteration
        self.previous_error = smoothed_error
        self.last_update_time = current_time
        
        return {
            'left_speed': left_speed,
            'right_speed': right_speed,
            'p_term': p_term,
            'i_term': i_term,
            'd_term': d_term,
            'correction': correction,
            'is_stopped': False
        }


# Global controller instance (singleton pattern)
_controller = NavigationController()


def compute_navigation(bot_corners, target_corners):
    """
    High-level navigation computation: given bot and target markers,
    compute all angles, errors, and the command to send.
    
    This function uses the global NavigationController to maintain state
    across frames for smoothing and hysteresis.
    
    Args:
        bot_corners: 4x2 array of bot marker corners
        target_corners: 4x2 array of target marker corners
    
    Returns:
        Dictionary with keys:
            - bot_center: (x, y)
            - bot_heading: degrees
            - target_center: (x, y)
            - target_angle: degrees
            - angle_error_raw: degrees (unsmoothed)
            - angle_error_smoothed: degrees (smoothed, used for control)
            - target_size_px: float
            - command: string ("FORWARD", "LEFT", "RIGHT", "STOP")
    """
    from aruco_detection import marker_center, marker_size
    
    bot_ctr = marker_center(bot_corners)
    target_ctr = marker_center(target_corners)
    
    bot_hdg = bot_heading_deg(bot_corners)
    tgt_angle = target_angle_deg(bot_ctr, target_ctr)
    raw_error = angle_error_deg(bot_hdg, tgt_angle)
    
    tgt_size = marker_size(target_corners)
    
    # Use controller to get smoothed error and stable command
    cmd, smoothed_error = _controller.update(raw_error, tgt_size)
    
    return {
        "bot_center": bot_ctr,
        "bot_heading": bot_hdg,
        "target_center": target_ctr,
        "target_angle": tgt_angle,
        "angle_error_raw": raw_error,
        "angle_error_smoothed": smoothed_error,
        "target_size_px": tgt_size,
        "command": cmd,
    }


def reset_navigation_state():
    """
    Reset the navigation controller state.
    
    Call this when markers are lost or at the start of navigation.
    """
    _controller.reset()


def print_debug(nav):
    """
    Print navigation debug info to console (useful for calibration mode).
    
    Args:
        nav: dictionary returned by compute_navigation()
    """
    print("=" * 70)
    print(f"BOT CENTER:        ({nav['bot_center'][0]:.1f}, {nav['bot_center'][1]:.1f})")
    print(f"BOT HEADING:       {nav['bot_heading']:+7.2f}°")
    print(f"TARGET CENTER:     ({nav['target_center'][0]:.1f}, {nav['target_center'][1]:.1f})")
    print(f"TARGET ANGLE:      {nav['target_angle']:+7.2f}°")
    print(f"RAW ERROR:         {nav['angle_error_raw']:+7.2f}°")
    print(f"SMOOTHED ERROR:    {nav['angle_error_smoothed']:+7.2f}°")
    print(f"TARGET SIZE:       {nav['target_size_px']:.1f} px")
    print(f"COMMAND:           {nav['command']}")
    print("=" * 70)
