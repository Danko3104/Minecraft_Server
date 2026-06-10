import os
import json
import requests
from flask import Blueprint, jsonify, request

plugins_bp = Blueprint('plugins', __name__, url_prefix='/api/plugins')

MODRINTH_API = 'https://api.modrinth.com/v2'
HANGAR_API = 'https://hangar.papermc.io/api/v1'


def _get_plugins_dir() -> str:
    from panel.drive import DRIVE_PATH, get_active_server
    name = get_active_server()
    if not name:
        return None
    return os.path.join(DRIVE_PATH, name, 'plugins')


def search_modrinth(query: str, limit: int = 10) -> list:
    try:
        res = requests.get(f'{MODRINTH_API}/search', params={
            'query': query,
            'facets': json.dumps([['project_type:plugin']]),
            'limit': limit
        }, timeout=10)
        res.raise_for_status()
        data = res.json()
        results = []
        for hit in data.get('hits', []):
            results.append({
                'source': 'modrinth',
                'name': hit.get('title', 'Unknown'),
                'slug': hit.get('slug', ''),
                'description': hit.get('description', ''),
                'downloads': hit.get('downloads', 0),
                'author': hit.get('author', 'Unknown'),
                'icon_url': hit.get('icon_url', ''),
                'latest_version': hit.get('latest_version', ''),
                'url': f'https://modrinth.com/plugin/{hit.get("slug", "")}',
                'download_url': None  # Se obtiene al instalar
            })
        return results
    except Exception as e:
        print(f"[ERROR] search_modrinth: {e}")
        return []


def get_modrinth_version_download(slug: str) -> str:
    try:
        res = requests.get(f'{MODRINTH_API}/project/{slug}/version', params={'loaders': json.dumps(['paper']), 'game_versions': json.dumps(['1.21'])}, timeout=10)
        res.raise_for_status()
        versions = res.json()
        if versions:
            for file in versions[0].get('files', []):
                url = file.get('url', '')
                if url.endswith('.jar'):
                    return url
        return None
    except Exception as e:
        print(f"[ERROR] get_modrinth_version_download: {e}")
        return None


def search_hangar(query: str, limit: int = 10) -> list:
    try:
        res = requests.get(f'{HANGAR_API}/projects', params={
            'q': query,
            'limit': limit,
            'sort': 'downloads'
        }, timeout=10, headers={'Accept': 'application/json', 'User-Agent': 'MineColab/1.0'})
        res.raise_for_status()
        data = res.json()
        results = []
        for project in data.get('result', []):
            results.append({
                'source': 'hangar',
                'name': project.get('name', 'Unknown'),
                'slug': project.get('slug', ''),
                'description': project.get('description', ''),
                'downloads': project.get('downloads', 0),
                'author': project.get('author', ''),
                'icon_url': project.get('iconUrl', ''),
                'latest_version': project.get('latestVersion', ''),
                'url': f'https://hangar.papermc.io/{project.get("namespace", "")}',
                'download_url': None
            })
        return results
    except Exception as e:
        print(f"[ERROR] search_hangar: {e}")
        return []


@plugins_bp.route('/search', methods=['GET'])
def search_plugins():
    try:
        query = request.args.get('q', '').strip()
        source = request.args.get('source', 'all')
        limit = int(request.args.get('limit', 10))

        if not query:
            return jsonify({"success": False, "error": "Falta parámetro 'q'"}), 400

        results = []
        if source in ('all', 'modrinth'):
            results.extend(search_modrinth(query, limit))
        if source in ('all', 'hangar'):
            results.extend(search_hangar(query, limit))

        # Ordenar por descargas
        results.sort(key=lambda x: x.get('downloads', 0), reverse=True)
        results = results[:limit]

        return jsonify({"success": True, "results": results, "query": query})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@plugins_bp.route('/install', methods=['POST'])
def install_plugin():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Body vacío"}), 400

        source = data.get('source', '')
        slug = data.get('slug', '')
        name = data.get('name', slug)

        if not slug:
            return jsonify({"success": False, "error": "Falta 'slug'"}), 400

        plugins_dir = _get_plugins_dir()
        if not plugins_dir:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        os.makedirs(plugins_dir, exist_ok=True)

        # Obtener URL de descarga
        download_url = None
        if source == 'modrinth':
            download_url = get_modrinth_version_download(slug)
        elif source == 'hangar':
            try:
                res = requests.get(f'{HANGAR_API}/projects/{slug}/download', timeout=10, headers={'Accept': 'application/json', 'User-Agent': 'MineColab/1.0'}, allow_redirects=True)
                if res.ok:
                    download_url = res.url
            except Exception as e:
                return jsonify({"success": False, "error": f"Error obteniendo URL de descarga: {e}"}), 500

        if not download_url:
            return jsonify({"success": False, "error": "No se pudo obtener URL de descarga"}), 500

        # Descargar
        safe_name = name.replace(' ', '_').lower()
        jar_path = os.path.join(plugins_dir, f'{safe_name}.jar')

        try:
            res = requests.get(download_url, stream=True, timeout=60)
            res.raise_for_status()
            with open(jar_path, 'wb') as f:
                for chunk in res.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            return jsonify({"success": False, "error": f"Error al descargar: {e}"}), 500

        return jsonify({
            "success": True,
            "message": f"Plugin '{name}' instalado",
            "file": f'{safe_name}.jar'
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@plugins_bp.route('/installed', methods=['GET'])
def list_installed():
    try:
        plugins_dir = _get_plugins_dir()
        if not plugins_dir or not os.path.exists(plugins_dir):
            return jsonify({"success": True, "plugins": []})

        plugins = []
        for f in sorted(os.listdir(plugins_dir)):
            if f.endswith('.jar'):
                fpath = os.path.join(plugins_dir, f)
                size = os.path.getsize(fpath)
                mtime = os.path.getmtime(fpath)
                from datetime import datetime
                plugins.append({
                    "name": f.replace('.jar', ''),
                    "file": f,
                    "size_display": f"{size/1024:.0f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB",
                    "size_bytes": size,
                    "modified": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                })
        return jsonify({"success": True, "plugins": plugins})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@plugins_bp.route('/uninstall', methods=['POST'])
def uninstall_plugin():
    try:
        data = request.get_json()
        if not data or 'file' not in data:
            return jsonify({"success": False, "error": "Falta 'file'"}), 400

        plugins_dir = _get_plugins_dir()
        if not plugins_dir:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        jar_path = os.path.join(plugins_dir, data['file'])
        if not os.path.exists(jar_path):
            return jsonify({"success": False, "error": "Plugin no encontrado"}), 404

        os.remove(jar_path)
        return jsonify({"success": True, "message": f"Plugin '{data['file']}' eliminado"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
