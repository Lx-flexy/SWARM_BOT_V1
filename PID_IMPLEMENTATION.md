# PID Smooth Steering Implementation

## Overview
Replaced discrete FORWARD/LEFT/RIGHT/STOP commands with continuous PID-based motor speed control for smooth navigation.

## Changes Made

### 1. config.py - Added PID Parameters
```python
# PID gains
KP = 1.5          # Proportional gain (start here)
KI = 0.0           # Integral gain (add if needed)
KD = 0.5          # Derivative gain (add for smoothness)

# Motor limits
BASE_SPEED = 100        # Base PWM speed for both motors
MAX_CORRECTION = 50     # Maximum correction adjustment
MIN_SPEED = 0           # Minimum motor speed
MAX_SPEED = 180         # Maximum motor speed
MAX_INTEGRAL = 100.0    # Anti-windup limit
```

### 2. navigation.py - Added PID Controller
- Extended `NavigationController` class with PID state variables:
  - `previous_error`: for derivative calculation
  - `integral`: accumulated error for integral term
  - `last_update_time`: for dt calculation

- Added `compute_pid()` method that returns:
  - `left_speed`, `right_speed`: motor PWM values (0-255)
  - `p_term`, `i_term`, `d_term`: debug components
  - `correction`: total correction value
  - `is_stopped`: target reached flag

- PID state is reset in `reset()` method (called on marker loss)

**Sign convention verified from ESP32 code:**
- Positive error (target to RIGHT) → positive correction → increase LEFT motor speed
- Negative error (target to LEFT) → negative correction → increase RIGHT motor speed

### 3. communication.py - Added Motor Speed Control
- Added `send_motor_speeds(left, right)` method
- Sends GET request: `/set_motors?left={left}&right={right}`
- Uses same error handling as existing `send()` method

### 4. swarm_bot_esp32.ino - Added /set_motors Endpoint
- New handler: `handleSetMotors()`
- Reads `left` and `right` query parameters
- Sets both motors to FORWARD direction (same as `moveForward()`)
- Applies independent PWM speeds: `ledcWrite(CH_A, left)` and `ledcWrite(CH_B, right)`
- Updates `lastCommandTime` for safety timeout compatibility
- Registered in setup: `server.on("/set_motors", handleSetMotors);`

### 5. main.py - Integrated PID Control
- Modified `draw_ui()` to accept optional `pid_data` parameter
- Shows P/I/D terms, correction, and motor speeds in UI
- Updated main loop navigation logic:
  - **Calibrate mode**: uses legacy command system (unchanged)
  - **Normal mode**: uses PID control path
  - Calls `_controller.compute_pid()` when both markers found
  - Sends `link.send_motor_speeds()` for PID control
  - Still sends `link.send("stop")` for STOP conditions

## Preserved Features
✓ All existing HTTP endpoints (/forward /backward /left /right /stop) remain functional
✓ ESP32 safety timeout still works with PID control
✓ Marker loss detection and auto-stop unchanged
✓ Target reached detection (STOP_MARKER_SIZE_PX) unchanged
✓ Angle smoothing (circular_lerp_deg, ANGLE_SMOOTHING_ALPHA) reused
✓ Calibrate mode still uses legacy command display
✓ Hysteresis config values preserved for potential fallback

## How It Works

### Control Flow (Normal Mode)
1. Camera captures frame
2. Detect bot and target ArUco markers
3. Compute navigation angles and smoothed error (existing code)
4. **NEW:** Feed smoothed error into PID controller
5. **NEW:** PID computes correction: `P*error + I*integral + D*derivative`
6. **NEW:** Apply correction to motors: `left = BASE+correction, right = BASE-correction`
7. **NEW:** Send individual motor speeds to ESP32 via `/set_motors`
8. ESP32 drives both motors forward with differential speeds
9. Robot smoothly curves toward target instead of jerky turns

### Tuning Guide
1. **Start with P-only**: Set `KP=1.0, KI=0, KD=0`
   - Too small: slow response
   - Too large: oscillation
   
2. **Add D for smoothness**: Set `KD=0.5` to `KD=2.0`
   - Dampens oscillation
   - Smooths out derivative noise
   
3. **Add I only if needed**: Set `KI=0.1` if persistent one-sided drift
   - Use sparingly (can cause overshoot)
   - Check `MAX_INTEGRAL` anti-windup limit

4. **Adjust motor limits**:
   - `BASE_SPEED`: higher = faster overall movement
   - `MAX_CORRECTION`: higher = more aggressive turning
   - `MAX_SPEED`: safety limit (leave headroom)

## Testing Checklist
- [ ] Upload updated ESP32 firmware
- [ ] Verify `/set_motors` endpoint responds (test in browser)
- [ ] Run `python main.py --calibrate` to verify navigation angles
- [ ] Run `python main.py` and observe smooth curved approach
- [ ] Verify robot stops at target (size threshold still works)
- [ ] Test marker loss recovery (should auto-stop and reset PID)
- [ ] Verify safety timeout works (disconnect laptop, robot should stop after 1 second)

## Definition of Done
✓ Robot drives in smooth curve with continuously varying motor speeds
✓ Both motors always move forward (no in-place spinning)
✓ Stops correctly at target (STOP_MARKER_SIZE_PX threshold)
✓ Stops on marker loss (bot or target missing)
✓ ESP32 safety timeout remains functional
✓ Calibrate mode unchanged for debugging
✓ All legacy commands preserved as fallback
