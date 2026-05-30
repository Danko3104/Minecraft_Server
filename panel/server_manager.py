"""
Server Manager - Controla el proceso de Java (Minecraft).
Permite iniciar, detener y gestionar el servidor.
"""

import os
import sys
import time
import subprocess
import json
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

            # Preparar server.properties
            if not self.prepare_server_properties(server_name):
                return {
                    "success": False,
                    "error": "Error al preparar server.properties"
                }

            # Obtener comando
            command = self.get_java_command(server_name)
            server_path = self.get_server_path(server_name)

            print(f"[INFO] Iniciando servidor '{server_name}'...")
            print(f"[INFO] Comando: {' '.join(command)}")
            print(f"[INFO] Directorio: {server_path}")

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

            # Guardar tiempos
            self.start_time = datetime.now()
            self.intentional_stop = False

            # Esperar 3 segundos y verificar que sigue vivo
            time.sleep(3)

            if self.process.poll() is not None:
                # El proceso murió
                return {
                    "success": False,
                    "error": f"El servidor falló al iniciar. Código: {self.process.returncode}"
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
        status = {
            "running": self.is_running(),
            "uptime_seconds": 0,
            "pid": None
        }

        if self.process:
            status["pid"] = self.process.pid

            if self.start_time and self.is_running():
                uptime = datetime.now() - self.start_time
                status["uptime_seconds"] = int(uptime.total_seconds())

        return status

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
