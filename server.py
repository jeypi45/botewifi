#!/usr/bin/env python3
"""
Bottle Piso WiFi Backend Server
Handles IR sensor detection and WiFi access control for Orange Pi
"""

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import threading
import time
import subprocess
import os

# GPIO library for Orange Pi
try:
    import OPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    print("Warning: OPi.GPIO not available. Running in simulation mode.")
    GPIO_AVAILABLE = False

app = Flask(__name__)
CORS(app)

# Configuration
IR_SENSOR_PIN = 7  # GPIO pin for IR sensor (adjust based on your setup)
WIFI_INTERFACE = "wlan0"  # WiFi interface name
TIMER_DURATION = 10  # seconds
WIFI_DURATION = 300  # 5 minutes of internet access after bottle insertion

# Global state
bottle_detected = False
wifi_active = False
timer_running = False
current_timer = 0
active_users = {}  # Track active users and their expiry times

def setup_gpio():
    """Initialize GPIO for IR sensor"""
    if GPIO_AVAILABLE:
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(IR_SENSOR_PIN, GPIO.IN)
        print(f"GPIO initialized. IR Sensor on pin {IR_SENSOR_PIN}")
    else:
        print("Running in simulation mode without GPIO")

def cleanup_gpio():
    """Cleanup GPIO on exit"""
    if GPIO_AVAILABLE:
        GPIO.cleanup()

def read_ir_sensor():
    """Read IR sensor state"""
    if GPIO_AVAILABLE:
        # IR sensor typically outputs LOW when object is detected
        return GPIO.input(IR_SENSOR_PIN) == GPIO.LOW
    else:
        # Simulation mode - always return False
        return False

def enable_wifi_access(mac_address):
    """Enable WiFi access for a specific MAC address"""
    try:
        # Add iptables rule to allow internet access
        subprocess.run([
            'sudo', 'iptables', '-t', 'nat', '-I', 'PREROUTING',
            '-m', 'mac', '--mac-source', mac_address,
            '-j', 'ACCEPT'
        ], check=True)
        
        subprocess.run([
            'sudo', 'iptables', '-I', 'FORWARD',
            '-m', 'mac', '--mac-source', mac_address,
            '-j', 'ACCEPT'
        ], check=True)
        
        print(f"WiFi access enabled for {mac_address}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error enabling WiFi access: {e}")
        return False

def disable_wifi_access(mac_address):
    """Disable WiFi access for a specific MAC address"""
    try:
        # Remove iptables rules
        subprocess.run([
            'sudo', 'iptables', '-t', 'nat', '-D', 'PREROUTING',
            '-m', 'mac', '--mac-source', mac_address,
            '-j', 'ACCEPT'
        ], check=False)
        
        subprocess.run([
            'sudo', 'iptables', '-D', 'FORWARD',
            '-m', 'mac', '--mac-source', mac_address,
            '-j', 'ACCEPT'
        ], check=False)
        
        print(f"WiFi access disabled for {mac_address}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error disabling WiFi access: {e}")
        return False

def block_all_internet():
    """Block internet access for all users (captive portal mode)"""
    try:
        # Redirect all HTTP traffic to captive portal
        subprocess.run([
            'sudo', 'iptables', '-t', 'nat', '-A', 'PREROUTING',
            '-p', 'tcp', '--dport', '80',
            '-j', 'DNAT', '--to-destination', '192.168.1.1:80'
        ], check=True)
        
        subprocess.run([
            'sudo', 'iptables', '-t', 'nat', '-A', 'PREROUTING',
            '-p', 'tcp', '--dport', '443',
            '-j', 'DNAT', '--to-destination', '192.168.1.1:80'
        ], check=True)
        
        print("Captive portal mode enabled")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error setting up captive portal: {e}")
        return False

def get_client_mac(ip_address):
    """Get MAC address from IP address"""
    try:
        # Read ARP table to get MAC address
        result = subprocess.run(
            ['arp', '-n', ip_address],
            capture_output=True,
            text=True
        )
        
        lines = result.stdout.split('\n')
        for line in lines:
            if ip_address in line:
                parts = line.split()
                if len(parts) >= 3:
                    return parts[2]
        return None
    except Exception as e:
        print(f"Error getting MAC address: {e}")
        return None

def monitor_ir_sensor():
    """Background thread to monitor IR sensor"""
    global bottle_detected
    
    while True:
        if read_ir_sensor():
            if not bottle_detected:
                bottle_detected = True
                print("Bottle detected!")
        else:
            bottle_detected = False
        
        time.sleep(0.1)  # Check every 100ms

