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
    Decorador que verifica el token JWT en el header Authorization.
    """
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # Leer token del header Authorization: Bearer {token}
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]  # Quitar 'Bearer '

        if not token:
            return jsonify({"error": "No autorizado. Token faltante."}), 401

        try:
            # Verificar token
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado. Inicia sesión nuevamente."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido."}), 401

    return decorated


# =============================================================================
# RUTAS DE AUTENTICACIÓN
# =============================================================================

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    POST /api/auth/login
    Recibe {password} y retorna token JWT si es correcto.
    """
    try:
        data = request.get_json()

        if not data or 'password' not in data:
            return jsonify({
                "success": False,
                "error": "Falta 'password' en el body"
            }), 400

        password = data['password']

        # Obtener contraseña desde configuración global
        config = get_global_config()
        stored_password = config.get('panel_password', 'minecolab2024')

        # Comparar contraseñas
        if password != stored_password:
            return jsonify({
                "success": False,
                "error": "Contraseña incorrecta"
            }), 401

        # Generar token JWT
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
