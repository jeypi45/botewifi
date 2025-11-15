#!/bin/bash
# Quick setup script for Bottle Piso WiFi

echo "=================================="
echo "Bottle Piso WiFi - Quick Setup"
echo "=================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (use sudo)"
    exit 1
fi

# Update system
echo "Updating system packages..."
apt-get update

# Install dependencies
echo "Installing dependencies..."
apt-get install -y python3 python3-pip python3-dev
apt-get install -y hostapd dnsmasq iptables iptables-persistent

# Install Python packages
echo "Installing Python packages..."
pip3 install -r requirements.txt

# Create templates directory
echo "Setting up directory structure..."
mkdir -p templates
cp index.html templates/ 2>/dev/null || echo "index.html already in templates/"

# Enable IP forwarding
echo "Enabling IP forwarding..."
sysctl -w net.ipv4.ip_forward=1
if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi

# Setup iptables rules
echo "Setting up iptables rules..."
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT

# Save iptables rules
echo "Saving iptables rules..."
iptables-save > /etc/iptables/rules.v4

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Configure hostapd in /etc/hostapd/hostapd.conf"
echo "2. Configure dnsmasq in /etc/dnsmasq.conf"
echo "3. Set static IP for wlan0 (192.168.1.1)"
echo "4. Update API_URL in templates/index.html"
echo "5. Connect IR sensor to GPIO pin 7"
echo "6. Run: sudo python3 server.py"
echo ""
echo "See README.md for detailed instructions"
