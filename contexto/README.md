# MineColab Panel - Resumen del Proyecto

## 📁 Estado del Proyecto

**Repositorio:** https://github.com/Danko3104/Minecraft_Server.git
**Último commit:** `b89b092` - feat: implementacion de rcon, consola, dashboard, socketio events y fixes de seguridad

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
│   ├── app.py                # Flask app + rutas API + middleware auth
│   ├── drive.py              # Google Drive manager
│   ├── rcon.py               # Cliente RCON con socket/struct
│   ├── server_manager.py     # Control de proceso Minecraft
│   ├── tunnel.py             # Minekube Connect (plugin interno)
│   ├── socketio_events.py    # Eventos WebSocket (console streaming)
│   ├── static/
│   │   └── index.html        # Panel web completo
│   └── routes/
│       ├── __init__.py
│       ├── auth.py           # Login JWT + verify_token real
│       ├── console.py        # Rutas de consola (output, command, players)
│       ├── dashboard.py      # Stats e info del dashboard
│       ├── files.py          # Gestión de archivos del servidor
│       ├── players.py        # Gestión de jugadores (kick, ban, op, whitelist)
│       ├── plugins.py        # Buscar e instalar plugins (Modrinth, Hangar)
│       └── servers.py        # Crear/instalar servidores
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

3. **panel/rcon.py** - Cliente RCON personalizado
   - `RCONClient(host, port, password)`
   - `connect()` - Handshake de autenticación
   - `disconnect()` - Cierre de conexión
   - `send_command(command)` - Envía comandos y recibe respuesta
   - `is_connected()` - Verifica estado de conexión
   - Implementación con `socket` y `struct` nativos (sin dependencias externas)

4. **panel/app.py** - Flask con SocketIO
   - Rutas: `/`, `/api/ping`, `/api/status`, `/api/servers`
   - WebSocket events: connect, disconnect, ping
   - WebSocket events avanzados: `console:subscribe`, `server:status`
   - Blueprints registrados: auth, servers, players, plugins, files, console, dashboard
   - Middleware `before_request` para autenticación en endpoints críticos
   - Debug mode controlado por env var `FLASK_DEBUG`

5. **panel/routes/auth.py** - Autenticación JWT
   - `POST /api/auth/login` - Login con contraseña (verifica contra config)
   - `GET /api/auth/check` - Verificar token
   - `POST /api/auth/logout` - Logout
   - Decorador `@verify_token` para proteger rutas
   - Función `check_token()` para middleware global
   - Secret key via env var `MINECOLAB_JWT_SECRET`

6. **panel/server_manager.py** - Control del servidor Minecraft
   - `start(server_name)` - Inicia con diagnóstico completo
   - `stop()` - Detiene via RCON o stdin
   - `is_running()` - Verifica estado
   - `get_status()` - Retorna uptime, PID
   - `send_command(cmd)` - Envía comandos via RCON o stdin
   - `diagnose(server_name)` - Diagnóstico detallado
   - `get_last_output()` - Últimas líneas del output
   - Auto-crear eula.txt con eula=true
   - Verificar Java instalado antes de iniciar
   - Captura de output en hilo separado
   - Token Minekube aleatorio (secrets.token_urlsafe)

7. **panel/routes/servers.py** - Gestión de servidores
   - `GET /api/software/types` - Tipos disponibles (18 tipos)
   - `GET /api/software/versions?type=X` - Versiones desde APIs oficiales
   - `POST /api/servers` - Crear nuevo servidor
   - `POST /api/servers/{name}/install` - Instalar JAR
   - `GET /api/servers/{name}/install-status` - Estado de instalación
   - Instaladores: Paper ✅, Purpur ✅, Vanilla ✅, Fabric ✅
   - Función `sort_versions()` para ordenar correctamente

8. **panel/routes/players.py** - Gestión de jugadores
   - `GET /api/players` - Lista de jugadores online
   - `POST /api/players/kick` - Expulsar jugador
   - `POST /api/players/ban` - Banear jugador
   - `POST /api/players/unban` - Desbanear
   - `POST /api/players/op` - Dar OP
   - `POST /api/players/say` - Enviar mensaje
   - `GET /api/players/whitelist` - Ver whitelist
   - `POST /api/players/whitelist/add` - Añadir a whitelist
   - `POST /api/players/whitelist/remove` - Quitar de whitelist
   - `GET /api/players/banned` - Lista de baneados

9. **panel/routes/plugins.py** - Gestión de plugins
   - `GET /api/plugins/search?q=` - Buscar plugins (Modrinth + Hangar)
   - `POST /api/plugins/install` - Instalar plugin con dependencias
   - `GET /api/plugins/installed` - Listar instalados
   - `POST /api/plugins/check-updates` - Buscar actualizaciones
   - `POST /api/plugins/update-all` - Actualizar todos
   - `POST /api/plugins/uninstall` - Desinstalar
   - `POST /api/plugins/upload` - Subir .jar manualmente

