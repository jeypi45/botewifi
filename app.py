from flask_cors import CORS
from flask import Flask, jsonify, send_file, request
import OPi.GPIO as GPIO
import time
import subprocess

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

# -------------------------------
# GPIO Setup for Orange Pi
# -------------------------------
IR_SENSOR_PIN = "PC7"  # Port C, Pin 7

GPIO.setmode(GPIO.SUNXI)  # Use Allwinner/Sunxi pin naming (PA, PB, PC, etc.)
GPIO.setup(IR_SENSOR_PIN, GPIO.IN)

# -------------------------------
# Motion Detection State
# -------------------------------
motion_detected = False
last_detection_time = None
motion_count = 0
last_motion_count = 0  # Track previous count to detect new bottles

# -------------------------------
# Piso WiFi Timer System (Multi-User)
# -------------------------------
session_active = False  # Controls if IR detection is active
internet_active = False
MINUTES_PER_BOTTLE = 5
SECONDS_PER_BOTTLE = MINUTES_PER_BOTTLE * 60

# Store time for each device/user (key: device_id, value: {time_remaining, session_start, bottles})
user_sessions = {}
pending_bottles = 0  # Bottles detected but not yet assigned to a user

def check_motion_and_add_time():
    """Check motion sensor and add to pending bottles when detected"""
    global motion_detected, last_detection_time, motion_count, last_motion_count
    global internet_active, session_active, pending_bottles
    
    try:
        sensor_value = GPIO.input(IR_SENSOR_PIN)
        if sensor_value == GPIO.LOW:
            if not motion_detected:
                motion_count += 1
                
                # Only count bottles if session is active
                if session_active and motion_count > last_motion_count:
                    last_motion_count = motion_count
                    pending_bottles += 1
                    
                    # Enable internet if not active
                    if not internet_active:
                        enable_internet()
                        internet_active = True
                    
                    print(f"🍾 Bottle detected! Pending bottles: {pending_bottles}")
                
            motion_detected = True
            last_detection_time = time.time()
        else:
            if last_detection_time and (time.time() - last_detection_time) > 2:
                motion_detected = False
        
        return motion_detected
    except Exception as e:
        print(f"Error reading sensor: {e}")
        return False

def get_user_time_remaining(device_id):
    """Calculate remaining time for a specific user"""
    if device_id not in user_sessions:
        return 0
    
    session = user_sessions[device_id]
    elapsed = int(time.time() - session['session_start'])
    remaining = max(0, session['time_remaining'] - elapsed)
    
    # If time expired, remove session
    if remaining <= 0:
        del user_sessions[device_id]
        return 0
    
    return remaining

# -------------------------------
# Flask Routes
# -------------------------------
@app.route('/')
def index():
    return send_file('index.html')

@app.route('/guide')
def guide():
    return send_file('guide.html')

@app.route('/qrcode')
def qrcode():
    return send_file('qrcode.html')

@app.route('/status')
def status():
    is_motion = check_motion_and_add_time()
    device_id = request.headers.get('X-Device-ID', 'unknown')
    
    # Get user's remaining time
    user_time = get_user_time_remaining(device_id)
    user_bottles = user_sessions.get(device_id, {}).get('bottles', 0)
    
    return jsonify({
        'motion_detected': is_motion,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pin': IR_SENSOR_PIN,
        'motion_count': motion_count,
        'session_active': session_active,
        'pending_bottles': pending_bottles,
        'total_users': len(user_sessions),
        'user_time_remaining': user_time,
        'user_bottles': user_bottles
    })

@app.route('/test_pin')
def test_pin():
    try:
        value = GPIO.input(IR_SENSOR_PIN)
        return jsonify({
            'pin': IR_SENSOR_PIN,
            'value': value,
            'status': 'LOW (Motion)' if value == GPIO.LOW else 'HIGH (No motion)'
        })
    except Exception as e:
        return jsonify({'error': str(e)})
def enable_internet():
    """Enable internet connection"""
    subprocess.run(['sudo', 'sysctl', '-w', 'net.ipv4.ip_forward=1'], check=True)
    subprocess.run(['sudo', 'iptables', '-t', 'nat', '-A', 'POSTROUTING', '-o', 'end0', '-j', 'MASQUERADE'], check=True)
    subprocess.run(['sudo', 'iptables', '-A', 'FORWARD', '-i', 'enxec9a0c1a0b4c', '-o', 'end0', '-j', 'ACCEPT'], check=True)
    subprocess.run(['sudo', 'iptables', '-A', 'FORWARD', '-i', 'end0', '-o', 'enxec9a0c1a0b4c', '-m', 'state', '--state', 'RELATED,ESTABLISHED', '-j', 'ACCEPT'], check=True)

