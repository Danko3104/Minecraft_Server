"""
Módulo de puente entre Flask y Google Drive.
Maneja todo el almacenamiento del servidor Minecraft.
"""

import os
import json
import shutil
from typing import Dict, List
from jproperties import Properties

# =============================================================================
# CONSTANTE
# =============================================================================

DRIVE_PATH = '/content/drive/MyDrive/minecraft'


# =============================================================================
# CONFIGURACIÓN POR DEFECTO
# =============================================================================

DEFAULT_GLOBAL_CONFIG = {
    "server_list": [],
    "server_in_use": "",
    "ngrok_proxy": {"authtoken": "", "region": ""},
    "zrok_proxy": {"authtoken": ""},
    "playit_proxy": {"secretkey": "", "address": ""},
    "tailscale_proxy": {"authtoken": ""},
    "backup_schedule": {
        "enabled": False,
        "interval_hours": 6,
        "keep_last_n": 5,
        "last_backup": ""
    },
    "notifications": {
        "discord_webhook": "",
        "enabled": False
    },
    "panel_password": "minecolab2024"
}

DEFAULT_SERVER_CONFIG = {
    "server_type": "",
    "server_version": "",
    "tunnel_service": "ngrok",
    "java": {
        "CustomEnabled": "False",
        "version": "",
        "build": ""
    }
}


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def _ensure_dir(path: str) -> bool:
    """Crea un directorio si no existe."""
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as e:
        print(f"[ERROR] No se pudo crear el directorio {path}: {e}")
        return False


# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================

def get_drive_path() -> str:
    """
    Retorna DRIVE_PATH y verifica que exista.
    Lanza excepción si el path no existe.
    """
    try:
        if not os.path.exists(DRIVE_PATH):
            raise FileNotFoundError(
                f"La ruta de Drive no existe: {DRIVE_PATH}. "
                "Asegúrate de montar Google Drive primero."
            )
        return DRIVE_PATH
    except Exception as e:
        print(f"[ERROR] get_drive_path: {e}")
        raise


def get_global_config() -> dict:
    """
    Lee y retorna server_list.txt como dict.
    Si no existe, lo crea con valores por defecto.
    """
    try:
        config_path = os.path.join(DRIVE_PATH, 'server_list.txt')

        if not os.path.exists(config_path):
            # Crear el archivo con configuración por defecto
            _ensure_dir(DRIVE_PATH)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_GLOBAL_CONFIG, f, indent=2)
            print(f"[INFO] Archivo {config_path} creado con configuración por defecto")
            return DEFAULT_GLOBAL_CONFIG.copy()

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        if 'playit_proxy' in config and isinstance(config['playit_proxy'], dict):
            config['playit_proxy'].setdefault('address', '')

        return config
    except json.JSONDecodeError as e:
        print(f"[ERROR] get_global_config: Error al parsear JSON: {e}")
        return DEFAULT_GLOBAL_CONFIG.copy()
    except Exception as e:
        print(f"[ERROR] get_global_config: {e}")
        return DEFAULT_GLOBAL_CONFIG.copy()


def save_global_config(config: dict) -> bool:
    """
    Guarda el dict en server_list.txt.
    Retorna True si éxito, False si falla.
    """
    try:
        config_path = os.path.join(DRIVE_PATH, 'server_list.txt')
        _ensure_dir(DRIVE_PATH)

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

        print(f"[INFO] Configuración global guardada en {config_path}")
        return True
    except Exception as e:
        print(f"[ERROR] save_global_config: {e}")
        return False


def get_server_config(server_name: str) -> dict:
    """
    Lee colabconfig.txt del servidor indicado.
    Si no existe, retorna dict con estructura por defecto.
    """
    try:
        config_path = os.path.join(DRIVE_PATH, server_name, 'colabconfig.txt')

        if not os.path.exists(config_path):
            return DEFAULT_SERVER_CONFIG.copy()

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        return config
    except json.JSONDecodeError as e:
        print(f"[ERROR] get_server_config: Error al parsear JSON: {e}")
        return DEFAULT_SERVER_CONFIG.copy()
    except Exception as e:
        print(f"[ERROR] get_server_config: {e}")
        return DEFAULT_SERVER_CONFIG.copy()


def save_server_config(server_name: str, config: dict) -> bool:
    """
    Guarda colabconfig.txt del servidor indicado.
    """
    try:
        server_path = os.path.join(DRIVE_PATH, server_name)
        _ensure_dir(server_path)

        config_path = os.path.join(server_path, 'colabconfig.txt')

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

        print(f"[INFO] Configuración del servidor '{server_name}' guardada en {config_path}")
        return True
    except Exception as e:
        print(f"[ERROR] save_server_config: {e}")
        return False


def list_servers() -> list:
    """
    Lee server_list de get_global_config().
    Retorna lista de nombres de servidores.
    """
    try:
        config = get_global_config()
        return config.get('server_list', [])
    except Exception as e:
        print(f"[ERROR] list_servers: {e}")
        return []


def get_active_server() -> str:
    """
    Retorna server_in_use de la config global.
    Si está vacío, retorna string vacío.
    """
    try:
        config = get_global_config()
        return config.get('server_in_use', '')
    except Exception as e:
        print(f"[ERROR] get_active_server: {e}")
        return ''


