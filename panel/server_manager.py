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
        self.last_output_lines: List[str] = []  # Últimas líneas de salida del proceso

    def get_server_path(self, server_name: str) -> str:
        """
        Retorna la ruta del servidor en Drive.
        """
        base = '/content/drive/MyDrive/minecraft'
        return os.path.join(base, server_name)

    def prepare_server_properties(self, server_name: str) -> bool:
        """
        Lee server.properties y agrega/sobreescribe propiedades RCON.
        """
        try:
            server_path = self.get_server_path(server_name)
            props_path = os.path.join(server_path, 'server.properties')

            # Si no existe, crear uno básico
            if not os.path.exists(props_path):
                properties = Properties()
                properties['enable-rcon'] = 'true'
                properties['rcon.port'] = str(self.rcon_port)
                properties['rcon.password'] = self.rcon_password
                properties['server-port'] = '25565'
                properties['max-players'] = '20'
                properties['level-name'] = 'world'
                properties['enforce-secure-profile'] = 'false'
                properties['online-mode'] = 'false'
                properties['white-list'] = 'true'

                with open(props_path, 'wb') as f:
                    properties.store(f)
                print(f"[INFO] server.properties creado para '{server_name}'")
                return True

            # Leer existente
            properties = Properties()
            with open(props_path, 'rb') as f:
                properties.load(f)

            # Modificar propiedades RCON
            properties['enable-rcon'] = 'true'
            properties['rcon.port'] = str(self.rcon_port)
            properties['rcon.password'] = self.rcon_password
            properties['enforce-secure-profile'] = 'false'
            properties['online-mode'] = 'false'
            properties['white-list'] = 'true'

            # Guardar
            with open(props_path, 'wb') as f:
                properties.store(f)

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

            # Comandos base para Java
            java_cmd = [
                "java",
                "-Xms512M",
                "-Xmx2G",
                "-XX:+UseG1GC",
                "-XX:+ParallelRefProcEnabled",
                "-XX:MaxGCPauseMillis=200"
            ]

            # Según server_type
            if server_type in ['paper', 'purpur', 'folia', 'vanilla', 'snapshot']:
                java_cmd.extend(["-jar", "server.jar", "--nogui"])

            elif server_type == 'fabric':
                java_cmd.extend(["-jar", "fabric-server-launch.jar", "--nogui"])

            elif server_type in ['forge', 'neoforge']:
                # Verificar si existe run.sh
                run_sh = os.path.join(server_path, 'run.sh')
                if os.path.exists(run_sh):
                    return ["bash", run_sh, "--nogui"]
                else:
                    java_cmd.extend(["-jar", "server.jar", "--nogui"])

            elif server_type == 'bedrock':
                return ["./bedrock_server"]

            else:
                # Default
                java_cmd.extend(["-jar", "server.jar", "--nogui"])

            return java_cmd

        except Exception as e:
            print(f"[ERROR] get_java_command: {e}")
            return ["java", "-jar", "server.jar", "--nogui"]

    def _start_output_reader(self):
        """
        Inicia el hilo que lee la salida del proceso.
        """
        def read_output():
            """Lee la salida del proceso y la guarda en last_output_lines."""
            try:
                for line in self.process.stdout:
                    line = line.strip()
                    if line:
                        self.last_output_lines.append(line)
                        print(f"[MINECRAFT] {line}")
                        # Mantener solo las últimas 200 líneas
                        if len(self.last_output_lines) > 200:
                            self.last_output_lines.pop(0)
            except Exception as e:
                print(f"[ERROR] read_output: {e}")

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
                'server.jar': 'server.jar' in files,
                'fabric-server-launch.jar': 'fabric-server-launch.jar' in files,
                'forge': any(f.startswith('forge') and f.endswith('.jar') for f in files),
                'neoforge': any(f.startswith('neo') and f.endswith('.jar') for f in files),
                'bedrock_server': 'bedrock_server' in files
            }

            # Determinar cuál usar
            jar_file = None
            if jar_files['server.jar']:
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

    def _setup_minekube(self, server_path: str) -> bool:
        try:
            plugins_dir = os.path.join(server_path, 'plugins')
            os.makedirs(plugins_dir, exist_ok=True)

            jar_path = os.path.join(plugins_dir, 'connect-spigot.jar')
            if not os.path.exists(jar_path):
                print(f"[INFO] Descargando Minekube Connect plugin...")
                import urllib.request
                url = 'https://github.com/minekube/connect/releases/latest/download/connect-spigot.jar'
                urllib.request.urlretrieve(url, jar_path)
                print(f"[OK] Minekube Connect plugin descargado")
            else:
                print(f"[OK] Minekube Connect plugin ya existe")

            connect_config_dir = os.path.join(plugins_dir, 'connect')
            os.makedirs(connect_config_dir, exist_ok=True)
            config_path = os.path.join(connect_config_dir, 'config.yml')
            if not os.path.exists(config_path):
                with open(config_path, 'w') as f:
                    f.write('endpoint: "minecolab"\n')
                print(f"[OK] config.yml creado con endpoint: minecolab")
            else:
                print(f"[OK] config.yml ya existe")

            return True
        except Exception as e:
            print(f"[WARNING] Minekube setup falló: {e}")
            return False

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

            # Minekube Connect plugin
            self._setup_minekube(server_path)

            # Obtener comando
            command = self.get_java_command(server_name)

            print(f"[INFO] Iniciando servidor '{server_name}'...")
            print(f"[INFO] Comando: {' '.join(command)}")
            print(f"[INFO] Directorio: {server_path}")

            # Limpiar output anterior
            self.last_output_lines = []

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

            # Guardar tiempos
            self.start_time = datetime.now()
            self.intentional_stop = False

            # Esperar 5 segundos y verificar que sigue vivo
            time.sleep(5)

            if self.process.poll() is not None:
                # El proceso murió - retornar output capturado
                error_output = self.last_output_lines[-50:] if self.last_output_lines else ["No hay output capturado"]
                return {
                    "success": False,
                    "error": f"El servidor falló al iniciar. Código: {self.process.returncode}",
                    "output": error_output,
                    "diagnosis": {
                        "command": command,
                        "server_path": server_path,
                        "java": java_info,
                        "jar": jar_info,
                        "eula": eula_info
                    }
                }

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
        """
        try:
            # Verificar si hay proceso
            if self.process is None:
                return {
                    "success": False,
                    "error": "El servidor no está corriendo"
                }

            self.intentional_stop = True

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


# =============================================================================
# INSTANCIA GLOBAL
# =============================================================================

server_manager = ServerManager()
