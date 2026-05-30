# MineColab Panel - Resumen del Proyecto

## 📁 Estado del Proyecto

**Repositorio:** https://github.com/Danko3104/Minecraft_Server.git
**Último commit:** `ca6824d` - docs: actualizar instrucciones en Server.ipynb

---

## 📋 Estructura del Repositorio

```
minecolab-panel/
├── README.md
├── requirements.txt
├── Server.ipynb              # Notebook para Colab (ACTUALIZADO)
├── contexto/                 # carpeta de contexto (este archivo)
├── panel/
│   ├── __init__.py
│   ├── app.py                # Flask app + rutas API
│   ├── drive.py              # Google Drive manager
│   ├── rcon.py               # TODO
│   ├── server_manager.py     # Control de proceso Minecraft
│   ├── tunnel.py             # TODO
│   ├── socketio_events.py    # TODO
│   ├── static/
│   │   └── index.html        # Panel web completo
│   └── routes/
│       ├── __init__.py
│       ├── auth.py           # Login JWT
│       ├── dashboard.py      # TODO
│       ├── servers.py        # Crear/instalar servidores
│       └── servers.py        # TODO
└── scripts/
    ├── __init__.py
    └── start.py              # Arranque en Colab (CON WHILE TRUE)
```

---

## 🎯 Funcionalidades Implementadas

### ✅ COMPLETADO

1. **Estructura base del proyecto** - Todos los archivos creados
2. **panel/drive.py** - Lectura/escritura en Google Drive
   - `get_global_config()`, `save_global_config()`
   - `get_server_config()`, `save_server_config()`
   - `list_servers()`, `get_active_server()`, `set_active_server()`
   - `server_exists()`, `get_server_path()`
   - `get_server_properties()`, `save_server_properties()`
   - `get_ops()`, `get_whitelist()`, `get_banned_players()`
   - `get_drive_usage()`

3. **panel/app.py** - Flask con SocketIO
   - Rutas: `/`, `/api/ping`, `/api/status`, `/api/servers`
   - WebSocket events: connect, disconnect, ping
   - Blueprints registrados: auth, servers

4. **panel/routes/auth.py** - Autenticación JWT
   - `POST /api/auth/login` - Login con contraseña
   - `GET /api/auth/check` - Verificar token
   - `POST /api/auth/logout` - Logout
   - Decorador `@verify_token` para proteger rutas

5. **panel/server_manager.py** - Control del servidor Minecraft
   - `start(server_name)` - Inicia con diagnóstico completo
   - `stop()` - Detiene via RCON o stdin
   - `is_running()` - Verifica estado
   - `get_status()` - Retorna uptime, PID
   - `send_command(cmd)` - Envía comandos
   - `diagnose(server_name)` - Diagnóstico detallado
   - `get_last_output()` - Últimas líneas del output
   - Auto-crear eula.txt con eula=true
   - Verificar Java instalado antes de iniciar
   - Captura de output en hilo separado

6. **panel/routes/servers.py** - Gestión de servidores
   - `GET /api/software/types` - Tipos disponibles (18 tipos)
   - `GET /api/software/versions?type=X` - Versiones desde APIs oficiales
   - `POST /api/servers` - Crear nuevo servidor
   - `POST /api/servers/{name}/install` - Instalar JAR
   - `GET /api/servers/{name}/install-status` - Estado de instalación
   - Instaladores: Paper ✅, Purpur ✅, Vanilla ✅, Fabric ✅
   - Función `sort_versions()` para ordenar correctamente

7. **panel/static/index.html** - Panel web completo
   - Login con contraseña (por defecto: `minecolab2024`)
   - Dashboard con:
     - Selector de servidor
     - Botones INICIAR/DETENER funcionales
     - Tarjetas: Estado, Servidor Activo, Tiempo Sesión, Tiempo Restante
     - Indicador ON/OFF (punto verde/rojo)
   - Modal "Nuevo Servidor":
     - Nombre, Tipo, Versión
     - Carga dinámica de versiones
     - Instalación con progreso y polling
     - Manejo de errores con mensajes en UI
   - Auto-refresco cada 5 segundos

8. **scripts/start.py** - Arranque en Google Colab
   - `install_java("21")` - Instala OpenJDK 21 JDK
   - `check_drive_mounted()` - Verifica Drive montado
   - `create_drive_structure()` - Crea carpetas en Drive
   - `install_cloudflared()` - Instala cloudflared
   - `start_flask_thread()` - Inicia Flask en hilo daemon
   - `start_cloudflare_tunnel()` - Inicia túnel Cloudflare
   - `launch()` - Orquesta todo en orden
   - **`while True`** - Mantiene celda activa indefinidamente
   - `cleanup()` - Limpieza ordenada al interrumpir

9. **Server.ipynb** - Notebook para Colab
   - Celda única con:
     - Montar Drive
     - Instalar dependencias
     - Clonar repositorio
     - Ejecutar `launch()`
   - Instrucciones actualizadas sobre celda activa

---

## 🔌 Rutas API Registradas (19 total)

