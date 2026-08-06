"""ops_dashboard.tunnel — Cloudflare Tunnel setup helper for remote dashboard access.

Provides CLI helpers for managing a Cloudflare named tunnel that exposes the
ops dashboard (port 5060) to the internet via a fixed hostname.

## Cloudflare Tunnel Setup for Ops Dashboard

### Prerequisites
- Cloudflare account with a domain managed by Cloudflare
- cloudflared CLI installed on the host machine

### Step 1: Install cloudflared
```bash
brew install cloudflare/cloudflare/cloudflared
```

### Step 2: Authenticate with Cloudflare
```bash
cloudflared tunnel login
# Opens browser — select the domain to authorize
# Creates ~/.cloudflared/cert.pem
```

### Step 3: Create the named tunnel
```bash
cloudflared tunnel create ops-dashboard
# Outputs: Created tunnel ops-dashboard with id <TUNNEL_ID>
# Creates: ~/.cloudflared/<TUNNEL_ID>.json (credentials file)
```

### Step 4: Create config.yml
Create `~/.cloudflared/config.yml` with the following structure:
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

### Step 5: Route DNS
```bash
cloudflared tunnel route dns ops-dashboard ops.yourdomain.com
# Creates CNAME: ops.yourdomain.com → <TUNNEL_ID>.cfargotunnel.com
```

### Step 6: Run the tunnel
```bash
cloudflared tunnel run ops-dashboard
```

### Step 7: Register as macOS launchd service (optional, for persistence)
```bash
# Create ~/Library/LaunchAgents/com.cloudflare.cloudflared.plist
# Point to: cloudflared tunnel run --config ~/.cloudflared/config.yml ops-dashboard
# Use launchctl to load/start the service
```

### Security Notes
- The dashboard uses Basic Auth (OPS_USER/OPS_PASSWORD env vars).
- The tunnel does NOT bypass authentication — all requests require valid credentials.
- Tunnel credentials file (~/.cloudflared/<TUNNEL_ID>.json) contains sensitive data — restrict permissions:
  ```bash
  chmod 600 ~/.cloudflared/<TUNNEL_ID>.json
  ```
- The tunnel hostname should not be publicly listed to reduce attack surface.

### Important Constraints
- This script does NOT auto-create the tunnel (requires browser auth).
- This script does NOT modify existing Cloudflare Workers config.
- The tunnel is additive — does not affect existing wrangler deploys.
"""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Default tunnel configuration
DEFAULT_TUNNEL_NAME = "ops-dashboard"
DEFAULT_PORT = 5060
DEFAULT_CONFIG_DIR = Path.home() / ".cloudflared"


def check_cloudflared() -> bool:
    """Verify that cloudflared is installed and accessible.

    Returns:
        True if cloudflared is found in PATH, False otherwise.
    """
    result = shutil.which("cloudflared")
    if result is None:
        logger.error("cloudflared not found in PATH. Install with: brew install cloudflare/cloudflare/cloudflared")
        return False
    logger.info("cloudflared found at: %s", result)
    return True


