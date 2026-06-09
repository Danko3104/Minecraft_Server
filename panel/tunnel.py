import subprocess
import os
import time
import threading


def start_serveo() -> bool:
    try:
        subprocess.run(['pkill', '-f', 'serveo'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['pkill', '-f', 'ssh.*serveo'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

        proc = subprocess.Popen(
            [
                'ssh', '-o', 'StrictHostKeyChecking=no',
                '-o', 'ServerAliveInterval=30',
                '-o', 'ServerAliveCountMax=3',
                '-R', 'minecraftcito:25565:localhost:25565',
                'serveo.net'
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        def leer_output_serveo(proc):
            for line in iter(proc.stderr.readline, b''):
                print(f"[SERVEO] {line.decode().strip()}")

        time.sleep(2)
        t = threading.Thread(target=leer_output_serveo, args=(proc,), daemon=True)
        t.start()

        time.sleep(3)
        poll = proc.poll()
        print(f"[DEBUG] serveo estado: {poll}")

        if poll is not None:
            return False

        return True

    except Exception as e:
        print(f"[ERROR] start_serveo: {e}")
        return False


def get_minecraft_url() -> str:
    return "minecraftcito.serveo.net:25565"


def is_playit_configured() -> bool:
    return False
