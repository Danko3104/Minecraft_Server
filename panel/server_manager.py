"""
Server Manager - Controla el proceso de Java (Minecraft).
Permite iniciar, detener y gestionar el servidor.
"""

import os
import sys
import time
import subprocess
import json
import threading
import shutil
import re
import zipfile
import tempfile
import gzip
import struct
from datetime import datetime
from typing import Optional, Dict, List

# Agregar path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jproperties import Properties

try:
    from mcrcon import RCon
    MCRCON_AVAILABLE = True
except ImportError:
    MCRCON_AVAILABLE = False

from panel.drive import get_server_path, server_exists, get_server_config

# =============================================================================
# VARIABLES GLOBALES
# =============================================================================

_process = None          # El subprocess de Java
_start_time = None       # datetime cuando se inició
_intentional_stop = False  # Para distinguir stop manual de crash

# =============================================================================
# CLASE SERVERMANAGER
# =============================================================================


class ServerManager:
    """
    Gestiona el ciclo de vida del servidor de Minecraft.
    """

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.start_time: Optional[datetime] = None
        self.intentional_stop = False
        self.rcon_password = "minecolab_panel"
        self.rcon_port = 25575
        self.last_output_lines: List[str] = []
        self._log_file_handle = None
        self._lock = threading.Lock()

    def get_server_path(self, server_name: str) -> str:
        """
        Retorna la ruta del servidor.
        """
        from panel.drive import DRIVE_PATH
        return os.path.join(DRIVE_PATH, server_name)

    def prepare_server_properties(self, server_name: str) -> bool:
        try:
            server_path = self.get_server_path(server_name)
            props_path = os.path.join(server_path, 'server.properties')

            # Propiedades críticas — SIEMPRE se fuerzan (necesarias para RCON, conexión, etc.)
            FORCED = {
                'enable-rcon': 'true',
                'rcon.port': str(self.rcon_port),
                'rcon.password': self.rcon_password,
                'server-port': '25565',
                'enforce-secure-profile': 'false',
                'online-mode': 'false',
            }

            # Propiedades por defecto — solo se escriben si el archivo no existe
            DEFAULTS = {
                'max-players': '20',
                'level-name': 'world',
                'motd': 'A Minecraft Server',
                'difficulty': 'normal',
                'gamemode': 'survival',
                'pvp': 'true',
                'spawn-monsters': 'true',
                'spawn-animals': 'true',
                'render-distance': '10',
                'simulation-distance': '8',
                'view-distance': '10',
                'spawn-protection': '16',
                'enable-command-block': 'false',
                'network-compression-threshold': '128',
            }

            if not os.path.exists(props_path):
                with open(props_path, 'w') as f:
                    for k, v in {**FORCED, **DEFAULTS}.items():
                        f.write(f'{k}={v}\n')
                print(f"[INFO] server.properties creado para '{server_name}'")
                return True

            with open(props_path, 'r') as f:
                lines = f.readlines()

            seen = set()
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if '=' in stripped and not stripped.startswith('#'):
                    key = stripped.split('=', 1)[0].strip()
                    seen.add(key)
                    if key in FORCED:
                        # Siempre escribir el valor forzado
                        new_lines.append(f'{key}={FORCED[key]}\n')
                    else:
                        # Mantener el valor existente del usuario
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            # Agregar forzadas que falten
            for k, v in FORCED.items():
                if k not in seen:
                    new_lines.append(f'{k}={v}\n')
                    seen.add(k)

            # Agregar defaults que falten (solo si el usuario no las ha puesto)
            for k, v in DEFAULTS.items():
                if k not in seen:
                    new_lines.append(f'{k}={v}\n')

            with open(props_path, 'w') as f:
                f.writelines(new_lines)

            print(f"[INFO] server.properties actualizado para '{server_name}'")
            return True

        except Exception as e:
            print(f"[ERROR] prepare_server_properties: {e}")
            return False

    def get_java_command(self, server_name: str) -> List[str]:
        """
        Construye el comando Java según el tipo de servidor.
        """
        try:
            config = get_server_config(server_name)
            server_type = config.get('server_type', 'Vanilla').lower()
            server_path = self.get_server_path(server_name)

            # Detectar memoria disponible (Colab suele tener ~2-3G libres)
            try:
                import psutil
                available_gb = psutil.virtual_memory().available / (1024**3)
            except ImportError:
                available_gb = 0
            xmx = "1G" if 0 < available_gb < 2.5 else "2G"
            xms = "256M" if 0 < available_gb < 2.5 else "512M"
            if available_gb > 0:
                print(f"[INFO] Memoria disponible: {available_gb:.1f}G, usando -Xmx{xmx} -Xms{xms}")

            # Comandos base para Java
            java_cmd = [
                "java",
                f"-Xms{xms}",
                f"-Xmx{xmx}",
                "-XX:-UseContainerSupport",
                "-XX:+UseG1GC",
                "-XX:+ParallelRefProcEnabled",
                "-XX:MaxGCPauseMillis=200"
            ]

            # Elegir jar: paper.jar si existe, sino server.jar
            jar_name = "server.jar"
            paper_jar = os.path.join(server_path, "paper.jar")
            if os.path.exists(paper_jar):
                jar_name = "paper.jar"

            # Según server_type
            if server_type in ['paper', 'purpur', 'folia', 'vanilla', 'snapshot']:
                java_cmd.extend(["-jar", jar_name, "--nogui"])

            elif server_type == 'fabric':
                java_cmd.extend(["-jar", "fabric-server-launch.jar", "--nogui"])

            elif server_type in ['forge', 'neoforge']:
                run_sh = os.path.join(server_path, 'run.sh')
                if os.path.exists(run_sh):
                    return ["bash", run_sh, "--nogui"]
                else:
                    java_cmd.extend(["-jar", jar_name, "--nogui"])

            elif server_type == 'bedrock':
                return ["./bedrock_server"]

            else:
                java_cmd.extend(["-jar", jar_name, "--nogui"])

            return java_cmd

        except Exception as e:
            print(f"[ERROR] get_java_command: {e}")
            return ["java", "-jar", "server.jar", "--nogui"]

    def _get_log_path(self, server_name: str) -> str:
        server_path = self.get_server_path(server_name)
        log_dir = os.path.join(server_path, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, 'console.log')

    def _rotate_logs(self, server_name: str):
        log_dir = os.path.join(self.get_server_path(server_name), 'logs')
        if not os.path.exists(log_dir):
            return
        MAX_LOG_FILES = 3
        base = os.path.join(log_dir, 'console.log')
        for i in range(MAX_LOG_FILES - 1, 0, -1):
            old = f'{base}.{i}'
            new = f'{base}.{i + 1}'
            if os.path.exists(old):
                if os.path.exists(new):
                    os.remove(new)
                os.rename(old, new)
        if os.path.exists(base):
            os.rename(base, f'{base}.1')

    def _start_output_reader(self):
        """
        Inicia el hilo que lee la salida del proceso.
        """
        def read_output():
            """Lee la salida del proceso y la guarda en last_output_lines y log file."""
            try:
                for line in self.process.stdout:
                    line = line.strip()
                    if line:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        self.last_output_lines.append(line)
                        print(f"[MINECRAFT] {line}")
                        if self._log_file_handle and not self._log_file_handle.closed:
                            self._log_file_handle.write(f'[{timestamp}] {line}\n')
                            self._log_file_handle.flush()
                        # Mantener solo las últimas 200 líneas
                        if len(self.last_output_lines) > 200:
                            self.last_output_lines.pop(0)
            except Exception as e:
                print(f"[ERROR] read_output: {e}")
            finally:
                if self._log_file_handle and not self._log_file_handle.closed:
                    self._log_file_handle.close()
                    self._log_file_handle = None

        output_thread = threading.Thread(target=read_output, daemon=True)
        output_thread.start()
        return output_thread

    def _check_java_installed(self) -> Dict:
        """
        Verifica que Java está instalado y retorna información.
        """
        try:
            result = subprocess.run(
                ['java', '-version'],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return {
                    "installed": False,
                    "version": None,
                    "error": "Java no está instalado o no está en PATH"
                }

            # java -version escribe a stderr
            version_output = result.stderr if result.stderr else result.stdout
            return {
                "installed": True,
                "version": version_output.split('\n')[0] if version_output else "Desconocida",
                "error": None
            }
        except FileNotFoundError:
            return {
                "installed": False,
                "version": None,
                "error": "Comando 'java' no encontrado"
            }
        except Exception as e:
            return {
                "installed": False,
                "version": None,
                "error": str(e)
            }

    def _find_server_jar(self, server_path: str) -> Dict:
        """
        Busca el archivo JAR del servidor en el directorio.
        """
        try:
            if not os.path.exists(server_path):
                return {
                    "found": False,
                    "jar_file": None,
                    "files": []
                }

            files = os.listdir(server_path)

            # Buscar archivos específicos
            jar_files = {
                'paper.jar': 'paper.jar' in files,
                'server.jar': 'server.jar' in files,
                'fabric-server-launch.jar': 'fabric-server-launch.jar' in files,
                'forge': any(f.startswith('forge') and f.endswith('.jar') for f in files),
                'neoforge': any(f.startswith('neo') and f.endswith('.jar') for f in files),
                'bedrock_server': 'bedrock_server' in files
            }

            # Determinar cuál usar
            jar_file = None
            if jar_files['paper.jar']:
                jar_file = 'paper.jar'
            elif jar_files['server.jar']:
                jar_file = 'server.jar'
            elif jar_files['fabric-server-launch.jar']:
                jar_file = 'fabric-server-launch.jar'
            elif jar_files['forge'] or jar_files['neoforge']:
                # Buscar el primer forge*.jar
                for f in files:
                    if f.startswith('forge') and f.endswith('.jar'):
                        jar_file = f
                        break
                    if f.startswith('neo') and f.endswith('.jar'):
                        jar_file = f
                        break
            elif jar_files['bedrock_server']:
                jar_file = 'bedrock_server'

            return {
                "found": jar_file is not None,
                "jar_file": jar_file,
                "files": sorted(files),
                "jar_types": jar_files
            }
        except Exception as e:
            return {
                "found": False,
                "jar_file": None,
                "files": [],
                "error": str(e)
            }

    def _ensure_eula_accepted(self, server_path: str) -> Dict:
        """
        Verifica y crea eula.txt con eula=true si es necesario.
        """
        try:
            eula_path = os.path.join(server_path, 'eula.txt')

            if not os.path.exists(eula_path):
                # Crear eula.txt con eula=true
                with open(eula_path, 'w') as f:
                    f.write("#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://aka.ms/minecrafteula)\n")
                    f.write("eula=true\n")
                return {
                    "exists": False,
                    "accepted": True,
                    "created": True,
                    "message": "eula.txt creado automáticamente con eula=true"
                }

            # Leer existente
            with open(eula_path, 'r') as f:
                content = f.read()

            # Verificar si eula=true
            if 'eula=true' in content.lower():
                return {
                    "exists": True,
                    "accepted": True,
                    "created": False,
                    "message": "EULA ya aceptada"
                }
            else:
                # Actualizar a eula=true
                with open(eula_path, 'w') as f:
                    f.write("#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://aka.ms/minecrafteula)\n")
                    f.write("eula=true\n")
                return {
                    "exists": True,
                    "accepted": True,
                    "created": False,
                    "updated": True,
                    "message": "eula.txt actualizado a eula=true"
                }

        except Exception as e:
            return {
                "exists": False,
                "accepted": False,
                "created": False,
                "error": str(e)
            }

    def diagnose(self, server_name: str) -> dict:
        """
        Retorna información completa de diagnóstico para un servidor.
        """
        try:
            server_path = self.get_server_path(server_name)
            path_exists = os.path.exists(server_path)

            # Obtener archivos en el directorio
            files_in_directory = []
            if path_exists and os.path.isdir(server_path):
                files_in_directory = sorted(os.listdir(server_path))

            # Verificar Java
            java_info = self._check_java_installed()

            # Leer colabconfig.txt
            colabconfig = get_server_config(server_name)

            # Verificar server.properties
            server_properties_exists = os.path.exists(os.path.join(server_path, 'server.properties')) if path_exists else False

            # Verificar eula.txt
            eula_info = self._ensure_eula_accepted(server_path) if path_exists else {
                "exists": False,
                "accepted": False,
                "error": "Directorio no existe"
            }

            # Buscar JAR
            jar_info = self._find_server_jar(server_path)

            return {
                "server_name": server_name,
                "server_path": server_path,
                "path_exists": path_exists,
                "files_in_directory": files_in_directory,
                "java_installed": java_info["installed"],
                "java_version": java_info.get("version", "N/A"),
                "java_error": java_info.get("error"),
                "colabconfig": colabconfig,
                "server_properties_exists": server_properties_exists,
                "eula_exists": eula_info.get("exists", False),
                "eula_accepted": eula_info.get("accepted", False),
                "eula_message": eula_info.get("message"),
                "jar_found": jar_info["found"],
                "jar_file": jar_info.get("jar_file"),
                "jar_types": jar_info.get("jar_types", {}),
                "all_files": files_in_directory
            }

        except Exception as e:
            return {
                "error": str(e),
                "server_name": server_name
            }

    def start(self, server_name: str) -> dict:
        """
        Inicia el servidor de Minecraft.
        """
        try:
            # Verificar si ya está corriendo
            if self.is_running():
                return {
                    "success": False,
                    "error": "El servidor ya está corriendo"
                }

            # Verificar que el servidor existe
            if not server_exists(server_name):
                return {
                    "success": False,
                    "error": f"Servidor '{server_name}' no encontrado"
                }

            server_path = self.get_server_path(server_name)

            # DIAGNÓSTICO PREVIO: Verificar Java
            java_info = self._check_java_installed()
            if not java_info["installed"]:
                return {
                    "success": False,
                    "error": f"Java no está instalado: {java_info.get('error', 'Error desconocido')}",
                    "diagnosis": {"java": java_info}
                }

            print(f"[INFO] Java版本: {java_info.get('version', 'N/A')}")

            # DIAGNÓSTICO PREVIO: Verificar JAR del servidor
            jar_info = self._find_server_jar(server_path)
            if not jar_info["found"]:
                return {
                    "success": False,
                    "error": f"No se encontró el JAR del servidor en {server_path}",
                    "server_path": server_path,
                    "files_found": jar_info.get("files", []),
                    "diagnosis": {"jar": jar_info}
                }

            print(f"[INFO] JAR encontrado: {jar_info.get('jar_file')}")

            # DIAGNÓSTICO PREVIO: Asegurar EULA aceptada
            eula_info = self._ensure_eula_accepted(server_path)
            print(f"[INFO] EULA: {eula_info.get('message', 'N/A')}")

            # Preparar server.properties
            if not self.prepare_server_properties(server_name):
                return {
                    "success": False,
                    "error": "Error al preparar server.properties"
                }

            # Obtener comando
            command = self.get_java_command(server_name)

            print(f"[INFO] Iniciando servidor '{server_name}'...")
            print(f"[INFO] Comando: {' '.join(command)}")
            print(f"[INFO] Directorio: {server_path}")

            # Limpiar output anterior
            self.last_output_lines = []
            # Rotar y abrir archivo de log
            self._rotate_logs(server_name)
            log_path = self._get_log_path(server_name)
            self._log_file_handle = open(log_path, 'w', encoding='utf-8')

            with self._lock:
                # Cambiar al directorio del servidor
                os.chdir(server_path)

                # Iniciar proceso
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )

                # Iniciar hilo para leer output
                self._start_output_reader()

                # Guardar tiempos y nombre del servidor
                self.start_time = datetime.now()
                self._current_server = server_name
                self.intentional_stop = False

                # Esperar hasta 5s (retorna early si el proceso muere)
                try:
                    retcode = self.process.wait(timeout=5)
                    # Murió temprano
                    error_output = self.last_output_lines[-50:] if self.last_output_lines else ["No hay output"]
                    self.process = None
                    self.start_time = None
                    print(f"[ERROR] Servidor '{server_name}' falló al iniciar (código: {retcode})")
                    return {
                        "success": False,
                        "error": f"El servidor falló al iniciar. Código: {retcode}",
                        "output": error_output
                    }
                except subprocess.TimeoutExpired:
                    # Sigue vivo — éxito
                    pass

            print(f"[INFO] Servidor '{server_name}' iniciado (PID: {self.process.pid})")

            return {
                "success": True,
                "message": f"Servidor '{server_name}' iniciando...",
                "pid": self.process.pid
            }

        except FileNotFoundError as e:
            return {
                "success": False,
                "error": f"Comando no encontrado: {e}"
            }
        except Exception as e:
            print(f"[ERROR] start: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def stop(self) -> dict:
        """
        Detiene el servidor de Minecraft.
        Antes de detener, guarda el mundo y hace backup automático.
        """
        with self._lock:
            return self._stop_locked()

    def _stop_locked(self) -> dict:
        try:
            # Verificar si hay proceso
            if self.process is None:
                return {
                    "success": False,
                    "error": "El servidor no está corriendo"
                }

            self.intentional_stop = True

            # Backup automático del mundo (si se conoce el server_name)
            if hasattr(self, '_current_server') and self._current_server:
                print("[INFO] Guardando mundo...")
                if MCRCON_AVAILABLE and self.process.poll() is None:
                    try:
                        with RCon("localhost", self.rcon_port, self.rcon_password) as rcon:
                            rcon.command("save-all")
                    except Exception:
                        pass
                print("[INFO] Haciendo backup automático del mundo...")
                self._backup_world(self._current_server)

            # Intentar primero con RCON
            if MCRCON_AVAILABLE and self.process.poll() is None:
                try:
                    print("[INFO] Enviando comando 'stop' via RCON...")
                    with RCon("localhost", self.rcon_port, self.rcon_password) as rcon:
                        rcon.command("stop")
                    print("[INFO] Comando stop enviado via RCON")
                except Exception as e:
                    print(f"[WARNING] RCON falló: {e}, usando stdin...")

                    # Fallback: enviar al stdin
                    try:
                        self.process.stdin.write("stop\n")
                        self.process.stdin.flush()
                        print("[INFO] Comando stop enviado al stdin")
                    except Exception as e2:
                        print(f"[WARNING] stdin falló: {e2}")

            # Esperar hasta 30 segundos
            print("[INFO] Esperando que el servidor se detenga...")
            try:
                self.process.wait(timeout=30)
                print("[INFO] Servidor detenido correctamente")
            except subprocess.TimeoutExpired:
                print("[WARNING] Timeout, terminando proceso...")
                self.process.terminate()

                # Esperar 5 segundos más
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("[ERROR] Forzando terminación...")
                    self.process.kill()

            # Limpiar
            self.process = None
            self.start_time = None

            print("[INFO] Servidor detenido")

            return {
                "success": True,
                "message": "Servidor detenido"
            }

        except Exception as e:
            print(f"[ERROR] stop: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def is_running(self) -> bool:
        """
        Verifica si el servidor está corriendo.
        """
        if self.process is None:
            return False

        return self.process.poll() is None

    def get_status(self) -> dict:
        """
        Retorna el estado del servidor.
        """
        running = self.is_running()
        players = []
        tps = 20.0

        if running:
            try:
                # Intentar RCON con timeout corto
                # Si falla no importa, el servidor sigue corriendo
                from mcrcon import MCRcon  # la clase ya se importa arriba en el archivo
                rcon = MCRcon('localhost', self.rcon_port, self.rcon_password)
                rcon.connect()
                response = rcon.command('list')
                rcon.disconnect()
                # parsear jugadores de response
                # Formato típico: "There are X/max players: player1, player2, ..."
                if response and ':' in response:
                    players_part = response.split(':', 1)[1].strip()
                    if players_part:
                        players = [p.strip() for p in players_part.split(',') if p.strip()]
            except Exception:
                pass  # RCON falló pero el servidor sigue vivo

        uptime = 0
        if self.start_time and running:
            uptime = int((datetime.now() - self.start_time).total_seconds())

        return {
            "running": running,
            "players": players,
            "tps": tps,
            "uptime_seconds": uptime,
            "pid": self.process.pid if self.process else None
        }
    def get_last_output(self) -> List[str]:
        """
        Retorna las últimas líneas de output del proceso.
        """
        return self.last_output_lines[-100:]

    def get_log_path(self, server_name: str) -> str:
        return self._get_log_path(server_name)

    def get_log_files(self, server_name: str) -> list:
        log_dir = os.path.join(self.get_server_path(server_name), 'logs')
        if not os.path.exists(log_dir):
            return []
        files = []
        for f in sorted(os.listdir(log_dir), reverse=True):
            fpath = os.path.join(log_dir, f)
            if os.path.isfile(fpath):
                size = os.path.getsize(fpath)
                mtime = os.path.getmtime(fpath)
                from datetime import datetime as dt
                files.append({
                    "name": f,
                    "size": size,
                    "size_display": f"{size/1024:.0f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB",
                    "modified": dt.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        return files

    def send_command(self, command: str) -> str:
        """
        Envía un comando al servidor (via RCON o stdin).
        """
        if not self.is_running():
            return "Servidor no está corriendo"

        # Intentar via RCON primero
        if MCRCON_AVAILABLE:
            try:
                with RCon("localhost", self.rcon_port, self.rcon_password) as rcon:
                    response = rcon.command(command)
                return response if response else "Comando enviado"
            except Exception as e:
                print(f"[WARNING] RCON falló: {e}, usando stdin...")

        # Fallback: stdin
        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
            return "Comando enviado"
        except Exception as e:
            return f"Error al enviar comando: {e}"

    # =========================================================================
    # BACKUP DEL MUNDO
    # =========================================================================

    def get_backups_dir(self) -> str:
        """Retorna la ruta de la carpeta de backups."""
        if os.path.isdir('/content/drive/MyDrive'):
            return '/content/drive/MyDrive/Copias de mundo de Minecraft'
        from panel.drive import DRIVE_PATH
        return os.path.join(os.path.dirname(DRIVE_PATH), 'Backups')

    def _get_world_path(self, server_name: str) -> str:
        """Retorna la ruta del directorio del mundo según level-name en server.properties."""
        server_path = self.get_server_path(server_name)
        props = self.read_server_properties(server_name)
        level_name = props.get('level-name', 'world')
        return os.path.join(server_path, level_name)

    def _backup_world(self, server_name: str) -> Optional[str]:
        """
        Hace backup comprimido del mundo en Copias de mundo de Minecraft/.
        Retorna el nombre del backup o None si falla.
        """
        try:
            server_path = self.get_server_path(server_name)
            world_path = self._get_world_path(server_name)
            if not os.path.exists(world_path):
                print(f"[INFO] No hay mundo que respaldar para '{server_name}'")
                return None

            backups_dir = self.get_backups_dir()
            os.makedirs(backups_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_name = f"{server_name}_world_{timestamp}.zip"
            backup_path = os.path.join(backups_dir, backup_name)

            shutil.make_archive(backup_path[:-4], 'zip', world_path)
            print(f"[INFO] Backup comprimido creado: {backup_path}")

            # Prune: mantener solo el último backup
            world_backups = [
                e for e in os.listdir(backups_dir)
                if e.startswith(server_name + '_world_') and e.endswith('.zip') and os.path.isfile(os.path.join(backups_dir, e))
            ]
            world_backups.sort(reverse=True)
            for old in world_backups[1:]:
                old_path = os.path.join(backups_dir, old)
                os.remove(old_path)
                print(f"[INFO] Backup antiguo eliminado: {old}")

            return backup_name
        except Exception as e:
            print(f"[ERROR] _backup_world: {e}")
            return None

    def _backup_full_server(self, server_name: str) -> Optional[str]:
        """
        Hace backup completo del servidor (world + config + plugins) en un zip
        dentro de Copias de mundo de Minecraft/.
        """
        try:
            server_path = self.get_server_path(server_name)
            backups_dir = self.get_backups_dir()
            os.makedirs(backups_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_name = f"{server_name}_full_{timestamp}.zip"
            backup_path = os.path.join(backups_dir, backup_name)

            shutil.make_archive(backup_path[:-4], 'zip', server_path)
            print(f"[INFO] Backup completo creado: {backup_path}")
            return backup_name
        except Exception as e:
            print(f"[ERROR] _backup_full_server: {e}")
            return None

    def list_backups(self, server_name: str) -> List[Dict]:
        """
        Lista los backups (zips) del servidor con fecha y tamaño.
        """
        try:
            backups_dir = self.get_backups_dir()
            if not os.path.exists(backups_dir):
                return []

            result = []
            for entry in sorted(os.listdir(backups_dir), reverse=True):
                entry_path = os.path.join(backups_dir, entry)
                # Filtrar solo backups zip que empiecen con el nombre del servidor
                if entry.startswith(server_name + '_world_') and entry.endswith('.zip') and os.path.isfile(entry_path):
                    size = os.path.getsize(entry_path)
                    ts_str = entry.replace(server_name + '_world_', '').replace('.zip', '')
                    try:
                        ts = datetime.strptime(ts_str, "%Y-%m-%d_%H-%M-%S")
                    except ValueError:
                        ts = None
                    result.append({
                        "name": entry,
                        "date": ts.strftime("%Y-%m-%d %H:%M:%S") if ts else ts_str,
                        "size_bytes": size,
                        "size_display": f"{size/1024/1024:.1f} MB" if size > 1024*1024 else f"{size/1024:.0f} KB"
                    })
            return result
        except Exception as e:
            print(f"[ERROR] list_backups: {e}")
            return []

    def restore_backup(self, server_name: str, backup_name: str) -> Dict:
        """
        Restaura un backup comprimido: detiene server, reemplaza world/, reinicia.
        """
        try:
            backups_dir = self.get_backups_dir()
            backup_path = os.path.join(backups_dir, backup_name)
            if not os.path.exists(backup_path):
                return {"success": False, "error": f"Backup '{backup_name}' no encontrado"}

            server_path = self.get_server_path(server_name)
            world_path = self._get_world_path(server_name)

            was_running = self.is_running()
            if was_running:
                # Forzar guardado antes de detener
                if MCRCON_AVAILABLE:
                    try:
                        with RCon("localhost", self.rcon_port, self.rcon_password) as rcon:
                            rcon.command("save-all")
                    except Exception:
                        pass
                self.stop()
                time.sleep(2)

            # Backup comprimido del mundo actual antes de restaurar
            if os.path.exists(world_path):
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                pre_restore_backup = os.path.join(backups_dir, f"{server_name}_world_{timestamp}_prerestore.zip")
                shutil.make_archive(pre_restore_backup[:-4], 'zip', world_path)

            # Eliminar mundo actual
            if os.path.exists(world_path):
                shutil.rmtree(world_path)

            # Extraer backup zip
            with zipfile.ZipFile(backup_path, 'r') as zf:
                zf.extractall(world_path)
            print(f"[INFO] Backup '{backup_name}' restaurado para '{server_name}'")

            if was_running:
                self.start(server_name)

            return {"success": True, "message": f"Backup '{backup_name}' restaurado"}
        except Exception as e:
            print(f"[ERROR] restore_backup: {e}")
            return {"success": False, "error": str(e)}

    def delete_backup(self, server_name: str, backup_name: str) -> Dict:
        """
        Elimina un backup comprimido.
        """
        try:
            backups_dir = self.get_backups_dir()
            backup_path = os.path.join(backups_dir, backup_name)
            if not os.path.exists(backup_path):
                return {"success": False, "error": f"Backup '{backup_name}' no encontrado"}
            os.remove(backup_path)
            return {"success": True, "message": f"Backup '{backup_name}' eliminado"}
        except Exception as e:
            print(f"[ERROR] delete_backup: {e}")
            return {"success": False, "error": str(e)}

    def _get_world_data_version(self, world_path: str) -> Optional[int]:
        """Lee la DataVersion del level.dat de un mundo Minecraft."""
        level_dat = os.path.join(world_path, 'level.dat')
        if not os.path.exists(level_dat):
            return None
        try:
            with gzip.open(level_dat, 'rb') as f:
                raw = f.read()
            # Buscar TAG_Int(3) + name_len(2) "DataVersion" + int(4)
            match = re.search(b'\x03\x00\x0bDataVersion', raw)
            if match:
                version_bytes = raw[match.end():match.end()+4]
                return struct.unpack('>i', version_bytes)[0]
        except Exception:
            pass
        return None

    def _clean_world_dirs(self, server_path: str, names: list):
        """Limpia carpetas de mundo y archivos huérfanos del servidor."""
        for name in names:
            for suffix in ['', '_nether', '_the_end', '_end', '_DIM1', '_DIM-1']:
                dim_path = os.path.join(server_path, name + suffix)
                if os.path.exists(dim_path):
                    if os.path.isdir(dim_path):
                        shutil.rmtree(dim_path)
                    else:
                        os.remove(dim_path)
        # Archivos huérfanos comunes que ensucian el directorio
        orphan_files = ['session.lock', 'uid.dat', '.thanos', '.console_history',
                        'version_history.json', 'server-icon.php', 'colabconfig.txt',
                        'tunnel', 'cache', 'logs']
        for fname in orphan_files:
            fpath = os.path.join(server_path, fname)
            if os.path.exists(fpath):
                if os.path.isdir(fpath):
                    shutil.rmtree(fpath, ignore_errors=True)
                else:
                    os.remove(fpath)

    def _copy_player_files(self, source_root: str, server_path: str):
        """Copia archivos de datos de jugadores desde la fuente al servidor."""
        player_files = ['usercache.json', 'ops.json', 'whitelist.json',
                        'banned-players.json', 'banned-ips.json']
        for pf in player_files:
            src = os.path.join(source_root, pf)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(server_path, pf))
                print(f"[INFO] Datos de jugadores restaurados: {pf}")

    def upload_world(self, server_name: str, zip_path: str) -> Dict:
        """
        Reemplaza el mundo actual con el contenido de un .zip.
        Antes hace backup del mundo actual.
        Si el zip es un backup completo de servidor (contiene server.properties,
        server.jar, eula.txt, etc.), extrae solo el mundo y los datos de jugadores.
        """
        try:
            server_path = self.get_server_path(server_name)

            was_running = self.is_running()
            if was_running:
                if MCRCON_AVAILABLE:
                    try:
                        with RCon("localhost", self.rcon_port, self.rcon_password) as rcon:
                            rcon.command("save-all")
                    except Exception:
                        pass
                self.stop()
                time.sleep(2)

            # Backup automático del mundo actual
            self._backup_world(server_name)

            # Extraer a temp para inspeccionar estructura
            temp_dir = tempfile.mkdtemp()
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.extractall(temp_dir)

                items = [i for i in os.listdir(temp_dir) if not i.startswith('.')]
                if not items:
                    items = os.listdir(temp_dir)

                # ---- Detectar si es un backup completo de servidor ----
                source_root = temp_dir
                is_full_server = False
                server_indicators = {'server.properties', 'server.jar', 'eula.txt',
                                     'bukkit.yml', 'spigot.yml', 'paper.yml', 'plugins'}

                if len(items) == 1:
                    single_path = os.path.join(temp_dir, items[0])
                    if os.path.isdir(single_path):
                        sub_set = set(os.listdir(single_path))
                        if server_indicators & sub_set:
                            is_full_server = True
                            source_root = single_path
                else:
                    item_set = set(items)
                    if server_indicators & item_set:
                        is_full_server = True

                if is_full_server:
                    # =========================================================
                    # MODO: BACKUP COMPLETO DE SERVIDOR
                    # =========================================================
                    backup_props_path = os.path.join(source_root, 'server.properties')
                    level_name = 'world'
                    if os.path.exists(backup_props_path):
                        with open(backup_props_path, 'r') as f:
                            for line in f:
                                line = line.strip()
                                if line and '=' in line and not line.startswith('#'):
                                    key, _, value = line.partition('=')
                                    if key.strip() == 'level-name':
                                        level_name = value.strip()
                    new_level_name = level_name

                    old_props = self.read_server_properties(server_name)
                    old_level_name = old_props.get('level-name', 'world')

                    self._clean_world_dirs(server_path, [old_level_name, new_level_name, 'world'])

                    for suffix in ['', '_nether', '_the_end']:
                        src = os.path.join(source_root, level_name + suffix)
                        if os.path.exists(src):
                            shutil.move(src, os.path.join(server_path, new_level_name + suffix))

                    world_path = os.path.join(server_path, new_level_name)

                    self._copy_player_files(source_root, server_path)

                    cfg_src = os.path.join(source_root, 'colabconfig.txt')
                    if os.path.exists(cfg_src):
                        shutil.copy2(cfg_src, os.path.join(server_path, 'colabconfig.txt'))
                        print(f"[INFO] Configuración del servidor restaurada")

                    icon_src = os.path.join(source_root, 'server-icon.png')
                    if os.path.exists(icon_src):
                        shutil.copy2(icon_src, os.path.join(server_path, 'server-icon.png'))
                        print(f"[INFO] Icono del servidor restaurado")

                    print(f"[INFO] Backup completo detectado. Mundo '{new_level_name}' restaurado con datos de jugadores")
                else:
                    # =========================================================
                    # MODO: MUNDO SIMPLE
                    # =========================================================
                    main_world_dir = None
                    for item in items:
                        item_path = os.path.join(temp_dir, item)
                        if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, 'level.dat')):
                            main_world_dir = item
                            break

                    if main_world_dir and len(items) > 1:
                        new_level_name = main_world_dir
                    elif len(items) == 1 and os.path.isdir(os.path.join(temp_dir, items[0])):
                        new_level_name = items[0]
                    else:
                        props = self.read_server_properties(server_name)
                        new_level_name = props.get('level-name', 'world')

                    old_props = self.read_server_properties(server_name)
                    old_level_name = old_props.get('level-name', 'world')

                    self._clean_world_dirs(server_path, [old_level_name, new_level_name, 'world'])

                    if main_world_dir and len(items) > 1:
                        for item in items:
                            dest = os.path.join(server_path, item)
                            if os.path.exists(dest):
                                if os.path.isdir(dest):
                                    shutil.rmtree(dest)
                                else:
                                    os.remove(dest)
                        for item in items:
                            shutil.move(os.path.join(temp_dir, item), os.path.join(server_path, item))
                        world_path = os.path.join(server_path, new_level_name)
                    elif len(items) == 1 and os.path.isdir(os.path.join(temp_dir, items[0])):
                        source_dir = os.path.join(temp_dir, new_level_name)
                        world_path = os.path.join(server_path, new_level_name)
                        os.makedirs(world_path, exist_ok=True)
                        for item in os.listdir(source_dir):
                            shutil.move(os.path.join(source_dir, item), os.path.join(world_path, item))
                    else:
                        source_dir = temp_dir
                        world_path = os.path.join(server_path, new_level_name)
                        os.makedirs(world_path, exist_ok=True)
                        for item in items:
                            shutil.move(os.path.join(source_dir, item), os.path.join(world_path, item))

                    # También copiar archivos de jugadores en modo mundo simple
                    self._copy_player_files(temp_dir, server_path)
                    cfg_src_simple = os.path.join(temp_dir, 'colabconfig.txt')
                    if os.path.exists(cfg_src_simple):
                        shutil.copy2(cfg_src_simple, os.path.join(server_path, 'colabconfig.txt'))
                        print(f"[INFO] Configuración del servidor restaurada")

                # Actualizar server.properties con el nuevo level-name
                props = self.read_server_properties(server_name)
                props['level-name'] = new_level_name
                self.write_server_properties(server_name, props)
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

            world_path_final = os.path.join(server_path, new_level_name)
            level_dat_path = os.path.join(world_path_final, 'level.dat')

            if not os.path.exists(level_dat_path):
                msg = f"No se encontró level.dat en el zip subido para '{server_name}'. El servidor generará un mundo nuevo."
                print(f"[WARNING] {msg}")
                return {"success": False, "error": msg}

            # Validar compatibilidad de versión del mundo
            world_data_version = self._get_world_data_version(world_path_final)
            if world_data_version is not None:
                print(f"[INFO] DataVersion del mundo subido: {world_data_version}")
                # Intentar obtener la versión del jar actual
                try:
                    jar_path = os.path.join(server_path, 'paper.jar')
                    if not os.path.exists(jar_path):
                        jar_path = os.path.join(server_path, 'server.jar')
                    if os.path.exists(jar_path):
                        with zipfile.ZipFile(jar_path, 'r') as zf:
                            if 'version.json' in zf.namelist():
                                with zf.open('version.json') as f:
                                    vdata = json.loads(f.read().decode('utf-8'))
                                    server_data_version = vdata.get('world_version', vdata.get('data_version', 0))
                                    if server_data_version and world_data_version > server_data_version:
                                        warn = (f"El mundo subido tiene DataVersion {world_data_version} "
                                                f"pero el servidor es {server_data_version}. "
                                                f"El mundo puede no cargarse correctamente.")
                                        print(f"[WARNING] {warn}")
                except Exception:
                    pass

            print(f"[INFO] Mundo subido para '{server_name}' → '{new_level_name}'")

            if was_running:
                self.start(server_name)

            return {"success": True, "message": f"Mundo '{new_level_name}' subido correctamente"}
        except Exception as e:
            print(f"[ERROR] upload_world: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # MÉTODOS DE CONFIGURACIÓN (SETTINGS)
    # =========================================================================

    def read_server_properties(self, server_name: str) -> Dict[str, str]:
        """
        Lee server.properties y retorna como dict.
        """
        try:
            server_path = self.get_server_path(server_name)
            props_path = os.path.join(server_path, 'server.properties')
            props = {}
            if os.path.exists(props_path):
                with open(props_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and '=' in line and not line.startswith('#'):
                            key, _, value = line.partition('=')
                            props[key.strip()] = value.strip()
            return props
        except Exception as e:
            print(f"[ERROR] read_server_properties: {e}")
            return {}

    def write_server_properties(self, server_name: str, new_props: Dict[str, str]) -> bool:
        """
        Actualiza server.properties con los valores dados.
        Solo sobreescribe las claves existentes; agrega las que faltan.
        """
        try:
            server_path = self.get_server_path(server_name)
            props_path = os.path.join(server_path, 'server.properties')
            current = self.read_server_properties(server_name)

            # Actualizar solo las claves dadas
            current.update(new_props)

            # Asegurar valores críticos
            current['enable-rcon'] = 'true'
            current['rcon.port'] = str(self.rcon_port)
            current['rcon.password'] = self.rcon_password
            current['server-port'] = '25565'
            current['online-mode'] = 'false'
            current['enforce-secure-profile'] = 'false'

            lines = []
            seen = set()
            if os.path.exists(props_path):
                with open(props_path, 'r') as f:
                    for line in f:
                        stripped = line.strip()
                        if '=' in stripped and not stripped.startswith('#'):
                            key = stripped.split('=', 1)[0].strip()
                            seen.add(key)
                            if key in current:
                                lines.append(f'{key}={current[key]}\n')
                            else:
                                lines.append(line)
                        else:
                            lines.append(line)

            for k, v in current.items():
                if k not in seen:
                    lines.append(f'{k}={v}\n')

            with open(props_path, 'w') as f:
                f.writelines(lines)

            print(f"[INFO] server.properties actualizado para '{server_name}'")
            return True
        except Exception as e:
            print(f"[ERROR] write_server_properties: {e}")
            return False

    def get_paper_version(self, server_name: str) -> Optional[str]:
        """
        Obtiene la versión de PaperMC desde el manifest del JAR.
        """
        try:
            server_path = self.get_server_path(server_name)
            jar_path = os.path.join(server_path, 'paper.jar')

            if not os.path.exists(jar_path):
                # Intentar server.jar
                jar_path = os.path.join(server_path, 'server.jar')
                if not os.path.exists(jar_path):
                    return None

            # Leer version.json del JAR
            with zipfile.ZipFile(jar_path, 'r') as zf:
                if 'version.json' in zf.namelist():
                    with zf.open('version.json') as f:
                        data = json.loads(f.read().decode('utf-8'))
                        return data.get('name', data.get('id', 'Desconocida'))

                # Alternativa: leer paper.yml
                if 'META-INF/versions.list' in zf.namelist():
                    with zf.open('META-INF/versions.list') as f:
                        content = f.read().decode('utf-8').strip()
                        if content:
                            return content.split('\n')[-1].split('\t')[-1]

            return None
        except Exception as e:
            print(f"[ERROR] get_paper_version: {e}")
            return None

    def check_paper_updates(self, server_name: str) -> Dict:
        """
        Consulta la API de PaperMC para ver si hay versión más nueva.
        """
        try:
            current_version = self.get_paper_version(server_name)
            if not current_version:
                return {"success": False, "error": "No se pudo determinar la versión actual"}

            import requests
            response = requests.get(
                'https://api.papermc.io/v2/projects/paper',
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            all_versions = data.get('versions', [])

            # Encontrar versión más nueva
            def parse_version(v):
                parts = str(v).split('.')
                try:
                    return tuple(int(p) for p in parts)
                except ValueError:
                    return (0,)

            sorted_versions = sorted(all_versions, key=parse_version)
            latest = sorted_versions[-1] if sorted_versions else current_version

            # Comparar
            is_update = parse_version(latest) > parse_version(current_version)

            return {
                "success": True,
                "current_version": current_version,
                "latest_version": latest,
                "update_available": is_update,
                "all_versions": all_versions[-5:]  # Últimas 5
            }
        except Exception as e:
            print(f"[ERROR] check_paper_updates: {e}")
            return {"success": False, "error": str(e)}

    def update_paper(self, server_name: str, target_version: str, full_backup: bool = False) -> Dict:
        """
        Actualiza PaperMC: detiene servidor, respalda mundo, descarga nuevo JAR, reinicia.
        Retorna steps con estado para mostrar progreso en el frontend.
        """
        steps = []

        try:
            server_path = self.get_server_path(server_name)

            # Paso 1: Detener servidor
            steps.append({"step": "stop", "status": "active", "message": "Deteniendo servidor..."})
            if self.is_running():
                self.stop()
                time.sleep(2)
            steps[-1]["status"] = "done"
            steps[-1]["message"] = "Servidor detenido"

            # Paso 2: Backup comprimido del mundo
            steps.append({"step": "backup", "status": "active", "message": "Haciendo backup comprimido del mundo..."})
            world_path = os.path.join(server_path, 'world')
            if os.path.exists(world_path):
                backup_name = f'{server_name}_preupdate_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.zip'
                backup_path = os.path.join(server_path, backup_name)
                shutil.make_archive(backup_path[:-4], 'zip', world_path)
                steps[-1]["message"] = f"Backup comprimido creado: {backup_name}"
            else:
                steps[-1]["message"] = "No se encontró mundo para backup"
            steps[-1]["status"] = "done"

            # Paso 2b: Backup completo opcional
            if full_backup:
                steps.append({"step": "full_backup", "status": "active", "message": "Haciendo backup completo del servidor..."})
                fb = self._backup_full_server(server_name)
                steps[-1]["message"] = f"Backup completo creado: {fb}" if fb else "Error al crear backup completo"
                steps[-1]["status"] = "done"

            # Paso 3: Descargar nuevo Paper
            steps.append({"step": "download", "status": "active", "message": f"Descargando Paper {target_version}..."})

            import requests
            # Obtener builds
            res = requests.get(
                f'https://api.papermc.io/v2/projects/paper/versions/{target_version}',
                timeout=10
            )
            res.raise_for_status()
            version_data = res.json()
            builds = version_data.get('builds', [])
            if not builds:
                raise Exception(f"No hay builds para Paper {target_version}")
            build = builds[-1]

            # Obtener detalles del build
            res = requests.get(
                f'https://api.papermc.io/v2/projects/paper/versions/{target_version}/builds/{build}',
                timeout=10
            )
            res.raise_for_status()
            build_data = res.json()
            jar_name = build_data['downloads']['application']['name']

            # Descargar
            download_url = f'https://api.papermc.io/v2/projects/paper/versions/{target_version}/builds/{build}/downloads/{jar_name}'
            res = requests.get(download_url, stream=True, timeout=120)
            res.raise_for_status()

            jar_path = os.path.join(server_path, 'paper.jar')
            total = int(res.headers.get('content-length', 0))
            downloaded = 0
            with open(jar_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)

            steps[-1]["status"] = "done"
            steps[-1]["message"] = f"Paper {target_version} (build {build}) descargado"

            # Paso 4: Iniciar servidor
            steps.append({"step": "restart", "status": "active", "message": "Reiniciando servidor..."})
            start_result = self.start(server_name)
            if start_result.get("success"):
                steps[-1]["status"] = "done"
                steps[-1]["message"] = "Servidor iniciado"
            else:
                steps[-1]["status"] = "done"
                steps[-1]["message"] = f"Servidor listo para iniciar manualmente ({start_result.get('error', '')})"

            return {"success": True, "steps": steps}

        except Exception as e:
            print(f"[ERROR] update_paper: {e}")
            steps.append({"step": "error", "status": "error", "message": str(e)})
            return {"success": False, "error": str(e), "steps": steps}

    def reset_world(self, server_name: str) -> Dict:
        """
        Resetea el mundo: backup + eliminación + reinicio.
        """
        try:
            server_path = self.get_server_path(server_name)
            world_path = self._get_world_path(server_name)

            # Detener servidor si corre
            was_running = self.is_running()
            if was_running:
                self.stop()
                time.sleep(2)

            # Backup comprimido del mundo actual
            if os.path.exists(world_path):
                backup_name = f'{server_name}_prereset_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.zip'
                backup_path = os.path.join(server_path, backup_name)
                shutil.make_archive(backup_path[:-4], 'zip', world_path)
                shutil.rmtree(world_path)
                msg = f"Mundo respaldado como '{backup_name}' y eliminado"
            else:
                msg = "No se encontró mundo para resetear"

            # Reiniciar servidor si estaba corriendo
            if was_running:
                self.start(server_name)

            return {"success": True, "message": msg}

        except Exception as e:
            print(f"[ERROR] reset_world: {e}")
            return {"success": False, "error": str(e)}


# =============================================================================
# INSTANCIA GLOBAL
# =============================================================================

server_manager = ServerManager()
