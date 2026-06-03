# Panel Tunnel Module - Handles Playit tunneling for Minecraft

import subprocess
import os
import textwrap

# Global variables
_minecraft_url = ""
_playit_process = None
_playit_configured = False

def install_playit() -> bool:
    """Instala Playit si no está instalado."""
    try:
        # Verificar si ya está instalado
        result = subprocess.run(['which', 'playit'], capture_output=True)
        if result.returncode == 0 and result.stdout.strip():
            return True
        
        # Instalar Playit
        # 1. Añadir clave GPG
        cmd1 = "curl -SsL https://playit-cloud.github.io/ppa/key.gpg | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/playit.gpg"
        result1 = subprocess.run(cmd1, shell=True, capture_output=True, text=True)
        if result1.returncode != 0:
            print(f"[ERROR] Falló al añadir clave GPG: {result1.stderr}")
            return False
        
        # 2. Añadir repositorio
        cmd2 = 'echo "deb [signed-by=/etc/apt/trusted.gpg.d/playit.gpg] https://playit-cloud.github.io/ppa/data ./\" | sudo tee /etc/apt/sources.list.d/playit-cloud.list'
        result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
        if result2.returncode != 0:
            print(f"[ERROR] Falló al añadir repositorio: {result2.stderr}")
            return False
        
        # 3. Actualizar repositorios
        result3 = subprocess.run(['sudo', 'apt', '-qq', 'update'], capture_output=True, text=True)
        if result3.returncode != 0:
            print(f"[ERROR] Falló al actualizar repositorios: {result3.stderr}")
            return False
        
        # 4. Instalar playit
        result4 = subprocess.run(['sudo', 'apt', 'install', '-y', 'playit'], capture_output=True, text=True)
        if result4.returncode != 0:
            print(f"[ERROR] Falló al instalar playit: {result4.stderr}")
            return False
        
        return True
    except Exception as e:
        print(f"[ERROR] install_playit: {e}")
        return False

def setup_playit(secret_key="") -> bool:
    """Configura Playit con la secret key."""
    if not secret_key:
        return False
    try:
        config_dir = "/root/.config/playit"
        os.makedirs(config_dir, exist_ok=True)
        config_file = os.path.join(config_dir, "playit.toml")
        with open(config_file, 'w') as f:
            f.write(f'secret_key = "{secret_key}"\n')
        return True
    except Exception as e:
        print(f"[ERROR] setup_playit: {e}")
        return False

def start_playit(secret_key="") -> dict:
    """Inicia Playit y retorna resultado."""
    global _playit_process, _playit_configured
    
    # Instalar Playit
    if not install_playit():
        return {"success": False, "error": "Failed to install Playit"}
    
    # Configurar si se proporciona secret key
    configured = setup_playit(secret_key)
    _playit_configured = configured
    
    # Iniciar proceso
    try:
        _playit_process = subprocess.Popen(
            ['playit'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
    except Exception as e:
        return {"success": False, "error": f"Failed to start Playit: {e}"}
    
    # Esperar 8 segundos para que se establezca la conexión
    import time
    time.sleep(8)
    
    return {"success": True, "configured": configured}

def get_minecraft_url() -> str:
    """Retorna la URL de Minecraft (actualmente solo indicador)."""
    return _minecraft_url

def set_minecraft_url(url: str):
    """Establece la URL de Minecraft."""
    global _minecraft_url
    _minecraft_url = url

def is_playit_configured() -> bool:
    """Retorna si Playit está configurado con secret key."""
    return _playit_configured

def stop_playit():
    """Detiene el proceso de Playit."""
    global _playit_process
    if _playit_process is not None:
        _playit_process.terminate()
        _playit_process = None