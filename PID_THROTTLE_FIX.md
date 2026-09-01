# PID Motor Control Throttling Fix

## Problem Identified
The `send_motor_speeds()` method was being called from the camera loop on **every frame** (~30 Hz), creating a new HTTP connection each time. The ESP32's single-threaded `WebServer` library cannot handle 30+ new TCP connections per second, causing request failures and preventing the motors from moving in PID mode.

## Root Cause
- Main loop calls `link.send_motor_speeds()` every frame
- Each call does `requests.get()` (new TCP connection)
- ESP32 WebServer gets overwhelmed
- Most requests timeout or fail
- Motors don't move despite correct PID calculations

## Solution Applied

### 1. Added Motor Send Interval to config.py
```python
MOTOR_SEND_INTERVAL_S = 0.05  # 20 Hz (50ms between updates)
```
- 20 Hz is frequent enough for smooth control
- Infrequent enough to not overwhelm ESP32

### 2. Added Throttling to send_motor_speeds()
```python
# Check if enough time has elapsed
if (now - self.last_sent_time) < config.MOTOR_SEND_INTERVAL_S:
    return True  # skip this frame, treat as success

# Only send when interval has elapsed
requests.get(url, timeout=config.REQUEST_TIMEOUT)
self.last_sent_time = now
```

### 3. Added int() Casting
```python
left_speed = int(left_speed)
right_speed = int(right_speed)
```
- PID may output floats
- ESP32 `toInt()` expects integer values

## What Wasn't Changed
✓ Existing `send()` method throttling unchanged (COMMAND_COOLDOWN)
✓ Main loop calling pattern unchanged (still calls every frame)
✓ ESP32 Arduino code unchanged (no firmware update needed)
✓ Throttling logic lives in `communication.py` (main.py doesn't need to care)

## Testing
After this fix:
1. Run `python main.py`
2. Place robot facing away from target
3. **Motors should now actually turn**
4. Robot should curve smoothly toward target
5. Check terminal for errors (should see very few/none)

## Before vs After

### Before (Broken)
```
Camera loop (30 Hz)
  ↓
send_motor_speeds() every frame
  ↓
30 TCP connections/sec
  ↓
ESP32 WebServer overwhelmed
  ↓
Motors don't move
```

### After (Fixed)
```
Camera loop (30 Hz)
  ↓
send_motor_speeds() called every frame
  ↓
Throttled to 20 Hz inside method
  ↓
ESP32 handles 20 requests/sec easily
  ↓
Motors move smoothly
```

## Technical Details
- **Throttle rate**: 20 Hz (50ms interval)
- **Why 20 Hz?** Smooth enough for human perception, gentle on ESP32
- **Shared timer**: Uses same `self.last_sent_time` as `send()` method
- **Skip behavior**: Returns `True` (success) when skipped, so main loop doesn't think it failed