def set_active_server(server_name: str) -> bool:
    """
    Actualiza server_in_use en server_list.txt.
    """
    try:
        config = get_global_config()
        config['server_in_use'] = server_name
        return save_global_config(config)
    except Exception as e:
        print(f"[ERROR] set_active_server: {e}")
        return False


def server_exists(server_name: str) -> bool:
    """
    Verifica si existe la carpeta del servidor en Drive.
    """
    try:
        server_path = os.path.join(DRIVE_PATH, server_name)
        return os.path.exists(server_path) and os.path.isdir(server_path)
    except Exception as e:
        print(f"[ERROR] server_exists: {e}")
        return False


def get_server_properties(server_name: str) -> dict:
    """
    Lee server.properties y retorna como dict.
    Usa jproperties para parsear.
    """
    try:
        props_path = os.path.join(DRIVE_PATH, server_name, 'server.properties')

        if not os.path.exists(props_path):
            return {}

        properties = Properties()
        with open(props_path, 'rb') as f:
            properties.load(f)

        return {key: properties.get(key, '') for key in properties}
    except Exception as e:
        print(f"[ERROR] get_server_properties: {e}")
        return {}


def save_server_properties(server_name: str, props: dict) -> bool:
    """
    Guarda dict como server.properties usando jproperties.
    """
    try:
        server_path = os.path.join(DRIVE_PATH, server_name)
        _ensure_dir(server_path)

        props_path = os.path.join(server_path, 'server.properties')

        properties = Properties(props)
        with open(props_path, 'wb') as f:
            properties.store(f)

        print(f"[INFO] server.properties guardado para '{server_name}'")
        return True
    except Exception as e:
        print(f"[ERROR] save_server_properties: {e}")
        return False


def get_ops(server_name: str) -> list:
    """
    Lee ops.json, retorna lista o [] si no existe.
    """
    try:
        ops_path = os.path.join(DRIVE_PATH, server_name, 'ops.json')

        if not os.path.exists(ops_path):
            return []

        with open(ops_path, 'r', encoding='utf-8') as f:
            ops = json.load(f)

        return ops if isinstance(ops, list) else []
    except json.JSONDecodeError as e:
        print(f"[ERROR] get_ops: Error al parsear JSON: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] get_ops: {e}")
        return []


def get_whitelist(server_name: str) -> list:
    """
    Lee whitelist.json, retorna lista o [] si no existe.
    """
    try:
        wl_path = os.path.join(DRIVE_PATH, server_name, 'whitelist.json')

        if not os.path.exists(wl_path):
            return []

        with open(wl_path, 'r', encoding='utf-8') as f:
            whitelist = json.load(f)

        return whitelist if isinstance(whitelist, list) else []
    except json.JSONDecodeError as e:
        print(f"[ERROR] get_whitelist: Error al parsear JSON: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] get_whitelist: {e}")
        return []


def get_banned_players(server_name: str) -> list:
    """
    Lee banned-players.json, retorna lista o [] si no existe.
    """
    try:
        banned_path = os.path.join(DRIVE_PATH, server_name, 'banned-players.json')

        if not os.path.exists(banned_path):
            return []

        with open(banned_path, 'r', encoding='utf-8') as f:
            banned = json.load(f)

        return banned if isinstance(banned, list) else []
    except json.JSONDecodeError as e:
        print(f"[ERROR] get_banned_players: Error al parsear JSON: {e}")
        return []
    except Exception as e:
        print(f"[ERROR] get_banned_players: {e}")
        return []


def get_drive_usage() -> dict:
    """
    Usa shutil.disk_usage para obtener el uso de Drive.
    Retorna {total_gb, used_gb, free_gb} redondeados a 2 decimales.
    """
    try:
        drive_path = get_drive_path()
        usage = shutil.disk_usage(drive_path)

        return {
            'total_gb': round(usage.total / (1024 ** 3), 2),
            'used_gb': round(usage.used / (1024 ** 3), 2),
            'free_gb': round(usage.free / (1024 ** 3), 2)
        }
    except Exception as e:
        print(f"[ERROR] get_drive_usage: {e}")
        return {'total_gb': 0.0, 'used_gb': 0.0, 'free_gb': 0.0}


def get_server_path(server_name: str) -> str:
    """
    Retorna la ruta completa del servidor en Drive.
    """
    try:
        return os.path.join(DRIVE_PATH, server_name)
    except Exception as e:
        print(f"[ERROR] get_server_path: {e}")
        return ''


# =============================================================================
# MAIN - TESTING
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("MINECOLAB PANEL - DRIVE.PY TEST")
    print("=" * 60)

    print("\n[TEST] get_global_config():")
    try:
        config = get_global_config()
        print(json.dumps(config, indent=2))
    except Exception as e:
        print(f"[ERROR] {e}")

    print("\n[TEST] list_servers():")
    try:
        servers = list_servers()
        print(f"Servers: {servers}")
    except Exception as e:
        print(f"[ERROR] {e}")

    print("\n" + "=" * 60)
