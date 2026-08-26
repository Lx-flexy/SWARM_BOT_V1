# Anti-Oscillation Fixes - Summary

## Problem Analysis

### Why Oscillation Was Happening

The robot was oscillating between LEFT/RIGHT commands because:

1. **Single threshold** (15°) - Camera measurements naturally fluctuate around this value:
   ```
   Frame 1: +17° → RIGHT
   Frame 2: +13° → FORWARD
   Frame 3: +19° → RIGHT
   Frame 4: +11° → FORWARD
   Frame 5: +16° → RIGHT
   ```

2. **No smoothing** - Every noisy frame caused an immediate command change

3. **No hysteresis** - Crossing the threshold in either direction had the same effect

4. **No command stability** - Commands could change every frame (30-60 times per second)

5. **Aggressive turns** - Differential turning (LEFT/RIGHT) is powerful and overshoots easily

## Solutions Implemented

### 1. ✅ Increased Navigation Deadband

**Location:** `config.py`

```python
TURN_ENTER_DEG = 25.0  # Increased from 15°
```

**Effect:** Robot only turns when error exceeds ±25°, creating a wider "forward zone"

---

### 2. ✅ Hysteresis (Enter/Exit Thresholds)

**Location:** `navigation.py` - `NavigationController._decide_with_hysteresis()`

```python
TURN_ENTER_DEG = 25.0   # Enter turn
TURN_EXIT_DEG = 15.0    # Exit turn (10° hysteresis gap)
```

**Behavior:**

**From FORWARD:**
- Error +20° → Stay FORWARD (below 25° enter threshold)
- Error +26° → Switch to RIGHT (exceeded enter threshold)

**While turning RIGHT:**
- Error +22° → Continue RIGHT (above 15° exit threshold)
- Error +17° → Continue RIGHT (still above exit threshold)
- Error +14° → Switch to FORWARD (dropped below exit threshold)

**Result:** 10° hysteresis gap prevents command flapping

---

### 3. ✅ Angle Smoothing (Exponential Moving Average)

**Location:** `navigation.py` - `NavigationController.update()`

```python
ANGLE_SMOOTHING_ALPHA = 0.3
```

**Formula:**
```python
smoothed_error = circular_lerp_deg(
    previous_smoothed_error,
    raw_angle_error,
    alpha
)
```

**Special handling for angle wraparound:**
- Uses `circular_lerp_deg()` to prevent incorrect averaging near ±180°
- Example: lerp(179°, -179°) = 180° (correct) instead of 0° (wrong)

**Effect:** 
- Raw noise is filtered out
- Robot responds to sustained angle changes, not single-frame spikes

---

### 4. ✅ Command Stability (Minimum Duration)

**Location:** `navigation.py` - `NavigationController.update()`

```python
MIN_COMMAND_DURATION = 0.15  # seconds
```

**Behavior:**
- Once a command is issued, it must be held for at least 0.15 seconds
- Timer resets when command changes
- Safety override: STOP command always allowed immediately

**Effect:**
- Prevents command changes every frame (would be 30-60 Hz)
- Allows ~6-7 command changes per second maximum
- Gives motors time to execute before next decision

---

### 5. ✅ Short Turning Pulses (Implicit)

**Implementation:** Combination of:
- Minimum command duration (0.15s)
- Hysteresis (robot exits turn sooner than it enters)
- Smoothing (prevents sustained turn commands on noise)

**Pattern:**
```
Measure → Turn briefly (0.15s minimum) → Measure → Correct → Forward → Repeat
```

**Effect:** Robot makes small correction turns instead of continuous rotation

---

### 6. ✅ FORWARD Stability Zone

**Location:** `navigation.py` - Hysteresis thresholds

```python
# When in FORWARD, only turn if |error| > 25°
# When turning, continue until |error| < 15°
```

**Effect:**
- Small errors (±15°) are ignored when robot is going forward
- Robot prefers forward motion over constant micro-corrections

---

### 7. ✅ Circular Angle Handling

**Location:** `navigation.py` - `circular_lerp_deg()`

**Problem it solves:**
```python
# WRONG: Normal average of 179° and -179°
avg = (179 + (-179)) / 2 = 0°  # Incorrect!

# CORRECT: Circular interpolation
result = circular_lerp_deg(179, -179, 0.5) = ±180°  # Correct!
```

**Effect:** Smoothing works correctly even when robot crosses the ±180° boundary

---

### 8. ✅ Target Distance Logic Preserved

**Location:** `navigation.py` - `NavigationController.update()`

```python
if target_marker_size_px >= config.STOP_MARKER_SIZE_PX:
    return "STOP"
```

**Effect:** Existing proximity detection unchanged

---

### 9. ✅ Enhanced Debug Display

**Location:** `main.py` - `draw_ui()`

**New display:**
```
RAW ERROR:       +27.4°    (gray - noisy measurement)
SMOOTHED ERROR:  +22.1°    (colored - used for control)
COMMAND:         FORWARD
```

**Effect:** You can see both raw noise and smoothed signal for tuning

---

## Files Modified

### 1. `config.py`
**Added parameters:**
```python
ANGLE_SMOOTHING_ALPHA = 0.3      # Smoothing strength
TURN_ENTER_DEG = 25.0            # Enter turn threshold
TURN_EXIT_DEG = 15.0             # Exit turn threshold (hysteresis)
MIN_COMMAND_DURATION = 0.15      # Command hold time (seconds)
```

