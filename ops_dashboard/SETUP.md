# Ops Dashboard Setup

## Overview

The ops dashboard provides fleet health monitoring for all 5000 pipelines. It runs on port 5060 and is protected by Basic Auth.

## Quick Start

```bash
# Install dependencies
pip install flask

# Set authentication credentials
export OPS_USER=ops
export OPS_PASSWORD=your-secure-password

# Run the dashboard
python -m ops_dashboard.app
```

## Remote Access via Cloudflare Tunnel

For mobile/remote access without exposing port 5060 directly, use a Cloudflare Tunnel.

### Prerequisites

- Cloudflare account with a domain managed by Cloudflare
- `cloudflared` CLI installed

### Installation

```bash
brew install cloudflare/cloudflare/cloudflared
```

### Authentication

```bash
cloudflared tunnel login
# Opens browser — select the domain to authorize
# Creates ~/.cloudflared/cert.pem
```

### Create Tunnel

```bash
cloudflared tunnel create ops-dashboard
# Outputs: Created tunnel ops-dashboard with id <TUNNEL_ID>
# Creates: ~/.cloudflared/<TUNNEL_ID>.json (credentials file)
```

### Configure Tunnel

Create `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /Users/twinssn/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: ops.yourdomain.com
    service: http://localhost:5060
    originRequest:
      noTLSVerify: false
  - service: http_status:404
```

### Route DNS

```bash
cloudflared tunnel route dns ops-dashboard ops.yourdomain.com
# Creates CNAME: ops.yourdomain.com → <TUNNEL_ID>.cfargotunnel.com
```

### Start Tunnel

```bash
cloudflared tunnel run ops-dashboard
```

### macOS Persistence (launchd)

To run the tunnel automatically on macOS login:

```bash
# Use the tunnel helper script
python -m ops_dashboard.tunnel launchd --name ops-dashboard

# Load the service
launchctl load ~/Library/LaunchAgents/com.cloudflare.cloudflared.ops-dashboard.plist
```

### Using the Helper Script

The `tunnel.py` module provides CLI helpers:

```bash
# Check if cloudflared is installed
python -m ops_dashboard.tunnel check

# Create a tunnel with DNS routing
python -m ops_dashboard.tunnel create --name ops-dashboard --hostname ops.yourdomain.com

# Start the tunnel
python -m ops_dashboard.tunnel start --name ops-dashboard

# List all tunnels
python -m ops_dashboard.tunnel list

# Get tunnel URL from config
python -m ops_dashboard.tunnel url

# Create launchd plist for persistence
python -m ops_dashboard.tunnel launchd --name ops-dashboard
```

## Security

- **Basic Auth**: All routes require authentication (OPS_USER/OPS_PASSWORD env vars)
- **Tunnel Auth**: The tunnel does NOT bypass authentication — all requests require valid credentials
- **Credentials File**: `~/.cloudflared/<TUNNEL_ID>.json` contains sensitive data — restrict permissions:
  ```bash
  chmod 600 ~/.cloudflared/<TUNNEL_ID>.json
  ```
- **Hostname Privacy**: The tunnel hostname should not be publicly listed to reduce attack surface

## Important Notes

- The tunnel is additive — does not affect existing wrangler deploys or Cloudflare Workers
- The dashboard must be running on port 5060 for the tunnel to work
- Cloudflare Tunnel requires prior browser authentication (`cloudflared tunnel login`)
- This script does NOT auto-create the tunnel — human authentication is required first
