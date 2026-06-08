import subprocess
from flask import Blueprint, jsonify
from panel.tunnel import _wait_for_secret_key_after_claim, get_playit_tunnel_address, start_minecraft_tunnel
from panel.drive import get_global_config, save_global_config
from panel.routes.auth import verify_token

tunnels_bp = Blueprint('tunnels', __name__, url_prefix='/api/tunnels')


@tunnels_bp.route('/playit/start-claim', methods=['POST'])
@verify_token
def api_playit_start_claim():
    try:
        result = start_minecraft_tunnel(tunnel_service='playit')
        if result.get("status") == "needs_claim":
            return jsonify({
                "success": True,
                "claim_code": result["claim_code"]
            })
        return jsonify({
            "success": False,
            "error": result.get("error", "No se pudo iniciar el claim")
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@tunnels_bp.route('/playit/confirm-claim', methods=['POST'])
@verify_token
def api_playit_confirm_claim():
    try:
        result = _wait_for_secret_key_after_claim()
        if not result.get("success"):
            return jsonify({
                "success": False,
                "error": result.get("error", "Failed to get secret key")
            }), 500

        secret_key = result["secret_key"]

        config = get_global_config()
        if 'playit_proxy' not in config:
            config['playit_proxy'] = {}
        config['playit_proxy']['secretkey'] = secret_key

        address = get_playit_tunnel_address()
        config['playit_proxy']['address'] = address
        save_global_config(config)

        return jsonify({
            "success": True,
            "address": address
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@tunnels_bp.route('/playit/status', methods=['GET'])
def api_playit_status():
    try:
        config = get_global_config()
        playit_proxy = config.get('playit_proxy', {})

        result = subprocess.run(['pgrep', 'playit'], capture_output=True, text=True)
        running = result.returncode == 0 and result.stdout.strip() != ""

        return jsonify({
            "configured": bool(playit_proxy.get('secretkey', '')),
            "address": playit_proxy.get('address', ''),
            "running": running
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@tunnels_bp.route('/playit/reset', methods=['POST'])
@verify_token
def api_playit_reset():
    try:
        config = get_global_config()
        if 'playit_proxy' not in config:
            config['playit_proxy'] = {}
        config['playit_proxy']['secretkey'] = ''
        config['playit_proxy']['address'] = ''
        save_global_config(config)

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