**Removed (replaced by hysteresis):**
```python
ANGLE_ERROR_DEADBAND_DEG = 15.0  # No longer used
```

---

### 2. `navigation.py`
**Added:**
- `circular_lerp_deg()` - Angle interpolation with wraparound handling
- `NavigationController` class - Stateful controller with:
  - `smoothed_error` - EMA of angle error
  - `current_command` - Current command state
  - `last_command_change_time` - For minimum duration enforcement
  - `update()` - Main control logic with smoothing + hysteresis
  - `_decide_with_hysteresis()` - Threshold logic with state-dependent thresholds
  - `reset()` - Clear state when markers lost
- `reset_navigation_state()` - Global reset function

**Modified:**
- `compute_navigation()` - Now uses NavigationController
- Returns both `angle_error_raw` and `angle_error_smoothed`
- `print_debug()` - Shows both raw and smoothed errors

---

### 3. `main.py`
**Modified:**
- Import `reset_navigation_state`
- Call `reset_navigation_state()` at startup and when markers lost
- `draw_ui()` - Display both raw and smoothed errors
- References `nav['angle_error_smoothed']` instead of `nav['angle_error']`

---

## Recommended Initial Values

```python
# Smoothing
ANGLE_SMOOTHING_ALPHA = 0.3      # 30% new, 70% old
                                  # Lower = more smoothing
                                  # Higher = faster response

# Hysteresis  
TURN_ENTER_DEG = 25.0            # Start turning at ±25°
TURN_EXIT_DEG = 15.0             # Stop turning at ±15°
                                  # Gap = 10° hysteresis

# Command stability
MIN_COMMAND_DURATION = 0.15      # Hold command for 150ms
                                  # ~6-7 changes/second max

# Distance
STOP_MARKER_SIZE_PX = 140.0      # Unchanged
```

---

## Tuning Guide

### If robot is still oscillating:
1. **Increase smoothing:** Lower `ANGLE_SMOOTHING_ALPHA` (try 0.2)
2. **Increase hysteresis gap:** Raise `TURN_ENTER_DEG` (try 30°)
3. **Increase command duration:** Raise `MIN_COMMAND_DURATION` (try 0.2)

### If robot is too sluggish:
1. **Decrease smoothing:** Raise `ANGLE_SMOOTHING_ALPHA` (try 0.4)
2. **Decrease command duration:** Lower `MIN_COMMAND_DURATION` (try 0.1)

### If robot overshoots:
1. **Increase hysteresis gap:** Widen gap between ENTER and EXIT thresholds
2. **Increase smoothing:** Lower `ANGLE_SMOOTHING_ALPHA`

---

## Expected Behavior After Fix

### Test 1: Target Straight Ahead
```
Raw errors: +5°, +8°, +3°, +7°, +4°, +6°, +2°
Smoothed:   +5°, +6°, +5°, +6°, +5°, +5°, +4°
Command:    FORWARD (stable, no oscillation)
```

### Test 2: Gradual Right Turn Needed
```
Raw errors: +10°, +15°, +20°, +24°, +27°, +30°
Smoothed:   +10°, +12°, +15°, +18°, +21°, +24°
Command:    FORWARD → FORWARD → FORWARD → FORWARD → FORWARD → RIGHT
            (only turns after sustained error above 25°)
```

### Test 3: While Turning Right
```
Raw errors: +28°, +22°, +19°, +16°, +13°
Smoothed:   +27°, +25°, +23°, +21°, +18°
Command:    RIGHT → RIGHT → RIGHT → RIGHT → FORWARD
            (continues turning until error drops below 15°)
```

### Test 4: Noisy Measurements Near Threshold
```
Raw errors: +23°, +27°, +24°, +26°, +22°
Smoothed:   +23°, +24°, +24°, +25°, +24°
Command:    FORWARD → FORWARD → FORWARD → RIGHT → RIGHT
            (smoothing prevents single spike from causing turn)
```

---

## Testing Instructions

1. **Run normal mode:**
   ```bash
   python main.py
   ```

2. **Observe debug overlay:**
   - Watch both RAW ERROR and SMOOTHED ERROR
   - Smoothed should be less jittery than raw
   - Commands should change slowly and deliberately

3. **Check for oscillation:**
   - Robot should make smooth corrections
   - Should prefer FORWARD over constant turning
   - Turns should be brief and purposeful

4. **Tune if needed:**
   - Edit values in `config.py`
   - No code changes required for tuning
   - Restart script to apply changes

---

## Key Principles

✅ **Stability over precision** - Smooth, predictable motion is more important than perfect alignment

✅ **Prefer forward** - Robot should spend most time going forward, not turning

✅ **Brief corrections** - Small turn pulses instead of continuous rotation

✅ **Filter noise** - React to sustained errors, ignore single-frame spikes

✅ **State awareness** - Different thresholds based on current command (hysteresis)

---

## Architecture Preserved

✅ ESP32 hardware unchanged  
✅ TB6612FNG wiring unchanged  
✅ ArUco dictionary unchanged (DICT_4X4_50)  
✅ Marker IDs unchanged (1, 25)  
✅ Wi-Fi unchanged  
✅ HTTP commands unchanged (forward/backward/left/right/stop)  
✅ Basic navigation logic unchanged  
✅ No PID controller added  
✅ No path planning added  

Only the **decision logic** was improved with smoothing, hysteresis, and stability.
