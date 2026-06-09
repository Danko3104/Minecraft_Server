import subprocess
from flask import Blueprint, jsonify, request
from panel.tunnel import start_minecraft_tunnel, _is_localtonet_running
from panel.drive import get_global_config, save_global_config
from panel.routes.auth import verify_token

tunnels_bp = Blueprint('tunnels', __name__, url_prefix='/api/tunnels')


@tunnels_bp.route('/localtonet/save-token', methods=['POST'])
@verify_token
def api_localtonet_save_token():
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "Faltan datos en el body"
            }), 400

        authtoken = data.get('authtoken', '')
        address = data.get('address', '')

        if not authtoken:
            return jsonify({
                "success": False,
                "error": "authtoken no puede estar vac\u00edo"
            }), 400

        if not address:
            return jsonify({
                "success": False,
                "error": "address no puede estar vac\u00edo"
            }), 400

        config = get_global_config()
        if 'localtonet_proxy' not in config:
            config['localtonet_proxy'] = {}
        config['localtonet_proxy']['authtoken'] = authtoken
        config['localtonet_proxy']['address'] = address
        save_global_config(config)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@tunnels_bp.route('/localtonet/connect', methods=['POST'])
@verify_token
def api_localtonet_connect():
    try:
        config = get_global_config()
        localtonet_proxy = config.get('localtonet_proxy', {})
        authtoken = localtonet_proxy.get('authtoken', '')
        address = localtonet_proxy.get('address', '')

        if not authtoken:
            return jsonify({
                "success": False,
                "error": "No hay token configurado"
            }), 400

        if not address:
            return jsonify({
                "success": False,
                "error": "No hay dirección configurada"
            }), 400

        result = start_minecraft_tunnel(
            tunnel_service='localtonet',
            server_config=config,
            server_type=''
        )

        if result.get("status") == "running":
            return jsonify({
                "success": True,
                "address": address
            })

        return jsonify({
            "success": False,
            "error": result.get("error", "No se pudo conectar")
        }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@tunnels_bp.route('/localtonet/status', methods=['GET'])
def api_localtonet_status():
    try:
        config = get_global_config()
        localtonet_proxy = config.get('localtonet_proxy', {})

        return jsonify({
            "configured": bool(localtonet_proxy.get('authtoken', '')),
            "address": localtonet_proxy.get('address', ''),
            "running": _is_localtonet_running()
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
