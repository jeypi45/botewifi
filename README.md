# Bottle Piso WiFi System

A WiFi access control system using Orange Pi and IR sensor. Users insert a bottle to activate internet access.

## Hardware Requirements
- Orange Pi (any model with GPIO)
- IR Sensor Module
- Plastic bottles for insertion detection
- WiFi dongle/adapter (if not built-in)

## Software Requirements
- Python 3.7+
- Flask web server
- OPi.GPIO library
- iptables (for network control)

## Wiring Diagram
```
IR Sensor Module → Orange Pi
VCC  → 5V (Pin 2 or 4)
GND  → Ground (Pin 6, 9, 14, 20, 25, 30, 34, or 39)
OUT  → GPIO 7 (Pin 7) - Configurable in server.py
```

## Installation

### 1. Install Python Dependencies
```bash
cd /path/to/botewifi
sudo pip3 install -r requirements.txt
```

### 2. Install OPi.GPIO (if not already installed)
```bash
sudo apt-get update
sudo apt-get install python3-dev python3-pip
sudo pip3 install OPi.GPIO
```

### 3. Configure Network (Orange Pi as WiFi Hotspot)

#### Install required packages
```bash
sudo apt-get install hostapd dnsmasq iptables
```

#### Configure hostapd (WiFi Access Point)
Edit `/etc/hostapd/hostapd.conf`:
```
interface=wlan0
driver=nl80211
ssid=BottleWiFi
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=bottle123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
```

#### Configure dnsmasq (DHCP Server)
Edit `/etc/dnsmasq.conf`:
```
interface=wlan0
dhcp-range=192.168.1.10,192.168.1.100,255.255.255.0,24h
dhcp-option=3,192.168.1.1
dhcp-option=6,8.8.8.8,8.8.4.4
server=8.8.8.8
address=/#/192.168.1.1
```

#### Configure static IP for wlan0
Edit `/etc/network/interfaces` or use NetworkManager:
```
auto wlan0
iface wlan0 inet static
    address 192.168.1.1
    netmask 255.255.255.0
```

#### Enable IP forwarding
```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

Make it permanent by editing `/etc/sysctl.conf`:
```
net.ipv4.ip_forward=1
```

#### Setup iptables NAT
```bash
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
sudo iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT

# Save iptables rules
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

### 4. Move HTML to templates folder
```bash
mkdir templates
mv index.html templates/
```

### 5. Update API URL in index.html
Edit `templates/index.html` and change the API_URL to your Orange Pi's IP:
```javascript
const API_URL = 'http://192.168.1.1:5000/api';
```

## Running the Server

### Manual Start
```bash
sudo python3 server.py
```

### Run as System Service
Create `/etc/systemd/system/bottlewifi.service`:
```ini
[Unit]
Description=Bottle Piso WiFi Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/botewifi
ExecStart=/usr/bin/python3 /path/to/botewifi/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable bottlewifi
sudo systemctl start bottlewifi
sudo systemctl status bottlewifi
```

## Configuration

Edit `server.py` to customize:
- `IR_SENSOR_PIN = 7` - GPIO pin for IR sensor
- `TIMER_DURATION = 10` - Countdown timer in seconds
- `WIFI_DURATION = 300` - Internet access duration (5 minutes)
- `WIFI_INTERFACE = "wlan0"` - WiFi interface name

## Testing

### Test IR Sensor
```bash
sudo python3 -c "
import OPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)
GPIO.setup(7, GPIO.IN)

print('Reading IR sensor... (Ctrl+C to exit)')
while True:
    status = GPIO.input(7)
    print(f'Sensor: {\"DETECTED\" if status == 0 else \"NO OBJECT\"}')
    time.sleep(0.5)
"
```

### Test Flask Server
```bash
# Start server
sudo python3 server.py

# In another terminal, test the API
curl http://192.168.1.1:5000/api/status
curl -X POST http://192.168.1.1:5000/api/insert_bottle
```

## How It Works

1. **User connects** to "BottleWiFi" access point
2. **Captive portal** redirects to the web interface (index.html)
3. **User clicks** "Insert Bottle" button
4. **IR sensor** detects bottle insertion
5. **10-second countdown** begins
6. **After countdown**, user's MAC address is granted internet access
7. **Internet access** lasts for 5 minutes (configurable)
8. **Access expires** automatically after time limit

## API Endpoints

- `GET /` - Serve web interface
- `GET /api/status` - Get system status
- `GET /api/check_bottle` - Check if bottle is detected
- `POST /api/insert_bottle` - Start the activation process
- `POST /api/disconnect` - Manually disconnect user

## Troubleshooting

### IR Sensor not working
- Check wiring connections
- Verify GPIO pin number in code matches physical connection
- Test sensor with LED or multimeter
- Adjust sensor sensitivity (potentiometer on sensor module)

### WiFi not activating
- Check iptables rules: `sudo iptables -L -n -v`
- Verify IP forwarding: `cat /proc/sys/net/ipv4/ip_forward`
- Check network interfaces: `ip addr show`
- View logs: `sudo journalctl -u bottlewifi -f`

### Cannot connect to WiFi
- Verify hostapd is running: `sudo systemctl status hostapd`
- Check dnsmasq: `sudo systemctl status dnsmasq`
- Restart services: `sudo systemctl restart hostapd dnsmasq`

### Web interface not loading
- Verify Flask is running on port 5000
- Check firewall rules
- Test with: `curl http://localhost:5000`

## Security Notes

⚠️ **Important Security Considerations:**
- Change default WiFi password in hostapd.conf
- Implement user authentication if needed
- Add rate limiting to prevent abuse
- Monitor system logs regularly
- Consider adding payment integration for commercial use

## License
MIT License - Use freely for personal or commercial projects
