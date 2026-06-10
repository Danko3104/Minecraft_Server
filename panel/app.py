"""
Aplicación Flask principal del MineColab Panel.
Maneja las rutas HTTP y WebSocket para el panel de control.
"""

from datetime import datetime
import os
import re
import psutil
from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from panel.drive import (
    get_active_server,
    list_servers,
    set_active_server,
    save_server_config,
    get_global_config,
    save_global_config
)
from panel.server_manager import server_manager
from panel.routes.servers import servers_bp
from panel.routes.players import players_bp
from panel.routes.plugins import plugins_bp

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'minecolab-secret-key-change-in-production'

# CORS habilitado para todos los orígenes (necesario para Colab)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# SocketIO con async_mode='threading'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Registrar blueprints
app.register_blueprint(servers_bp)
app.register_blueprint(players_bp)
app.register_blueprint(plugins_bp)

# =============================================================================
# VARIABLES GLOBALES
# =============================================================================

server_process = None        # Proceso de Minecraft (subprocess)
server_start_time = None     # datetime cuando se inició Minecraft
session_start_time = datetime.now()  # Cuando arrancó Flask

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

        return jsonify({
            "flask": True,
            "minecraft_running": server_manager.is_running(),
            "active_server": get_active_server(),
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

        command = data['command']
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


@app.route('/api/server/stats', methods=['GET'])
def api_server_stats():
    try:
        if not server_manager.is_running():
            return jsonify({"success": False, "error": "Servidor no está corriendo"}), 400

        tps_resp = server_manager.send_command('tps')
        ram_bytes = psutil.Process(server_manager.process.pid).memory_info().rss if server_manager.process else 0
        cpu_percent = psutil.Process(server_manager.process.pid).cpu_percent(interval=0.5) if server_manager.process else 0

        import re
        tps_values = []
        m = re.findall(r'(?:§[a-z])?(\d+\.\d+)', tps_resp)
        if m:
            tps_values = [float(v) for v in m[:3]]

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

        if not version:
            return jsonify({"success": False, "error": "Falta 'version' en el body"}), 400

        result = server_manager.update_paper(active_server, version)
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
                return send_file(icon_path, mimetype='image/png')
            return jsonify({"success": False, "error": "No hay icono"}), 404

        elif request.method == 'POST':
            if 'file' not in request.files:
                return jsonify({"success": False, "error": "Falta archivo"}), 400

            f = request.files['file']
            if not f.filename.lower().endswith('.png'):
                return jsonify({"success": False, "error": "Solo archivos .png"}), 400

            f.save(icon_path)
            return jsonify({"success": True, "message": "Icono del servidor actualizado. Se requiere reinicio."})

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
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

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

# =============================================================================
# WEBSOCKET / SOCKETIO EVENTS
# =============================================================================

@socketio.on('connect')
def handle_connect():
    """Maneja conexión de cliente WebSocket."""
    try:
        print(f"[SOCKETIO] Cliente conectado: {request.sid}")
        emit('connected', {'message': 'Conectado al MineColab Panel'})
    except Exception as e:
        print(f"[SOCKETIO] Error en connect: {e}")


@socketio.on('disconnect')
def handle_disconnect():
    """Maneja desconexión de cliente WebSocket."""
    try:
        print(f"[SOCKETIO] Cliente desconectado: {request.sid}")
    except Exception as e:
        print(f"[SOCKETIO] Error en disconnect: {e}")


@socketio.on('ping')
def handle_ping(data):
    """Maneja ping desde el cliente."""
    try:
        emit('pong', {'ok': True, 'message': 'Pong desde servidor'})
    except Exception as e:
        print(f"[SOCKETIO] Error en ping: {e}")


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
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
