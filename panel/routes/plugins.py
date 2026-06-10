import os
import json
import requests
from flask import Blueprint, jsonify, request

plugins_bp = Blueprint('plugins', __name__, url_prefix='/api/plugins')

MODRINTH_API = 'https://api.modrinth.com/v2'
HANGAR_API = 'https://hangar.papermc.io/api/v1'


def _get_server_version() -> str:
    from panel.server_manager import server_manager
    from panel.drive import get_active_server
    name = get_active_server()
    if not name:
        return None
    return server_manager.get_paper_version(name)


def _get_server_major_version() -> str:
    version = _get_server_version()
    if not version:
        return '1.21'
    parts = version.split('.')
    return f'{parts[0]}.{parts[1]}' if len(parts) >= 2 else '1.21'


def _get_server_full_version() -> str:
    version = _get_server_version()
    return version if version else '1.21'


def _get_plugins_dir() -> str:
    from panel.drive import DRIVE_PATH, get_active_server
    name = get_active_server()
    if not name:
        return None
    return os.path.join(DRIVE_PATH, name, 'plugins')


def _installed_slugs() -> set:
    """Retorna set de slugs (nombres de archivo sin .jar) ya instalados."""
    d = _get_plugins_dir()
    if not d or not os.path.exists(d):
        return set()
    return {f.replace('.jar', '') for f in os.listdir(d) if f.endswith('.jar')}


def _download_jar(download_url: str, jar_path: str) -> None:
    res = requests.get(download_url, stream=True, timeout=60)
    res.raise_for_status()
    with open(jar_path, 'wb') as f:
        for chunk in res.iter_content(chunk_size=8192):
            f.write(chunk)


def _lookup_project_slug(project_id: str) -> str:
    """Convierte un UUID de proyecto Modrinth a slug."""
    try:
        res = requests.get(f'{MODRINTH_API}/project/{project_id}', timeout=10)
        res.raise_for_status()
        return res.json().get('slug', project_id)
    except Exception:
        return project_id


def _find_compatible_version(versions: list, major_version: str) -> dict:
    for v in versions:
        gv = v.get('game_versions', [])
        for g in gv:
            if g == major_version or g.startswith(major_version + '.'):
                return v
    if versions:
        return versions[0]
    return None


def get_modrinth_download(slug: str, major_version: str) -> dict:
    """
    Retorna {url, version_name, game_versions, supported, error, dependencies}.
    dependencies es una lista de dicts {project_id, dependency_type}.
    """
    try:
        res = requests.get(
            f'{MODRINTH_API}/project/{slug}/version',
            params={'loaders': json.dumps(['paper'])},
            timeout=10
        )
        res.raise_for_status()
        versions = res.json()

        if not versions:
            return {'url': None, 'version_name': None, 'supported': False,
                    'error': 'No hay versiones disponibles', 'dependencies': []}

        compatible = _find_compatible_version(versions, major_version)

        if not compatible:
            return {
                'url': None, 'version_name': None, 'supported': False,
                'error': f'No hay versión compatible con {major_version}. '
                         f'Última disponible: {versions[0].get("name", "?")} '
                         f'(para Minecraft {", ".join(versions[0].get("game_versions", []))})',
                'dependencies': []
            }

        jar_url = None
        for f in compatible.get('files', []):
            if f.get('url', '').endswith('.jar'):
                jar_url = f['url']
                break

        return {
            'url': jar_url,
            'version_name': compatible.get('name', 'Unknown'),
            'game_versions': compatible.get('game_versions', []),
            'supported': jar_url is not None,
            'error': None if jar_url else 'No se encontró archivo JAR',
            'dependencies': compatible.get('dependencies', [])
        }
    except Exception as e:
        return {'url': None, 'version_name': None, 'supported': False,
                'error': str(e), 'dependencies': []}


def _install_with_deps(slug: str, major_version: str, plugins_dir: str,
                       installed: set, depth: int = 0) -> dict:
    """
    Instala un plugin y sus dependencias required/embedded recursivamente.
    Retorna {success, message, installed_files, skipped_deps, errors}.
    depth previene recursión infinita (máx 5 niveles).
    """
    result = {'installed_files': [], 'skipped_deps': [], 'errors': []}

    if slug in installed:
        result['skipped_deps'].append(f'{slug} (ya instalado)')
        return result

    if depth > 5:
        result['errors'].append(f'{slug}: demasiados niveles de dependencia')
        return result

    info = get_modrinth_download(slug, major_version)
    if not info['supported']:
        result['errors'].append(f'{slug}: {info.get("error", "No compatible")}')
        return result

    safe_name = slug.replace(' ', '_').lower()
    jar_path = os.path.join(plugins_dir, f'{safe_name}.jar')

    try:
        _download_jar(info['url'], jar_path)
        installed.add(slug)
        result['installed_files'].append(safe_name)
    except Exception as e:
        result['errors'].append(f'{slug}: error al descargar - {e}')
        return result

    # Procesar dependencias REQUIRED (embedded viene dentro del JAR)
    for dep in info.get('dependencies', []):
        dep_type = dep.get('dependency_type', '')
        if dep_type != 'required':
            continue
        dep_id = dep.get('project_id', '')
        if not dep_id:
            continue
        dep_slug = _lookup_project_slug(dep_id)

        sub = _install_with_deps(dep_slug, major_version, plugins_dir,
                                 installed, depth + 1)
        result['installed_files'].extend(sub['installed_files'])
        result['skipped_deps'].extend(sub['skipped_deps'])
        result['errors'].extend(sub['errors'])

    return result


