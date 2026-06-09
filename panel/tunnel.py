"""
Tunnel management.
"""

import os
import subprocess
import threading
import queue
import time as t

_minecraft_url = "64.181.171.17:25565"

def set_minecraft_url(url: str):
    global _minecraft_url
    _minecraft_url = url

def get_current_minecraft_url() -> str:
    return _minecraft_url

def _install_frpc():
    frpc_path = "/usr/local/bin/frpc"
    if os.path.exists(frpc_path):
        return
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

def start_frp() -> bool:
    try:
        _install_frpc()

        subprocess.run(['pkill', '-f', 'frpc'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t.sleep(1)

        config = 'serverAddr = "64.181.171.17"\nserverPort = 7000\n\n[[proxies]]\nname = "minecraft"\ntype = "tcp"\nlocalIP = "127.0.0.1"\nlocalPort = 25565\nremotePort = 25565\n'
        with open("/tmp/frpc.toml", "w") as f:
            f.write(config)

        print("[INFO] Starting frpc...")
        proc = subprocess.Popen(
            ['/usr/local/bin/frpc', '-c', '/tmp/frpc.toml'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        q = queue.Queue()
        def reader(stream):
            for line in iter(stream.readline, b''):
                q.put(line.decode().strip())
        threading.Thread(target=reader, args=(proc.stdout,), daemon=True).start()
        threading.Thread(target=reader, args=(proc.stderr,), daemon=True).start()

        end = t.time() + 10
        connected = False
        while t.time() < end:
            try:
                line = q.get(timeout=1)
                print(f"[FRPC] {line}")
                if 'login to server success' in line.lower() or 'start proxy success' in line.lower():
                    connected = True
                    break
                if 'error' in line.lower() or 'failed' in line.lower():
                    print(f"[ERROR] frpc: {line}")
            except:
                pass

        if connected:
            print(f"[OK] frpc conectado a VPS: 64.181.171.17:25565")
            return True
        else:
            print("[WARNING] frpc no confirmó conexión en 10 segundos")
            return proc.poll() is None

    except Exception as e:
        print(f"[ERROR] start_frp: {e}")
        return False
