# 🎵 Network Music Mesh - Plan de Implementación

> **Project Repo:** https://github.com/pabloflores465/network-mesh-iso
> **Last Update:** 2025-04-14

## Descripción
Sistema de red mesh auto-organizada entre nodos GNU/Linux bootables desde USB.
Cada nodo detecta redes mesh activas o crea la suya propia. El nodo con más
recursos se convierte automáticamente en **Master** y transmite música por
streaming a todos los nodos conectados.

---

## Entregables Completados ✅

### ✅ 1. Scripts del Agente Mesh (`scripts/mesh_agent.py`, `nixos/scripts/`)
- [x] Discovery UDP broadcast cada 2s
- [x] Escaneo WiFi / creación de AP (hostapd) / unión a redes
- [x] Elección de master basada en score (RAM + CPU + WiFi)
- [x] Re-elección periódica ante cambios de topología
- [x] Icecast2 + ffmpeg streaming automático en el Master
- [x] Client slave escucha stream del Master
- [x] API REST JSON (puerto 8000)
  - `GET /api/status` — estado completo del nodo
  - `GET /api/songs` — catálogo de canciones
  - `GET /api/nodes` — nodos visibles
  - `POST /api/force_song` — forzar canción específica
- [x] Catálogo SQLite con metadatos de canciones

### ✅ 2. Interfaz TUI (`scripts/mesh_tui.py`)
- [x] TUI con curses mostrando todos los indicadores
- [x] Tasa de transmisión (TX bitrate)
- [x] Nodos visibles con detalle
- [x] Nivel de señal (RSSI)
- [x] Modulación WiFi
- [x] Canciones locales (25 por nodo)
- [x] Canción actual en streaming
- [x] Log de actividad

### ✅ 3. Interfaz Web (`scripts/webui.py`)
- [x] Dashboard Flask con auto-refresh cada 3s
- [x] Tarjeta de nodo: ID, rol, red, modulación, señal, bitrate
- [x] Tabla de nodos visibles con señal y rol
- [x] Lista de canciones locales
- [x] Indicadores de color (🟢🟡🔴 para señal)
- [x] Acceso desde cualquier navegador

### ✅ 4. Configuración NixOS (`nixos/flake.nix`, `nixos/configuration.nix`)
- [x] Flake.nix con nixpkgs nixos-24.11
- [x] configuration.nix con todos los paquetes necesarios
- [x] Base: installation-cd-minimal.nix (live CD)
- [x] Paquetes: python3, flask, hostapd, wpa_supplicant, icecast, ffmpeg, etc.
- [x] Servicios systemd: mesh-agent, mesh-webui
- [x] Allow unfree packages (para ffmpeg-full)
- [x] MOTD con instrucciones
- [x] **La evaluación del flake funciona correctamente** ✅
- [x] Target: x86_64-linux (Intel/AMD)

### ✅ 5. Canciones (2420+ generadas, 1.2GB)
- [x] 2420 canciones sintetizadas con sox (`songs/raw/`)
- [x] 16 géneros × 12 mood combinations
- [x] Duraciones de 30-90 segundos
- [x] Script `download_songs.py` para descargar/regenerar
- [x] Script `gen_songs.sh` Docker para sox
- [x] Distribución: 25 canciones únicas por nodo × 80 nodos = 2000

### ✅ 6. Repositorio Git + GitHub
- [x] Repo inicializado
- [x] .gitignore configurado (excluye songs raw, output)
- [x] Commit inicial con toda la documentación y código
- [x] Push a GitHub: https://github.com/pabloflores465/network-mesh-iso

---

## Entregables Pendientes ❌

### ❌ 7. Construcción de la ISO
- [ ] **Build ISO bootable x86_64** → **BLOCKED: Docker tiene solo 3.8GB RAM**
  - El flake evalúa correctamente ✅
  - La configuración NixOS es válida ✅
  - El build falla por OOM en emulación x86_64 desde Mac ARM64
  - **Solución:** ejecutar `nix build` en:
    1. Máquinas Linux nativas x86_64 (recomendado)
    2. Mac con Docker configurado a 8GB+ RAM
    3. VM Linux con NixOS

### ❌ 8. Testing
- [ ] Boot en QEMU x86_64
- [ ] Simular 2-3 nodos
- [ ] Verificar mesh + streaming

---

## Cómo Construir la ISO (cuando tengas recursos suficientes)

### En NixOS Linux (recomendado):
```bash
cd nixos/
nix build .#nixosConfigurations.mesh-iso.config.system.build.isoImage
ls -l result/
```

### En cualquier Linux con Nix:
```bash
cd nixos/
nix --extra-experimental-features "nix-command flakes" \
  build .#nixosConfigurations.mesh-iso.config.system.build.isoImage
ls -l result/
```

### En macOS (requiere Docker con 8GB+ RAM):
```bash
docker build --platform linux/amd64 -t nix-builder -f Dockerfile.nix .
cd nixos/
docker run --platform linux/amd64 --security-opt seccomp=unconfined --rm \
  -v "$(pwd):/src" -w /src nix-builder \
  nix build .#nixosConfigurations.mesh-iso.config.system.build.isoImage \
  --extra-experimental-features "nix-command flakes" \
  --option sandbox false
```

---

## Arquitectura Final

```
┌─────────────┐     UDP Heartbeat      ┌─────────────┐
│  Node 001   │ ◄─────────────────────► │  Node 002   │
│  MASTER ⭐  │     WiFi (2.4GHz)       │   SLAVE     │
│ 25 songs    │     MeshMusic-xxxx       │ 25 songs    │
│ Icecast     │                         │ mpg123      │
│ Port 8080   │                         │ Port 8080   │
└─────────────┘                         └─────────────┘
       │                                       │
       │        ┌─────────────┐                │
       └───────►│  Node 003   │◄───────────────┘
                │   SLAVE     │
                │ 25 songs    │
                │ mpg123      │
                └─────────────┘

Si Node 003 se aleja → crea su propia red MeshMusic-yyyy
con su propio master, aceptando nodos cercanos.
```

## Indicadores por Nodo

| Indicador | TUI | Web UI | API |
|-----------|-----|--------|-----|
| Tasa transmisión | ✅ | ✅ | ✅ `tx_bitrate_kbps` |
| Nodos visibles | ✅ | ✅ | ✅ `/api/nodes` |
| Señal RSSI | ✅ | ✅ | ✅ `signal_dbm` |
| Modulación | ✅ | ✅ | ✅ `modulation` |
| Canciones locales | ✅ | ✅ | ✅ `/api/songs` |
| Canción actual | ✅ | ✅ | ✅ `current_song` |
