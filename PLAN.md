# 🎵 Network Music Mesh - Plan de Implementación

## Descripción General
Sistema de red mesh auto-organizada entre nodos GNU/Linux (USB boot),
donde cada nodo comparte canciones por streaming y la red se fragmenta/
reconecta dinámicamente según proximidad.

---

## Arquitectura del Sistema

### Capa 1 - Infraestructura de Red (mesh)
- **olsrd2** o **batman-adv** como protocolo de enrutamiento mesh
- **hostapd** para crear punto de acceso WiFi cuando no detecta red existente
- **wpa_supplicant** para unirse a redes existentes
- Detección automática: escanear → ¿hay red master? → unirse : crear nueva
- Fragmentación por distancia: si pierde conexión → crea red hija/propia

### Capa 2 - Descubrimiento de Nodos
- **avahi/mDNS** para descubrimiento de servicios en red local
- **UDP heartbeat** (puro y simple) cada 2s para detectar vecinos
- Cada nodo anuncia: ID, recursos, canciones locales, señal RSSI

### Capa 3 - Selección de Master (Distributed Leader Election)
- Algoritmo estilo Bul Election basado en:
  - RAM disponible
  - CPU speed
  - Ancho de banda de red
  - Score = (RAM_GB * 2) + (CPU_cores * 3) + (WiFi_speed_Mbps)
- El mayor score → Master
- Re-elección periódica y al detectar cambios de topología

### Capa 4 - Streaming de Música
- **Icecast2** como servidor de streaming en el Master
- **mpg123** / **ffmpeg** para decodificar y enviar al stream
- **Liquidsoap** como motor de playlist/rotación automática
- **darkice** o script custom como fuente → icecast
- Master selecciona canción aleatoria de entre TODAS las canciones de TODOS los nodos
- También acepta comandos externos (`curl`, CLI) para canción específica

### Capa 5 - Base de Datos de Canciones
- Cada nodo tiene 25 canciones únicas (solo ese nodo las posee)
- Catálogo distribuido: cada nodo conoce qué canciones tienen los demás
- Política de almacenamiento: `/var/lib/network-music/local/` (propias)
- Metadatos: SQLite local con ID, título, artista, duración, nodo_origen

### Capa 6 - Interfaz de Control
- **TUI** en ncurses (Python o Rust)
- **Web UI** ligera (Python + Flask/FastAPI) para acceso remoto
- Muestra indicadores en tiempo real:
  - Tasa de transmisión activa (bitrate del stream)
  - Nodos visibles activamente
  - Nivel de señal (RSSI) de cada nodo
  - Modulación WiFi en uso (802.11a/b/g/n/ac)
  - Canciones locales (las 25 propias)
  - Canción actual en streaming

---

## Estructura del Repositorio

```
network_iso/
├── PLAN.md                    ← Este archivo
├── nixos/
│   ├── configuration.nix      ← Configuración principal NixOS
│   ├── hardware-configuration.nix ← Hardware genérico x86_64
│   ├── flake.nix              ← Flake para build reproducible
│   ├── flake.lock
│   └── overlay/
│       └── default.nix        ← Overlays custom si necesario
├── services/
│   ├── network-mesh.service.nix    ← Servicio mesh
│   ├── master-election.service.nix ← Elección de master
│   ├── music-stream.service.nix    ← Streaming Icecast
│   └── node-agent.service.nix      ← Agente de nodo
├── scripts/
│   ├── mesh-manager.py        ← Script principal TUI/Web
│   ├── mesh_agent.py          ← Daemon de agente en cada nodo
│   ├── master_election.py     ← Algoritmo de elección
│   ├── download_songs.py      ← Descarga 2000 canciones sin copyright
│   ├── distribute_songs.py    ← Asigna 25 por nodo
│   └── song_catalog.py        ← Catálogo SQLite
├── songs/
│   └── raw/                   ← 2000 canciones descargadas
│   └── nodes/
│       ├── node001/           ← 25 canciones del nodo 1
│       ├── node002/
│       └── ...
├── build.sh                   ← Script de construcción de la ISO
└── README.md
```

---

## Checklist de Entregables

### Fase 1: Setup del Entorno de Build
- [x] Instalar Nix en el sistema host (macOS) → Se usa Docker con imagen nixos/nix x86_64
- [x] Configurar cross-compilation x86_64-linux desde macOS arm64
- [x] Verificar que se pueda construir una ISO mínima de NixOS → En progreso (build_iso2.sh)

### Fase 2: Configuración NixOS Base
- [x] Flake.nix con inputs de NixOS stable (nixos-24.11)
- [x] configuration.nix base con paquetes esenciales
- [x] Incluir: hostapd, wpa_supplicant, icecast, ffmpeg, avahi, python3, iwd, dnsmasq
- [x] Crear usuario root con auto-login al boot (USB live)

### Fase 3: Servicios de Red Mesh
- [x] Servicio de escaneo WiFi periódico (mesh_agent.py - UDP discovery)
- [x] Servicio de creación de AP (hostapd) si no hay red
- [x] Servicio de unión a red existente si se detecta master
- [x] Monitoreo de distancia/calidad de enlace (RSSI, bitrate)
- [x] Servicio de fragmentación: crear red independiente si se aleja

### Fase 4: Elección de Master
- [x] Script de evaluación de recursos (RAM, CPU, WiFi)
- [x] Protocolo de elección distribuida (score-based Bul Election)
- [x] Sistema de re-elección ante cambios de topología
- [x] Broadcast del nuevo master a todos los nodos (heartbeat UDP)

### Fase 5: Streaming de Música
- [x] Icecast2 configurado como servicio en el Master
- [x] Script fuente que rote canciones aleatoriamente (ffmpeg → icecast)
- [x] Endpoint HTTP POST /api/force_song para forzar canción específica
- [x] Clientes en nodos no-master para recibir stream (mpg123 curl)

### Fase 6: Catálogo y Almacenamiento de Canciones
- [x] Generar 2000+ canciones sin copyright (sox synth, 600MB+)
- [x] Asignar 25 canciones únicas por nodo (distribute_to_nodes)
- [x] Catalogar en SQLite con metadatos (SongCatalog class)
- [x] Política de almacenamiento por nodo (/opt/mesh/songs/)

### Fase 7: Interfaz de Control (TUI + Web)
- [x] TUI con curses mostrando todos los indicadores (mesh_tui.py)
- [x] Web UI con Flask mostrando dashboard (webui.py - puerto 8080)
- [x] Indicadores: bitrate, nodos visibles, RSSI, modulación, canciones, canción actual

### Fase 8: Construcción de la ISO
- [x] Integrar todo en la imagen NixOS (configuration.nix completo)
- [ ] Incluir canciones pre-instaladas (25 por nodo, con selector) → Se incluye en build
- [⏳] Crear ISO bootable x86_64 → **BUILD EN PROGRESO** (build_iso2.sh)
- [ ] Verificar tamaño y funcionalidad

### Fase 9: Testing
- [ ] Boot de ISO en QEMU x86_64
- [ ] Simular 2-3 nodos en VM
- [ ] Verificar mesh, streaming, TUI

---

## Plan de Ejecución (en orden)

1. `setup_nix.sh` - Instalar nix y preparar build environment
2. `flake.nix` - Definir el flake de la ISO
3. `configuration.nix` - Configurar NixOS
4. `mesh_agent.py` - Daemon agente de nodo
5. `mesh_manager.py` - TUI/Web de control
6. `download_songs.py` - Descargar canciones
7. `master_election.py` - Protocolo de elección
8. `build.sh` - Construir ISO
9. Iterar y corregir
