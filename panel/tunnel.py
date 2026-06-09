"""
Tunnel management.
"""

import os
import select
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

def check_local_port(port=25565) -> bool:
    """Verifica que el puerto local esté accesible antes de tunelizar."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        result = s.connect_ex(('127.0.0.1', port))
        s.close()
        if result == 0:
            print(f"[OK] Puerto local {port} ACCESIBLE vía 127.0.0.1")
            return True
        print(f"[WARN] Puerto local {port} NO accesible vía 127.0.0.1 (errno={result})")
        return False
    except Exception as e:
        print(f"[WARN] check_local_port: {e}")
        return False

_tunnel_proc = None

def start_pyjamas() -> str:
    """Retorna la dirección pyjam.as o None si falla"""
    global _tunnel_proc
    try:
        subprocess.run(['pkill', '-f', 'pyjam.as'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['pkill', '-f', 'ssh.*pyjam'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t.sleep(1)

        print("[INFO] Conectando a pyjam.as...")
        proc = subprocess.Popen(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ServerAliveInterval=30',
             '-o', 'ServerAliveCountMax=3', '-N', '-T',
             '-R', '1:localhost:25565', 'plan@pyjam.as'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        _tunnel_proc = proc

        def drain(stream, prefix):
            for line in iter(stream.readline, b''):
                text = line.decode().strip()
                if text:
                    print(f"{prefix} {text}")
        threading.Thread(target=drain, args=(proc.stdout, "[PYJAMAS]"), daemon=True).start()
        threading.Thread(target=drain, args=(proc.stderr, "[PYJAMAS]"), daemon=True).start()

        end = t.time() + 15
        address = None
        while t.time() < end:
            if proc.poll() is not None:
                break
            try:
                import select
                ready = select.select([proc.stdout, proc.stderr], [], [], 1)[0]
                for stream in ready:
                    line = stream.readline().decode().strip()
                    if line:
                        if 'pyjam.as' in line and ':' in line:
                            import re
                            m = re.search(r'[\w.-]+\.pyjam\.as:\d+', line)
                            if m:
                                address = m.group(0)
                            break
            except (ValueError, OSError):
                continue
            if address:
                break

        if proc.poll() is None:
            address = address or "activo (verificar output arriba)"
            print(f"[OK] Túnel pyjam.as activo: {address}")
            return address

        print(f"[ERROR] pyjam.as terminó con código {proc.poll()}")
        return None
    except Exception as e:
        print(f"[ERROR] start_pyjamas: {e}")
        return None

ORACLE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpQIBAAKCAQEA2MeMFtvYxdyYBBYv91X4wpqVMArqL1PZCrYEeJWzD5fInEgW
/qTs+UE+LqlVSflo1ZZnmgUyTKHAFDE8DUVMZKNgQArXtKLcI0Y0DWotaVLDA7JT
tuf/ewOtmaP2tmAjMXKsLWgr3SwNM1nvqOy6iNPDP3/95veIlwgKCQ73l5izyi9w
D7XALYYW8EfSkPtQuYlaVsvzylJddZVjBkut2pPTE6sa3j0pW9vxa4nirBS5ck4y
PvzG2OwMtE7FrtEsp2NCMPWfcrrGQHrX3OGjRWZAZ+r3AdXPh+Os684DGqFlysz6
8H2WTriLJlBsTTBYGn+AIilFTvq1hvSSNp3xbwIDAQABAoIBAAYAWDzVxJrjBYOv
cuUqXc2oET3tlMLPU8XmeMSMgxLeb9urvz84z6VYN2F7/J7PUdCqmPRRn9fb7oEL
RTn/fiLscaC0QXkrEmRuRXNNn4jilVWH3VDF/B5VYWah0cBbdFNNH754u3t5rw/f
NdxRBBpU9SXP5EvoScFso+J7pe0YwcM+5FsrMFHcxQVCCY6yVGTh/NWvU2IP1Xsk
4pClthLVFMeIR1/FEfDhrVq26G7ow01en48ZKGWwL3svRxH4kvXD4sgWZyqOdKOL
3UxFjOV7LfRUIE0UkVTmS0M8tU11HJPOpctb1iBds8BPeUNgN2V5Ze541F/N9vt6
jeqxrUECgYEA7zaJcSxTPQMKMM8Z7DvcUXWT6xUkEk1choJRq4T0xL97Obrn+Rzh
FlYocNP2eM0iR2b9XNBya5V7aQLcmUDqFSApR4wlFnU7iyMVSRB8ZBL9Z6O5G2H6
5zJF2JTFcQUalDwyQeNkcoQd3/WfYasmHHRYoxZTuic5uNe2FN+YOGECgYEA5/39
0LGABvHkC9iZcWY1v42O8Vk+YGANL3ggt+aD6dQmDuOwbQxQf3ynecObz8UZK7Ya
SR/9C/zbAQBOoLTg5K9R+5aVqUKwTkHGs+Nec04N3uctBMvNZeSyRA/sgoo0LUha
P/zUc0ujusGdfS3lJ/xkX0xxqtwr1Cx2x3nKO88CgYEAtgvID0PPWQg+MiT6Mmjf
43JajrY5DGCpgIgexSxa5nxet/GA5nlO5yPMhQkacpaSdspvGLpdyXgqQiF2Zn8b
ZdZi89s4wl2XYeziHweX0sUM6lmT3r3zJw2AUDHwDHH450TkbnYyFGBtJ+qST87j
IxZ7+ilcsLd3Wy92l24ONyECgYEA34ZZDMBJc+eS61sKFTn+5Y6WQLLVJ/TEH42m
MKq5RQ30kXoOXjN0SDGqB+dR9DGbHAO8deKNZQR/WwqZt7wvyAeofTlNACXSS8SS
mHalZYG6WZ/yP2HCiL9+h5e0MN7KgSrqUibf6CrkGag9fwQ+fHVxnGTCTHcQ/8DL
vUz6bv8CgYEAsXwpboKbX4KEWEjNCxwT2PSL0kg64VWd0eHE1iNUHc2VzcmwpVjF
Wt9QjjXLay0HeDMMhKkV8rJlNd1Jts4jkmzc4CqBaniKRZldKX3TjiiZEXTLnZp2
/1Z/vRk7fYm5p2SyCYGXnSLFZXyE6r3iwFLYIdpObqtajXofutRdU98=
-----END RSA PRIVATE KEY-----"""