def manage_user_timers():
    """Background thread to manage active user timers"""
    global active_users
    
    while True:
        current_time = time.time()
        expired_users = []
        
        for mac_address, expiry_time in active_users.items():
            if current_time >= expiry_time:
                disable_wifi_access(mac_address)
                expired_users.append(mac_address)
                print(f"WiFi access expired for {mac_address}")
        
        # Remove expired users
        for mac_address in expired_users:
            del active_users[mac_address]
        
        time.sleep(1)  # Check every second

@app.route('/')
def index():
    """Serve the main HTML page"""
    return render_template('index.html')

@app.route('/api/check_bottle', methods=['GET'])
def check_bottle():
    """API endpoint to check if bottle is detected"""
    return jsonify({
        'detected': bottle_detected,
        'timestamp': time.time()
    })

@app.route('/api/insert_bottle', methods=['POST'])
def insert_bottle():
    """API endpoint called when user clicks Insert Bottle"""
    global timer_running, current_timer, wifi_active
    
    # Get client IP and MAC address
    client_ip = request.remote_addr
    mac_address = get_client_mac(client_ip)
    
    if not mac_address:
        # Fallback MAC address for testing
        mac_address = request.json.get('mac_address', 'unknown')
    
    print(f"Insert bottle request from IP: {client_ip}, MAC: {mac_address}")
    
    # Check if bottle is actually detected (or simulation mode)
    if not GPIO_AVAILABLE or bottle_detected:
        # Start timer
        timer_running = True
        current_timer = TIMER_DURATION
        
        # Enable WiFi after timer
        def enable_after_timer():
            global timer_running, wifi_active, active_users
            time.sleep(TIMER_DURATION)
            
            # Enable WiFi access for this user
            if enable_wifi_access(mac_address):
                wifi_active = True
                # Set expiry time
                active_users[mac_address] = time.time() + WIFI_DURATION
                print(f"WiFi enabled for {mac_address} for {WIFI_DURATION} seconds")
            
            timer_running = False
        
        threading.Thread(target=enable_after_timer, daemon=True).start()
        
        return jsonify({
            'success': True,
            'message': 'Bottle detected! WiFi will be enabled in 10 seconds.',
            'timer': TIMER_DURATION,
            'wifi_duration': WIFI_DURATION,
            'mac_address': mac_address
        })
    else:
        return jsonify({
            'success': False,
            'message': 'No bottle detected. Please insert a bottle first.',
            'detected': bottle_detected
        }), 400

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current system status"""
    client_ip = request.remote_addr
    mac_address = get_client_mac(client_ip)
    
    user_active = mac_address in active_users if mac_address else False
    time_remaining = 0
    
    if user_active:
        time_remaining = int(active_users[mac_address] - time.time())
    
    return jsonify({
        'bottle_detected': bottle_detected,
        'timer_running': timer_running,
        'wifi_active': user_active,
        'time_remaining': max(0, time_remaining),
        'mac_address': mac_address,
        'client_ip': client_ip
    })

@app.route('/api/disconnect', methods=['POST'])
def disconnect_user():
    """Manually disconnect a user"""
    client_ip = request.remote_addr
    mac_address = get_client_mac(client_ip)
    
    if mac_address and mac_address in active_users:
        disable_wifi_access(mac_address)
        del active_users[mac_address]
        return jsonify({
            'success': True,
            'message': 'Disconnected successfully'
        })
    
    return jsonify({
        'success': False,
        'message': 'User not found or not connected'
    }), 400

def initialize_system():
    """Initialize the system on startup"""
    print("Initializing Bottle Piso WiFi System...")
    
    # Setup GPIO
    setup_gpio()
    
    # Setup captive portal (optional)
    # block_all_internet()
    
    # Start monitoring threads
    if GPIO_AVAILABLE:
        sensor_thread = threading.Thread(target=monitor_ir_sensor, daemon=True)
        sensor_thread.start()
        print("IR sensor monitoring started")
    
    timer_thread = threading.Thread(target=manage_user_timers, daemon=True)
    timer_thread.start()
    print("User timer management started")
    
    print("System initialized successfully!")

if __name__ == '__main__':
    try:
        initialize_system()
        
        # Run Flask server
        # Use 0.0.0.0 to make it accessible from other devices
        app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        cleanup_gpio()
