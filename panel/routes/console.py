import re
from flask import Blueprint, jsonify, request

console_bp = Blueprint('console', __name__, url_prefix='/api/console')


@console_bp.route('/output', methods=['GET'])
def console_output():
    try:
        from panel.server_manager import server_manager
        lines = server_manager.get_last_output()
        return jsonify({"success": True, "lines": lines})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@console_bp.route('/command', methods=['POST'])
def console_command():
    try:
        data = request.get_json()
        if not data or 'command' not in data:
            return jsonify({"success": False, "error": "Falta 'command' en el body"}), 400

        command = data['command']

        from panel.server_manager import server_manager
        from panel.rcon import RCONClient
        from panel.drive import get_active_server

        active = get_active_server()
        if not active:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        try:
            rcon = RCONClient()
            if rcon.connect():
                response = rcon.send_command(command)
                rcon.disconnect()
                return jsonify({"success": True, "response": response, "via": "rcon"})
        except Exception:
            pass

        response = server_manager.send_command(command)
        return jsonify({"success": True, "response": response, "via": "stdin"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@console_bp.route('/players', methods=['GET'])
def console_players():
    try:
        from panel.server_manager import server_manager
        from panel.rcon import RCONClient

        resp = None
        try:
            rcon = RCONClient()
            if rcon.connect():
                resp = rcon.send_command('list')
                rcon.disconnect()
        except Exception:
            pass

        if not resp:
            resp = server_manager.send_command('list')

        players = []
        max_players = 20

        m = re.search(r'There are (\d+) of .*? (\d+) players? online:\s*(.*)', resp)
        if m:
            count = int(m.group(1))
            mx = int(m.group(2))
            max_players = mx
            names_str = m.group(3).strip()
            if names_str and names_str != 'There are no':
                names = [n.strip() for n in names_str.split(',') if n.strip()]
                for name in names:
                    players.append({"name": name, "uuid": None})

        if not players and server_manager.is_running():
            for line in reversed(server_manager.get_last_output()):
                m = re.search(r'There are (\d+) of .*? (\d+) players? online:\s*(.*)', line)
                if m:
                    names_str = m.group(3).strip()
                    if names_str and names_str != 'There are no':
                        names = [n.strip() for n in names_str.split(',') if n.strip()]
                        for name in names:
                            players.append({"name": name, "uuid": None})
                    max_players = int(m.group(2))
                    break

        return jsonify({
            "success": True,
            "players": players,
            "max": max_players,
            "count": len(players)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
