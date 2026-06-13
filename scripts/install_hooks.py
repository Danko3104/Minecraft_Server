"""
Instala el hook pre-commit para actualizar contexto/README.md automáticamente.
Ejecutar: python scripts/install_hooks.py
"""

import shutil
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent / ".git" / "hooks"
HOOK_PATH = HOOKS_DIR / "pre-commit"
SCRIPT_PATH = Path(__file__).resolve().parent / "update_context.py"

PYTHON_PATH = sys.executable.replace("\\", "/")
DRIVE_C = PYTHON_PATH.replace("C:/", "/c/").replace("D:/", "/d/")

HOOK_CONTENT = f"""#!/bin/sh
# Hook pre-commit: actualiza contexto/README.md con el último commit
"{DRIVE_C}" "{SCRIPT_PATH}"
if [ $? -ne 0 ]; then
    echo "[pre-commit] Error al actualizar contexto"
    exit 1
fi
"""


def main():
    if not HOOKS_DIR.exists():
        print("Error: No se encuentra .git/hooks/")
        print("¿Estás en la raíz del repositorio?")
        sys.exit(1)

    if not SCRIPT_PATH.exists():
        print(f"Error: No se encuentra {SCRIPT_PATH}")
        sys.exit(1)

    # Backup existing hook if present
    if HOOK_PATH.exists() and not HOOK_PATH.read_text().startswith(HOOK_CONTENT[:20]):
        backup = HOOK_PATH.with_suffix(".bak")
        shutil.copy2(HOOK_PATH, backup)
        print(f"Backup del hook existente: {backup}")

    HOOK_PATH.write_text(HOOK_CONTENT)
    print(f"Hook instalado: {HOOK_PATH}")
    print("Ahora cada commit actualizará contexto/README.md automáticamente.")


if __name__ == "__main__":
    main()
