# PID Tuning Guide - Fix Circling and Weak Turns

## Problems Fixed

### 1. Bot circling around target
**Cause:** Bot was moving at full speed even when very close to target, causing it to overshoot and circle around.

**Fix:** Added adaptive speed reduction near target:
```python
SLOW_DOWN_DISTANCE_PX = 100.0   # Start slowing when marker > 100px
SLOW_DOWN_SPEED = 60            # Reduce to 60 PWM when close
```

### 2. Weak/slow turns (not sharp enough)
**Cause:** 
- Low P gain (KP=1.0) gave weak correction
- Low MAX_CORRECTION (50) limited turn sharpness
- No D term to smooth out response

**Fix:** Increased aggressiveness:
```python
KP = 2.5              # 2.5x stronger correction (was 1.0)
KD = 0.5              # Added derivative for smoothness
MAX_CORRECTION = 80   # Increased from 50
BASE_SPEED = 120      # Increased from 100 for more momentum
MIN_SPEED = 30        # Prevent motors from stopping completely
MAX_SPEED = 200       # Higher ceiling (was 180)
```

## New Parameter Values

### PID Gains
```python
KP = 2.5   # Proportional: 2.5 degrees error = +2.5 correction
KI = 0.0   # Integral: OFF (not needed for this application)
KD = 0.5   # Derivative: dampens oscillation
```

### Motor Speeds
```python
BASE_SPEED = 120              # Normal cruising speed (far from target)
SLOW_DOWN_SPEED = 60          # Reduced speed (close to target)
SLOW_DOWN_DISTANCE_PX = 100   # Marker size threshold to trigger slowdown
```

### Limits
```python
MAX_CORRECTION = 80   # Maximum turn adjustment
MIN_SPEED = 30        # Never go below this (keeps momentum)
MAX_SPEED = 200       # Safety ceiling
```

## How Adaptive Speed Works

```
Distance from target (marker size):
  
  0-100 px     → BASE_SPEED = 120 (full speed, sharp turns)
  100-140 px   → SLOW_DOWN_SPEED = 60 (half speed, gentle approach)
  ≥140 px      → STOP (target reached)
```

### Example Scenario:
1. **Far from target** (marker = 50px):
   - Base speed = 120
   - Error = 30° → correction = 75 (2.5 × 30)
   - Left motor: 120 + 75 = 195
   - Right motor: 120 - 75 = 45
   - **Sharp turn toward target**

2. **Close to target** (marker = 120px):
   - Base speed = 60 (slowed down!)
   - Error = 10° → correction = 25 (2.5 × 10)
   - Left motor: 60 + 25 = 85
   - Right motor: 60 - 25 = 35
   - **Gentle approach, no circling**

3. **At target** (marker ≥ 140px):
   - Both motors: 0
   - **Stopped**

## Tuning Tips

### If bot still circles:
```python
# Option 1: Start slowing down earlier
SLOW_DOWN_DISTANCE_PX = 80.0  # (was 100)

# Option 2: Slow down more aggressively
SLOW_DOWN_SPEED = 40  # (was 60)

# Option 3: Stop earlier
STOP_MARKER_SIZE_PX = 120.0  # (was 140)
```

### If turns are still too weak:
```python
# Option 1: Increase P gain
KP = 3.0  # (was 2.5)

# Option 2: Increase max correction
MAX_CORRECTION = 100  # (was 80)
```

### If turns are too sharp (overshooting):
```python
# Option 1: Decrease P gain
KP = 2.0  # (was 2.5)

# Option 2: Increase D gain (more damping)
KD = 1.0  # (was 0.5)

# Option 3: Reduce max correction
MAX_CORRECTION = 60  # (was 80)
```

### If bot oscillates/wiggles:
```python
# Increase derivative gain for smoother response
KD = 1.0  # (was 0.5)

# Or increase angle smoothing
ANGLE_SMOOTHING_ALPHA = 0.2  # (was 0.3) - more smoothing
```

## Testing Checklist
- [ ] Bot makes sharp turns when far from target
- [ ] Bot slows down when approaching target
- [ ] Bot doesn't circle around target
- [ ] Bot stops at target center
- [ ] No oscillation/wiggling during approach
- [ ] Smooth curved path (not jerky)

## Expected Behavior
1. **Far from target**: Fast movement, sharp corrections
2. **Approaching target**: Gradual speed reduction
3. **Near target**: Slow, gentle final approach
4. **At target**: Clean stop at center

## Current Settings Summary
```python
# Aggressiveness (turning)
KP = 2.5
MAX_CORRECTION = 80

# Speed control
BASE_SPEED = 120 (far)
SLOW_DOWN_SPEED = 60 (close)
SLOW_DOWN_DISTANCE_PX = 100

# Smoothness
KD = 0.5
MIN_SPEED = 30

# Stop threshold
STOP_MARKER_SIZE_PX = 140
```

These values should give sharp turns when needed and prevent circling. Adjust as needed for your specific setup!
