import os
from flask import Blueprint, jsonify

tunnel_routes_bp = Blueprint('tunnel_routes', __name__, url_prefix='/api/tunnel')

TUNNEL_ADDRESS_FILE = '/tmp/tunnel_address.txt'

@tunnel_routes_bp.route('/address', methods=['GET'])
def api_tunnel_address():
    address = None
    if os.path.exists(TUNNEL_ADDRESS_FILE):
        with open(TUNNEL_ADDRESS_FILE) as f:
            content = f.read().strip()
            if content:
                address = content
    return jsonify({"address": address})
