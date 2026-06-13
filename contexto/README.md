# MineColab Panel - Estado del Proyecto

**Repositorio:** https://github.com/Danko3104/Minecraft_Server.git
**Último commit:** `cfee173 fix: -XX:-UseContainerSupport para evitar que Java se cuelgue en Colab con cgroup no estandar`

---

## 📋 Estructura

```
panel/
├── app.py               # Flask + SocketIO + middleware auth
├── drive.py             # Google Drive manager
├── rcon.py              # Cliente RCON (socket/struct)
├── server_manager.py    # Control proceso Minecraft
├── tunnel.py            # Minekube Connect (doc)
├── socketio_events.py   # Eventos WebSocket (streaming consola)
├── static/index.html    # Panel web (~2200 líneas)
└── routes/
    ├── auth.py          # Login JWT + verify_token real
    ├── servers.py       # Crear/instalar servidores
    ├── players.py       # Jugadores (kick, ban, op, whitelist)
    ├── plugins.py       # Plugins (Modrinth, Hangar)
    ├── files.py         # Archivos (navegador, editor, upload)
    ├── console.py       # Consola (output, command, players)
    └── dashboard.py     # Stats del panel
scripts/start.py         # Arranque en Colab
Server.ipynb             # Notebook para Colab
```

---

## ✅ Implementado

- **Panel web**: Dashboard, servidores, consola, jugadores, plugins, archivos, settings
- **API REST**: 50+ rutas con auth JWT real en endpoints críticos (POST/PUT/DELETE)
- **Instalación**: Paper, Purpur, Vanilla, Fabric
- **Control Minecraft**: Start/Stop/Command/Diagnose via RCON o stdin
- **Jugadores**: List, kick, ban, unban, op, whitelist
- **Plugins**: Búsqueda (Modrinth + Hangar), instalación con dependencias, updates
- **Archivos**: Navegador, editor texto, upload/download/delete, mkdir
- **RCON**: Cliente personalizado con socket/struct sin dependencias externas
- **Dashboard**: Stats del panel, info de Java
- **SocketIO**: Streaming de consola en tiempo real, estado del servidor
- **Túnel**: Cloudflare + Minekube Connect (minecolab.play.minekube.net)
- **Seguridad**: verify_token funcional, login con contraseña, middleware global, debug=false por defecto, token Minekube aleatorio, secret key via env var
- **Colab**: Celda activa con `while True`, instalación automática de Java 21

---

## 🔌 Rutas API

### Públicas (sin auth)
`GET /` `GET /api/ping` `GET /api/status` `GET /api/servers`
`GET /api/software/types` `GET /api/software/versions`
`POST /api/auth/login` `GET /api/auth/check` `POST /api/auth/logout`
`GET /api/server/last-output` `GET /api/server/diagnose`
`GET /api/console/output` `GET /api/console/players`
`GET /api/players` `GET /api/players/whitelist` `GET /api/players/banned`
`GET /api/plugins/search` `GET /api/plugins/installed`
`GET /api/files/list` `GET /api/files/download` `GET /api/files/read`
`GET /api/dashboard/stats` `GET /api/dashboard/java-info`

### Protegidas (requieren token)
`POST /api/servers` `POST /api/servers/select` `POST /api/servers/{name}/install`
`POST /api/server/start` `POST /api/server/stop` `POST /api/server/command` `GET /api/server/stats`
`POST /api/console/command`
`POST /api/players/kick` `POST /api/players/ban` `POST /api/players/unban` `POST /api/players/op` `POST /api/players/say`
`POST /api/players/whitelist/add` `POST /api/players/whitelist/remove`
`POST /api/plugins/install` `POST /api/plugins/check-updates` `POST /api/plugins/update-all` `POST /api/plugins/uninstall` `POST /api/plugins/upload`
`PUT /api/files/write` `POST /api/files/upload` `POST /api/files/delete` `POST /api/files/mkdir`
`GET/PUT /api/settings/server-properties` `GET /api/settings/paper-version`
`POST /api/settings/check-updates` `POST /api/settings/update`
`POST /api/settings/reset-world` `GET/POST /api/settings/server-icon`
`POST /api/settings/backup-world` `GET /api/settings/backups`
`POST /api/settings/backups/restore` `POST /api/settings/backups/delete`
`POST /api/settings/upload-world`

---

## 🛠️ Tipos de Servidor (18)

`Vanilla` `Snapshot` `Paper` `Purpur` `Mohist` `Arclight` `Velocity` `Banner`
`Fabric` `Folia` `Forge` `Neoforge` `Bedrock` `Crucible` `Magma` `Ketting`
`Cardboard` `Custom`

Instaladores implementados: **Paper** ✅ **Purpur** ✅ **Vanilla** ✅ **Fabric** ✅

---

## 🔑 Configuración Default

| Concepto | Valor |
|----------|-------|
| Contraseña panel | `minecolab2024` |
| Puerto Flask | 5000 |
| RCON password | `minecolab_panel` |
| RCON port | 25575 |
| Java | OpenJDK 21 JDK |
| Túnel | Cloudflare (trycloudflare.com) |
| Túnel Minekube | minecolab.play.minekube.net |
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

## 🧪 Tests en Colab

1. Crear servidor Paper → Instalar JAR → Iniciar
2. Ver output en consola del panel
3. Enviar comandos via RCON (stop, op, gamemode)
4. Ver lista de jugadores
5. Detener servidor limpiamente

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

**2026-06-12 · Último commit:** `cfee173 fix: -XX:-UseContainerSupport para evitar que Java se cuelgue en Colab con cgroup no estandar`
