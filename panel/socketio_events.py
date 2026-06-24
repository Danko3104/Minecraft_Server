"""
Eventos WebSocket para comunicación en tiempo real con el panel.
Requiere autenticación JWT para todas las operaciones.
"""

import time
import threading
import os
import jwt


def _get_secret():
    key = os.environ.get('MINECOLAB_JWT_SECRET')
    if key:
        return key
    return None


def _verify_token_from_args(data):
    secret = _get_secret()
    if not secret:
        return False
    token = None
    if isinstance(data, dict):
        token = data.get('token')
    if not token:
        return False
    try:
        jwt.decode(token, secret, algorithms=["HS256"])
        return True
    except Exception:
        return False


def register_socketio_events(socketio):
    from flask import request
    from flask_socketio import emit, disconnect

    @socketio.on('connect')
    def handle_connect():
        sid = request.sid
        token = request.args.get('token', '')
        secret = _get_secret()
        authed = False
        if secret and token:
            try:
                jwt.decode(token, secret, algorithms=["HS256"])
                authed = True
            except Exception:
                pass
        if not authed and secret:
            print(f"[SOCKETIO] Conexión rechazada (sin token): {sid}")
            disconnect()
            return
        print(f"[SOCKETIO] Cliente conectado: {sid}")
        emit('connected', {'message': 'Conectado al MineColab Panel'})

    @socketio.on('disconnect')
    def handle_disconnect():
        print(f"[SOCKETIO] Cliente desconectado: {request.sid}")

    @socketio.on('ping')
    def handle_ping(data):
        emit('pong', {'ok': True, 'message': 'Pong desde servidor'})

    @socketio.on('console:subscribe')
    def handle_console_subscribe(data):
        if not _verify_token_from_args(data):
            emit('error', {'message': 'Token requerido'})
            return
        from panel.server_manager import server_manager
        sid = request.sid
        print(f"[SOCKETIO] Cliente {sid} suscrito a consola")
        emit('console:subscribed', {'ok': True})

        def stream_console():
            last_len = 0
            while True:
                try:
                    lines = server_manager.get_last_output()
                    if len(lines) > last_len:
                        new_lines = lines[last_len:]
                        last_len = len(lines)
                        socketio.emit('console:output', {'lines': new_lines}, to=sid)
                    time.sleep(1)
                except Exception:
                    break

        thread = threading.Thread(target=stream_console, daemon=True)
        thread.start()

    @socketio.on('server:status')
    def handle_server_status(data):
        if not _verify_token_from_args(data):
            emit('error', {'message': 'Token requerido'})
            return
        from panel.server_manager import server_manager
        from panel.drive import get_active_server
        running = server_manager.is_running()
        active = get_active_server()
        status = server_manager.get_status() if running else {}
        emit('server:status', {
            'running': running,
            'active_server': active,
            'uptime': status.get('uptime', 0),
            'pid': status.get('pid', None)
        })
