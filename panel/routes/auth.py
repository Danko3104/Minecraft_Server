"""
Blueprint de autenticación para el panel.
Maneja login con contraseña y tokens JWT.
"""

import os
from datetime import datetime, timedelta
from functools import wraps
import jwt
from flask import Blueprint, jsonify, request

from panel.drive import get_global_config

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

SECRET_KEY = os.environ.get('MINECOLAB_JWT_SECRET', 'minecolab-secret-key-change-in-production')
TOKEN_EXPIRY_HOURS = 24


def check_token():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False
    token = auth_header[7:]
    try:
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return True
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False


def verify_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_token():
            return jsonify({"success": False, "error": "Token requerido o inválido"}), 401
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data or 'password' not in data:
            return jsonify({"success": False, "error": "Falta 'password' en el body"}), 400

        config = get_global_config()
        expected = config.get('panel_password', 'minecolab2024')

        if data['password'] != expected:
            return jsonify({"success": False, "error": "Contraseña incorrecta"}), 401

        payload = {
            "user": "admin",
            "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS),
            "iat": datetime.utcnow()
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        return jsonify({"success": True, "token": token})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@auth_bp.route('/check', methods=['GET'])
@verify_token
def check_auth():
    try:
        return jsonify({"authenticated": True})
    except Exception as e:
        return jsonify({"authenticated": False, "error": str(e)}), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    return jsonify({
        "success": True,
        "message": "Sesión cerrada correctamente"
    })