| Ruta | Método | Descripción | Autenticación |
|------|--------|-------------|---------------|
| `/` | GET | HTML del panel | No |
| `/api/ping` | GET | Health check | No |
| `/api/status` | GET | Estado del panel | ✅ Token |
| `/api/servers` | GET | Lista servidores | ✅ Token |
| `/api/servers` | POST | Crear servidor | ✅ Token |
| `/api/servers/select` | POST | Seleccionar activo | ✅ Token |
| `/api/servers/{name}/install` | POST | Instalar JAR | ✅ Token |
| `/api/servers/{name}/install-status` | GET | Estado instalación | ✅ Token |
| `/api/software/types` | GET | Tipos de servidor | No |
| `/api/software/versions` | GET | Versiones por tipo | No |
| `/api/auth/login` | POST | Login | No |
| `/api/auth/check` | GET | Verificar token | ✅ Token |
| `/api/auth/logout` | POST | Logout | No |
| `/api/server/start` | POST | Iniciar Minecraft | ✅ Token |
| `/api/server/stop` | POST | Detener Minecraft | ✅ Token |
| `/api/server/command` | POST | Enviar comando | ✅ Token |
| `/api/server/last-output` | GET | Output del servidor | ✅ Token |
| `/api/server/diagnose` | GET | Diagnóstico completo | ✅ Token |
| `/static/<path>` | GET | Archivos estáticos | No |

---

## 🛠️ Tipos de Servidor Soportados (18)

```python
SERVER_TYPES = [
    'Vanilla', 'Snapshot', 'Paper', 'Purpur', 'Mohist',
    'Arclight', 'Velocity', 'Banner', 'Fabric', 'Folia',
    'Forge', 'Neoforge', 'Bedrock', 'Crucible', 'Magma',
    'Ketting', 'Cardboard', 'Custom'
]
```

### Instaladores Implementados:
- ✅ **Paper** - Descarga desde api.papermc.io
- ✅ **Purpur** - Descarga desde api.purpurmc.org
- ✅ **Vanilla** - Descarga desde Mojang
- ✅ **Fabric** - Usa installer oficial
- 📁 **Forge** - Próximamente
- 📁 **NeoForge** - Próximamente
- 📁 **Otros** - Próximamente

---

## 🔑 Configuración por Defecto

- **Contraseña del panel:** `minecolab2024`
- **Puerto Flask:** 5000
- **RCON password:** `minecolab_panel`
- **RCON port:** 25575
- **Java:** OpenJDK 21 JDK
- **Túnel:** Cloudflare (trycloudflare.com)

---

## 📊 Estado de Archivos

| Archivo | Estado | Líneas | Descripción |
|---------|--------|--------|-------------|
| `README.md` | ✅ | 1 | Título del proyecto |
| `requirements.txt` | ✅ | 11 | Dependencias Python |
| `Server.ipynb` | ✅ | ~100 | Notebook Colab |
| `panel/__init__.py` | ✅ | 1 | Package init |
| `panel/app.py` | ✅ | ~280 | Flask app |
| `panel/drive.py` | ✅ | ~400 | Google Drive |
| `panel/server_manager.py` | ✅ | ~550 | Control Minecraft |
| `panel/routes/auth.py` | ✅ | ~120 | Autenticación |
| `panel/routes/servers.py` | ✅ | ~700 | Gestión servidores |
| `panel/static/index.html` | ✅ | ~1100 | Panel web |
| `scripts/start.py` | ✅ | ~600 | Arranque Colab |
| `panel/rcon.py` | 📁 TODO | - | RCON client |
| `panel/tunnel.py` | 📁 TODO | - | Túneles (ngrok, zrok) |
| `panel/socketio_events.py` | 📁 TODO | - | WebSocket events |
| `panel/routes/dashboard.py` | 📁 TODO | - | Dashboard routes |

---

## 🚀 Próximos Pasos (Pendientes)

1. **panel/rcon.py** - Cliente RCON para enviar comandos
2. **panel/tunnel.py** - Soporte para ngrok, zrok, playit
3. **panel/socketio_events.py** - Eventos WebSocket en tiempo real
4. **panel/routes/dashboard.py** - Rutas específicas del dashboard
5. **Consola en vivo** - Mostrar output de Minecraft en el panel
6. **Gestión de jugadores** - Whitelist, ops, bans
7. **Backups automáticos** - Programar backups de worlds
8. **Notificaciones Discord** - Webhook para eventos

---

## 🧪 Flujo de Uso en Colab

1. Abrir `Server.ipynb` en Google Colab
2. Ejecutar la celda única
3. Esperar a que aparezca:
   ```
   ✅ SISTEMA ACTIVO
   No cierres esta celda.
   Panel Web: https://xxxx.trycloudflare.com
   Contraseña: minecolab2024
   ```
4. Abrir URL en navegador
5. Loguearse con la contraseña
6. Click en "+ Nuevo Servidor"
7. Completar: Nombre, Tipo (Paper), Versión (1.20.4)
8. Esperar instalación
9. Click en "▶ INICIAR"
10. Ver output del servidor

---

## ⚠️ Problemas Conocidos y Soluciones

| Problema | Solución |
|----------|----------|
| Java no está instalado | `install_java()` lo instala automáticamente |
| Celda termina sola | `while True` mantiene celda activa |
| Nombre duplicado | Validación en frontend y backend |
| Versiones desordenadas | `sort_versions()` ordena correctamente |
| EULA no aceptada | Auto-crear eula.txt con eula=true |

---

## 📝 Comandos Útiles

```bash
# Ver rutas registradas
python -c "from panel.app import app; print([str(r) for r in app.url_map.iter_rules()])"

# Verificar imports
python -c "from panel.server_manager import server_manager; print('OK')"

# Probar sort_versions
python -c "from panel.routes.servers import sort_versions; print(sort_versions(['1.8', '1.20.4', '1.9']))"
# Resultado: ['1.20.4', '1.9', '1.8']

# Probar diagnose endpoint
curl http://localhost:5000/api/server/diagnose -H "Authorization: Bearer {TOKEN}"
```

---

## 📅 Fecha de Creación

**2026-05-30**

Este documento resume todo el trabajo realizado hasta el momento para poder continuar en una nueva sesión.
