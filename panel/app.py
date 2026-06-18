"""
Aplicación Flask principal del MineColab Panel.
Maneja las rutas HTTP y WebSocket para el panel de control.
"""

from datetime import datetime
import os
import re
import shutil
import tempfile
import psutil
import threading
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from panel.routes.auth import check_token

from panel.drive import (
    get_active_server,
    list_servers,
    set_active_server,
    save_server_config,
    get_global_config,
    save_global_config,
    get_server_config
)
from panel.server_manager import server_manager
from panel.routes.servers import servers_bp
from panel.routes.players import players_bp
from panel.routes.plugins import plugins_bp
from panel.routes.files import files_bp
from panel.routes.console import console_bp
from panel.routes.dashboard import dashboard_bp

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('MINECOLAB_JWT_SECRET', 'minecolab-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB para mundos grandes

# CORS habilitado para todos los orígenes (necesario para Colab)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# SocketIO con async_mode='threading'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Registrar blueprints
app.register_blueprint(servers_bp)
app.register_blueprint(players_bp)
app.register_blueprint(plugins_bp)
app.register_blueprint(files_bp)
app.register_blueprint(console_bp)
app.register_blueprint(dashboard_bp)

# =============================================================================
# MIDDLEWARE DE AUTENTICACIÓN
# =============================================================================

PUBLIC_API_PATHS = [
    '/api/ping',
    '/api/auth/login',
    '/api/auth/check',
    '/api/auth/logout',
    '/api/software/types',
    '/api/software/versions',
    '/api/settings/server-icon',
    '/api/settings/check-updates',
    '/api/settings/check-plugin-compatibility',
    '/api/settings/plugin-recommendations',
    '/api/settings/property-recommendations',
    '/api/settings/property-recommendations/apply',
    '/api/settings/server-properties',
    '/api/servers',
    '/api/server/chunky-progress',
]


@app.before_request
def require_auth():
    if not request.path.startswith('/api/'):
        return
    if request.path in PUBLIC_API_PATHS:
        return
    if request.path.startswith('/api/players/'):
        return
    if request.path.startswith('/api/settings/'):
        return
    if request.path.startswith('/api/server/'):
        return
    if request.path.startswith('/api/files/'):
        return
    if request.path.startswith('/api/plugins/'):
        return
    if request.path.startswith('/api/servers/'):
        return
    if request.path.startswith('/api/console/'):
        return
    if request.method == 'GET':
        return
    if not check_token():
        return jsonify({"success": False, "error": "No autorizado"}), 401


# =============================================================================
# VARIABLES GLOBALES
# =============================================================================

server_process = None        # Proceso de Minecraft (subprocess)
server_start_time = None     # datetime cuando se inició Minecraft
session_start_time = datetime.now()  # Cuando arrancó Flask

# Estado de procesamiento de uploads (upload_id -> dict con status/progress/result/error)
_upload_status: dict = {}
_upload_lock = threading.Lock()

# =============================================================================
# RUTAS PRINCIPALES
# =============================================================================


@app.route('/')
def index():
    """
    Ruta principal - sirve el archivo HTML del panel.
    """
    try:
        return send_from_directory('static', 'index.html')
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/ping', methods=['GET'])
def api_ping():
    """
    Endpoint para verificar que Flask responde.
    """
    try:
        return jsonify({"ok": True, "message": "MineColab API corriendo"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/status', methods=['GET'])
def api_status():
    """
    Retorna el estado general del panel.
    """
    try:
        now = datetime.now()
        session_uptime = (now - session_start_time).total_seconds()
        colab_max_time = 43200  # 12 horas en segundos (límite Colab)
        colab_time_remaining = max(0, colab_max_time - session_uptime)

        active = get_active_server()
        server_type = ''
        if active:
            cfg = get_server_config(active)
            server_type = cfg.get('server_type', '')

        return jsonify({
            "flask": True,
            "minecraft_running": server_manager.is_running(),
            "active_server": active,
            "active_server_type": server_type,
            "servers": list_servers(),
            "session_uptime_seconds": int(session_uptime),
            "colab_time_remaining": int(colab_time_remaining)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/servers', methods=['GET'])
def api_servers():
    """
    Retorna lista de servidores disponibles.
    """
    try:
        servers = list_servers()
        active = get_active_server()

        return jsonify({
            "servers": servers,
            "active": active
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/servers/select', methods=['POST'])
def api_select_server():
    """
    Selecciona un servidor como activo.
    Body JSON: {"server_name": "nombre"}
    """
    try:
        data = request.get_json()

        if not data or 'server_name' not in data:
            return jsonify({
                "success": False,
                "error": "Falta 'server_name' en el body"
            }), 400

        server_name = data['server_name']

        if not server_name:
            return jsonify({
                "success": False,
                "error": "server_name no puede estar vacío"
            }), 400

        success = set_active_server(server_name)

        if success:
            return jsonify({
                "success": True,
                "active": server_name
            })
        else:
            return jsonify({
                "success": False,
                "error": "No se pudo establecer el servidor activo"
            }), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/server/start', methods=['POST'])
def api_server_start():
    """
    Inicia el servidor de Minecraft.
    """
    try:
        # Obtener servidor activo
        active_server = get_active_server()

        if not active_server:
            return jsonify({
                "success": False,
                "error": "No hay servidor activo. Selecciona uno primero."
            }), 400

        # Iniciar servidor
        result = server_manager.start(active_server)

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/server/stop', methods=['POST'])
def api_server_stop():
    """
    Detiene el servidor de Minecraft.
    """
    try:
        result = server_manager.stop()
        return jsonify(result)

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/server/command', methods=['POST'])
def api_server_command():
    """
    Envía un comando al servidor.
    Body JSON: {"command": "say hola"}
    """
    try:
        data = request.get_json()

        if not data or 'command' not in data:
            return jsonify({
                "success": False,
                "error": "Falta 'command' en el body"
            }), 400

        command = data['command'].strip().lower()

        # Si es "stop", redirigir al método oficial que guarda/backupea
        if command == 'stop':
            result = server_manager.stop()
            return jsonify(result)

        response = server_manager.send_command(command)

        return jsonify({
            "success": True,
            "response": response
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/server/chunky-progress', methods=['POST'])
def api_server_chunky_progress():
    """
    POST /api/server/chunky-progress
    Body: {"percent": 45.5, "eta": "35s", "chunk": "(100, 64)", "running": true}
    Envía un actionbar a todos los jugadores con el progreso de Chunky.
    """
    try:
        if not server_manager.is_running():
            return jsonify({"success": False, "error": "Servidor no está corriendo"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Body requerido"}), 400

        pct = data.get('percent')
        running = data.get('running', True)
        eta = data.get('eta', '')

        if running and pct is not None:
            pct_display = round(pct, 1)
            eta_text = f" | ETA: {eta}" if eta else ""
            cmd = f'title @a actionbar {{"text":"⛏ Chunky: {pct_display}%{eta_text}","color":"gold","bold":true}}'
        else:
            cmd = 'title @a actionbar {"text":"⛏ Chunky completado!","color":"green","bold":true}'

        response = server_manager.send_command(cmd)
        return jsonify({"success": True, "response": response})

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/server/stats', methods=['GET'])
def api_server_stats():
    try:
        if not server_manager.is_running():
            return jsonify({"success": False, "error": "Servidor no está corriendo"}), 400

        # Obtener TPS por RCON, con fallback a last_output
        tps_values = []
        tps_resp = server_manager.send_command('tps')
        import re
        if tps_resp and tps_resp != "Comando enviado":
            numbers = re.findall(r'\b\d+\.\d+\b', tps_resp)
            if len(numbers) >= 3:
                tps_values = [float(v) for v in numbers[:3]]
            else:
                numbers = re.findall(r'\b(\d+)\b', tps_resp)
                filtered = [float(v) for v in numbers if 0 <= float(v) <= 20.0]
                if len(filtered) >= 3:
                    tps_values = filtered[:3]
        if not tps_values:
            for line in reversed(server_manager.get_last_output()):
                if 'tps' in line.lower():
                    m = re.findall(r'\b\d+\.\d+\b', line)
                    if len(m) >= 3:
                        tps_values = [float(v) for v in m[:3]]
                        break

        ram_bytes = psutil.Process(server_manager.process.pid).memory_info().rss if server_manager.process else 0
        cpu_percent = psutil.Process(server_manager.process.pid).cpu_percent(interval=0.5) if server_manager.process else 0

        return jsonify({
            "success": True,
            "tps": tps_values,
            "ram_mb": round(ram_bytes / 1024 / 1024, 1),
            "cpu_percent": cpu_percent
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/server/last-output', methods=['GET'])
def api_server_last_output():
    """
    Retorna las últimas líneas de salida del servidor.
    """
    try:
        lines = server_manager.get_last_output()
        return jsonify({
            "lines": lines
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/console/log', methods=['GET'])
def api_console_log():
    """
    GET /api/console/log?lines=100
    Retorna las últimas N líneas del archivo de log persistente.
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        log_path = server_manager.get_log_path(active_server)
        if not os.path.exists(log_path):
            return jsonify({"success": True, "lines": [], "file": "console.log"})

        num_lines = request.args.get('lines', 100, type=int)
        num_lines = max(10, min(num_lines, 5000))

        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()

        tail = all_lines[-num_lines:]
        return jsonify({
            "success": True,
            "lines": [l.rstrip('\n\r') for l in tail],
            "total_lines": len(all_lines),
            "file": "console.log"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/console/logs', methods=['GET'])
def api_console_logs():
    """
    GET /api/console/logs
    Lista los archivos de log disponibles (con rotación).
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        files = server_manager.get_log_files(active_server)
        return jsonify({"success": True, "files": files})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/console/log/download', methods=['GET'])
def api_console_log_download():
    """
    GET /api/console/log/download?name=console.log
    Descarga un archivo de log.
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        log_name = request.args.get('name', 'console.log')
        log_dir = os.path.join(server_manager.get_server_path(active_server), 'logs')
        log_path = os.path.join(log_dir, log_name)

        if not os.path.exists(log_path) or not log_path.startswith(log_dir):
            return jsonify({"success": False, "error": "Archivo no encontrado"}), 404

        return send_file(log_path, as_attachment=True, download_name=log_name)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# RUTAS DE CONFIGURACIÓN (SETTINGS)
# =============================================================================


@app.route('/api/settings/server-properties', methods=['GET', 'PUT'])
def api_settings_server_properties():
    """
    GET /api/settings/server-properties — Lee server.properties del servidor activo
    PUT /api/settings/server-properties — Guarda server.properties
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        if request.method == 'GET':
            props = server_manager.read_server_properties(active_server)
            return jsonify({"success": True, "properties": props})

        elif request.method == 'PUT':
            data = request.get_json()
            if not data or 'properties' not in data:
                return jsonify({"success": False, "error": "Faltan 'properties' en el body"}), 400

            success = server_manager.write_server_properties(active_server, data['properties'])
            if success:
                return jsonify({"success": True, "message": "Propiedades guardadas"})
            else:
                return jsonify({"success": False, "error": "Error al guardar server.properties"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/paper-version', methods=['GET'])
def api_settings_paper_version():
    """
    GET /api/settings/paper-version — Retorna la versión de PaperMC instalada.
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        version = server_manager.get_paper_version(active_server)
        return jsonify({"success": True, "version": version or "Desconocida"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/check-plugin-compatibility', methods=['POST'])
def api_settings_check_plugin_compatibility():
    """
    POST /api/settings/check-plugin-compatibility
    Body: {"version": "1.21.1"}
    Verifica compatibilidad de plugins/mods con la versión destino.
    """
    try:
        data = request.get_json()
        target_version = data.get('version', '') if data else ''
        if not target_version:
            return jsonify({"success": False, "error": "Falta 'version'"}), 400

        from panel.routes.plugins import check_plugins_compatibility
        result = check_plugins_compatibility(target_version)
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/plugin-recommendations', methods=['GET'])
def api_settings_plugin_recommendations():
    """
    GET /api/settings/plugin-recommendations
    Recomienda instalar plugins/mods de otros servidores del mismo tipo.
    """
    try:
        from panel.routes.plugins import get_cross_server_recommendations
        result = get_cross_server_recommendations()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/property-recommendations', methods=['GET'])
def api_settings_property_recommendations():
    """
    GET /api/settings/property-recommendations
    Recomienda cambios útiles en server.properties basados en mejores prácticas.
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        current = server_manager.read_server_properties(active_server) or {}

        recommendations = [
            {
                "key": "spawn-protection",
                "current_value": current.get("spawn-protection", "16"),
                "recommended_value": "0",
                "label": "Desactivar protección de spawn",
                "description": "Permite a los jugadores construir y modificar el terreno cerca del punto de spawn.",
                "category": "gameplay"
            },
            {
                "key": "enable-command-blocks",
                "current_value": current.get("enable-command-blocks", "false"),
                "recommended_value": "true",
                "label": "Activar bloques de comandos",
                "description": "Permite usar bloques de comandos para crear mapas, minijuegos y mecanismos avanzados.",
                "category": "gameplay"
            },
            {
                "key": "max-tick-time",
                "current_value": current.get("max-tick-time", "60000"),
                "recommended_value": "-1",
                "label": "Desactivar watchdog timeout",
                "description": "Evita que el servidor se detenga por superar el límite de tick time. Útil para servidores con muchos plugins o granjas grandes.",
                "category": "performance"
            },
            {
                "key": "network-compression-threshold",
                "current_value": current.get("network-compression-threshold", "256"),
                "recommended_value": "256",
                "label": "Compresión de red óptima",
                "description": "Valor recomendado para equilibrar ancho de banda y CPU en la comunicación con jugadores.",
                "category": "performance"
            },
            {
                "key": "view-distance",
                "current_value": current.get("view-distance", "10"),
                "recommended_value": "8",
                "label": "Reducir distancia de renderizado a 8",
                "description": "Mejora el rendimiento del servidor reduciendo la distancia que se envía a los jugadores. Buena relación calidad/rendimiento.",
                "category": "performance"
            },
            {
                "key": "simulation-distance",
                "current_value": current.get("simulation-distance", "10"),
                "recommended_value": "6",
                "label": "Reducir distancia de simulación a 6",
                "description": "Reduce el área donde el servidor procesa entidades, mejorando el TPS en servidores con muchos jugadores.",
                "category": "performance"
            },
            {
                "key": "hardcore",
                "current_value": current.get("hardcore", "false"),
                "recommended_value": "true",
                "label": "Activar modo hardcore",
                "description": "Si un jugador muere, es baneado permanentemente. Dificultad máxima, sin regeneración natural.",
                "category": "gameplay"
            },
            {
                "key": "online-mode",
                "current_value": current.get("online-mode", "true"),
                "recommended_value": "true",
                "label": "Mantener online-mode=true",
                "description": "Verifica cuentas premium con Mojang. Desactivarlo permite que cualquiera entre con cualquier nombre, pero abre la puerta a ataques.",
                "category": "security"
            },
        ]

        return jsonify({"success": True, "recommendations": recommendations, "server": active_server})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/property-recommendations/apply', methods=['POST'])
def api_settings_property_recommendations_apply():
    """
    POST /api/settings/property-recommendations/apply
    Body: {"key": "spawn-protection", "value": "0"}
    Aplica una propiedad recomendada al server.properties.
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        data = request.get_json()
        if not data or 'key' not in data:
            return jsonify({"success": False, "error": "Falta 'key'"}), 400

        key = data['key']
        value = data.get('value', '')

        current = server_manager.read_server_properties(active_server)
        current[key] = value
        success = server_manager.write_server_properties(active_server, current)

        if success:
            return jsonify({"success": True, "message": f"{key} = {value} aplicado. Se requiere reinicio."})
        else:
            return jsonify({"success": False, "error": "Error al guardar server.properties"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/check-updates', methods=['POST'])
def api_settings_check_updates():
    """
    POST /api/settings/check-updates — Consulta API de PaperMC por versiones más nuevas.
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        result = server_manager.check_paper_updates(active_server)
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/update', methods=['POST'])
def api_settings_update():
    """
    POST /api/settings/update — Actualiza PaperMC a la versión especificada.
    Body: {"version": "1.21.1"}
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        data = request.get_json()
        version = data.get('version', '') if data else ''
        full_backup = data.get('full_backup', False) if data else False

        if not version:
            return jsonify({"success": False, "error": "Falta 'version' en el body"}), 400

        result = server_manager.update_paper(active_server, version, full_backup)
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/reset-world', methods=['POST'])
def api_settings_reset_world():
    """
    POST /api/settings/reset-world — Resetea el mundo con backup.
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        result = server_manager.reset_world(active_server)
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/server-icon', methods=['GET', 'POST'])
def api_settings_server_icon():
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        server_path = server_manager.get_server_path(active_server)
        icon_path = os.path.join(server_path, 'server-icon.png')

        if request.method == 'GET':
            if os.path.exists(icon_path):
                resp = send_file(icon_path, mimetype='image/png')
                resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                resp.headers['Pragma'] = 'no-cache'
                resp.headers['Expires'] = '0'
                return resp
            return jsonify({"success": False, "error": "No hay icono"}), 404

        elif request.method == 'POST':
            if 'file' not in request.files:
                return jsonify({"success": False, "error": "Falta archivo"}), 400

            f = request.files['file']
            if not f.filename.lower().endswith('.png'):
                return jsonify({"success": False, "error": "Solo archivos .png"}), 400

            temp_raw = os.path.join(tempfile.gettempdir(), 'upload_icon_raw.png')
            f.save(temp_raw)
            fsize = os.path.getsize(temp_raw)
            if fsize > 1024 * 1024:
                os.remove(temp_raw)
                return jsonify({"success": False, "error": "El icono debe ser menor a 1 MB"}), 400

            try:
                from PIL import Image
                img = Image.open(temp_raw)
                if img.mode not in ('RGBA', 'RGB'):
                    img = img.convert('RGBA')
                if img.size != (64, 64):
                    img = img.resize((64, 64), Image.LANCZOS)
                os.makedirs(os.path.dirname(icon_path), exist_ok=True)
                img.save(icon_path, format='PNG')
                os.remove(temp_raw)
            except Exception as e:
                if os.path.exists(temp_raw):
                    os.remove(temp_raw)
                return jsonify({"success": False, "error": f"El archivo no es una imagen PNG válida: {str(e)}"}), 400
            import shutil
            backup_icon = os.path.join(os.path.dirname(icon_path), '.server-icon-backup.png')
            shutil.copy2(icon_path, backup_icon)
            return jsonify({"success": True, "message": "Icono del servidor actualizado."})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/backup-world', methods=['POST'])
def api_settings_backup_world():
    """
    POST /api/settings/backup-world — Backup manual del mundo.
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        result = server_manager._backup_world(active_server)
        if result:
            return jsonify({"success": True, "backup_name": result, "message": f"Backup creado: {result}"})
        else:
            return jsonify({"success": False, "error": "No se pudo crear el backup"}), 500

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/backups', methods=['GET'])
def api_settings_list_backups():
    """
    GET /api/settings/backups — Lista backups del servidor activo.
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        backups = server_manager.list_backups(active_server)
        return jsonify({"success": True, "backups": backups})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/backups/restore', methods=['POST'])
def api_settings_restore_backup():
    """
    POST /api/settings/backups/restore — Restaura un backup.
    Body: {"backup_name": "..."}
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        data = request.get_json()
        backup_name = data.get('backup_name', '') if data else ''
        if not backup_name:
            return jsonify({"success": False, "error": "Falta 'backup_name'"}), 400

        result = server_manager.restore_backup(active_server, backup_name)
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/backups/delete', methods=['POST'])
def api_settings_delete_backup():
    """
    POST /api/settings/backups/delete — Elimina un backup.
    Body: {"backup_name": "..."}
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        data = request.get_json()
        backup_name = data.get('backup_name', '') if data else ''
        if not backup_name:
            return jsonify({"success": False, "error": "Falta 'backup_name'"}), 400

        result = server_manager.delete_backup(active_server, backup_name)
        return jsonify(result)

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/upload-world', methods=['POST'])
def api_settings_upload_world():
    """
    POST /api/settings/upload-world — Sube un .zip para reemplazar el mundo.
    Body: multipart/form-data con campo 'file'
    """
    try:
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        if 'file' not in request.files:
            return jsonify({"success": False, "error": "No se envió ningún archivo"}), 400

        file = request.files['file']
        if not file.filename.endswith('.zip'):
            return jsonify({"success": False, "error": "Solo se aceptan archivos .zip"}), 400

        # Guardar temporalmente
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp_path = tmp.name
        file.save(tmp_path)

        try:
            result = server_manager.upload_world(active_server, tmp_path)
            return jsonify(result)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



@app.route('/api/settings/upload-world-chunked', methods=['POST'])
def api_settings_upload_world_chunked():
    """
    POST /api/settings/upload-world-chunked — Recibe un chunk de archivo.
    Cuando llega el último, reensambla y procesa en segundo plano.
    Body (multipart): chunk (file), index, total, upload_id, filename
    """
    try:
        CHUNK_DIR = os.path.join(tempfile.gettempdir(), 'minecolab_upload_chunks')
        os.makedirs(CHUNK_DIR, exist_ok=True)
        active_server = get_active_server()
        if not active_server:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        if 'chunk' not in request.files:
            return jsonify({"success": False, "error": "No se envió el chunk"}), 400

        chunk = request.files['chunk']
        index = int(request.form.get('index', -1))
        total = int(request.form.get('total', 0))
        upload_id = request.form.get('upload_id', '')

        if index < 0 or total < 1 or not upload_id:
            return jsonify({"success": False, "error": "Parámetros inválidos"}), 400

        chunk_dir = os.path.join(CHUNK_DIR, upload_id)
        os.makedirs(chunk_dir, exist_ok=True)
        chunk.save(os.path.join(chunk_dir, f'chunk_{index:05d}'))

        if index == total - 1:
            for i in range(total):
                cp = os.path.join(chunk_dir, f'chunk_{i:05d}')
                if not os.path.exists(cp):
                    return jsonify({"success": False, "error": f"Falta el chunk {i}"}), 400

            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
                tmp_path = tmp.name
                for i in range(total):
                    cp = os.path.join(chunk_dir, f'chunk_{i:05d}')
                    with open(cp, 'rb') as f:
                        tmp.write(f.read())

            shutil.rmtree(chunk_dir, ignore_errors=True)

            # Inicializar estado de procesamiento
            with _upload_lock:
                _upload_status[upload_id] = {"status": "processing", "progress": "Reensamblando mundo...", "result": None, "error": None}

            # Procesar en segundo plano para evitar timeout
            def _process_upload():
                try:
                    with _upload_lock:
                        _upload_status[upload_id]["progress"] = "Procesando mundo..."
                    result = server_manager.upload_world(active_server, tmp_path)
                    with _upload_lock:
                        if result.get("success"):
                            _upload_status[upload_id]["status"] = "done"
                            _upload_status[upload_id]["result"] = result
                            _upload_status[upload_id]["progress"] = "Mundo subido correctamente"
                        else:
                            _upload_status[upload_id]["status"] = "error"
                            _upload_status[upload_id]["error"] = result.get("error", "Error desconocido")
                            _upload_status[upload_id]["progress"] = "Error"
                except Exception as e:
                    with _upload_lock:
                        _upload_status[upload_id]["status"] = "error"
                        _upload_status[upload_id]["error"] = str(e)
                        _upload_status[upload_id]["progress"] = "Error"
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

            threading.Thread(target=_process_upload, daemon=True).start()

            return jsonify({"success": True, "message": "Mundo recibido, procesando...", "upload_id": upload_id, "processing": True})

        return jsonify({"success": True, "message": f"Chunk {index+1}/{total} recibido"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/upload-world-status', methods=['GET'])
def api_settings_upload_world_status():
    """
    GET /api/settings/upload-world-status?upload_id=xxx
    Retorna el estado del procesamiento de un upload.
    """
    try:
        upload_id = request.args.get('upload_id', '')
        if not upload_id:
            return jsonify({"success": False, "error": "Falta upload_id"}), 400

        with _upload_lock:
            status = _upload_status.get(upload_id)

        if not status:
            return jsonify({"success": False, "error": "upload_id no encontrado"}), 404

        return jsonify({
            "success": True,
            "status": status["status"],
            "progress": status.get("progress", ""),
            "error": status.get("error"),
            "result": status.get("result")
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/settings/upload-world-cancel', methods=['POST'])
def api_settings_upload_world_cancel():
    """Limpia los chunks de una subida cancelada."""
    try:
        upload_id = request.json.get('upload_id', '') if request.is_json else ''
        if upload_id:
            chunk_dir = os.path.join(tempfile.gettempdir(), 'minecolab_upload_chunks', upload_id)
            if os.path.isdir(chunk_dir):
                shutil.rmtree(chunk_dir, ignore_errors=True)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# FIN RUTAS DE CONFIGURACIÓN
# =============================================================================


@app.route('/api/server/diagnose', methods=['GET'])
def api_server_diagnose():
    """
    Retorna información completa de diagnóstico del servidor activo.
    """
    try:
        active_server = get_active_server()

        if not active_server:
            return jsonify({
                "success": False,
                "error": "No hay servidor activo"
            }), 400

        diagnosis = server_manager.diagnose(active_server)
        return jsonify(diagnosis)

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# WEBSOCKET / SOCKETIO EVENTS
# =============================================================================

from panel.socketio_events import register_socketio_events
register_socketio_events(socketio)


# =============================================================================
# MANEJO DE ERRORES GLOBALES
# =============================================================================

@app.errorhandler(404)
def not_found(error):
    """Maneja errores 404."""
    return jsonify({"error": "Recurso no encontrado"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Maneja errores 500."""
    return jsonify({"error": "Error interno del servidor"}), 500


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("MINECOLAB PANEL")
    print("=" * 60)
    print(f"Iniciando MineColab Panel en puerto 5000...")
    print(f"Session start time: {session_start_time}")
    print("=" * 60)
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    socketio.run(app, host='0.0.0.0', port=5000, debug=debug_mode, allow_unsafe_werkzeug=debug_mode)
