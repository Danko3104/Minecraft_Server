import subprocess
import os
import re
import json
import time
import select

_playit_process = None
_minecraft_url = ""
_playit_configured = False


def _install_playit():
    cmd = 'command -v playit || (curl -SsL https://playit-cloud.github.io/ppa/key.gpg | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/playit.gpg > /dev/null && echo "deb [signed-by=/etc/apt/trusted.gpg.d/playit.gpg] https://playit-cloud.github.io/ppa/data ./" | sudo tee /etc/apt/sources.list.d/playit-cloud.list > /dev/null && sudo apt -qq update && sudo apt install -y playit)'
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', errors='ignore')
        print(f"[ERROR] _install_playit stderr:\n{stderr}")
        raise Exception(f"Failed to install playit:\n{stderr}")


def _start_playit_and_get_claim_code() -> dict:
    global _playit_process
    try:
        _install_playit()

        _playit_process = subprocess.Popen(
            ['playit'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        output = ""
        start = time.time()
        timeout = 30
        poll = select.poll()
        poll.register(_playit_process.stdout, select.POLLIN)

        while time.time() - start < timeout:
            if poll.poll(500):
                raw = _playit_process.stdout.readline()
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
            elif _playit_process.poll() is not None:
                break

        _playit_process.terminate()
        _playit_process = None
        return {"success": False, "error": "No se encontr\u00f3 claim code en la salida", "output": output}
    except Exception as e:
        print(f"[ERROR] _start_playit_and_get_claim_code: {e}")
        return {"success": False, "error": str(e)}


def _get_playit_secret_path() -> str:
    try:
        result = subprocess.run(['playit', 'secret-path'], capture_output=True, timeout=10)
        if result.returncode == 0:
            return result.stdout.decode('utf-8', errors='ignore').strip()
    except:
        pass
    return "/root/.config/playit/playit.toml"


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
    global _playit_process, _playit_configured
    try:
        config_path = _get_playit_secret_path()
        config_dir = os.path.dirname(config_path)
        os.makedirs(config_dir, exist_ok=True)

        with open(config_path, 'w') as f:
            f.write(f'secret_key = "{secret_key}"\n')

        _playit_process = subprocess.Popen(
            ['playit', '-s', 'start'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        _playit_configured = True
        return True
    except Exception as e:
        print(f"[ERROR] _start_playit_with_secret_key: {e}")
        return False


def get_playit_tunnel_address() -> str:
    try:
        result = subprocess.run(
            ['playit', 'tunnels', 'list'],
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
        result = subprocess.run(['pgrep', 'playit'], capture_output=True)
        return result.returncode == 0 and result.stdout.decode('utf-8', errors='ignore').strip() != ""
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
        return {"status": "error", "error": result.get("error", "Failed to get claim code")}

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
    global _playit_process
    if _playit_process is not None:
        _playit_process.terminate()
        try:
            _playit_process.wait(timeout=5)
        except:
            _playit_process.kill()
        _playit_process = None
