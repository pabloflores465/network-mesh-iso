# 🎵 Network Music Mesh - NixOS ISO

## Descripción
Sistema de red mesh auto-organizada entre nodos GNU/Linux bootables desde USB.
Cada nodo bootear desde una USB con NixOS, detecta redes mesh activas en WiFi,
se une a la más cercana o crea su propia red si está aislado. El nodo con más
recursos (RAM + CPU) se convierte automáticamente en **Master** y transmite
música por streaming (Icecast) a todos los nodos conectados.

## Cómo Funciona

### Flujo de Arranque
1. **Boot USB** → El nodo arranca con NixOS personalizado
2. **mesh-setup.service** → Genera un ID único de nodo basado en MAC
3. **mesh-agent.service** → Inicia el agente principal:
   - Escanea WiFi buscando redes "MeshMusic*"
   - Si encuentra una → se une como **slave**
   - Si NO encuentra → crea su propio punto de acceso WiFi → se convierte en **master**
4. **Descubrimiento** → Heartbeats UDP cada 2 segundos descubren nodos vecinos
5. **Elección de Master** → Cada 15s se evalúa: el nodo con más recursos gana
6. **Streaming** → El Master reproduce canciones de Icecast; los slaves escuchan

### Si un nodo se aleja
- Pierde conexión con el master → se queda sin red
- Crea su propia red MeshMusic independiente
- Acepta otros nodos slaves que estén en su rango
- Cada "isla" tiene su propio master

## Indicadores por Nodo

Cada nodo muestra (en TUI y Web UI):
- 📡 **Tasa de transmisión activa** (kbitrate del stream)
- 👁️ **Nodos que ve activamente** (lista de vecinos)
- 📶 **Nivel de señal RSSI** con el que ve a cada nodo
- 📻 **Modulación WiFi** utilizada (802.11a/n/ac o 802.11b/g/n)
- 🎵 **Canciones locales** (25 canciones únicas del nodo)
- ▶️ **Canción actual en streaming**

## Interfaz de Control

### TUI (Terminal)
```bash
python3 mesh_tui.py
```
- Muestra estado del nodo, nodos visibles, canciones, log de actividad
- Teclas: `q` = salir, `r` = refrescar

### Web UI (Navegador)
Accede a `http://<IP-DEL-NODO>:8080`
- Dashboard en tiempo real con auto-refresh cada 3s
- Muestra todos los indicadores
- Permite forzar canción específica (POST /api/force_song)

### API REST (JSON)
- `GET /api/status` — Estado completo del nodo
- `GET /api/songs` — Catálogo de todas las canciones
- `GET /api/nodes` — Nodos visibles con detalles
- `POST /api/force_song` — Forzar canción al stream `{"song_id": 42}`

## Estructura

```
network_iso/
├── PLAN.md                          # Plan de implementación (tachado ✅)
├── README.md                        # Este archivo
├── nixos/
│   ├── flake.nix                    # Flake con config y scripts embebidos
│   ├── configuration.nix            # Configuración NixOS completa
│   └── hardware-configuration.nix   # Hardware genérico x86_64
├── scripts/
│   ├── mesh_agent.py                # 🤖 Agente principal (mesh + master + stream)
│   ├── mesh_tui.py                  # 🖥️ Interfaz TUI en la terminal
│   └── webui.py                     # 🌐 Dashboard Web (Flask + auto-refresh)
├── songs/
│   └── raw/                         # 🎵 2000+ canciones sintetizadas (~1.2GB)
├── build.sh                         # Script de build de la ISO
├── Dockerfile.nix                   # Docker image para Nix builder
└── build_iso.sh                     # Build ISO con Docker
```

## Construir la ISO

### En NixOS Linux (recomendado):
```bash
cd nixos/
nix build .#nixosConfigurations.mesh-iso.config.system.build.isoImage
ls -l result/*.iso
```

### En macOS con Docker (emulación x86_64, ~2 horas):
```bash
docker build --platform linux/amd64 -t nix-builder -f Dockerfile.nix .
TMP=$(mktemp -d); cp nixos/* "$TMP/"
docker run --platform linux/amd64 --rm -v "$TMP:/src" nix-builder \
  nix build /src#nixosConfigurations.mesh-iso.config.system.build.isoImage
```

### Escribir a USB:
```bash
sudo dd if=result/iso/*.iso of=/dev/diskX bs=4m conv=sync
# o usar Etcher / Ventoy
```

## Generar Canciones

Las 2000+ canciones sintetizadas se generan con `sox` en Docker:

```bash
docker run --platform linux/amd64 --rm \
  -v $(pwd)/songs/raw:/songs/raw \
  -w /songs/raw alpine \
  sh -c "apk add sox && for i in $(seq 0 1999); do
    sox -n -r 8000 -c 1 track_$(printf '%04d' $i).wav synth 60 sine $((80+i*7%500)); done"
```

## Puertos

| Puerto | Servicio |
|--------|----------|
| 22     | SSH |
| 8000   | Icecast + API REST |
| 8001   | Heartbeat UDP (descubrimiento mesh) |
| 8080   | Web UI Dashboard |
| 5353   | mDNS/Avahi |

## WiFi Config

- **SSID**: `MeshMusic-<NODO_ID>`
- **Password**: `meshmusic123`
- **Canal**: 6 (2.4GHz)

## Notas

- El master selecciona canciones **aleatoriamente** de todo el catálogo distribuido
- Se puede forzar canción específica vía `curl -X POST -d '{"song_id": 42}' http://<MASTER>:8000/api/force_song`
- Cada nodo tiene su propio ID derivado de la dirección MAC
- La elección de master es automática basada en recursos (RAM×2 + CPU×3 + WiFi)
