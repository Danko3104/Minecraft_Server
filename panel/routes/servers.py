"""
Blueprint para gestión de servidores.
Maneja crear, listar, eliminar e instalar servidores.
"""

import os
import re
import json
import time
import threading
import subprocess
import requests
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
from flask import Blueprint, jsonify, request

from panel.drive import (
    DRIVE_PATH,
    get_global_config,
    save_global_config,
    get_server_config,
    save_server_config,
    list_servers,
    get_active_server,
    set_active_server,
    server_exists
)

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

servers_bp = Blueprint('servers', __name__, url_prefix='/api')

# Tipos de servidor soportados
SERVER_TYPES = [
    'Vanilla', 'Snapshot', 'Paper', 'Purpur', 'Mohist',
    'Arclight', 'Velocity', 'Banner', 'Fabric', 'Folia',
    'Forge', 'Neoforge', 'Bedrock', 'Crucible', 'Magma',
    'Ketting', 'Cardboard', 'Custom'
]

# Versiones fallback para tipos sin API pública
FALLBACK_VERSIONS = ['1.20.4', '1.20.1', '1.19.4', '1.19.2', '1.18.2', '1.16.5']

# Estado de instalación por servidor
install_status: Dict[str, Dict] = {}


# =============================================================================
# FUNCIONES DE ORDENAMIENTO
# =============================================================================

def sort_versions(versions: list) -> list:
    """
    Ordena versiones de Minecraft de más nueva a más vieja.
    Maneja versiones como: 1.20.4, 1.20, 1.9, 1.8.9, 24w14a
    """
    def version_key(v):
        try:
            # Ignorar snapshots (contienen letras) y ponerlos al final
            if any(c.isalpha() for c in v):
                return (0, 0, 0, v)
            parts = str(v).split('.')
            return (
                int(parts[0]) if len(parts) > 0 else 0,
                int(parts[1]) if len(parts) > 1 else 0,
                int(parts[2]) if len(parts) > 2 else 0,
                v
            )
        except (ValueError, AttributeError):
            return (0, 0, 0, v)

    return sorted(versions, key=version_key, reverse=True)


# =============================================================================
# FUNCIONES DE API PARA VERSIONES
# =============================================================================

