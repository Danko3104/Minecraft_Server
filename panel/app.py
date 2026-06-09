"""
Aplicación Flask principal del MineColab Panel.
Maneja las rutas HTTP y WebSocket para el panel de control.
"""

from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
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
