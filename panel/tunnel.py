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
                'ssh',
                '-N',
                '-T',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'ServerAliveInterval=30',
                '-o', 'ServerAliveCountMax=3',
                '-o', 'ExitOnForwardFailure=yes',
                '-R', 'minecraftcito:25565:localhost:25565',
                'serveo.net'
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        time.sleep(6)

        import select
        output_lines = []
        while True:
            ready = select.select([proc.stdout, proc.stderr], [], [], 0.5)[0]
            if not ready:
                break
            for stream in ready:
                line = stream.readline().decode().strip()
                if line:
                    output_lines.append(line)
                    print(f"[SERVEO] {line}")

        poll = proc.poll()
        print(f"[DEBUG] serveo estado: {poll}")
        if poll is None:
            print("[OK] Serveo corriendo")
            return True
        return False

    except Exception as e:
        print(f"[ERROR] start_serveo: {e}")
        return False


def get_minecraft_url() -> str:
    return "minecraftcito.serveo.net:25565"


def is_playit_configured() -> bool:
    return False