def get_paper_versions() -> List[str]:
    """Obtiene versiones de PaperMC."""
    try:
        response = requests.get(
            'https://api.papermc.io/v2/projects/paper',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        versions = data.get('versions', [])
        return sort_versions(versions)
    except Exception as e:
        print(f"[ERROR] get_paper_versions: {e}")
        return []


def get_purpur_versions() -> List[str]:
    """Obtiene versiones de Purpur."""
    try:
        response = requests.get(
            'https://api.purpurmc.org/v2/purpur',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        versions = data.get('versions', [])
        return sort_versions(versions)
    except Exception as e:
        print(f"[ERROR] get_purpur_versions: {e}")
        return []


def get_fabric_versions() -> List[str]:
    """Obtiene versiones estables de Fabric."""
    try:
        response = requests.get(
            'https://meta.fabricmc.net/v2/versions/game',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        # Filtrar solo estables y extraer campo version
        stable = [v['version'] for v in data if v.get('stable', False)]
        return sort_versions(stable)
    except Exception as e:
        print(f"[ERROR] get_fabric_versions: {e}")
        return []


def get_vanilla_versions() -> List[str]:
    """Obtiene versiones release de Vanilla."""
    try:
        response = requests.get(
            'https://launchermeta.mojang.com/mc/game/version_manifest.json',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        versions = data.get('versions', [])
        release = [v['id'] for v in versions if v.get('type') == 'release']
        return sort_versions(release)
    except Exception as e:
        print(f"[ERROR] get_vanilla_versions: {e}")
        return []


def get_snapshot_versions() -> List[str]:
    """Obtiene versiones snapshot de Vanilla."""
    try:
        response = requests.get(
            'https://launchermeta.mojang.com/mc/game/version_manifest.json',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        versions = data.get('versions', [])
        snapshots = [v['id'] for v in versions if v.get('type') == 'snapshot']
        return sort_versions(snapshots)
    except Exception as e:
        print(f"[ERROR] get_snapshot_versions: {e}")
        return []


def get_forge_versions() -> List[str]:
    """Obtiene versiones de Forge desde promotions_slim.json."""
    try:
        response = requests.get(
            'https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        promos = data.get('promos', {})
        # Extraer versiones únicas de Minecraft de las claves
        mc_versions = set()
        for key in promos.keys():
            # Claves tipo "1.20.1-recommended" o "1.20.1-latest"
            match = re.match(r'(\d+\.\d+\.?\d*)-', key)
            if match:
                mc_versions.add(match.group(1))
        return sort_versions(list(mc_versions))
    except Exception as e:
        print(f"[ERROR] get_forge_versions: {e}")
        return []


def get_neoforge_versions() -> List[str]:
    """Obtiene versiones de NeoForge desde Maven."""
    try:
        response = requests.get(
            'https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml',
            timeout=10
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        versions = []
        versioning = root.find('versioning')
        if versioning is not None:
            versions_elem = versioning.find('versions')
            if versions_elem is not None:
                for v in versions_elem.findall('version'):
                    if v.text:
                        versions.append(v.text)
        return sort_versions(versions)[:20]  # Limitar a 20 más recientes
    except Exception as e:
        print(f"[ERROR] get_neoforge_versions: {e}")
        return []


def get_mohist_versions() -> List[str]:
    """Obtiene versiones de Mohist."""
    try:
        response = requests.get(
            'https://mohistmc.com/api/v2/projects/mohist/versions',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        versions = data.get('versions', [])
        # Extraer campo version de cada objeto
        return sort_versions([v.get('version', '') for v in versions if v.get('version')])
    except Exception as e:
        print(f"[ERROR] get_mohist_versions: {e}")
        return []


def get_server_versions(server_type: str) -> List[str]:
    """
    Obtiene versiones para un tipo de servidor.
    """
    type_lower = server_type.lower()

    if type_lower == 'paper':
        return get_paper_versions()
    elif type_lower == 'purpur':
        return get_purpur_versions()
    elif type_lower == 'fabric':
        return get_fabric_versions()
    elif type_lower == 'vanilla':
        return get_vanilla_versions()
    elif type_lower == 'snapshot':
        return get_snapshot_versions()
    elif type_lower == 'forge':
        return get_forge_versions()
    elif type_lower == 'neoforge':
        return get_neoforge_versions()
    elif type_lower == 'mohist':
        return get_mohist_versions()
    else:
        # Para los demás (Arclight, Velocity, Banner, Folia, Crucible, Magma, Ketting, Cardboard, Custom)
        return FALLBACK_VERSIONS.copy()


# =============================================================================
# FUNCIONES DE INSTALACIÓN
# =============================================================================

def set_install_status(server_name: str, installing: bool = False, progress: str = "", done: bool = False, error: str = ""):
    """Actualiza el estado de instalación."""
    install_status[server_name] = {
        "installing": installing,
        "progress": progress,
        "done": done,
        "error": error
    }


def get_install_status(server_name: str) -> Dict:
    """Obtiene el estado de instalación."""
    return install_status.get(server_name, {
        "installing": False,
        "progress": "",
        "done": False,
        "error": ""
    })


def install_paper(server_name: str, version: str, server_path: str) -> Dict:
    """
    Instala PaperMC.
    """
    try:
        set_install_status(server_name, True, f"Obteniendo información de Paper {version}...")

        # 1. Obtener último build
        response = requests.get(
            f'https://api.papermc.io/v2/projects/paper/versions/{version}',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        builds = data.get('builds', [])
        if not builds:
            return {"success": False, "error": f"No hay builds disponibles para {version}"}
        build = builds[-1]  # Último build

        set_install_status(server_name, True, f"Obteniendo detalles del build {build}...")

        # 2. Obtener detalles del build
        response = requests.get(
            f'https://api.papermc.io/v2/projects/paper/versions/{version}/builds/{build}',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        jar_name = data['downloads']['application']['name']

        set_install_status(server_name, True, f"Descargando Paper {version} (build {build})...")

        # 3. Descargar JAR
        download_url = f'https://api.papermc.io/v2/projects/paper/versions/{version}/builds/{build}/downloads/{jar_name}'
        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()

        jar_path = os.path.join(server_path, 'paper.jar')
        with open(jar_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # 4. Crear eula.txt
        eula_path = os.path.join(server_path, 'eula.txt')
        with open(eula_path, 'w') as f:
            f.write("#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://aka.ms/minecrafteula)\n")
            f.write("eula=true\n")

        set_install_status(server_name, False, "Instalación completada", True, "")
        return {"success": True, "message": f"Paper {version} instalado correctamente"}

    except requests.RequestException as e:
        set_install_status(server_name, False, "", False, f"Error de red: {str(e)}")
        return {"success": False, "error": f"Error de red: {str(e)}"}
    except Exception as e:
        set_install_status(server_name, False, "", False, str(e))
        return {"success": False, "error": str(e)}


def install_purpur(server_name: str, version: str, server_path: str) -> Dict:
    """
    Instala Purpur.
    """
    try:
        set_install_status(server_name, True, f"Obteniendo último build de Purpur {version}...")

        # 1. Obtener último build
        response = requests.get(
            f'https://api.purpurmc.org/v2/purpur/{version}',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        build = data['builds']['latest']

        set_install_status(server_name, True, f"Descargando Purpur {version} (build {build})...")

        # 2. Descargar JAR
        download_url = f'https://api.purpurmc.org/v2/purpur/{version}/{build}/download'
        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()

        jar_path = os.path.join(server_path, 'server.jar')
        with open(jar_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # 3. Crear eula.txt
        eula_path = os.path.join(server_path, 'eula.txt')
        with open(eula_path, 'w') as f:
            f.write("#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://aka.ms/minecrafteula)\n")
            f.write("eula=true\n")

        set_install_status(server_name, False, "Instalación completada", True, "")
        return {"success": True, "message": f"Purpur {version} instalado correctamente"}

    except requests.RequestException as e:
        set_install_status(server_name, False, "", False, f"Error de red: {str(e)}")
        return {"success": False, "error": f"Error de red: {str(e)}"}
    except Exception as e:
        set_install_status(server_name, False, "", False, str(e))
        return {"success": False, "error": str(e)}


def install_vanilla(server_name: str, version: str, server_path: str) -> Dict:
    """
    Instala Vanilla (server.jar oficial de Mojang).
    """
    try:
        set_install_status(server_name, True, f"Buscando {version} en Mojang...")

        # 1. Obtener manifest
        response = requests.get(
            'https://launchermeta.mojang.com/mc/game/version_manifest.json',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        # Buscar la versión
        version_url = None
        for v in data.get('versions', []):
            if v.get('id') == version:
                version_url = v.get('url')
                break

        if not version_url:
            set_install_status(server_name, False, "", False, f"Versión {version} no encontrada")
            return {"success": False, "error": f"Versión {version} no encontrada"}

        set_install_status(server_name, True, f"Obteniendo detalles de {version}...")

        # 2. Obtener detalles de la versión
        response = requests.get(version_url, timeout=10)
        response.raise_for_status()
        version_data = response.json()

        server_jar_url = version_data['downloads']['server']['url']

        set_install_status(server_name, True, f"Descargando Vanilla {version}...")

        # 3. Descargar JAR
        response = requests.get(server_jar_url, stream=True, timeout=60)
        response.raise_for_status()

        jar_path = os.path.join(server_path, 'server.jar')
        with open(jar_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # 4. Crear eula.txt
        eula_path = os.path.join(server_path, 'eula.txt')
        with open(eula_path, 'w') as f:
            f.write("#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://aka.ms/minecrafteula)\n")
            f.write("eula=true\n")

        set_install_status(server_name, False, "Instalación completada", True, "")
        return {"success": True, "message": f"Vanilla {version} instalado correctamente"}

    except requests.RequestException as e:
        set_install_status(server_name, False, "", False, f"Error de red: {str(e)}")
        return {"success": False, "error": f"Error de red: {str(e)}"}
    except Exception as e:
        set_install_status(server_name, False, "", False, str(e))
        return {"success": False, "error": str(e)}


def install_fabric(server_name: str, version: str, server_path: str) -> Dict:
    """
    Instala Fabric.
    """
    try:
        set_install_status(server_name, True, f"Obteniendo loader de Fabric para {version}...")

        # 1. Obtener loader
        response = requests.get(
            f'https://meta.fabricmc.net/v2/versions/loader/{version}',
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if not data:
            set_install_status(server_name, False, "", False, f"No hay loader para {version}")
            return {"success": False, "error": f"No hay loader para {version}"}

        loader_version = data[0]['loader']['version']

        set_install_status(server_name, True, f"Descargando installer de Fabric...")

        # 2. Descargar installer
        installer_url = f'https://meta.fabricmc.net/v2/versions/installer'
        response = requests.get(installer_url, timeout=10)
        response.raise_for_status()
        installer_data = response.json()
        installer_version = installer_data[0]['version']

        installer_jar_path = os.path.join(server_path, 'fabric-installer.jar')
        download_url = f"https://maven.fabricmc.net/net/fabricmc/fabric-installer/{installer_version}/fabric-installer-{installer_version}.jar"

        response = requests.get(download_url, stream=True, timeout=60)
        response.raise_for_status()

        with open(installer_jar_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        set_install_status(server_name, True, f"Ejecutando installer de Fabric...")

        # 3. Ejecutar installer
        result = subprocess.run(
            ['java', '-jar', installer_jar_path, 'server',
             '-mcversion', version,
             '-loader', loader_version,
             '-downloadMinecraft'],
            cwd=server_path,
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode != 0:
            set_install_status(server_name, False, "", False, f"Installer falló: {result.stderr}")
            return {"success": False, "error": f"Installer falló: {result.stderr}"}

        # Mover el JAR generado a server.jar
        generated_jar = os.path.join(server_path, 'fabric-server-launch.jar')
        if os.path.exists(generated_jar):
            # Ya está en el lugar correcto
            pass

        # 4. Crear eula.txt
        eula_path = os.path.join(server_path, 'eula.txt')
        with open(eula_path, 'w') as f:
            f.write("#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://aka.ms/minecrafteula)\n")
            f.write("eula=true\n")

        # Limpiar installer
        try:
            os.remove(installer_jar_path)
        except:
            pass

        set_install_status(server_name, False, "Instalación completada", True, "")
        return {"success": True, "message": f"Fabric {version} instalado correctamente"}

    except subprocess.TimeoutExpired as e:
        set_install_status(server_name, False, "", False, "Timeout instalando Fabric")
        return {"success": False, "error": "Timeout instalando Fabric"}
    except requests.RequestException as e:
        set_install_status(server_name, False, "", False, f"Error de red: {str(e)}")
        return {"success": False, "error": f"Error de red: {str(e)}"}
    except Exception as e:
        set_install_status(server_name, False, "", False, str(e))
        return {"success": False, "error": str(e)}


def install_forge(server_name: str, version: str, server_path: str) -> Dict:
    """
    Instala Forge (próximamente).
    """
    set_install_status(server_name, False, "", False, "")
    return {"success": False, "error": f"Instalación de Forge próximamente"}


def install_neoforge(server_name: str, version: str, server_path: str) -> Dict:
    """
    Instala NeoForge (próximamente).
    """
    set_install_status(server_name, False, "", False, "")
    return {"success": False, "error": f"Instalación de NeoForge próximamente"}


def install_unsupported(server_name: str, server_type: str, server_path: str) -> Dict:
    """
    Para tipos sin instalación implementada.
    """
    set_install_status(server_name, False, "", False, "")
    return {"success": False, "error": f"Instalación de {server_type} próximamente"}


def install_server(server_name: str, server_type: str, version: str) -> Dict:
    """
    Instala el JAR del servidor según el tipo.
    """
    server_path = os.path.join(DRIVE_PATH, server_name)

    # Crear carpeta si no existe
    os.makedirs(server_path, exist_ok=True)

    # Funciones de instalación por tipo
    installers = {
        'Paper': install_paper,
        'Purpur': install_purpur,
        'Vanilla': install_vanilla,
        'Fabric': install_fabric,
        'Forge': install_forge,
        'Neoforge': install_neoforge,
    }

    installer = installers.get(server_type, lambda *args: install_unsupported(*args, server_type=server_type))

    return installer(server_name, version, server_path)


# =============================================================================
# RUTAS
# =============================================================================

@servers_bp.route('/software/types', methods=['GET'])
def get_software_types():
    """
    GET /api/software/types
    Retorna lista de tipos de servidor soportados.
    """
    try:
        return jsonify({
            "types": SERVER_TYPES
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@servers_bp.route('/software/versions', methods=['GET'])
def get_software_versions():
    """
    GET /api/software/versions?type=Paper
    Retorna versiones para un tipo de servidor.
    """
    try:
        server_type = request.args.get('type')

        if not server_type:
            return jsonify({
                "success": False,
                "error": "Falta parámetro 'type'"
            }), 400

        versions = get_server_versions(server_type)

        return jsonify({
            "versions": versions
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@servers_bp.route('/servers', methods=['POST'])
def create_server():
    """
    POST /api/servers
    Crea un nuevo servidor (sin instalar JAR todavía).
    Body: {name, type, version}
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Body JSON vacío"
            }), 400

        name = data.get('name', '').strip()
        server_type = data.get('type', 'Vanilla')
        version = data.get('version', '')

        # Validar nombre
        if not name:
            return jsonify({
                "success": False,
                "error": "El nombre no puede estar vacío"
            }), 400

        # Validar sin espacios ni caracteres especiales
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return jsonify({
                "success": False,
                "error": "El nombre solo puede contener letras, números, guiones y guiones bajos"
            }), 400

        # Validar que no existe ya
        servers = list_servers()
        if name in servers:
            return jsonify({
                "success": False,
                "error": f"Ya existe un servidor llamado '{name}'"
            }), 400

        # Crear carpeta del servidor
        server_path = os.path.join(DRIVE_PATH, name)
        os.makedirs(server_path, exist_ok=True)

        # Crear colabconfig.txt
        config = {
            "server_type": server_type,
            "server_version": version,
            "tunnel_service": "minekube",
            "java": {
                "CustomEnabled": "False",
                "version": "",
                "build": ""
            }
        }

        if not save_server_config(name, config):
            return jsonify({
                "success": False,
                "error": "Error al guardar configuración del servidor"
            }), 500

        # Agregar a server_list
        global_config = get_global_config()
        if name not in global_config.get('server_list', []):
            global_config['server_list'].append(name)
            save_global_config(global_config)

        # Si no hay servidor activo, establecer este como activo
        if not get_active_server():
            set_active_server(name)

        return jsonify({
            "success": True,
            "server_name": name,
            "server_type": server_type,
            "server_version": version
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@servers_bp.route('/servers/<server_name>/install', methods=['POST'])
def install_server_route(server_name):
    """
    POST /api/servers/{name}/install
    Instala el JAR del servidor.
    """
    try:
        # Verificar que el servidor existe
        if not server_exists(server_name):
            return jsonify({
                "success": False,
                "error": f"Servidor '{server_name}' no encontrado"
            }), 404

        # Obtener configuración
        config = get_server_config(server_name)
        server_type = config.get('server_type', 'Vanilla')
        version = config.get('server_version', '')

        if not version:
            return jsonify({
                "success": False,
                "error": "El servidor no tiene versión configurada"
            }), 400

        # Ejecutar instalación en hilo separado
        def run_install():
            result = install_server(server_name, server_type, version)
            print(f"[INFO] Instalación de {server_name}: {result}")

        install_thread = threading.Thread(target=run_install, daemon=True)
        install_thread.start()

        return jsonify({
            "success": True,
            "message": f"Iniciando instalación de {server_type} {version}...",
            "server_name": server_name
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@servers_bp.route('/servers/<server_name>/install-status', methods=['GET'])
def get_install_status_route(server_name):
    """
    GET /api/servers/{name}/install-status
    Retorna el estado de la instalación.
    """
    try:
        status = get_install_status(server_name)
        return jsonify(status)

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@servers_bp.route('/servers', methods=['GET'])
def list_servers_route():
    """
    GET /api/servers
    Retorna lista de servidores (igual que el existente en app.py pero aquí para consistencia).
    """
    try:
        servers = list_servers()
        active = get_active_server()

        return jsonify({
            "servers": servers,
            "active": active
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
