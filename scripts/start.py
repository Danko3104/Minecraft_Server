"""
Script de arranque del MineColab Panel.
Se ejecuta desde la celda única del notebook en Google Colab.
"""

import os
import sys
import time
import threading
import subprocess
import re
import webbrowser
from typing import Optional

# Agregar el path del proyecto para poder importar panel
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel

# =============================================================================
# VARIABLES GLOBALES
# =============================================================================

console = Console()

cloudflared_process = None  # Proceso de cloudflared (global para poder detenerlo)
flask_thread = None         # Hilo de Flask
panel_url = None            # URL del panel Cloudflare

# Paths
DRIVE_MOUNT = '/content/drive/MyDrive'
MINECRAFT_DIR = os.path.join(DRIVE_MOUNT, 'minecraft')
BACKUP_DIR = os.path.join(MINECRAFT_DIR, 'backup')
BACKUP_WORLD_DIR = os.path.join(BACKUP_DIR, 'world')
BACKUP_SERVER_DIR = os.path.join(BACKUP_DIR, 'server')
LOGS_DIR = os.path.join(MINECRAFT_DIR, 'logs')


# =============================================================================
# FUNCIONES DE VERIFICACIÓN Y PREPARACIÓN
# =============================================================================

def check_drive_mounted() -> bool:
    """
    Verifica que Google Drive está montado.
    Retorna True si /content/drive/MyDrive existe.
    """
    try:
        exists = os.path.exists(DRIVE_MOUNT)
        if not exists:
            print(f"[ERROR] Google Drive no está montado en {DRIVE_MOUNT}")
            return False
        print(f"[OK] Google Drive montado en {DRIVE_MOUNT}")
        return True
    except Exception as e:
        print(f"[ERROR] check_drive_mounted: {e}")
        return False


def create_drive_structure() -> bool:
    """
    Verifica y crea la estructura de carpetas en Drive.
    """
    try:
        dirs_to_create = [
            MINECRAFT_DIR,
            BACKUP_DIR,
            BACKUP_WORLD_DIR,
            BACKUP_SERVER_DIR,
            LOGS_DIR
        ]

        for dir_path in dirs_to_create:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                print(f"[OK] Creado: {dir_path}")
            else:
                print(f"[OK] Ya existe: {dir_path}")

        return True
    except Exception as e:
        print(f"[ERROR] create_drive_structure: {e}")
        return False


