# Deploy User Guide to GitHub Pages

## Quick Setup Steps:

### 1. Enable GitHub Pages
1. Go to your repository: https://github.com/jeypi45/botewifi
2. Click **Settings** (top menu)
3. Scroll down to **Pages** (left sidebar)
4. Under "Source", select **Deploy from a branch**
5. Select branch: **main**
6. Select folder: **/ (root)**
7. Click **Save**

### 2. Wait for Deployment
- GitHub will build and deploy your site (takes 1-2 minutes)
- Once ready, your guide will be available at:
  - **https://jeypi45.github.io/botewifi/guide.html**

### 3. Update QR Code (Already Done!)
- The qrcode.html file has been updated to support both local and GitHub Pages URLs
- It will automatically detect which URL to use

### 4. Test Your Deployment
1. Wait 1-2 minutes after enabling GitHub Pages
2. Visit: https://jeypi45.github.io/botewifi/guide.html
3. If it works, your QR code will now work from anywhere!

## URLs After Deployment:

- **User Guide:** https://jeypi45.github.io/botewifi/guide.html
- **QR Code Page:** https://jeypi45.github.io/botewifi/qrcode.html
- **Local System:** http://10.0.0.1:5000 (only works on your WiFi network)

## Updating the Guide:

Whenever you make changes:
1. Commit your changes: `git add . && git commit -m "Update guide"`
2. Push to GitHub: `git push`
3. GitHub Pages auto-updates within 1-2 minutes

## Note:
- The main Bote WiFi system (app.py) still runs locally on your Orange Pi
- Only the user guide is hosted on GitHub Pages for public access
- Users can scan the QR code from anywhere to read the guide
- They still need to connect to your WiFi to use the actual system
