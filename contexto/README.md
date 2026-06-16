# MineColab Panel - Estado del Proyecto

**Repositorio:** https://github.com/Danko3104/Minecraft_Server.git
**Último commit:** `294b375 feat: add whitelist toggle in server properties + fix write overwrite bug`

---

## 📋 Estructura

```
panel/
├── app.py               # Flask + SocketIO + middleware auth
├── drive.py             # Google Drive manager
├── rcon.py              # Cliente RCON (socket/struct)
├── server_manager.py    # Control proceso Minecraft
├── tunnel.py            # Oracle Cloud SSH tunnel
├── socketio_events.py   # Eventos WebSocket (streaming consola)
├── static/index.html    # Panel web (~3400 líneas)
└── routes/
    ├── auth.py          # Login JWT + verify_token real
    ├── servers.py       # Crear/instalar servidores (18 tipos)
    ├── players.py       # Jugadores (kick, ban, op, whitelist, delete registro)
    ├── plugins.py       # Plugins (Modrinth, Hangar) + Mods (Modrinth)
    ├── files.py         # Archivos (navegador, editor, upload)
    ├── console.py       # Consola (output, command, players)
    └── dashboard.py     # Stats del panel
scripts/start.py         # Arranque en Colab
Server.ipynb             # Notebook para Colab
```

---

## ✅ Implementado

- **Panel web**: Dashboard, servidores, consola, jugadores, plugins/mods, archivos, settings
- **API REST**: 50+ rutas con auth JWT real en endpoints críticos (POST/PUT/DELETE)
- **Instalación**: Paper, Purpur, Vanilla, Fabric (Forge/NeoForge próximamente)
- **Control Minecraft**: Start/Stop/Command/Diagnose via RCON o stdin
- **Jugadores**: List, kick, ban, unban, op, whitelist, eliminar registro (usercache.json)
- **Plugins**: Búsqueda (Modrinth + Hangar), instalación con dependencias, updates
- **Mods**: Búsqueda en Modrinth con filtro por loader (Fabric/Forge/NeoForge), instalación en mods/
- **Contenido adaptativo**: La pestaña muestra "Plugins" o "Mods" según el tipo de servidor, se oculta para Vanilla
- **Archivos**: Navegador, editor texto, upload/download/delete, mkdir
- **RCON**: Cliente personalizado con socket/struct sin dependencias externas
- **Dashboard**: Stats del panel, info de Java, TPS/RAM/CPU con indicadores de color
- **SocketIO**: Streaming de consola en tiempo real, estado del servidor
- **Túnel**: Cloudflare (panel web) + Oracle Cloud SSH (Minecraft, IP fija)
- **Seguridad**: verify_token funcional, login con contraseña, middleware global, debug=false por defecto, secret key via env var
- **Colab**: Celda activa con `while True`, instalación automática de Java 21
- **Notificaciones**: Sistema de tipos configurables desde el dropdown, soporte de notificaciones del navegador
- **Backups**: Automáticos al detener servidor, manuales, listado, restauración, poda (últimos 3)
- **Subida de mundos**: ZIP con detección automática de level-name, subida por chunks para archivos grandes

---

## 🔌 Rutas API

### Públicas (sin auth)
`GET /` `GET /api/ping` `GET /api/status` `GET /api/servers`
`GET /api/software/types` `GET /api/software/versions`
`POST /api/auth/login` `GET /api/auth/check` `POST /api/auth/logout`
`GET /api/server/last-output` `GET /api/server/diagnose` `GET /api/server/stats`
`GET /api/console/output` `GET /api/console/players`
`GET /api/players` `GET /api/players/whitelist` `GET /api/players/banned`
`GET /api/plugins/search` `GET /api/plugins/installed` `GET /api/plugins/info`
`GET /api/files/list` `GET /api/files/download` `GET /api/files/read`
`GET /api/dashboard/stats` `GET /api/dashboard/java-info`
`GET/POST /api/settings/server-icon`
`GET /api/settings/server-properties` `GET /api/settings/paper-version`
`GET /api/settings/backups`