def check_cloudflared_installed() -> bool:
    """
    Verifica si cloudflared está instalado.
    """
    try:
        result = subprocess.run(
            ['which', 'cloudflared'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0 and result.stdout.strip() != ''
    except Exception as e:
        print(f"[ERROR] check_cloudflared_installed: {e}")
        return False


def check_java_installed() -> bool:
    """
    Verifica si Java está instalado.
    """
    try:
        result = subprocess.run(
            ['java', '-version'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def install_java(java_version: str = "21") -> bool:
    """
    Instala Java si no está instalado.
    Usa Java 21 como versión principal para Minecraft 1.20.5+
    Retorna True si éxito.
    """
    try:
        # Verificar si ya está instalado y es la versión correcta
        if check_java_installed():
            result = subprocess.run(['java', '-version'], capture_output=True, text=True)
            version_output = result.stderr if result.stderr else result.stdout
            version_line = version_output.split('\n')[0]
            print(f"[INFO] Java detectado: {version_line}")

            # Verificar si es Java 21 exactamente
            if 'version "21' in version_line:
                print(f"[OK] Java 21 ya está instalado")
                # Configurar variables de entorno
                os.environ['JAVA_HOME'] = '/usr/lib/jvm/java-21-openjdk-amd64'
                os.environ['PATH'] = os.environ.get('JAVA_HOME', '') + '/bin:' + os.environ.get('PATH', '')
                return True
            else:
                print("[INFO] Java instalado no es versión 21, instalando Java 21...")

        print(f"[INFO] Instalando Java 21...")

        # Actualizar repositorios
        print(f"[INFO] Actualizando repositorios...")
        subprocess.run(['apt-get', 'update', '-qq'], check=True)

        # Instalar Java 21 JDK (mejor compatibilidad que JRE)
        print(f"[INFO] Instalando openjdk-21-jdk-headless...")
        result = subprocess.run(
            ['apt-get', 'install', '-y', '-q', 'openjdk-21-jdk-headless'],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"[ERROR] Error instalando Java: {result.stderr}")
            return False

        # Configurar variables de entorno para Java 21
        os.environ['JAVA_HOME'] = '/usr/lib/jvm/java-21-openjdk-amd64'
        os.environ['PATH'] = os.environ['JAVA_HOME'] + '/bin:' + os.environ.get('PATH', '')

        # Verificar instalación
        if check_java_installed():
            result = subprocess.run(['java', '-version'], capture_output=True, text=True)
            version_output = result.stderr if result.stderr else result.stdout
            version_line = version_output.split('\n')[0]
            print(f"[OK] Java 21 instalado correctamente: {version_line}")

            # Verificar versión completa
            result = subprocess.run(['java', '-version'], capture_output=True, text=True)
            print(f"[INFO] {result.stderr.strip()}")

            return True
        else:
            print("[ERROR] Java no se detecta después de la instalación")
            return False

    except subprocess.CalledProcessError as e:
        print(f"[ERROR] install_java: CalledProcessError - {e}")
        return False
    except Exception as e:
        print(f"[ERROR] install_java: {e}")
        return False


def install_cloudflared() -> bool:
    """
    Instala cloudflared si no está instalado.
    Retorna True si éxito.
    """
    try:
        if check_cloudflared_installed():
            print("[OK] cloudflared ya está instalado")
            return True

        print("[INFO] Instalando cloudflared...")

        # Descargar cloudflared
        print("[INFO] Descargando cloudflared...")
        result = subprocess.run(
            ['wget', '-q', 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb'],
            capture_output=True,
            text=True,
            cwd='/tmp'
        )

        if result.returncode != 0:
            print(f"[ERROR] Error descargando cloudflared: {result.stderr}")
            return False

        print("[OK] cloudflared descargado")

        # Instalar el paquete .deb
        print("[INFO] Instalando paquete .deb...")
        result = subprocess.run(
            ['dpkg', '-i', '/tmp/cloudflared-linux-amd64.deb'],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"[ERROR] Error instalando cloudflared: {result.stderr}")
            return False

        print("[OK] cloudflared instalado correctamente")
        return True

    except Exception as e:
        print(f"[ERROR] install_cloudflared: {e}")
        return False


# =============================================================================
# FUNCIONES DE FLASK
# =============================================================================

def run_flask_app():
    """
    Función que corre Flask en el hilo secundario.
    Importa y ejecuta la app desde panel.app.
    """
    try:
        from panel.app import socketio
        socketio.run(
            app=None,  # Se importa dentro para evitar circular imports
            host='0.0.0.0',
            port=5000,
            debug=False,
            allow_unsafe_werkzeug=True,
            use_reloader=False  # Importante: desactivar reloader en hilo
        )
    except Exception as e:
        print(f"[ERROR] Error en Flask thread: {e}")


def start_flask_thread() -> bool:
    """
    Inicia Flask en un hilo daemon.
    Espera y verifica que responde.
    Retorna True si éxito.
    """
    global flask_thread

    try:
        print("[INFO] Iniciando Flask en hilo separado...")

        # Importar app y socketio aquí para evitar circular imports
        from panel.app import app, socketio

        def flask_runner():
            """Runner interno que usa la app importada."""
            try:
                socketio.run(
                    app,
                    host='0.0.0.0',
                    port=5000,
                    debug=False,
                    allow_unsafe_werkzeug=True,
                    use_reloader=False
                )
            except Exception as e:
                print(f"[ERROR] Flask thread error: {e}")

        # Crear y iniciar el hilo daemon
        flask_thread = threading.Thread(target=flask_runner, daemon=True)
        flask_thread.start()

        # Esperar 2 segundos para que Flask levante
        print("[INFO] Esperando a que Flask levante...")
        time.sleep(2)

        # Verificar que responde (timeout 10 segundos)
        import urllib.request
        import urllib.error

        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                with urllib.request.urlopen('http://localhost:5000/api/ping', timeout=2) as response:
                    if response.status == 200:
                        print(f"[OK] Flask respondiendo en puerto 5000 (intento {attempt + 1})")
                        return True
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
                pass
            except Exception as e:
                print(f"[WARNING] Intento {attempt + 1} fallido: {e}")

            time.sleep(1)

        print("[ERROR] Flask no respondió en 10 segundos")
        return False

    except Exception as e:
        print(f"[ERROR] start_flask_thread: {e}")
        return False


# =============================================================================
# FUNCIONES DE CLOUDFLARE TUNNEL
# =============================================================================

def get_cloudflare_url(process) -> Optional[str]:
    """
    Lee stderr del proceso cloudflared.
    Extrae y retorna la URL trycloudflare.com.
    Timeout de 30 segundos, si no encuentra retorna None.
    """
    try:
        print("[INFO] Esperando URL de Cloudflare...")

        start_time = time.time()
        timeout = 30  # segundos

        # Patrón para extraer la URL
        url_pattern = re.compile(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com')

        while time.time() - start_time < timeout:
            if process.stderr:
                line = process.stderr.readline()
                if line:
                    line = line.decode('utf-8', errors='ignore') if isinstance(line, bytes) else line
                    print(f"[DEBUG] cloudflared: {line.strip()}")

                    # Buscar la URL en la línea
                    match = url_pattern.search(line)
                    if match:
                        url = match.group(0)
                        print(f"[OK] URL de Cloudflare encontrada: {url}")
                        return url

            # Verificar si el proceso murió
            if process.poll() is not None:
                print("[ERROR] El proceso cloudflared terminó inesperadamente")
                return None

            time.sleep(0.5)

        print("[ERROR] Timeout de 30 segundos esperando URL de Cloudflare")
        return None

    except Exception as e:
        print(f"[ERROR] get_cloudflare_url: {e}")
        return None


def start_cloudflare_tunnel() -> Optional[str]:
    """
    Inicia el túnel Cloudflare para el panel.
    Retorna la URL del túnel o None si falla.
    """
    global cloudflared_process

    try:
        print("[INFO] Iniciando túnel Cloudflare...")

        # Comando para cloudflared
        cmd = [
            'cloudflared',
            'tunnel',
            '--url',
            'http://localhost:5000'
        ]

        # Iniciar proceso capturando stderr para leer la URL
        cloudflared_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE
        )

        # Obtener la URL
        url = get_cloudflare_url(cloudflared_process)

        if url:
            print(f"[OK] Túnel Cloudflare iniciado: {url}")
            return url
        else:
            print("[ERROR] No se pudo obtener la URL del túnel")
            return None

    except Exception as e:
        print(f"[ERROR] start_cloudflare_tunnel: {e}")
        return None


# =============================================================================
# FUNCIÓN PRINCIPAL DE LANZAMIENTO
# =============================================================================

def launch():
    """
    Función principal que llama todo en orden.
    Manejo de errores en cada paso con mensajes claros.
    """
    global panel_url

    console.print(Panel.fit(
        "🚀 Iniciando MineColab Panel...",
        title="MineColab",
        border_style="blue"
    ))

    # Paso 1: Verificar Google Drive
    print("\n" + "=" * 60)
    print("PASO 1: Verificando Google Drive")
    print("=" * 60)

    if not check_drive_mounted():
        error_msg = (
            "❌ Google Drive no está montado.\n\n"
            "Debes montar Google Drive primero ejecutando en una celda:\n"
            "  from google.colab import drive\n"
            "  drive.mount('/content/drive')"
        )
        console.print(Panel(error_msg, title="ERROR", border_style="red"))
        return False

    # Paso 2: Crear estructura de carpetas
    print("\n" + "=" * 60)
    print("PASO 2: Creando estructura de carpetas")
    print("=" * 60)

    if not create_drive_structure():
        error_msg = "❌ Error creando la estructura de carpetas en Drive."
        console.print(Panel(error_msg, title="ERROR", border_style="red"))
        return False

    # Paso 3: Instalar cloudflared
    print("\n" + "=" * 60)
    print("PASO 3: Verificando cloudflared")
    print("=" * 60)

    if not install_cloudflared():
        error_msg = "❌ Error instalando cloudflared. Verifica tu conexión a internet."
        console.print(Panel(error_msg, title="ERROR", border_style="red"))
        return False

    # Paso 4: Instalar Java
    print("\n" + "=" * 60)
    print("PASO 4: Verificando Java")
    print("=" * 60)

    print("Verificando Java...")
    if not install_java("21"):
        error_msg = "❌ No se pudo instalar Java. Verifica tu conexión a internet."
        console.print(Panel(error_msg, title="ERROR", border_style="red"))
        return False
    print("Java listo.")

    # Paso 4.5: Iniciando túnel Localtonet
    print("\n" + "="*60)
    print("PASO 4.5: Iniciando túnel Localtonet")
    print("="*60)
    try:
        from panel import drive, tunnel
        server_data = drive.load_server_list()
        authtoken = None
        for s in server_data.values():
            proxy = s.get("localtonet_proxy", {})
            if proxy.get("authtoken"):
                authtoken = proxy["authtoken"]
                break

        if authtoken:
            success = tunnel.start_localtonet(authtoken)
            if success:
                print("[OK] Localtonet corriendo")
            else:
                print("[WARNING] Localtonet no pudo iniciarse, continuando sin túnel TCP")
        else:
            print("[WARNING] No hay authtoken de localtonet guardado, continuando sin túnel TCP")
    except Exception as e:
        print(f"[WARNING] Error iniciando localtonet: {e}")

    # Paso 5: Iniciar Flask
    print("\n" + "=" * 60)
    print("PASO 5: Iniciando Flask")
    print("=" * 60)

    if not start_flask_thread():
        error_msg = "❌ Error iniciando Flask. Revisa los logs para más detalles."
        console.print(Panel(error_msg, title="ERROR", border_style="red"))
        return False

    # Paso 6: Iniciar túnel Cloudflare
    print("\n" + "=" * 60)
    print("PASO 6: Iniciando túnel Cloudflare")
    print("=" * 60)

    panel_url = start_cloudflare_tunnel()

    if not panel_url:
        error_msg = "❌ Error iniciando el túnel Cloudflare."
        console.print(Panel(error_msg, title="ERROR", border_style="red"))
        return False

    # Paso 7: Mostrar resultado final
    print("\n" + "=" * 60)
    print("MINECOLAB PANEL LISTO")
    print("=" * 60)

    # Panel final bonito con rich
    final_message = f"""
Panel Web:
  {panel_url}

Abre esa URL en tu navegador

El servidor de Minecraft se
controla desde el panel
    """

    console.print(Panel(
        final_message,
        title="MineColab Panel Listo",
        border_style="green"
    ))

    webbrowser.open(panel_url)

    print("\n" + "=" * 60)
    print("✅ SISTEMA ACTIVO")
    print("=" * 60)
    print("   No cierres esta celda.")
    print("   Gestiona tu servidor desde el panel web.")
    print("   Para detener todo, interrumpe esta celda (■)")
    print("=" * 60 + "\n")

    # MANTENER LA CELDA VIVA - Bucle infinito hasta interrupción
    try:
        while True:
            time.sleep(30)

            # Verificar que Flask sigue respondiendo
            try:
                import requests
                r = requests.get('http://localhost:5000/api/ping', timeout=5)
                if r.status_code != 200:
                    print("⚠️  Flask no responde correctamente, verificando...")
            except requests.RequestException:
                print("⚠️  Flask no responde en este ciclo...")
            except Exception:
                pass

    except KeyboardInterrupt:
        print("\n🛑  Deteniendo MineColab...")
        cleanup()


def cleanup():
    """
    Detiene todos los procesos al interrumpir la celda.
    Limpieza ordenada de Minecraft, cloudflared y otros recursos.
    """
    import requests

    print("\n" + "-" * 60)
    print("CLEANUP - Deteniendo servicios...")
    print("-" * 60)

    # 1. Intentar detener Minecraft limpiamente via API
    try:
        r = requests.post('http://localhost:5000/api/server/stop', timeout=10)
        if r.status_code == 200:
            print("✅ Servidor Minecraft detenido via API")
        else:
            print("⚠️  Minecraft no estaba corriendo o error al detener")
    except requests.RequestException:
        print("⚠️  No se pudo conectar a Flask para detener Minecraft")
    except Exception:
        pass

    # 2. Matar proceso de cloudflared si existe
    global cloudflared_process
    if cloudflared_process is not None:
        try:
            cloudflared_process.terminate()
            print("✅ Túnel Cloudflare cerrado")
        except Exception as e:
            print(f"⚠️  Error cerrando cloudflared: {e}")

    # 3. Esperar un momento para que los procesos terminen
    time.sleep(2)

    print("\n" + "=" * 60)
    print("👋  MineColab detenido correctamente")
    print("=" * 60)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    launch()
