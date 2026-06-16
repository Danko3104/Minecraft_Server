# MineColab Panel

Panel web para gestionar servidores Minecraft desde Google Colab.

## Características

- **Panel web completo**: Dashboard, consola en vivo, jugadores, plugins/mods, archivos, propiedades, configuración
- **Soporte para múltiples tipos de servidor**: Paper, Purpur, Vanilla, Fabric, Forge, NeoForge y más
- **Plugins y Mods**: Buscador e instalador integrado con Modrinth y Hangar, instalación con dependencias
- **Consola en tiempo real**: Streaming de output vía WebSocket, auto-scroll, historial de comandos
- **Gestión de jugadores**: Lista, kick, ban, unban, op, deop, whitelist, eliminación de registro
- **Archivos**: Navegador de archivos, editor de texto, upload/download/delete
- **Backups**: Automáticos al detener el servidor, manuales, listado, restauración y eliminación
- **Subida de mundos**: Via ZIP o carpeta completa con detección automática de level-name
- **Actualización de PaperMC**: Desde el panel con backup automático del mundo
- **Túnel Oracle Cloud**: Conexión SSH reversa para IP pública fija
- **Túnel Cloudflare**: Acceso web al panel via trycloudflare.com
- **Notificaciones del navegador**: Eventos configurables (inicio, parada, errores, backups)
- **Autenticación JWT**: Middleware de seguridad en endpoints críticos

## Tipos de Servidor Soportados

| Categoría | Tipos |
|-----------|-------|
| Plugin | Paper, Purpur, Mohist, Arclight, Banner, Folia, Crucible, Magma, Ketting, Cardboard, Velocity |
| Mod | Fabric, Forge, NeoForge |
| Vanilla | Vanilla, Snapshot |
| Otros | Bedrock, Custom |

## Stack Técnico

- **Backend**: Flask + Flask-SocketIO + Flask-CORS
- **Frontend**: HTML/CSS/JS vanilla con Font Awesome
- **Almacenamiento**: Google Drive (Colab) o local
- **Túneles**: Cloudflare (panel web) + Oracle Cloud SSH (Minecraft)
- **APIs externas**: Modrinth, Hangar, PaperMC, PurpurMC, Mojang, Forge, NeoForge


