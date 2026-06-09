"""
Tunnel management (disabled).
"""

_minecraft_url = None

def set_minecraft_url(url: str):
    global _minecraft_url
    _minecraft_url = url

def get_current_minecraft_url() -> str:
    return _minecraft_url
