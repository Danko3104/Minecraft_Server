"""
Tunnel management.
"""

import os
import subprocess
import time

_minecraft_url = "64.181.171.17:25565"

def set_minecraft_url(url: str):
    global _minecraft_url
    _minecraft_url = url

def get_current_minecraft_url() -> str:
    return _minecraft_url

def start_frp() -> bool:
    """
    Downloads frpc (if needed) and starts it in background.
    Connects to the VPS frp server at 64.181.171.17:7000
    and exposes localhost:25565 as 64.181.171.17:25565.
    Returns True if frpc started successfully.
    """
    try:
        frpc_path = "/usr/local/bin/frpc"
        if not os.path.exists(frpc_path):
            print("[INFO] Downloading frpc (linux_amd64)...")
            import urllib.request
            url = ("https://github.com/fatedier/frp/releases/download/v0.69.1/"
                   "frp_0.69.1_linux_amd64.tar.gz")
            urllib.request.urlretrieve(url, "/tmp/frp_amd64.tar.gz")
            import tarfile
            with tarfile.open("/tmp/frp_amd64.tar.gz") as tar:
                tar.extractall("/tmp")
            subprocess.run(["cp", "/tmp/frp_0.69.1_linux_amd64/frpc", frpc_path], check=True)
            subprocess.run(["chmod", "+x", frpc_path], check=True)
            print("[OK] frpc installed")

        config = 'serverAddr = "64.181.171.17"\nserverPort = 7000\n\n[[proxies]]\nname = "minecraft"\ntype = "tcp"\nlocalIP = "127.0.0.1"\nlocalPort = 25565\nremotePort = 25565\n'
        with open("/tmp/frpc.toml", "w") as f:
            f.write(config)

        print("[INFO] Starting frpc...")
        proc = subprocess.Popen(
            [frpc_path, "-c", "/tmp/frpc.toml"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        time.sleep(3)
        if proc.poll() is None:
            print("[OK] frpc tunnel established: 64.181.171.17:25565")
            return True
        else:
            stderr = proc.stderr.read().decode()
            print(f"[ERROR] frpc failed: {stderr}")
            return False
    except Exception as e:
        print(f"[ERROR] start_frp: {e}")
        return False