def search_modrinth(query: str, limit: int = 10) -> list:
    try:
        res = requests.get(f'{MODRINTH_API}/search', params={
            'query': query,
            'facets': json.dumps([['project_type:plugin']]),
            'limit': limit
        }, timeout=10)
        res.raise_for_status()
        data = res.json()
        major = _get_server_major_version()
        results = []
        for hit in data.get('hits', []):
            versions_list = hit.get('versions', [])
            is_compatible = major in versions_list or any(
                v.startswith(major + '.') for v in versions_list)
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
                'compatible': is_compatible,
                'download_url': None
            })
        return results
    except Exception as e:
        print(f"[ERROR] search_modrinth: {e}")
        return []


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
                'compatible': True,
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

        results.sort(key=lambda x: x.get('downloads', 0), reverse=True)
        results = results[:limit]

        return jsonify({
            "success": True,
            "results": results,
            "query": query,
            "server_version": _get_server_full_version()
        })
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
        major_version = _get_server_major_version()

        if source == 'modrinth':
            installed = _installed_slugs()
            dep_result = _install_with_deps(slug, major_version, plugins_dir, installed)

            if not dep_result['installed_files'] and dep_result['errors']:
                return jsonify({
                    "success": False,
                    "error": dep_result['errors'][0],
                    "server_version": _get_server_full_version()
                }), 400

            msg = f"Plugin '{name}' instalado"
            if dep_result['skipped_deps']:
                msg += " (deps ya presentes)"
            if dep_result['errors']:
                msg += f" | Errores: {'; '.join(dep_result['errors'])}"

            return jsonify({
                "success": True,
                "message": msg,
                "installed": dep_result['installed_files'],
                "warnings": dep_result['errors']
            })
        elif source == 'hangar':
            download_url = None
            try:
                res = requests.get(
                    f'{HANGAR_API}/projects/{slug}/download',
                    timeout=10,
                    headers={'Accept': 'application/json', 'User-Agent': 'MineColab/1.0'},
                    allow_redirects=True
                )
                if res.ok:
                    download_url = res.url
            except Exception as e:
                return jsonify({"success": False, "error": f"Error: {e}"}), 500

            if not download_url:
                return jsonify({"success": False, "error": "No se pudo obtener URL de descarga"}), 500

            safe_name = name.replace(' ', '_').lower()
            jar_path = os.path.join(plugins_dir, f'{safe_name}.jar')

            try:
                _download_jar(download_url, jar_path)
            except Exception as e:
                return jsonify({"success": False, "error": f"Error al descargar: {e}"}), 500

            return jsonify({
                "success": True,
                "message": f"Plugin '{name}' instalado",
                "file": f'{safe_name}.jar'
            })
        else:
            return jsonify({"success": False, "error": f"Fuente desconocida: {source}"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@plugins_bp.route('/installed', methods=['GET'])
def list_installed():
    try:
        plugins_dir = _get_plugins_dir()
        if not plugins_dir or not os.path.exists(plugins_dir):
            return jsonify({"success": True, "plugins": [], "server_version": _get_server_full_version()})

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
        return jsonify({"success": True, "plugins": plugins, "server_version": _get_server_full_version()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _get_plugin_updates() -> dict:
    plugins_dir = _get_plugins_dir()
    if not plugins_dir or not os.path.exists(plugins_dir):
        return {"success": True, "updates": []}

    major = _get_server_major_version()
    updates = []

    for f in sorted(os.listdir(plugins_dir)):
        if not f.endswith('.jar'):
            continue
        plugin_name = f.replace('.jar', '')

        res = requests.get(
            f'{MODRINTH_API}/search',
            params={'query': plugin_name, 'facets': json.dumps([['project_type:plugin']]), 'limit': 1},
            timeout=10
        )
        if not res.ok:
            continue
        data = res.json()
        hits = data.get('hits', [])
        if not hits:
            continue

        slug = hits[0].get('slug', '')
        info = get_modrinth_download(slug, major)

        if info['supported'] and info['url']:
            updates.append({
                'name': plugin_name,
                'slug': slug,
                'current_file': f,
                'latest_version': info['version_name'],
                'download_url': info['url']
            })

    return {"success": True, "updates": updates, "server_version": _get_server_full_version()}


@plugins_bp.route('/check-updates', methods=['POST'])
def check_plugin_updates():
    try:
        result = _get_plugin_updates()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@plugins_bp.route('/update-all', methods=['POST'])
def update_all_plugins():
    try:
        plugins_dir = _get_plugins_dir()
        if not plugins_dir:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        result = _get_plugin_updates()
        if not result.get('success'):
            return jsonify(result), 500

        updated = []
        errors = []

        for plugin in result.get('updates', []):
            try:
                jar_path = os.path.join(plugins_dir, plugin['current_file'])
                _download_jar(plugin['download_url'], jar_path)
                updated.append(plugin['name'])
            except Exception as e:
                errors.append(f"{plugin['name']}: {e}")

        return jsonify({
            "success": True,
            "updated": updated,
            "errors": errors
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@plugins_bp.route('/upload', methods=['POST'])
def upload_plugin():
    try:
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "Falta archivo"}), 400

        f = request.files['file']
        if not f.filename.endswith('.jar'):
            return jsonify({"success": False, "error": "Solo archivos .jar"}), 400

        plugins_dir = _get_plugins_dir()
        if not plugins_dir:
            return jsonify({"success": False, "error": "No hay servidor activo"}), 400

        os.makedirs(plugins_dir, exist_ok=True)
        dest = os.path.join(plugins_dir, f.filename)
        f.save(dest)

        return jsonify({
            "success": True,
            "message": f"Plugin '{f.filename}' subido"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
