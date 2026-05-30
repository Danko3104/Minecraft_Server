"""
Aplicación Flask principal del MineColab Panel.
Maneja las rutas HTTP y WebSocket para el panel de control.
"""

from datetime import datetime
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from panel.drive import (
    get_active_server,
    list_servers,
    set_active_server
)

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = 'minecolab-secret-key-change-in-production'

# CORS habilitado para todos los orígenes (necesario para Colab)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# SocketIO con async_mode='threading'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

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
    Ruta principal - retorna estado del panel.
    Más adelante aquí irá el HTML completo.
    """
    try:
        return jsonify({"status": "MineColab Panel funcionando"})
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
            "minecraft_running": False,  # Por ahora siempre false
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