### Protegidas (requieren token)
`POST /api/servers` `POST /api/servers/select` `POST /api/servers/{name}/install`
`POST /api/server/start` `POST /api/server/stop` `POST /api/server/command`
`POST /api/console/command`
`POST /api/players/kick` `POST /api/players/ban` `POST /api/players/unban`
`POST /api/players/op` `POST /api/players/deop` `POST /api/players/say`
`POST /api/players/whitelist/add` `POST /api/players/whitelist/remove`
`POST /api/players/delete`
`POST /api/plugins/install` `POST /api/plugins/check-updates`
`POST /api/plugins/update-all` `POST /api/plugins/uninstall` `POST /api/plugins/upload`
`PUT /api/files/write` `POST /api/files/upload` `POST /api/files/delete` `POST /api/files/mkdir`
`PUT /api/settings/server-properties`
`POST /api/settings/check-updates` `POST /api/settings/update`
`POST /api/settings/reset-world`
`POST /api/settings/backup-world`
`POST /api/settings/backups/restore` `POST /api/settings/backups/delete`
`POST /api/settings/upload-world` `POST /api/settings/upload-world-chunked`
`GET /api/settings/upload-world-status` `POST /api/settings/upload-world-cancel`

---

## 🛠️ Tipos de Servidor (18)

| Tipo | Categoría | Instalador |
|------|-----------|------------|
| Vanilla | Vanilla | ✅ |
| Snapshot | Vanilla | ❌ |
| Paper | Plugin | ✅ |
| Purpur | Plugin | ✅ |
| Fabric | Mod | ✅ |
| Forge | Mod | ⏳ |
| NeoForge | Mod | ⏳ |
| Mohist | Plugin | ❌ |
| Arclight | Plugin | ❌ |
| Velocity | Proxy | ❌ |
| Banner | Plugin | ❌ |
| Folia | Plugin | ❌ |
| Bedrock | Bedrock | ❌ |
| Crucible | Plugin | ❌ |
| Magma | Plugin | ❌ |
| Ketting | Plugin | ❌ |
| Cardboard | Plugin | ❌ |
| Custom | - | ❌ |

---

## 🔑 Configuración Default

| Concepto | Valor |
|----------|-------|
| Contraseña panel | `minecolab2024` |
| Puerto Flask | 5000 |
| RCON password | `minecolab_panel` |
| RCON port | 25575 |
| Java | OpenJDK 21 JDK |
| Túnel panel | Cloudflare (trycloudflare.com) |
| Túnel Minecraft | Oracle Cloud SSH reverso |
| JWT Secret | env var `MINECOLAB_JWT_SECRET` |
| Debug mode | env var `FLASK_DEBUG` (default false) |

---

## 📁 Pendientes

- **Forge / NeoForge** - Instaladores de servidores modded
- **Frontend auth** - Login flow en index.html para usar tokens JWT
- **Rate limiting** - Proteger login contra fuerza bruta
- **Backups automáticos** - Programar backups de worlds
- **Notificaciones Discord** - Webhook para eventos

---

## 🔗 APIs Externas

```
PaperMC   https://api.papermc.io/v2/projects/paper
PurpurMC  https://api.purpurmc.org/v2/purpur
Fabric    https://meta.fabricmc.net/v2/versions/game
Mojang    https://launchermeta.mojang.com/mc/game/version_manifest.json
Forge     https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json
NeoForge  https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml
Mohist    https://mohistmc.com/api/v2/projects/mohist/versions
Modrinth  https://api.modrinth.com/v2
Hangar    https://hangar.papermc.io/api/v1
```

---

**2026-06-15 · Último commit:** `294b375 feat: add whitelist toggle in server properties + fix write overwrite bug`