def start_ssh_tunnel() -> bool:
    try:
        key_path = "/tmp/oracle_key"
        with open(key_path, "w") as f:
            f.write(ORACLE_KEY)
        os.chmod(key_path, 0o600)

        subprocess.run(['pkill', '-f', 'ssh.*oracle_key'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t.sleep(1)

        print("[INFO] Starting SSH reverse tunnel to VPS...")
        proc = subprocess.Popen([
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ServerAliveInterval=30',
            '-o', 'ServerAliveCountMax=3',
            '-o', 'ExitOnForwardFailure=yes',
            '-N',
            '-R', '127.0.0.1:25565:localhost:25565',
            'ubuntu@64.181.171.17',
            '-i', key_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

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
                if line:
                    print(f"[SSH] {line}")
                if 'forwarding port' in line.lower() or 'entering interactive session' in line.lower():
                    connected = True
                    break
            except:
                pass

        if proc.poll() is None:
            print("[OK] SSH tunnel established: 64.181.171.17:25565")
            return True
        else:
            stderr_output = proc.stderr.read().decode() if proc.stderr else ""
            print(f"[ERROR] SSH tunnel failed: {stderr_output}")
            return False

    except Exception as e:
        print(f"[ERROR] start_ssh_tunnel: {e}")
        return False