10. **panel/routes/files.py** - Gestión de archivos
    - `GET /api/files/list?path=` - Listar directorio
    - `GET /api/files/download?path=` - Descargar archivo
    - `GET /api/files/read?path=` - Leer archivo como texto
    - `PUT /api/files/write` - Guardar archivo
    - `POST /api/files/upload` - Subir archivo
    - `POST /api/files/delete` - Eliminar archivo/carpeta
    - `POST /api/files/mkdir` - Crear carpeta

11. **panel/routes/console.py** - Consola en vivo
    - `GET /api/console/output` - Últimas líneas de la consola
    - `POST /api/console/command` - Enviar comando vía RCON
    - `GET /api/console/players` - Lista de jugadores con UUID

12. **panel/routes/dashboard.py** - Dashboard
    - `GET /api/dashboard/stats` - Estadísticas generales
    - `GET /api/dashboard/java-info` - Información de Java

13. **panel/socketio_events.py** - Eventos WebSocket avanzados
    - `connect` / `disconnect` / `ping` - Eventos básicos
    - `console:subscribe` - Streaming en tiempo real de la consola
    - `server:status` - Estado actual del servidor

14. **panel/tunnel.py** - Túnel Minekube Connect
    - Configurado via plugin dentro del servidor
    - Dominio: minecolab.play.minekube.net
    - No necesita lógica externa

15. **panel/static/index.html** - Panel web completo
    - Login con contraseña (por defecto: `minecolab2024`)
    - Dashboard con:
      - Selector de servidor
      - Botones INICIAR/DETENER funcionales
      - Tarjetas: Estado, Servidor Activo, Tiempo Sesión, Tiempo Restante
      - Indicador ON/OFF (punto verde/rojo)
    - Consola con output en vivo y entrada de comandos
    - Gestión de jugadores (lista, kick, ban, op, whitelist)
    - Gestión de plugins (búsqueda, instalación, actualización)
    - Gestión de archivos (navegador, editor, upload)
    - Settings (server.properties, Paper updates, backups, world upload)
    - Modal "Nuevo Servidor":
      - Nombre, Tipo, Versión
      - Carga dinámica de versiones
      - Instalación con progreso y polling
      - Manejo de errores con mensajes en UI
    - Auto-refresco cada 5 segundos

16. **scripts/start.py** - Arranque en Google Colab
    - `install_java("21")` - Instala OpenJDK 21 JDK
    - `check_drive_mounted()` - Verifica Drive montado
    - `create_drive_structure()` - Crea carpetas en Drive
    - `install_cloudflared()` - Instala cloudflared
    - `start_flask_thread()` - Inicia Flask en hilo daemon
    - `start_cloudflare_tunnel()` - Inicia túnel Cloudflare
    - `launch()` - Orquesta todo en orden
    - **`while True`** - Mantiene celda activa indefinidamente
    - `cleanup()` - Limpieza ordenada al interrumpir

17. **Server.ipynb** - Notebook para Colab
    - Celda única con:
      - Montar Drive
      - Instalar dependencias
      - Clonar repositorio
      - Ejecutar `launch()`
    - Instrucciones actualizadas sobre celda activa

---

## 🔌 Rutas API Registradas

