# ESP32 Turn Speed Reduction - Summary

## Problem

The robot was turning too aggressively, causing:
- Large frame-to-frame position changes
- Unstable ArUco heading/angle calculations
- LEFT → RIGHT → LEFT → RIGHT oscillation
- Camera unable to track smoothly during turns

## Solution

Implemented separate speed values for **forward/backward movement** vs **turning**.

### Changes Made

#### 1. Replaced Single Speed with Separate Speeds

**BEFORE:**
```cpp
const int CAR_SPEED = 90;   // Used for all movements
```

**AFTER:**
```cpp
int forwardSpeed = 120;     // Speed for FORWARD and BACKWARD
int turnSpeed = 60;         // Speed for LEFT and RIGHT (slower)
```

**Effect:** Turn speed is now 50% of forward speed (60 vs 120)

---

#### 2. Updated moveForward()

**BEFORE:**
```cpp
ledcWrite(CH_A, CAR_SPEED);
ledcWrite(CH_B, CAR_SPEED);
```

**AFTER:**
```cpp
ledcWrite(CH_A, forwardSpeed);
ledcWrite(CH_B, forwardSpeed);
```

---

#### 3. Updated moveBackward()

**BEFORE:**
```cpp
ledcWrite(CH_A, CAR_SPEED);
ledcWrite(CH_B, CAR_SPEED);
```

**AFTER:**
```cpp
ledcWrite(CH_A, forwardSpeed);
ledcWrite(CH_B, forwardSpeed);
```

---

#### 4. Updated turnLeft()

**BEFORE:**
```cpp
ledcWrite(CH_A, CAR_SPEED);
ledcWrite(CH_B, CAR_SPEED);
```

**AFTER:**
```cpp
ledcWrite(CH_A, turnSpeed);
ledcWrite(CH_B, turnSpeed);
```

**Note:** Motor directions (GPIO pin states) remain unchanged.

---

#### 5. Updated turnRight()

**BEFORE:**
```cpp
ledcWrite(CH_A, CAR_SPEED);
ledcWrite(CH_B, CAR_SPEED);
```

**AFTER:**
```cpp
ledcWrite(CH_A, turnSpeed);
ledcWrite(CH_B, turnSpeed);
```

**Note:** Motor directions (GPIO pin states) remain unchanged.

---

#### 6. Updated Root Handler (for verification)

**BEFORE:**
```cpp
server.send(200, "text/plain", "SWARM BOT ESP32 ready. Speed fixed at 90.");
```

**AFTER:**
```cpp
String msg = "SWARM BOT ESP32 ready. Forward speed: ";
msg += String(forwardSpeed);
msg += ", Turn speed: ";
msg += String(turnSpeed);
server.send(200, "text/plain", msg);
```

**Effect:** You can verify current speeds by visiting `http://<ESP32_IP>/` in browser

---

## What Was NOT Changed ✅

- ✅ Motor wiring unchanged
- ✅ GPIO pin definitions unchanged (PWMA=26, AIN1=27, AIN2=14, PWMB=16, BIN1=32, BIN2=13, STBY=25)
- ✅ TB6612FNG configuration unchanged
- ✅ Motor direction logic unchanged (LEFT/RIGHT directions preserved)
- ✅ Wi-Fi system unchanged
- ✅ HTTP endpoints unchanged (/forward, /backward, /left, /right, /stop)
- ✅ Safety timeout unchanged (1000ms)
- ✅ PWM frequency and resolution unchanged

---

## Speed Values

### Initial Configuration
```cpp
forwardSpeed = 120;    // Moderate forward speed
turnSpeed = 60;        // Slow, controlled turns (50% of forward)
```

### Tuning Guide

**If turns are still too fast:**
```cpp
turnSpeed = 50;    // Even slower turns
```

**If turns are too slow:**
```cpp
turnSpeed = 70;    // Slightly faster turns
```

**If forward speed needs adjustment:**
```cpp
forwardSpeed = 100;    // Slower forward
forwardSpeed = 140;    // Faster forward
```

**Range:** 0-255 (PWM duty cycle)
- 0 = stopped
- 255 = full speed
- Typical range: 50-150

---

## Expected Behavior

### Forward Movement
```
Command: /forward
Speed:   120 (moderate)
Effect:  Smooth, steady forward motion
```

