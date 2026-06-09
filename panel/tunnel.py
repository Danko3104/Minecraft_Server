import subprocess
import os
import time


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

        time.sleep(5)
        poll = proc.poll()
        print(f"[DEBUG] serveo estado: {poll}")

        if poll is not None:
            print(f"[DEBUG] stdout: {proc.stdout.read().decode()[:300]}")
            print(f"[DEBUG] stderr: {proc.stderr.read().decode()[:300]}")
            return False

        return True

    except Exception as e:
        print(f"[ERROR] start_serveo: {e}")
        return False


def get_minecraft_url() -> str:
    return "minecraftcito.serveo.net:25565"


def is_playit_configured() -> bool:
    return False
