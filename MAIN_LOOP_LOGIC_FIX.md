# Main Loop Logic Fix - PID Path Bug

## Problem Identified
In `main.py`, the PID control path had a critical logic bug that prevented motor commands from ever being sent.

### Root Cause
```python
# Top of loop
command = "STOP"  # initialized

# In PID path (bot + target found, not calibrate mode)
if pid_data['is_stopped']:
    command = "STOP"
    status = "TARGET REACHED"
else:
    status = "NAVIGATING (PID)"
    # BUG: command never reassigned, stays "STOP"

# Send logic
if command == "STOP":
    send_command(command, link, calibrate_mode)  # Always executes!
elif pid_data and not pid_data['is_stopped']:
    link.send_motor_speeds(...)  # Never executes!
```

**Why motors didn't move:**
1. In PID active case, `command` was never changed from its initial "STOP" value
2. Send logic checked `if command == "STOP"` first
3. This condition was always `True` in PID mode
4. So `send_command("stop", ...)` always executed
5. The `elif` branch with `send_motor_speeds()` never ran
6. Robot received STOP every frame instead of motor speeds

## Solution Applied

### Restructured Send Logic
```python
# New logic: check pid_data directly, not command variable
if not calibrate_mode and link:
    if pid_data is not None and not pid_data['is_stopped']:
        # PID active: send motor speeds
        link.send_motor_speeds(pid_data['left_speed'], pid_data['right_speed'])
    else:
        # All other cases: send STOP
        link.send('stop', force=True)
elif calibrate_mode and nav:
    pass  # calibrate mode unchanged
```

### Why This Works
- **Checks `pid_data` directly** instead of relying on `command` variable
- **If `pid_data` exists and robot not at target** → send motor speeds
- **Otherwise** (markers missing, target reached, calibrate mode) → send STOP
- `command` variable is now only used for status display, not control flow

## What Wasn't Changed
✓ `bot_missing_frames` / `target_missing_frames` handling unchanged
✓ `reset_navigation_state()` calls unchanged
✓ Calibrate mode behavior unchanged
✓ Status messages unchanged
✓ UI drawing unchanged
✓ No changes to `communication.py` or `.ino`

## Control Flow After Fix

### Case 1: PID Active (bot + target found, not at target, not calibrate)
```
pid_data = compute_pid(...)  ✓
pid_data['is_stopped'] = False  ✓
  ↓
if pid_data is not None and not pid_data['is_stopped']:  ✓ True
  ↓
link.send_motor_speeds(left, right)  ✓ Executes!
  ↓
Motors move
```

### Case 2: Target Reached
```
pid_data = compute_pid(...)  ✓
pid_data['is_stopped'] = True  ✓
  ↓
if pid_data is not None and not pid_data['is_stopped']:  ✗ False
  ↓
else: link.send('stop', force=True)  ✓ Executes
  ↓
Motors stop
```

### Case 3: Bot or Target Missing
```
pid_data = None  ✓
  ↓
if pid_data is not None and not pid_data['is_stopped']:  ✗ False
  ↓
else: link.send('stop', force=True)  ✓ Executes
  ↓
Motors stop (safety)
```

### Case 4: Calibrate Mode
```
calibrate_mode = True  ✓
  ↓
if not calibrate_mode and link:  ✗ False
  ↓
elif calibrate_mode and nav:  ✓ True
  ↓
pass  (no HTTP commands sent)
```

## Testing
After this fix:
1. Run `python main.py`
2. Place robot facing away from target
3. **Motors should now turn** (throttling fix + logic fix working together)
4. Robot should curve smoothly toward target
5. Should stop when target reached
6. Should stop if markers lost

## Combined Fixes
This fix works together with the throttling fix:
- **Throttling fix** (`communication.py`): Prevents overwhelming ESP32 with requests
- **Logic fix** (`main.py`): Ensures motor commands are actually sent

Both were needed for PID mode to work correctly.
