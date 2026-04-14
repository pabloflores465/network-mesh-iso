#!/usr/bin/env python3
"""
Mesh Agent - NODO PRINCIPAL
Maneja escaneo WiFi, creación/unión a redes mesh, detección de nodos,
heartbeats UDP, elección de master, y streaming.
"""

import os, sys, json, time, socket, uuid, struct, threading, subprocess, signal, re, sqlite3
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# ======================== CONFIG ========================
MESH_PORT = 8001
API_PORT = 8000
HEARTBEAT_INTERVAL = 2
SCAN_INTERVAL = 10
ELECTION_INTERVAL = 15
NODE_ID = str(uuid.uuid4())[:8]
AP_SSID_PREFIX = "MeshMusic"
AP_PASSWORD = "meshmusic123"
AP_CHANNEL = 6
SONGS_DIR = "/opt/mesh/songs/local"
SONGS_DB = "/var/lib/mesh/song_catalog.db"
STATE_FILE = "/var/lib/mesh/node_state.json"
MASTER_URL_FMT = "http://{}:{}/api"
DATA_DIR = Path("/var/lib/mesh")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ======================== GLOBALS ========================
state = {
    "node_id": NODE_ID,
    "is_master": False,
    "current_network": None,
    "visible_nodes": [],
    "master_ip": None,
    "master_node_id": None,
    "current_song": None,
    "resources": {},
    "modulation": "unknown",
    "signal_dbm": -99,
    "tx_bitrate": 0,
    "start_time": time.time()
}

