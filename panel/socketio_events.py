"""
Eventos WebSocket para comunicación en tiempo real con el panel.
"""

import time
import threading


def register_socketio_events(socketio):
    from flask import request
    from flask_socketio import emit

    @socketio.on('connect')
    def handle_connect():
        print(f"[SOCKETIO] Cliente conectado: {request.sid}")
        emit('connected', {'message': 'Conectado al MineColab Panel'})

    @socketio.on('disconnect')
    def handle_disconnect():
        print(f"[SOCKETIO] Cliente desconectado: {request.sid}")

    @socketio.on('ping')
    def handle_ping(data):
        emit('pong', {'ok': True, 'message': 'Pong desde servidor'})

    @socketio.on('console:subscribe')
    def handle_console_subscribe(data):
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
