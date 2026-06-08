import subprocess
import os
import re
import json
import time
import select

_minecraft_url = ""
_playit_configured = False

DOCKER_IMAGE = 'ghcr.io/playit-cloud/playit-agent:latest'
CONFIG_DIR = '/root/.config/playit'


def _install_playit():
    result = subprocess.run(['docker', '--version'], capture_output=True)
    if result.returncode != 0:
        raise Exception("Docker no est\u00e1 disponible en este entorno")


def _start_playit_and_get_claim_code() -> dict:
    try:
        _install_playit()

        os.makedirs(CONFIG_DIR, exist_ok=True)

        proc = subprocess.Popen(
            ['docker', 'run', '--rm', '--net=host',
             '-v', f'{CONFIG_DIR}:{CONFIG_DIR}',
             '--name', 'playit-agent',
             DOCKER_IMAGE],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        output = ""
        start = time.time()
        timeout = 60
        poll = select.poll()
        poll.register(proc.stdout, select.POLLIN)

        while time.time() - start < timeout:
            if poll.poll(500):
                raw = proc.stdout.readline()
                if not raw:
                    break
                line = raw.decode('utf-8', errors='ignore')
                output += line
                print(f"[PLAYIT] {line.strip()}")
                match = re.search(r'claim code[:\s]+([\w-]+)', output, re.IGNORECASE)
                if not match:
                    match = re.search(r'playit\.gg/claim/([\w-]+)', output, re.IGNORECASE)
                if match:
                    return {"success": True, "claim_code": match.group(1)}
            elif proc.poll() is not None:
                break

        return {"success": False, "error": "No se encontr\u00f3 claim code en la salida", "output": output}
    except Exception as e:
        print(f"[ERROR] _start_playit_and_get_claim_code: {e}")
        return {"success": False, "error": str(e)}


def _get_playit_secret_path() -> str:
    return os.path.join(CONFIG_DIR, 'playit.toml')


def _wait_for_secret_key_after_claim() -> dict:
    try:
        config_path = _get_playit_secret_path()
        timeout = 300
        start = time.time()

        while time.time() - start < timeout:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    content = f.read()
                match = re.search(r'secret_key\s*=\s*"([^"]+)"', content)
                if match:
                    return {"success": True, "secret_key": match.group(1)}
            time.sleep(3)

        return {"success": False, "error": "Timeout esperando secret_key (5 minutos)"}
    except Exception as e:
        print(f"[ERROR] _wait_for_secret_key_after_claim: {e}")
        return {"success": False, "error": str(e)}


def _start_playit_with_secret_key(secret_key: str) -> bool:
    global _playit_configured
    try:
        stop_playit()

        result = subprocess.run(
            ['docker', 'run', '-d', '--rm', '--net=host',
             '-e', f'SECRET_KEY={secret_key}',
             '--name', 'playit-agent',
             DOCKER_IMAGE],
            capture_output=True
        )
        if result.returncode != 0:
            stderr = result.stderr.decode('utf-8', errors='ignore')
            print(f"[ERROR] _start_playit_with_secret_key: {stderr}")
            return False

        _playit_configured = True
        return True
    except Exception as e:
        print(f"[ERROR] _start_playit_with_secret_key: {e}")
        return False


def get_playit_tunnel_address() -> str:
    try:
        result = subprocess.run(
            ['docker', 'exec', 'playit-agent', 'playit', 'tunnels', 'list'],
            capture_output=True, timeout=10
        )
        if result.returncode != 0:
            return ""

        data = json.loads(result.stdout.decode('utf-8', errors='ignore'))
        tunnels = data.get('tunnels', []) if isinstance(data, dict) else data
        if tunnels:
            address = tunnels[0].get('public_address', tunnels[0].get('address', ''))
            return address
        return ""
    except Exception as e:
        print(f"[ERROR] get_playit_tunnel_address: {e}")
        return ""


def _is_playit_running() -> bool:
    try:
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=playit-agent', '--format', '{{.Names}}'],
            capture_output=True
        )
        return b'playit-agent' in result.stdout
    except:
        return False


def start_minecraft_tunnel(tunnel_service: str = 'playit', secret_key: str = '') -> dict:
    if tunnel_service != 'playit':
        return {"status": "error", "error": f"Unknown tunnel service: {tunnel_service}"}

    global _playit_configured

    if _is_playit_running():
        _playit_configured = True
        address = get_playit_tunnel_address()
        if address:
            return {"status": "running", "address": address}
        return {"status": "running", "address": ""}

    _install_playit()

    if secret_key:
        if _start_playit_with_secret_key(secret_key):
            time.sleep(3)
            address = get_playit_tunnel_address()
            return {"status": "running", "address": address}
        return {"status": "error", "error": "Failed to start playit with secret key"}

    result = _start_playit_and_get_claim_code()
    if not result.get("success"):
        return {"status": "error", "error": result.get("error", "Failed to get claim code"), "output": result.get("output", "")}

    return {"status": "needs_claim", "claim_code": result["claim_code"]}


def setup_playit(secret_key: str = "") -> bool:
    if not secret_key:
        return False
    return _start_playit_with_secret_key(secret_key)


def get_minecraft_url() -> str:
    return _minecraft_url


def set_minecraft_url(url: str):
    global _minecraft_url
    _minecraft_url = url


def is_playit_configured() -> bool:
    return _playit_configured


def stop_playit():
    subprocess.run(['docker', 'stop', 'playit-agent'], capture_output=True)
