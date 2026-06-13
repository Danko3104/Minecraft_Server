"""
Actualiza automáticamente contexto/README.md con el último commit antes de cada push.
"""

import subprocess
import re
from datetime import date
from pathlib import Path

CONTEXT_FILE = Path(__file__).resolve().parent.parent / "contexto" / "README.md"


def get_last_commit():
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, check=True,
            cwd=CONTEXT_FILE.parent.parent
        )
        return result.stdout.strip()
    except Exception:
        return None


def update_context():
    if not CONTEXT_FILE.exists():
        print(f"[update_context] No encontrado: {CONTEXT_FILE}")
        return False

    content = CONTEXT_FILE.read_text(encoding="utf-8")
    commit = get_last_commit()
    if not commit:
        print("[update_context] No se pudo obtener el último commit")
        return False

    today = date.today().isoformat()

    lines = content.split("\n")
    changed = False

    for i, line in enumerate(lines):
        if line.startswith("**Último commit:**"):
            lines[i] = f"**Último commit:** `{commit}`"
            changed = True
        elif line.startswith("**20") and "·" in line and "Último commit" in line:
            lines[i] = f"**{today} · Último commit:** `{commit}`"
            changed = True

    if changed:
        CONTEXT_FILE.write_text("\n".join(lines), encoding="utf-8")
        subprocess.run(
            ["git", "add", str(CONTEXT_FILE.relative_to(CONTEXT_FILE.parent.parent, walk_up=True))],
            cwd=CONTEXT_FILE.parent.parent
        )
        print(f"[update_context] Contexto actualizado a: {commit}")
        return True

    print("[update_context] Sin cambios necesarios")
    return True


if __name__ == "__main__":
    update_context()
