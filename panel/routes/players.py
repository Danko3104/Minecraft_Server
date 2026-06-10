import os
import json
from flask import Blueprint, jsonify, request

players_bp = Blueprint('players', __name__, url_prefix='/api/players')

def _get_command(command: str) -> str:
    from panel.server_manager import server_manager
    return server_manager.send_command(command)

def _get_active_server_path() -> str:
    from panel.drive import get_active_server, DRIVE_PATH
    name = get_active_server()
    if not name:
        return None
    return os.path.join(DRIVE_PATH, name)

@players_bp.route('', methods=['GET'])
def api_players():
    try:
        resp = _get_command('list')
        players = []
        max_players = 20

        def _parse_player_list(text):
            import re
            m = re.search(r'There are (\d+) of .*? (\d+) players? online:\s*(.*)', text)
            if m:
                count = int(m.group(1))
                mx = int(m.group(2))
                names = m.group(3).strip()
                lst = []
                if names and names != 'There are no':
                    lst = [n.strip() for n in names.split(',') if n.strip()]
                return lst, mx
            return None, None

        parsed, mx = _parse_player_list(resp)
        if parsed is not None:
            players = parsed
            max_players = mx
        else:
            from panel.server_manager import server_manager
            import time
            # Esperar hasta 2s a que aparezca el output del comando 'list' en stdout
            for _ in range(10):
                for line in reversed(server_manager.get_last_output()):
                    parsed, mx = _parse_player_list(line)
                    if parsed is not None:
                        players = parsed
                        max_players = mx
                        return jsonify({"players": players, "max": max_players, "raw": resp})
                time.sleep(0.2)

        return jsonify({"players": players, "max": max_players, "raw": resp})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@players_bp.route('/kick', methods=['POST'])
def api_player_kick():
    try:
        data = request.get_json()
        player = data.get('player', '')
        reason = data.get('reason', '')
        cmd = f'kick {player} {reason}'.strip() if reason else f'kick {player}'
        resp = _get_command(cmd)
        return jsonify({"success": True, "message": f"Jugador {player} expulsado", "response": resp})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@players_bp.route('/ban', methods=['POST'])
def api_player_ban():
    try:
        data = request.get_json()
        player = data.get('player', '')
        reason = data.get('reason', '')
        cmd = f'ban {player} {reason}'.strip() if reason else f'ban {player}'
        resp = _get_command(cmd)
        return jsonify({"success": True, "message": f"Jugador {player} baneado", "response": resp})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@players_bp.route('/unban', methods=['POST'])
def api_player_unban():
    try:
        data = request.get_json()
        player = data.get('player', '')
        resp = _get_command(f'pardon {player}')
        return jsonify({"success": True, "message": f"Jugador {player} desbaneado", "response": resp})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@players_bp.route('/op', methods=['POST'])
def api_player_op():
    try:
        data = request.get_json()
        player = data.get('player', '')
        resp = _get_command(f'op {player}')
        return jsonify({"success": True, "message": f"Jugador {player} ahora es OP", "response": resp})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@players_bp.route('/say', methods=['POST'])
def api_player_say():
    try:
        data = request.get_json()
        message = data.get('message', '')
        if not message:
            return jsonify({"success": False, "error": "Mensaje vacío"}), 400
        resp = _get_command(f'say {message}')
        return jsonify({"success": True, "message": "Mensaje enviado", "response": resp})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@players_bp.route('/whitelist', methods=['GET'])
def api_whitelist():
    try:
        server_path = _get_active_server_path()
        whitelist = []
        if server_path:
            wl_path = os.path.join(server_path, 'whitelist.json')
            if os.path.exists(wl_path):
                with open(wl_path, 'r') as f:
                    data = json.load(f)
                whitelist = [entry.get('name', '?') for entry in data if isinstance(entry, dict)]
        return jsonify({"whitelist": whitelist})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@players_bp.route('/whitelist/add', methods=['POST'])
def api_whitelist_add():
    try:
        data = request.get_json()
        player = data.get('player', '')
        if not player:
            return jsonify({"success": False, "error": "Nombre de jugador requerido"}), 400
        from panel.server_manager import server_manager
        if not server_manager.is_running():
            return jsonify({"success": False, "error": "El servidor debe estar encendido para modificar la whitelist"}), 400
        resp = _get_command(f'whitelist add {player}')
        return jsonify({"success": True, "message": f"{player} agregado a la whitelist"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@players_bp.route('/whitelist/remove', methods=['POST'])
def api_whitelist_remove():
    try:
        data = request.get_json()
        player = data.get('player', '')
        if not player:
            return jsonify({"success": False, "error": "Nombre de jugador requerido"}), 400
        from panel.server_manager import server_manager
        if not server_manager.is_running():
            return jsonify({"success": False, "error": "El servidor debe estar encendido para modificar la whitelist"}), 400
        resp = _get_command(f'whitelist remove {player}')
        return jsonify({"success": True, "message": f"{player} quitado de la whitelist"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@players_bp.route('/banned', methods=['GET'])
def api_players_banned():
    try:
        resp = _get_command('banlist')
        banned = []
        if resp:
            import re
            m = re.search(r'There are (\d+) banned players?:\s*(.*)', resp)
            if m:
                names = m.group(2).strip()
                if names and names != 'There are no banned players':
                    banned = [n.strip() for n in names.split(',') if n.strip()]
        return jsonify({"banned": banned, "raw": resp})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
