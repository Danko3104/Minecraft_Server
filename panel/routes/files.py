import os
from flask import Blueprint, jsonify, request, send_file, Response

files_bp = Blueprint('files', __name__, url_prefix='/api/files')

SAFE_BASES = {}


def _get_bases(server_name: str) -> list:
    from panel.drive import DRIVE_PATH
    base = os.path.join(DRIVE_PATH, server_name)
    world = os.path.join(base, 'world')
    SAFE_BASES[server_name] = [os.path.normpath(base)]
    if os.path.isdir(world):
        SAFE_BASES[server_name].append(os.path.normpath(world))
    return SAFE_BASES[server_name]


def _resolve(server_name: str, rel_path: str) -> str:
    bases = _get_bases(server_name)
    full = os.path.normpath(os.path.join(bases[0], rel_path))
    for b in bases:
        if full.startswith(b):
            return full
    return None


@files_bp.route('/list', methods=['GET'])
def list_files():
    try:
        from panel.drive import get_active_server, DRIVE_PATH
        server_name = get_active_server()
        if not server_name:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        rel_path = request.args.get('path', '')
        if not rel_path:
            world = os.path.join(DRIVE_PATH, server_name, 'world')
            if os.path.isdir(world):
                rel_path = 'world'
        full = _resolve(server_name, rel_path)
        if not full:
            return jsonify({"success": False, "error": "Acceso denegado"}), 403
        if not os.path.exists(full):
            return jsonify({"success": False, "error": "Ruta no encontrada"}), 404
        if not os.path.isdir(full):
            return jsonify({"success": False, "error": "No es un directorio"}), 400

        entries = []
        for name in sorted(os.listdir(full)):
            fpath = os.path.join(full, name)
            is_dir = os.path.isdir(fpath)
            size = 0 if is_dir else os.path.getsize(fpath)
            mtime = os.path.getmtime(fpath)
            from datetime import datetime
            entries.append({
                "name": name,
                "is_dir": is_dir,
                "size": size,
                "size_display": f"{size/1024:.0f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB" if not is_dir else "",
                "modified": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            })

        return jsonify({
            "success": True,
            "path": rel_path or "/",
            "parent": os.path.dirname(rel_path) if rel_path else None,
            "entries": entries
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@files_bp.route('/download', methods=['GET'])
def download_file():
    try:
        from panel.drive import get_active_server
        server_name = get_active_server()
        if not server_name:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        rel_path = request.args.get('path', '')
        full = _resolve(server_name, rel_path)
        if not full:
            return jsonify({"success": False, "error": "Acceso denegado"}), 403
        if not os.path.isfile(full):
            return jsonify({"success": False, "error": "No es un archivo"}), 400

        return send_file(full, as_attachment=True, download_name=os.path.basename(full))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@files_bp.route('/read', methods=['GET'])
def read_file():
    try:
        from panel.drive import get_active_server
        server_name = get_active_server()
        if not server_name:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        rel_path = request.args.get('path', '')
        full = _resolve(server_name, rel_path)
        if not full:
            return jsonify({"success": False, "error": "Acceso denegado"}), 403
        if not os.path.isfile(full):
            return jsonify({"success": False, "error": "No es un archivo"}), 400

        size = os.path.getsize(full)
        if size > 5 * 1024 * 1024:
            return jsonify({"success": False, "error": "Archivo demasiado grande (>5MB)"}), 400

        try:
            with open(full, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception:
            return jsonify({"success": False, "error": "No se puede leer como texto"}), 400

        return jsonify({
            "success": True,
            "content": content,
            "name": os.path.basename(full),
            "path": rel_path,
            "size": size
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@files_bp.route('/write', methods=['PUT'])
def write_file():
    try:
        from panel.drive import get_active_server
        server_name = get_active_server()
        if not server_name:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        data = request.get_json()
        if not data or 'path' not in data or 'content' not in data:
            return jsonify({"success": False, "error": "Faltan 'path' y 'content'"}), 400

        full = _resolve(server_name, data['path'])
        if not full:
            return jsonify({"success": False, "error": "Acceso denegado"}), 403

        with open(full, 'w', encoding='utf-8') as f:
            f.write(data['content'])

        return jsonify({"success": True, "message": "Archivo guardado"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@files_bp.route('/upload', methods=['POST'])
def upload_file():
    try:
        from panel.drive import get_active_server
        server_name = get_active_server()
        if not server_name:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        current_path = request.form.get('path', '')
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "Falta archivo"}), 400

        f = request.files['file']
        full = _resolve(server_name, os.path.join(current_path, f.filename))
        if not full:
            return jsonify({"success": False, "error": "Acceso denegado"}), 403

        os.makedirs(os.path.dirname(full), exist_ok=True)
        f.save(full)

        return jsonify({"success": True, "message": f"Archivo subido: {f.filename}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@files_bp.route('/delete', methods=['POST'])
def delete_item():
    try:
        from panel.drive import get_active_server
        server_name = get_active_server()
        if not server_name:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({"success": False, "error": "Falta 'path'"}), 400

        full = _resolve(server_name, data['path'])
        if not full:
            return jsonify({"success": False, "error": "Acceso denegado"}), 403
        if not os.path.exists(full):
            return jsonify({"success": False, "error": "No encontrado"}), 404

        if os.path.isdir(full):
            import shutil
            shutil.rmtree(full)
            msg = "Carpeta eliminada"
        else:
            os.remove(full)
            msg = "Archivo eliminado"

        return jsonify({"success": True, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@files_bp.route('/mkdir', methods=['POST'])
def mkdir():
    try:
        from panel.drive import get_active_server
        server_name = get_active_server()
        if not server_name:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({"success": False, "error": "Falta 'path'"}), 400

        full = _resolve(server_name, data['path'])
        if not full:
            return jsonify({"success": False, "error": "Acceso denegado"}), 403

        os.makedirs(full, exist_ok=True)
        return jsonify({"success": True, "message": "Carpeta creada"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