# ======================== SONG CATALOG ========================
class SongCatalog:
    def __init__(self):
        self.db = sqlite3.connect(SONGS_DB, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        self.db.execute('''CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY, title TEXT, artist TEXT,
            file_path TEXT, file_hash TEXT, duration_sec REAL,
            size_bytes INT, source_node TEXT DEFAULT 'self',
            ts REAL DEFAULT (strftime('%s','now')))''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS node_registry (
            node_id TEXT PRIMARY KEY, ip TEXT, hostname TEXT,
            resources TEXT, songs_count INT DEFAULT 0,
            last_seen REAL DEFAULT (strftime('%s','now')))''')
        self.db.commit()

    def add_local(self, fp):
        try:
            import hashlib
            from pathlib import Path as PP
            p = PP(fp)
            if not p.exists():
                return
            with open(fp, 'rb') as f:
                h = hashlib.md5(f.read()[:8192]).hexdigest()[:12]
            title, artist, dur = p.stem, "Unknown", None
            try:
                r = subprocess.run(['ffprobe','-v','quiet','-print_format','json',
                    '-show_format', fp], capture_output=True, text=True, timeout=10)
                m = json.loads(r.stdout)
                t = m.get('format',{}).get('tags',{})
                title = t.get('title', p.stem)
                artist = t.get('artist', 'Unknown')
                dur = float(m.get('format',{}).get('duration', 0))
            except:
                pass
            self.db.execute('INSERT OR REPLACE INTO songs (title,artist,file_path,file_hash,duration_sec,size_bytes,source_node) VALUES (?,?,?,?,?,?,\'self\')',
                (title, artist, str(fp), h, dur, p.stat().st_size))
            self.db.commit()
        except Exception as e:
            print(f"[SONG] Error adding {fp}: {e}")

    def scan_local(self, d):
        if not os.path.exists(d):
            return
        for f in os.listdir(d):
            if f.lower().endswith(('.mp3','.ogg','.flac','.wav')):
                self.add_local(os.path.join(d, f))
        self.db.execute("UPDATE node_registry SET songs_count=(SELECT count(*) FROM songs WHERE source_node='self') WHERE node_id=?", (NODE_ID,))
        self.db.commit()

    def local_songs(self):
        return [dict(r) for r in self.db.execute("SELECT id,title,artist,duration_sec FROM songs WHERE source_node='self' ORDER BY title").fetchall()]

    def all_songs(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM songs ORDER BY source_node,title").fetchall()]

    def register_node(self, nid, ip, host, res, cnt):
        self.db.execute('INSERT OR REPLACE INTO node_registry (node_id,ip,hostname,resources,songs_count,last_seen) VALUES (?,?,?,?,?,strftime(\'%s\',\'now\'))',
            (nid, ip, host, json.dumps(res), cnt))
        self.db.commit()

    def registered_nodes(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM node_registry ORDER BY last_seen DESC").fetchall()]

    def master_candidate(self):
        nodes = self.registered_nodes()
        score = lambda n: (json.loads(n['resources']).get('ram_mb',512)/1024.0*2) + (json.loads(n['resources']).get('cpu_cores',1)*3) + json.loads(n['resources']).get('wifi_speed_mbps',54) if True else 0
        if not nodes:
            return NODE_ID
        best = max(nodes, key=score)
        return best['node_id']

catalog = SongCatalog()

# ======================== SYSTEM RESOURCES ========================
def get_resources():
    res = {"node_id": NODE_ID, "cpu_cores": os.cpu_count() or 1, "ram_mb": 512, "wifi_speed_mbps": 0, "hostname": socket.gethostname(), "ip": get_ip()}
    try:
        with open('/proc/meminfo') as f:
            for l in f:
                if l.startswith('MemTotal:'):
                    res['ram_mb'] = int(l.split()[1]) // 1024
    except: pass
    # WiFi
    try:
        r = subprocess.run(['iw','dev'], capture_output=True, text=True, timeout=5)
        iface = None
        for l in r.stdout.split('\n'):
            if 'Interface' in l:
                iface = l.split()[1]; break
        if iface:
            r2 = subprocess.run(['iw','dev',iface,'link'], capture_output=True, text=True, timeout=5)
            lk = r2.stdout
            sm = re.search(r'signal:\s+(-?\d+)\s+dBm', lk)
            state['signal_dbm'] = int(sm.group(1)) if sm else -99
            bm = re.search(r'tx bitrate:\s+([\d.]+)\s+(\w+)', lk)
            if bm:
                state['tx_bitrate'] = float(bm.group(1))
            fm = re.search(r'freq:\s+(\d+)', lk)
            if fm:
                fr = int(fm.group(1))
                state['modulation'] = '802.11a/n/ac (5GHz)' if fr >= 5000 else '802.11b/g/n (2.4GHz)'
                res['wifi_speed_mbps'] = float(bm.group(1)) if bm else 54
            sm2 = re.search(r'SSID:\s+(.+)', lk)
            if sm2:
                state['current_network'] = sm2.group(1).strip()
    except Exception as e:
        state['modulation'] = str(e)[:50]
    return res

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        return ip
    except:
        return "127.0.0.1"

# ======================== MESH DISCOVERY (UDP broadcast) ========================
class MeshDiscovery:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.settimeout(1)
        self.nodes = {}  # ip -> info
        self.lock = threading.Lock()

    def send_heartbeat(self):
        """Envía heartbeat con info del nodo"""
        msg = json.dumps({
            "type": "heartbeat",
            "node_id": NODE_ID,
            "is_master": state["is_master"],
            "ip": get_ip(),
            "resources": state["resources"],
            "songs_count": len(catalog.local_songs()),
            "current_song": state["current_song"],
            "modulation": state["modulation"],
            "signal_dbm": state["signal_dbm"],
            "tx_bitrate": state["tx_bitrate"],
            "network": state["current_network"]
        }).encode()
        try:
            self.sock.sendto(msg, ('<broadcast>', MESH_PORT))
            for ip in list(self.nodes.keys()):
                if ip != get_ip():
                    self.sock.sendto(msg, (ip, MESH_PORT))
        except:
            pass

    def listen(self):
        """Escucha heartbeats de otros nodos"""
        try:
            self.sock.bind(('', MESH_PORT))
        except:
            pass
        while True:
            try:
                data, addr = self.sock.recvfrom(4096)
                msg = json.loads(data)
                if msg.get("type") == "heartbeat" and msg["node_id"] != NODE_ID:
                    ip = addr[0]
                    with self.lock:
                        self.nodes[ip] = {
                            "ip": ip,
                            "node_id": msg["node_id"],
                            "is_master": msg.get("is_master", False),
                            "resources": msg.get("resources", {}),
                            "songs_count": msg.get("songs_count", 0),
                            "current_song": msg.get("current_song"),
                            "modulation": msg.get("modulation", "unknown"),
                            "signal_dbm": msg.get("signal_dbm", -99),
                            "tx_bitrate": msg.get("tx_bitrate", 0),
                            "network": msg.get("network"),
                            "last_seen": time.time()
                        }
                    # Register in catalog
                    catalog.register_node(msg["node_id"], ip,
                        msg.get("resources",{}).get("hostname","?"),
                        msg.get("resources",{}), msg.get("songs_count",0))
            except:
                pass

    def get_active_nodes(self):
        with self.lock:
            now = time.time()
            return {ip: info for ip, info in self.nodes.items() if now - info["last_seen"] < 30}

discovery = MeshDiscovery()

# ======================== MASTER ELECTION ========================
def run_election():
    """Ejecuta elección de master basada en recursos"""
    active = discovery.get_active_nodes()
    candidates = [(NODE_ID, state["resources"])]
    for ip, info in active.items():
        candidates.append((info["node_id"], info.get("resources", {})))

    def score(res):
        ram = res.get("ram_mb", 512) / 1024.0
        cpu = res.get("cpu_cores", 1)
        wifi = res.get("wifi_speed_mbps", 54)
        return (ram * 2) + (cpu * 3) + wifi

    best_id, best_res = max(candidates, key=lambda c: score(c[1]))

    if best_id == NODE_ID and not state["is_master"]:
        print(f"[ELECTION] I AM THE NEW MASTER (score: {score(state['resources']):.1f})")
        become_master()
    elif best_id != NODE_ID and best_id != state.get("master_node_id"):
        print(f"[ELECTION] New master: {best_id}")
        become_slave(best_id)

def become_master():
    state["is_master"] = True
    state["master_node_id"] = NODE_ID
    state["master_ip"] = get_ip()
    save_state()

def become_slave(master_id):
    state["is_master"] = False
    state["master_node_id"] = master_id
    # Find master IP
    for ip, info in discovery.get_active_nodes().items():
        if info["node_id"] == master_id:
            state["master_ip"] = ip
            break
    save_state()

def save_state():
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except:
        pass

# ======================== STREAMING ========================
class MusicStreamer:
    def __init__(self):
        self.current_process = None
        self._running = True
        self._forced_song = None

    def start_stream(self):
        """En master: inicia Icecast + fuente"""
        if not state["is_master"]:
            return
        try:
            # Config icecast
            ice_cfg = f"""<icecast>
<limits><clients>100</clients><sources>2</sources></limits>
<authentication><source-password>hackme</source-password></authentication>
<hostname>{get_ip()}</hostname>
<listen-address><port>8000</port></listen-address>
<fileserve>1</fileserve>
</icecast>"""
            with open('/tmp/icecast.xml', 'w') as f:
                f.write(ice_cfg)
            
            # Start icecast
            subprocess.run(['icecast', '-c', '/tmp/icecast.xml', '-b'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Start playlist rotation
            t = threading.Thread(target=self._playlist_loop, daemon=True)
            t.start()
            print("[STREAM] Icecast started + playlist rotation active")
        except Exception as e:
            print(f"[STREAM] Error: {e}")

    def _playlist_loop(self):
        """Rota canciones aleatoriamente"""
        import random
        while self._running:
            songs = [s for s in catalog.all_songs() if s.get('file_path') and os.path.exists(s['file_path'])]
            if songs and self._running:
                if self._forced_song:
                    song = next((s for s in songs if s['id'] == self._forced_song), None)
                    self._forced_song = None
                    if not song:
                        song = random.choice(songs)
                else:
                    song = random.choice(songs)
                
                state["current_song"] = f"{song['artist']} - {song['title']}"
                print(f"[STREAM] Playing: {state['current_song']}")
                
                # Stream with ffmpeg -> icecast
                try:
                    cmd = [
                        'ffmpeg', '-re', '-i', song['file_path'],
                        '-c:a', 'libmp3lame', '-b:a', '128k',
                        '-content_type', 'audio/mpeg',
                        '-f', 'mp3',
                        f'icecast://source:hackme@{get_ip()}:8000/mesh'
                    ]
                    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    # Wait until it finishes or forced change
                    try:
                        p.wait(timeout=300)
                    except subprocess.TimeoutExpired:
                        p.terminate()
                except:
                    time.sleep(5)
            else:
                time.sleep(5)

    def force_song(self, song_id):
        """Forzar canción específica"""
        self._forced_song = int(song_id)
        if self.current_process:
            self.current_process.terminate()

streamer = MusicStreamer()

# ======================== SLAVE STREAM LISTENER ========================
def listen_stream():
    """En slave: escucha stream del master"""
    while True:
        if state["is_master"] or not state["master_ip"]:
            time.sleep(5)
            continue
        try:
            url = f"http://{state['master_ip']}:8000/mesh"
            # Check if stream is available
            r = subprocess.run(['curl', '-sI', '--max-time', '3', url],
                capture_output=True, text=True)
            if r.returncode == 0:
                print(f"[CLIENT] Listening to stream from {state['master_ip']}")
                # Play with mpg123 or ffmpeg
                subprocess.run(['mpg123', '-@', url], 
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    cwd='/tmp')
        except:
            pass
        time.sleep(10)

# ======================== HTTP API ========================
class APIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silent

    def do_GET(self):
        if self.path == '/api/status':
            self._json({
                "node_id": NODE_ID,
                "is_master": state["is_master"],
                "current_network": state["current_network"],
                "visible_nodes": list(discovery.get_active_nodes().keys()),
                "node_details": discovery.get_active_nodes(),
                "signal_dbm": state["signal_dbm"],
                "modulation": state["modulation"],
                "tx_bitrate_kbps": state["tx_bitrate"],
                "local_songs": catalog.local_songs(),
                "current_song": state["current_song"],
                "resources": state["resources"],
                "uptime": time.time() - state["start_time"],
                "master_node_id": state.get("master_node_id")
            })
        elif self.path == '/api/songs':
            self._json({"songs": catalog.all_songs()})
        elif self.path == '/api/nodes':
            active = discovery.get_active_nodes()
            self._json({"nodes": list(active.values()), "count": len(active)})
        elif self.path == '/' or self.path == '/index.html':
            self._html(HTML_DASHBOARD)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/force_song':
            length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(length)) if length else {}
            song_id = data.get('song_id')
            if song_id and state["is_master"]:
                streamer.force_song(song_id)
                self._json({"status": "ok", "song_id": song_id})
            else:
                self._json({"status": "error", "reason": "not master or no song_id"})
        elif self.path == '/api/reconnect':
            # Force re-scan and re-election
            self._json({"status": "ok"})
        else:
            self.send_response(404)
            self.end_headers()

    def _json(self, data):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

def start_api():
    server = HTTPServer(('0.0.0.0', API_PORT), APIHandler)
    print(f"[API] Web UI running at http://0.0.0.0:{API_PORT}")
    server.serve_forever()

# ======================== TTY TUI ========================
HTML_DASHBOARD = """<!DOCTYPE html>
<html><head><title>Mesh Music Node</title>
<meta http-equiv="refresh" content="5">
<style>
body{font-family:monospace;background:#0a0a0a;color:#0f0;padding:20px}
.card{border:1px solid #333;padding:15px;margin:10px 0;border-radius:4px}
.card h2{color:#0ff;margin:0 0 10px}
.green{color:#0f0}.red{color:#f00}.yellow{color:#ff0}.white{color:#fff}
table{width:100%;border-collapse:collapse}
td,th{border:1px solid #333;padding:5px 10px;text-align:left}
th{color:#0ff}
</style></head><body>
<h1>🎵 Mesh Music Node</h1>
<p>Auto-refresh: every 5s | <a href="/api/status">JSON API</a></p>
<div id="content"><pre>Loading...</pre></div>
<script>
setInterval(async()=>{
  const r=await fetch('/api/status');
  const d=await r.json();
  let h=`<div class="card"><h2>🖥️ This Node</h2>
  <p>ID: <span class="green">${d.node_id}</span></p>
  <p>Master: <span class="${d.is_master?'green':'yellow'}">${d.is_master?'YES (I am master)':'NO'}</span></p>
  <p>Network: <span class="white">${d.current_network||'None'}</span></p>
  <p>Modulation: <span class="yellow">${d.modulation}</span></p>
  <p>Signal: ${d.signal_dbm} dBm | Bitrate: ${d.tx_bitrate_kbps} kbps</p>
  <p>Current Song: <span class="green">${d.current_song||'N/A'}</span></p>
  <p>Uptime: ${(d.uptime/60).toFixed(1)} min</p>
  <p>CPU: ${d.resources.cpu_cores||1} cores | RAM: ${d.resources.ram_mb||512} MB</p></div>`;
  
  h+=`<div class="card"><h2>👁️ Visible Nodes (${Object.keys(d.node_details||{}).length})</h2>`;
  const nodes=d.node_details||{};
  if(Object.keys(nodes).length===0) h+='<p class="red">No nodes visible</p>';
  else{h+='<table><tr><th>IP</th><th>Node ID</th><th>Songs</th><th>Master</th><th>RSSI</th></tr>';
  for(const[ip,n]of Object.entries(nodes)){
    h+=`<tr><td>${ip}</td><td>${n.node_id}</td><td>${n.songs_count}</td><td>${n.is_master?'⭐':' '}</td><td>${n.signal_dbm}dBm</td></tr>`;
  }h+='</table>';}`;
  h+='</div>';
  
  h+=`<div class="card"><h2>🎵 Local Songs (${(d.local_songs||[]).length})</h2>`;
  const songs=d.local_songs||[];
  if(songs.length===0) h+='<p>No local songs</p>';
  else{songs.forEach(s=>{h+=`<p>🎵 ${s.artist} - ${s.title}</p>`});}`;
  h+='</div>';
  document.getElementById('content').innerHTML=h;
},5000);
</script></body></html>"""

# ======================== MAIN ========================
def main():
    print("=" * 50)
    print("🎵  NETWORK MUSIC MESH - Node Agent")
    print(f"    Node ID: {NODE_ID}")
    print(f"    IP: {get_ip()}")
    print("=" * 50)

    # Scan local songs
    catalog.scan_local(SONGS_DIR)
    print(f"[INIT] Local songs cataloged: {len(catalog.local_songs())}")

    # Start discovery listener (background)
    t_listen = threading.Thread(target=discovery.listen, daemon=True)
    t_listen.start()

    # Start heartbeat sender (background)
    def heartbeat_loop():
        while True:
            discovery.send_heartbeat()
            time.sleep(HEARTBEAT_INTERVAL)
    t_hb = threading.Thread(target=heartbeat_loop, daemon=True)
    t_hb.start()

    # Start API server (background)
    t_api = threading.Thread(target=start_api, daemon=True)
    t_api.start()

    # Start stream listener (background) - for slave nodes
    t_client = threading.Thread(target=listen_stream, daemon=True)
    t_client.start()

    # Main loop: scan, election
    print("[INIT] Starting mesh scanning and election...")
    scan_count = 0
    while True:
        scan_count += 1
        state["resources"] = get_resources()
        visible = discovery.get_active_nodes()
        state["visible_nodes"] = list(visible.keys())

        # Log periodically
        if scan_count % 5 == 0:
            print(f"\n[TICK] Nodes visible: {len(visible)} | Master: {state['is_master']} | Network: {state['current_network']}")
            for ip, info in visible.items():
                print(f"  -> {ip} | {info['node_id']} | Songs: {info['songs_count']} | Signal: {info['signal_dbm']}dBm | {'⭐' if info['is_master'] else ''}")

        # Run election periodically
        if scan_count % (ELECTION_INTERVAL // HEARTBEAT_INTERVAL) == 0:
            run_election()
            if state["is_master"] and not streamer.current_process:
                streamer.start_stream()

        # Check if we lost connection to network
        if state["current_network"] and len(visible) == 0 and state["is_master"]:
            print(f"[MESH] Lost network '{state['current_network']}' - staying as master of orphaned network")

        time.sleep(SCAN_INTERVAL)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    signal.signal(signal.SIGINT, lambda s,f: sys.exit(0))
    main()
