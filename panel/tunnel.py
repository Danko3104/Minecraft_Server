import subprocess
import os
import time
import urllib.request
import tarfile

_localtonet_process = None
_minecraft_url = ""
_playit_configured = False


def _install_localtonet():
    if os.path.exists('/usr/local/bin/localtonet'):
        return

    url = "https://localtonet.com/download/localtonet-linux-x64.tar.gz"
    dest = "/tmp/localtonet.tar.gz"

    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as e:
        raise Exception(f"Failed to download localtonet: {e}")

    if not os.path.exists(dest) or os.path.getsize(dest) == 0:
        raise Exception("Downloaded file is missing or empty")

    with tarfile.open(dest, 'r:gz') as tar:
        tar.extractall('/usr/local/bin/')

    os.chmod('/usr/local/bin/localtonet', 0o755)


def _start_localtonet(authtoken: str) -> dict:
    global _localtonet_process
    try:
        if _is_localtonet_running():
            return {'success': True, 'already_running': True}

        _install_localtonet()

        _localtonet_process = subprocess.Popen(
            ['localtonet', 'tcpudp', '-t', authtoken, '-p', '25565'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        time.sleep(10)

        if _is_localtonet_running():
            return {'success': True}

        _localtonet_process = None
        return {'success': False, 'error': 'localtonet no logró conectar'}
    except Exception as e:
        print(f"[ERROR] _start_localtonet: {e}")
        return {'success': False, 'error': str(e)}


def stop_localtonet():
    global _localtonet_process
    if _localtonet_process is not None:
        _localtonet_process.terminate()
        try:
            _localtonet_process.wait(timeout=5)
        except:
            _localtonet_process.kill()
        _localtonet_process = None
    subprocess.run(['pkill', 'localtonet'], capture_output=True)


def _is_localtonet_running() -> bool:
    try:
        result = subprocess.run(['pgrep', 'localtonet'], capture_output=True)
        return result.returncode == 0
    except:
        return False


def start_minecraft_tunnel(tunnel_service: str = '', server_config: dict = None, server_type: str = '') -> dict:
    if tunnel_service != 'localtonet':
        return {"status": "error", "error": f"Tunnel service not supported: {tunnel_service}"}

    server_config = server_config or {}
    localtonet_proxy = server_config.get('localtonet_proxy', {})
    authtoken = localtonet_proxy.get('authtoken', '')
    address = localtonet_proxy.get('address', '')

    if not authtoken:
        return {'status': 'needs_token'}

    if not address:
        return {'status': 'needs_address'}

    try:
        _install_localtonet()
    except Exception as e:
        return {'status': 'error', 'error': str(e)}

    resultado = _start_localtonet(authtoken)
    if resultado.get('success'):
        return {'status': 'running', 'address': address}
    return {'status': 'error', 'error': resultado.get('error', 'Failed to start localtonet')}


def get_playit_tunnel_address() -> str:
    return _minecraft_url


def _wait_for_secret_key_after_claim() -> dict:
    return {"success": False, "error": "Not implemented for localtonet"}


def setup_playit(secret_key: str = "") -> bool:
    return False


def get_minecraft_url() -> str:
    return _minecraft_url


def set_minecraft_url(url: str):
    global _minecraft_url
    _minecraft_url = url


def is_playit_configured() -> bool:
    return _playit_configured


def stop_playit():
    stop_localtonet()


def _install_playit():
    pass


def _get_playit_secret_path() -> str:
    return ""
