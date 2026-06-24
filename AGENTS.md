# AGENTS.md — Contexto del Proyecto

## Repositorio
- **URL:** https://github.com/Danko3104/Minecraft_Server.git
- **Rama principal:** `main`
- **Regla:** Todo cambio debe ir con commit + push al repo.

## Descripción General
**MineColab Panel** — Panel web para gestionar servidores Minecraft desde Google Colab.
Backend en Flask + Flask-SocketIO, frontend vanilla HTML/CSS/JS con Font Awesome.
Almacenamiento en Google Drive o local.

## Estructura del Proyecto

```
Minecraft_Server/
├── Server.ipynb          # Notebook principal de Colab (monta Drive, instala deps, clona repo, inicia panel)
├── requirements.txt      # Dependencias Python (flask, flask-socketio, mcrcon, etc.)
├── README.md
├── AGENTS.md             # <-- Este archivo
├── panel/
│   ├── app.py            # Aplicación Flask principal (rutas API, middleware auth, websocket)
│   ├── server_manager.py # Controla proceso Java de Minecraft (iniciar, detener, RCON, stats)
│   ├── tunnel.py         # Túnel SSH reverso hacia Oracle Cloud
│   ├── drive.py          # Acceso a Google Drive (servidores, configs)
│   ├── rcon.py           # Cliente RCON
│   ├── socketio_events.py# Eventos WebSocket
│   ├── routes/
│   │   ├── auth.py       # Autenticación JWT
│   │   ├── servers.py    # Rutas de servidores
│   │   ├── players.py    # Gestión de jugadores
│   │   ├── plugins.py    # Plugins/Mods (Modrinth, Hangar)
│   │   ├── files.py      # Navegador/editor de archivos
│   │   ├── console.py    # Consola y logs
│   │   └── dashboard.py  # Dashboard
│   └── static/
│       ├── index.html    # Frontend single-page
│       └── backgrounds/
├── scripts/
│   ├── start.py          # Script de inicio
│   ├── install_hooks.py  # Hooks de git
│   └── update_context.py # Actualización de contexto
└── .gitignore
```

## Tipos de Servidor Soportados
- **Plugin:** Paper, Purpur, Mohist, Arclight, Banner, Folia, Crucible, Magma, Ketting, Cardboard, Velocity
- **Mod:** Fabric, Forge, NeoForge
- **Otros:** Vanilla, Snapshot, Bedrock, Custom

## Funcionalidades Clave
- Dashboard con estadísticas (TPS, RAM, CPU)
- Consola en tiempo real vía WebSocket
- Gestión de jugadores (kick, ban, op, whitelist, etc.)
- Buscador e instalador de plugins/mods (Modrinth + Hangar)
- Navegador de archivos con editor de texto
- Subida de mundos vía ZIP (con chunked upload para archivos grandes)
- Backups automáticos (al detener servidor) y manuales
- Actualización de PaperMC desde el panel
- Túnel Oracle Cloud (SSH reverso: 64.181.171.17:25565)
- Túnel Cloudflare (trycloudflare.com para acceso web)
- Notificaciones push en el navegador
- Autenticación JWT en endpoints críticos
- Recomendaciones de configuración (server.properties)

## Últimos Cambios Realizados (Commits)

| Commit | Descripción |
|--------|-------------|
| *(pendiente)* | fix: players-summary destruido por applyTranslations causaba "Cannot set properties of null" |
| `fece675` | fix: limpiar puerto 25565 en Oracle antes de iniciar túnel nuevo |
| `93dcfc5` | fix: eliminar CompressionLevel no soportado y mejorar mensaje error túnel Oracle |
| `94be672` | feat: notificación cuando Chunky termina de pre-generar chunks |
| `37d4546` | fix: checkServerReady busca en 500 líneas de log en vez de 20 para encontrar "Done" |
| `f4fe5d4` | fix: mostrar mensaje de error real en loadPlayers en vez de genérico |
| `53d381a` | fix: loadPlayers maneja error y data vacía en vez de colgarse en "Cargando..." |
| `e57042b` | fix: icono servidor con fallback SVG y tunnel reconoce key dinámicamente |
| `f7ca167` | fix: revertir DIFICULTAD y MODO DE JUEGO a select nativo en propiedades |
| `db706bd` | fix: eliminar overlay, dropdown absolute con z-index 1001 + wrapper 9999, trigger sólido |
| `e573f86` | fix: trigger sólido, dropdown fixed con posición JS |
| `6e3e775` | fix: .custom-select.open z-index a 9999 para superar cualquier stacking context |
| `6e2a283` | fix: .custom-select.open con z-index 1001 para quedar sobre el overlay |
| `25f8222` | fix: initCustomSelects con guard contra wrappers huérfanos y listeners duplicados |
| `65d293d` | fix: llamar initCustomSelects al cargar propiedades y verificar selects sin native-prop-select |
| `726fc56` | fix: fondo sólido en dropdown y convertir gamemode a custom select |

## APIs Externas Integradas
- Modrinth (plugins/mods)
- Hangar (plugins)
- PaperMC (versiones y builds)
- PurpurMC (versiones)
- Mojang (autenticación, UUIDs)
- Forge (versiones)
- NeoForge (versiones)
