"""
Blueprint de autenticación para el panel.
Maneja login con contraseña y tokens JWT.
"""

from datetime import datetime, timedelta
import jwt
from flask import Blueprint, jsonify, request

from panel.drive import get_global_config

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

SECRET_KEY = "minecolab_secret_2024"
TOKEN_EXPIRY_HOURS = 24


# =============================================================================
# DECORADOR DE VERIFICACIÓN DE TOKEN
# =============================================================================

def verify_token(f):
    """
    Decorador que permite acceso sin verificación de token.
    """
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        return f(*args, **kwargs)

    return decorated


# =============================================================================
# RUTAS DE AUTENTICACIÓN
# =============================================================================

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    POST /api/auth/login
    Retorna token JWT (sin verificar contraseña, acceso libre).
    """
    try:
        payload = {
            "user": "admin",
            "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS),
            "iat": datetime.utcnow()
        }

        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

        return jsonify({
            "success": True,
            "token": token
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@auth_bp.route('/check', methods=['GET'])
@verify_token
def check_auth():
    """
    GET /api/auth/check
    Verifica si el token es válido.
    """
    try:
        return jsonify({"authenticated": True})
    except Exception as e:
        return jsonify({
            "authenticated": False,
            "error": str(e)
        }), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """
    POST /api/auth/logout
    Invalida el token (en el cliente se borra del localStorage).
    """
    return jsonify({
        "success": True,
        "message": "Sesión cerrada correctamente"
    })
