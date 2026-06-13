import os
from datetime import datetime
from flask import Blueprint, jsonify

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')


@dashboard_bp.route('/stats', methods=['GET'])
def dashboard_stats():
    try:
        from panel.server_manager import server_manager
        from panel.drive import get_active_server, list_servers, get_drive_usage

        active = get_active_server()
        servers = list_servers()
        running = server_manager.is_running() if active else False
        status = server_manager.get_status() if running else {}

        total_ram = 0
        total_cpu = 0
        if running and server_manager.process:
            try:
                import psutil
                proc = psutil.Process(server_manager.process.pid)
                total_ram = round(proc.memory_info().rss / 1024 / 1024, 1)
                total_cpu = proc.cpu_percent(interval=0.3)
            except Exception:
                pass

        drive_usage = get_drive_usage()

        return jsonify({
            "success": True,
            "active_server": active,
            "total_servers": len(servers),
            "server_list": servers,
            "minecraft_running": running,
            "uptime_seconds": status.get('uptime', 0),
            "ram_mb": total_ram,
            "cpu_percent": total_cpu,
            "drive_used_gb": drive_usage.get('used_gb', 0),
            "drive_total_gb": drive_usage.get('total_gb', 0),
            "drive_usage_percent": drive_usage.get('usage_percent', 0),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route('/java-info', methods=['GET'])
def dashboard_java_info():
    try:
        import subprocess
        java_version = ""
        try:
            result = subprocess.run(['java', '-version'], capture_output=True, text=True, timeout=10)
            java_version = result.stderr.strip() if result.stderr else result.stdout.strip()
        except Exception:
            java_version = "Java no encontrado"

        import shutil
        java_path = shutil.which('java') or "No encontrado"

        return jsonify({
            "success": True,
            "java_version": java_version.split('\n')[0] if java_version else "Desconocido",
            "java_path": java_path
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