def create_tunnel(name: str = DEFAULT_TUNNEL_NAME, hostname: str = None, port: int = DEFAULT_PORT) -> dict:
    """Create a Cloudflare named tunnel and write config.yml.

    This function runs `cloudflared tunnel create` which requires prior
    authentication via `cloudflared tunnel login`.

    Args:
        name: Tunnel name (default: ops-dashboard)
        hostname: External hostname (e.g., ops.yourdomain.com). If None, DNS routing is skipped.
        port: Local port to tunnel to (default: 5060)

    Returns:
        dict with keys: success, tunnel_id, config_path, message
    """
    if not check_cloudflared():
        return {"success": False, "message": "cloudflared not installed"}

    # Create the tunnel
    cmd = ["cloudflared", "tunnel", "create", name]
    logger.info("Running: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        # Parse tunnel ID from output
        # Output format: "Created tunnel <name> with id <uuid>"
        tunnel_id = None
        for line in result.stdout.splitlines():
            if "with id" in line.lower():
                tunnel_id = line.split("with id")[-1].strip()
                break

        if not tunnel_id:
            # Try to extract from stderr or parse differently
            logger.warning("Could not parse tunnel ID from output: %s", result.stdout)

        logger.info("Tunnel '%s' created successfully. ID: %s", name, tunnel_id)

    except subprocess.CalledProcessError as e:
        logger.error("Failed to create tunnel: %s", e.stderr)
        return {"success": False, "message": f"Failed to create tunnel: {e.stderr}"}

    # Write config.yml
    config_path = DEFAULT_CONFIG_DIR / "config.yml"
    tunnel_id_str = tunnel_id or "<TUNNEL_ID>"
    credentials_path = DEFAULT_CONFIG_DIR / f"{tunnel_id_str}.json"

    ingress_lines = []
    if hostname:
        ingress_lines.append(f"  - hostname: {hostname}")
        ingress_lines.append(f"    service: http://localhost:{port}")
        ingress_lines.append("    originRequest:")
        ingress_lines.append("      noTLSVerify: false")
    else:
        ingress_lines.append(f"  - service: http://localhost:{port}")

    ingress_lines.append("  - service: http_status:404")

    config_content = f"""tunnel: {tunnel_id_str}
credentials-file: {credentials_path}

ingress:
{chr(10).join(ingress_lines)}
"""

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(config_content)
        logger.info("Config written to: %s", config_path)
    except Exception as e:
        logger.error("Failed to write config: %s", e)
        return {"success": False, "message": f"Config write failed: {e}"}

    # Route DNS if hostname provided
    if hostname and tunnel_id:
        dns_cmd = ["cloudflared", "tunnel", "route", "dns", name, hostname]
        logger.info("Running: %s", " ".join(dns_cmd))
        try:
            dns_result = subprocess.run(
                dns_cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info("DNS routed: %s", dns_result.stdout)
        except subprocess.CalledProcessError as e:
            logger.warning("DNS routing failed (may already exist): %s", e.stderr)

    return {
        "success": True,
        "tunnel_id": tunnel_id,
        "config_path": str(config_path),
        "message": f"Tunnel '{name}' created. Config at {config_path}",
    }


def start_tunnel(name: str = DEFAULT_TUNNEL_NAME) -> dict:
    """Start a Cloudflare named tunnel.

    Args:
        name: Tunnel name to start (default: ops-dashboard)

    Returns:
        dict with success status and message
    """
    if not check_cloudflared():
        return {"success": False, "message": "cloudflared not installed"}

    cmd = ["cloudflared", "tunnel", "run", name]
    logger.info("Starting tunnel: %s", " ".join(cmd))

    try:
        # Use Popen for non-blocking start (tunnel runs indefinitely)
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        logger.info("Tunnel started with PID: %d", process.pid)
        return {
            "success": True,
            "pid": process.pid,
            "message": f"Tunnel '{name}' started (PID: {process.pid})",
        }
    except Exception as e:
        logger.error("Failed to start tunnel: %s", e)
        return {"success": False, "message": f"Failed to start tunnel: {e}"}


def get_tunnel_url(name: str = DEFAULT_TUNNEL_NAME) -> str:
    """Return the assigned hostname for a tunnel.

    Reads the config.yml to extract the hostname.

    Args:
        name: Tunnel name (default: ops-dashboard)

    Returns:
        The hostname string, or empty string if not found.
    """
    config_path = DEFAULT_CONFIG_DIR / "config.yml"
    if not config_path.exists():
        logger.warning("Config not found at %s", config_path)
        return ""

    try:
        content = config_path.read_text()
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("hostname:"):
                return line.split("hostname:", 1)[1].strip()
    except Exception as e:
        logger.error("Failed to read config: %s", e)

    return ""


def list_tunnels() -> list:
    """List all configured Cloudflare tunnels.

    Returns:
        List of tunnel names/IDs.
    """
    if not check_cloudflared():
        return []

    cmd = ["cloudflared", "tunnel", "list"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        tunnels = []
        for line in result.stdout.splitlines()[1:]:  # Skip header
            parts = line.split()
            if parts:
                tunnels.append(parts[0])
        return tunnels
    except subprocess.CalledProcessError as e:
        logger.error("Failed to list tunnels: %s", e.stderr)
        return []


def delete_tunnel(name: str) -> dict:
    """Delete a Cloudflare named tunnel.

    Args:
        name: Tunnel name to delete

    Returns:
        dict with success status and message
    """
    if not check_cloudflared():
        return {"success": False, "message": "cloudflared not installed"}

    cmd = ["cloudflared", "tunnel", "delete", name]
    logger.info("Deleting tunnel: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("Tunnel deleted: %s", result.stdout)
        return {"success": True, "message": f"Tunnel '{name}' deleted"}
    except subprocess.CalledProcessError as e:
        logger.error("Failed to delete tunnel: %s", e.stderr)
        return {"success": False, "message": f"Failed to delete tunnel: {e.stderr}"}


def setup_launchd_service(name: str = DEFAULT_TUNNEL_NAME, config_path: str = None) -> dict:
    """Create a launchd plist for tunnel persistence on macOS.

    Args:
        name: Tunnel name (default: ops-dashboard)
        config_path: Path to config.yml (default: ~/.cloudflared/config.yml)

    Returns:
        dict with success status and plist path
    """
    if config_path is None:
        config_path = str(DEFAULT_CONFIG_DIR / "config.yml")

    plist_name = f"com.cloudflare.cloudflared.{name}"
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{plist_name}.plist"

    cloudflared_path = shutil.which("cloudflared")
    if not cloudflared_path:
        return {"success": False, "message": "cloudflared not found in PATH"}

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{plist_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{cloudflared_path}</string>
        <string>tunnel</string>
        <string>run</string>
        <string>--config</string>
        <string>{config_path}</string>
        <string>{name}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/{plist_name}.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/{plist_name}.log</string>
</dict>
</plist>
"""

    try:
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_path.write_text(plist_content)
        logger.info("launchd plist created at: %s", plist_path)
        return {
            "success": True,
            "plist_path": str(plist_path),
            "message": f"Plist created. Load with: launchctl load {plist_path}",
        }
    except Exception as e:
        logger.error("Failed to create plist: %s", e)
        return {"success": False, "message": f"Failed to create plist: {e}"}


def main():
    """CLI entry point for tunnel management."""
    import argparse

    parser = argparse.ArgumentParser(description="Cloudflare Tunnel helper for ops dashboard")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # check
    subparsers.add_parser("check", help="Check if cloudflared is installed")

    # create
    create_parser = subparsers.add_parser("create", help="Create a new tunnel")
    create_parser.add_argument("--name", default=DEFAULT_TUNNEL_NAME, help="Tunnel name")
    create_parser.add_argument("--hostname", help="External hostname (e.g., ops.yourdomain.com)")
    create_parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Local port")

    # start
    start_parser = subparsers.add_parser("start", help="Start a tunnel")
    start_parser.add_argument("--name", default=DEFAULT_TUNNEL_NAME, help="Tunnel name")

    # url
    url_parser = subparsers.add_parser("url", help="Get tunnel URL from config")
    url_parser.add_argument("--name", default=DEFAULT_TUNNEL_NAME, help="Tunnel name")

    # list
    subparsers.add_parser("list", help="List all tunnels")

    # delete
    del_parser = subparsers.add_parser("delete", help="Delete a tunnel")
    del_parser.add_argument("name", help="Tunnel name to delete")

    # launchd
    launchd_parser = subparsers.add_parser("launchd", help="Create launchd plist for persistence")
    launchd_parser.add_argument("--name", default=DEFAULT_TUNNEL_NAME, help="Tunnel name")
    launchd_parser.add_argument("--config", help="Path to config.yml")

    args = parser.parse_args()

    if args.command == "check":
        ok = check_cloudflared()
        print("cloudflared: OK" if ok else "cloudflared: NOT FOUND")
        sys.exit(0 if ok else 1)

    elif args.command == "create":
        result = create_tunnel(args.name, args.hostname, args.port)
        print(result["message"])
        sys.exit(0 if result["success"] else 1)

    elif args.command == "start":
        result = start_tunnel(args.name)
        print(result["message"])
        sys.exit(0 if result["success"] else 1)

    elif args.command == "url":
        url = get_tunnel_url(args.name)
        if url:
            print(f"Tunnel URL: {url}")
        else:
            print("No hostname found in config")
            sys.exit(1)

    elif args.command == "list":
        tunnels = list_tunnels()
        if tunnels:
            print("Tunnels:")
            for t in tunnels:
                print(f"  - {t}")
        else:
            print("No tunnels found")
        sys.exit(0)

    elif args.command == "delete":
        result = delete_tunnel(args.name)
        print(result["message"])
        sys.exit(0 if result["success"] else 1)

    elif args.command == "launchd":
        result = setup_launchd_service(args.name, args.config)
        print(result["message"])
        sys.exit(0 if result["success"] else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