### Backward Movement
```
Command: /backward
Speed:   120 (moderate)
Effect:  Smooth, steady backward motion
```

### Left Turn
```
Command: /left
Speed:   60 (slow)
Effect:  Slow, controlled rotation
        Camera has time to track
        ArUco heading stays stable
```

### Right Turn
```
Command: /right
Speed:   60 (slow)
Effect:  Slow, controlled rotation
        Camera has time to track
        ArUco heading stays stable
```

---

## How This Fixes Oscillation

### Before (Fast Turns)
```
1. Laptop sends: LEFT
2. Robot rotates FAST (speed 90)
3. Camera captures blurred/shifted frame
4. ArUco heading calculation becomes unstable
5. Navigation sees large angle change
6. Laptop sends: RIGHT (overcorrection)
7. Robot rotates FAST again
8. Oscillation continues: LEFT → RIGHT → LEFT → RIGHT
```

### After (Slow Turns)
```
1. Laptop sends: LEFT
2. Robot rotates SLOWLY (speed 60)
3. Camera captures stable frame
4. ArUco heading recalculated accurately
5. Navigation sees controlled angle change
6. Laptop sends: FORWARD (proper alignment)
7. Robot moves forward smoothly
```

---

## Combined with Python Anti-Oscillation

This ESP32 fix works **together** with the Python navigation improvements:

**ESP32 side (hardware):**
- Slower physical turn speed
- Camera can track smoothly

**Python side (software):**
- Angle smoothing (EMA)
- Hysteresis (ENTER/EXIT thresholds)
- Command stability (minimum duration)

**Result:**
- **Hardware:** Slow, predictable turns
- **Software:** Smart, stable decision-making
- **Combined:** Smooth approach to target with minimal oscillation

---

## Upload Instructions

1. Open Arduino IDE
2. Load `swarm_bot_esp32.ino`
3. Select board: **ESP32 Dev Module**
4. Select correct COM port
5. Upload
6. Open Serial Monitor (115200 baud)
7. Note the IP address printed
8. Test by visiting `http://<ESP32_IP>/` in browser
   - Should display: "SWARM BOT ESP32 ready. Forward speed: 120, Turn speed: 60"

---

## Testing

### Test 1: Forward Speed
```
Send: /forward
Expected: Robot moves forward at moderate speed
```

### Test 2: Turn Speed
```
Send: /left
Expected: Robot rotates slowly and smoothly
Observe: Camera tracking should be stable
```

### Test 3: Speed Verification
```
Visit: http://<ESP32_IP>/
Expected: "SWARM BOT ESP32 ready. Forward speed: 120, Turn speed: 60"
```

---

## Tuning Workflow

1. **Start with defaults:**
   ```cpp
   forwardSpeed = 120;
   turnSpeed = 60;
   ```

2. **Test with Python navigation:**
   ```bash
   python main.py
   ```

3. **Observe behavior:**
   - Watch debug overlay (RAW ERROR, SMOOTHED ERROR, COMMAND)
   - Watch robot movement

4. **If still oscillating:**
   - Lower `turnSpeed` (try 50)
   - Increase Python `TURN_ENTER_DEG` (try 30°)

5. **If too sluggish:**
   - Raise `turnSpeed` (try 70)
   - Decrease Python `MIN_COMMAND_DURATION` (try 0.1)

6. **Re-upload ESP32 code** after any speed change
7. **Restart Python script** to apply software changes

---

## Summary of All Changes

| File | What Changed |
|------|--------------|
| `swarm_bot_esp32.ino` | Added separate `forwardSpeed` and `turnSpeed` variables |
| | Updated `moveForward()` to use `forwardSpeed` |
| | Updated `moveBackward()` to use `forwardSpeed` |
| | Updated `turnLeft()` to use `turnSpeed` |
| | Updated `turnRight()` to use `turnSpeed` |
| | Updated `handleRoot()` to report current speeds |
| `main.py` | **No changes needed** |
| `navigation.py` | **No changes needed** |
| `config.py` | **No changes needed** |

**Total lines changed:** 6 functions + 1 variable declaration = ~15 lines

**Everything else:** Unchanged and working as before

---

Your robot should now make slow, controlled turns that allow the camera to track smoothly and the ArUco navigation system to make accurate decisions! 🚀