| Ruta | Método | Descripción | Auth |
|------|--------|-------------|------|
| `/` | GET | HTML del panel | No |
| `/api/ping` | GET | Health check | No |
| `/api/status` | GET | Estado del panel | No |
| `/api/servers` | GET | Lista servidores | No |
| `/api/servers` | POST | Crear servidor | ✅ |
| `/api/servers/select` | POST | Seleccionar activo | ✅ |
| `/api/servers/{name}/install` | POST | Instalar JAR | ✅ |
| `/api/servers/{name}/install-status` | GET | Estado instalación | No |
| `/api/software/types` | GET | Tipos de servidor | No |
| `/api/software/versions` | GET | Versiones por tipo | No |
| `/api/auth/login` | POST | Login | No |
| `/api/auth/check` | GET | Verificar token | ✅ |
| `/api/auth/logout` | POST | Logout | No |
| `/api/server/start` | POST | Iniciar Minecraft | ✅ |
| `/api/server/stop` | POST | Detener Minecraft | ✅ |
| `/api/server/command` | POST | Enviar comando | ✅ |
| `/api/server/stats` | GET | TPS, RAM, CPU | ✅ |
| `/api/server/last-output` | GET | Output del servidor | No |
| `/api/server/diagnose` | GET | Diagnóstico completo | No |
| `/api/console/output` | GET | Últimas líneas consola | ✅ |
| `/api/console/command` | POST | Enviar comando vía RCON | ✅ |
| `/api/console/players` | GET | Jugadores conectados | ✅ |
| `/api/players` | GET | Lista jugadores | No |
| `/api/players/kick` | POST | Expulsar jugador | ✅ |
| `/api/players/ban` | POST | Banear | ✅ |
| `/api/players/unban` | POST | Desbanear | ✅ |
| `/api/players/op` | POST | Dar OP | ✅ |
| `/api/players/say` | POST | Enviar mensaje | ✅ |
| `/api/players/whitelist` | GET | Ver whitelist | No |
| `/api/players/whitelist/add` | POST | Añadir whitelist | ✅ |
| `/api/players/whitelist/remove` | POST | Quitar whitelist | ✅ |
| `/api/players/banned` | GET | Lista baneados | No |
| `/api/plugins/search` | GET | Buscar plugins | No |
| `/api/plugins/install` | POST | Instalar plugin | ✅ |
| `/api/plugins/installed` | GET | Listar instalados | No |
| `/api/plugins/check-updates` | POST | Buscar updates | ✅ |
| `/api/plugins/update-all` | POST | Actualizar todos | ✅ |
| `/api/plugins/uninstall` | POST | Desinstalar | ✅ |
| `/api/plugins/upload` | POST | Subir .jar | ✅ |
| `/api/files/list` | GET | Listar archivos | No |
| `/api/files/download` | GET | Descargar archivo | No |
| `/api/files/read` | GET | Leer archivo | No |
| `/api/files/write` | PUT | Guardar archivo | ✅ |
| `/api/files/upload` | POST | Subir archivo | ✅ |
| `/api/files/delete` | POST | Eliminar archivo | ✅ |
| `/api/files/mkdir` | POST | Crear carpeta | ✅ |
| `/api/settings/server-properties` | GET/PUT | server.properties | ✅ |
| `/api/settings/paper-version` | GET | Versión Paper | ✅ |
| `/api/settings/check-updates` | POST | Buscar updates Paper | ✅ |
| `/api/settings/update` | POST | Actualizar Paper | ✅ |
| `/api/settings/reset-world` | POST | Resetear mundo | ✅ |
| `/api/settings/server-icon` | GET/POST | Icono del servidor | ✅ |
| `/api/settings/backup-world` | POST | Backup manual | ✅ |
| `/api/settings/backups` | GET | Listar backups | ✅ |
| `/api/settings/backups/restore` | POST | Restaurar backup | ✅ |
| `/api/settings/backups/delete` | POST | Eliminar backup | ✅ |
| `/api/settings/upload-world` | POST | Subir mundo .zip | ✅ |
| `/api/dashboard/stats` | GET | Estadísticas panel | No |
| `/api/dashboard/java-info` | GET | Info Java | No |
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
- **Túnel Minekube:** minecolab.play.minekube.net
- **JWT Secret:** via env var `MINECOLAB_JWT_SECRET`
- **Debug mode:** via env var `FLASK_DEBUG` (default false)

---

## 📊 Estado de Archivos

| Archivo | Estado | Descripción |
|---------|--------|-------------|
| `README.md` | ✅ | Título del proyecto |
| `requirements.txt` | ✅ | Dependencias Python |
| `Server.ipynb` | ✅ | Notebook Colab |
| `panel/__init__.py` | ✅ | Package init |
| `panel/app.py` | ✅ | Flask app ~610 líneas |
| `panel/drive.py` | ✅ | Google Drive ~390 líneas |
| `panel/rcon.py` | ✅ | RCON client ~115 líneas |
| `panel/server_manager.py` | ✅ | Control Minecraft ~1220 líneas |
| `panel/tunnel.py` | ✅ | Minekube Connect (doc) |
| `panel/socketio_events.py` | ✅ | WebSocket events |
| `panel/routes/auth.py` | ✅ | Autenticación JWT |
| `panel/routes/servers.py` | ✅ | Gestión servidores ~800 líneas |
| `panel/routes/players.py` | ✅ | Gestión jugadores ~175 líneas |
| `panel/routes/plugins.py` | ✅ | Gestión plugins ~510 líneas |
| `panel/routes/files.py` | ✅ | Gestión archivos ~230 líneas |
| `panel/routes/console.py` | ✅ | Consola en vivo |
| `panel/routes/dashboard.py` | ✅ | Dashboard stats |
| `panel/static/index.html` | ✅ | Panel web ~2200 líneas |
| `scripts/start.py` | ✅ | Arranque Colab ~600 líneas |

---

## 🚀 Próximos Pasos (Pendientes)

1. **Forge / NeoForge** - Instaladores de servidores modded
2. **Frontend auth** - Login flow en index.html para usar tokens
3. **Backups automáticos** - Programar backups de worlds
4. **Notificaciones Discord** - Webhook para eventos
5. **Rate limiting** - Proteger login contra fuerza bruta
6. **HTTPS** - Certificado SSL para el túnel

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

# Ver logs del servidor
curl http://localhost:5000/api/server/last-output
```

---

## 📅 Fecha de Creación

**2026-06-12** (Actualizado)

Este documento resume todo el trabajo realizado hasta el momento para poder continuar en una nueva sesión.