def disable_internet():
    """Disable internet connection"""
    subprocess.run(['sudo', 'sysctl', '-w', 'net.ipv4.ip_forward=0'], check=True)
    subprocess.run(['sudo', 'iptables', '-t', 'nat', '-F'], check=True)
    subprocess.run(['sudo', 'iptables', '-F', 'FORWARD'], check=True)

@app.route('/start_session')
def start_session():
    """Start IR detection session - enables bottle detection"""
    global session_active, motion_count, last_motion_count
    try:
        session_active = True
        # Reset motion counters to start fresh
        motion_count = 0
        last_motion_count = 0
        
        return jsonify({
            'success': True,
            'message': 'Session started! Insert bottles now.',
            'session_active': session_active
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/claim_bottle')
def claim_bottle():
    """Claim a pending bottle and add time to user's session"""
    global pending_bottles, user_sessions
    
    device_id = request.headers.get('X-Device-ID') or request.args.get('device_id', 'unknown')
    
    if pending_bottles <= 0:
        return jsonify({
            'success': False,
            'error': 'No bottles available to claim'
        })
    
    try:
        # Deduct from pending bottles
        pending_bottles -= 1
        
        # Get or create user session
        if device_id in user_sessions:
            # Calculate current remaining time
            elapsed = int(time.time() - user_sessions[device_id]['session_start'])
            current_remaining = max(0, user_sessions[device_id]['time_remaining'] - elapsed)
            
            # Add 5 minutes
            user_sessions[device_id]['time_remaining'] = current_remaining + SECONDS_PER_BOTTLE
            user_sessions[device_id]['session_start'] = time.time()
            user_sessions[device_id]['bottles'] += 1
        else:
            # New user
            user_sessions[device_id] = {
                'time_remaining': SECONDS_PER_BOTTLE,
                'session_start': time.time(),
                'bottles': 1
            }
        
        bottles = user_sessions[device_id]['bottles']
        time_remaining = user_sessions[device_id]['time_remaining']
        
        print(f"✅ Device {device_id} claimed bottle #{bottles}. Time: {time_remaining//60}:{time_remaining%60:02d}")
        
        return jsonify({
            'success': True,
            'message': f'{MINUTES_PER_BOTTLE} minutes added to your account!',
            'bottles': bottles,
            'time_remaining': time_remaining,
            'pending_bottles': pending_bottles
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get_time')
def get_time():
    """Get remaining time and internet status for specific user"""
    global internet_active, user_sessions, pending_bottles
    
    device_id = request.headers.get('X-Device-ID') or request.args.get('device_id', 'unknown')
    
    # Get user's remaining time
    user_time = get_user_time_remaining(device_id)
    user_bottles = user_sessions.get(device_id, {}).get('bottles', 0)
    
    # Check if any user has time remaining
    has_active_users = len(user_sessions) > 0
    
    if user_time > 0:
        return jsonify({
            'internet_active': internet_active,
            'time_remaining': user_time,
            'minutes_remaining': user_time // 60,
            'seconds_remaining': user_time % 60,
            'formatted_time': f"{user_time // 60}:{user_time % 60:02d}",
            'bottles_inserted': user_bottles,
            'session_active': session_active,
            'pending_bottles': pending_bottles,
            'total_users': len(user_sessions)
        })
    else:
        return jsonify({
            'internet_active': internet_active and has_active_users,
            'time_remaining': 0,
            'minutes_remaining': 0,
            'seconds_remaining': 0,
            'formatted_time': "0:00",
            'bottles_inserted': user_bottles,
            'session_active': session_active,
            'pending_bottles': pending_bottles,
            'total_users': len(user_sessions)
        })

@app.route('/connect_internet')
def connect_internet():
    """Manual connect (for testing)"""
    global internet_active, time_remaining, session_start_time
    try:
        enable_internet()
        internet_active = True
        if time_remaining == 0:
            time_remaining = SECONDS_PER_BOTTLE
        session_start_time = time.time()
        
        return jsonify({'success': True, 'message': 'Internet connected!'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/disconnect_internet')
def disconnect_internet():
    """Manual disconnect and end session for all users"""
    global internet_active, session_active, user_sessions, pending_bottles
    try:
        disable_internet()
        internet_active = False
        session_active = False  # Stop IR detection
        user_sessions.clear()  # Clear all user sessions
        pending_bottles = 0  # Clear pending bottles
        
        return jsonify({'success': True, 'message': 'Internet disconnected! All sessions cleared.'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# -------------------------------
# Main Program
# -------------------------------
if __name__ == '__main__':
    try:
        print("IR Motion Detection System Starting...")
        print(f"Using GPIO Pin: {IR_SENSOR_PIN}")
        print("Access the web interface at: http://10.0.0.1:5000")
        app.run(host='10.0.0.1', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        GPIO.cleanup()
