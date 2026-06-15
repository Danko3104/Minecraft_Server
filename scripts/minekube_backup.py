"""
BACKUP — Minekube Connect plugin setup
Eliminado de panel/server_manager.py el 15-Jun-2026.
Reemplazado por túnel SSH Oracle como única conexión.
Para restaurar:
  1. Copiar _setup_minekube a panel/server_manager.py
  2. Agregar en start(), después del bloque TimeoutExpired:
       self._setup_minekube(server_path)
     Y restaurar server-icon desde .server-icon-backup.png
"""

def _setup_minekube(self, server_path: str) -> bool:
    """Descarga y configura Minekube Connect plugin."""
    try:
        plugins_dir = os.path.join(server_path, 'plugins')
        os.makedirs(plugins_dir, exist_ok=True)

        jar_path = os.path.join(plugins_dir, 'connect-spigot.jar')
        if not os.path.exists(jar_path):
            print(f"[INFO] Descargando Minekube Connect plugin...")
            import urllib.request
            url = 'https://github.com/minekube/connect-java/releases/download/latest/connect-spigot.jar'
            urllib.request.urlretrieve(url, jar_path)
            print(f"[OK] Minekube Connect plugin descargado")
        else:
            print(f"[OK] Minekube Connect plugin ya existe")

        connect_config_dir = os.path.join(plugins_dir, 'connect')
        os.makedirs(connect_config_dir, exist_ok=True)

        config_path = os.path.join(connect_config_dir, 'config.yml')
        with open(config_path, 'w') as f:
            f.write('endpoint: "minecolab03-free"\n')
            f.write('allow-offline-mode-players: true\n')
        print(f"[OK] config.yml actualizado")

        token_path = os.path.join(connect_config_dir, 'token.json')
        import json
        with open(token_path, 'w') as f:
            json.dump({"token": "m0g3tdrihvr1oc8v8f3fushv"}, f)
        print(f"[OK] token.json configurado")

        return True
    except Exception as e:
        print(f"[WARNING] Minekube setup falló: {e}")
        return False

# Código original que llamaba a esta función en start():
#
#     except subprocess.TimeoutExpired:
#         pass
#
#     # Minekube Connect plugin
#     self._setup_minekube(server_path)
#     # Restaurar icono del servidor (Minekube lo sobreescribe)
#     backup_icon = os.path.join(server_path, '.server-icon-backup.png')
#     if os.path.exists(backup_icon):
#         import shutil
#         shutil.copy2(backup_icon, os.path.join(server_path, 'server-icon.png'))
