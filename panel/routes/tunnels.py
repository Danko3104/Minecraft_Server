from flask import Blueprint, jsonify

tunnels_bp = Blueprint('tunnels', __name__, url_prefix='/api/tunnels')


@tunnels_bp.route('/status', methods=['GET'])
def api_tunnel_status():
    return jsonify({
        "configured": True,
        "address": "minecraftcito.serveo.net:25565",
        "running": True
    })
