import os, json, time, threading, subprocess, re
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# Estado en caché
state = {'status': None, 'last_update': 0}
API_URL = "http://localhost:8000"

def fetch_status():
    try:
        r = subprocess.run(['curl', '-sf', '--max-time', '3', f'{API_URL}/api/status'],
            capture_output=True, text=True)
        if r.returncode == 0:
            state['status'] = json.loads(r.stdout)
            state['last_update'] = time.time()
    except:
        pass

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api')
def api():
    if state['status']:
        return jsonify(state['status'])
    return jsonify({'error': 'Agent not responding'})

@app.route('/api/force_song', methods=['POST'])
def force_song():
    song_id = request.json.get('song_id') if request.is_json else request.form.get('song_id')
    if song_id:
        subprocess.run(['curl', '-sf', '-X', 'POST', '-H',
            'Content-Type: application/json', '-d',
            json.dumps({'song_id': song_id}),
            f'{API_URL}/api/force_song'])
    return jsonify({'status': 'ok', 'song_id': song_id})

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>🎵 Mesh Music Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', monospace; background: #0d1117; color: #c9d1d9; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #58a6ff; margin-bottom: 5px; font-size: 1.8em; }
        .subtitle { color: #8b949e; margin-bottom: 20px; font-size: 0.9em; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 15px; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }
        .card h2 { color: #58a6ff; font-size: 1.1em; margin-bottom: 12px; border-bottom: 1px solid #21262d; padding-bottom: 8px; }
        .stat { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #21262d22; }
        .stat:last-child { border-bottom: none; }
        .stat-label { color: #8b949e; }
        .stat-value { color: #3fb950; font-weight: bold; }
        .stat-value.yellow { color: #d29922; }
        .stat-value.red { color: #f85149; }
        .master-badge { background: #f0883e; color: #000; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; font-weight: bold; }
        .slave-badge { background: #8b949e; color: #000; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 8px; border-bottom: 1px solid #21262d; }
        th { color: #8b949e; font-size: 0.8em; text-transform: uppercase; }
        .signal-good { color: #3fb950; }
        .signal-mid { color: #d29922; }
        .signal-bad { color: #f85149; }
        .song-list { max-height: 300px; overflow-y: auto; }
        .song-item { padding: 4px 0; }
        .song-item:hover { background: #21262d22; }
        .btn { background: #238636; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; margin: 5px 0; }
        .btn:hover { background: #2ea043; }
        .btn-red { background: #da3633; }
        .btn-red:hover { background: #b32425; }
        .loading { text-align: center; padding: 40px; color: #8b949e; }
        #last_update { color: #484f58; font-size: 0.8em; }
    </style>
</head>
<body>
<div class="container">
    <h1>🎵 Network Music Mesh</h1>
    <p class="subtitle">Auto-refresh cada 3s | <a href="/api" target="_blank">JSON API</a> | <span id="last_update"></span></p>
    <div id="content">
        <pre class="loading">Cargando datos del nodo...</pre>
    </div>
</div>
<script>
async function update() {
    try {
        const r = await fetch('/api');
        const d = await r.json();
        if (d.node_id) render(d);
    } catch(e) {
        document.getElementById('content').innerHTML = '<div class="card"><h2>⚠️ Error</h2><p>No se puede conectar al agent mesh</p></div>';
    }
}

function render(d) {
    const isMaster = d.is_master;
    const masterBadge = isMaster ? '<span class="master-badge">MASTER</span>' : '<span class="slave-badge">SLAVE</span>';
    const uptime = Math.floor(d.uptime / 60);
    const res = d.resources || {};
    
    let sigClass = d.signal_dbm > -50 ? 'signal-good' : d.signal_dbm > -70 ? 'signal-mid' : 'signal-bad';
    let sigLabel = d.signal_dbm > -50 ? '🟢' : d.signal_dbm > -70 ? '🟡' : '🔴';
    
    let html = `<div class="grid">
    <!-- Este Nodo -->
    <div class="card">
        <h2>🖥️ Este Nodo</h2>
        <div class="stat"><span class="stat-label">ID</span><span class="stat-value">${d.node_id}</span></div>
        <div class="stat"><span class="stat-label">Rol</span><span class="stat-value">${masterBadge}</span></div>
        <div class="stat"><span class="stat-label">Red Actual</span><span class="stat-value">${d.current_network || 'Ninguna'}</span></div>
        <div class="stat"><span class="stat-label">Modulación</span><span class="stat-value yellow">${d.modulation}</span></div>
        <div class="stat"><span class="stat-label">Señal (RSSI)</span><span class="stat-value ${sigClass}">${sigLabel} ${d.signal_dbm} dBm</span></div>
        <div class="stat"><span class="stat-label">TX Bitrate</span><span class="stat-value">${d.tx_bitrate_kbps} kbps</span></div>
        <div class="stat"><span class="stat-label">Uptime</span><span class="stat-value">${uptime} min</span></div>
        <div class="stat"><span class="stat-label">Canción Streaming</span><span class="stat-value">${d.current_song || 'N/A'}</span></div>
    </div>
    
    <!-- Recursos -->
    <div class="card">
        <h2>⚡ Recursos del Sistema</h2>
        <div class="stat"><span class="stat-label">CPU Cores</span><span class="stat-value">${res.cpu_cores || 'N/A'}</span></div>
        <div class="stat"><span class="stat-label">RAM</span><span class="stat-value">${res.ram_mb || 'N/A'} MB</span></div>
        <div class="stat"><span class="stat-label">Velocidad WiFi</span><span class="stat-value">${res.wifi_speed_mbps || 0} Mbps</span></div>
        <div class="stat"><span class="stat-label">Hostname</span><span class="stat-value">${res.hostname || 'N/A'}</span></div>
        <div class="stat"><span class="stat-label">IP</span><span class="stat-value">${res.ip || 'N/A'}</span></div>
    </div>
    
    <!-- Nodos Visibles -->
    <div class="card">
        <h2>👁️ Nodos Visibles (${Object.keys(d.node_details || {}).length})</h2>`;
    
    const nodes = d.node_details || {};
    if (Object.keys(nodes).length === 0) {
        html += '<p style="color:#8b949e">Ningún nodo visible en la red</p>';
    } else {
        html += '<table><tr><th>IP</th><th>Nodo</th><th>Canciones</th><th>Rol</th><th>Señal</th></tr>';
        for (const [ip, n] of Object.entries(nodes)) {
            const sClass = (n.signal_dbm || -99) > -50 ? 'signal-good' : (n.signal_dbm || -99) > -70 ? 'signal-mid' : 'signal-bad';
            const isM = n.is_master ? '👑 Master' : 'Slave';
            html += `<tr>
                <td>${ip}</td>
                <td>${n.node_id}</td>
                <td>${n.songs_count}</td>
                <td>${isM}</td>
                <td class="${sClass}">${n.signal_dbm || -99} dBm</td>
            </tr>`;
        }
        html += '</table>';
    }
    html += '</div>';
    
    // Canciones Locales
    html += `<div class="card">
        <h2>🎵 Canciones Locales (${(d.local_songs || []).length})</h2>
        <div class="song-list">`;
    
    const songs = d.local_songs || [];
    if (songs.length === 0) {
        html += '<p style="color:#8b949e">No hay canciones locales</p>';
    } else {
        songs.forEach((s, i) => {
            html += `<div class="song-item">${i+1}. ${s.artist} - ${s.title} <span style="color:#484f58">(${s.duration_sec || '?'}s)</span></div>`;
        });
    }
    
    html += '</div></div></div>';
    document.getElementById('content').innerHTML = html;
    document.getElementById('last_update').textContent = 'Última actualización: ' + new Date().toLocaleTimeString('es-MX');
}

update();
setInterval(update, 3000);
</script>
</body>
</html>'''

if __name__ == '__main__':
    # Iniciar fetch de status
    t = threading.Thread(target=lambda: [fetch_status() or time.sleep(3) for _ in iter(int, 1)], daemon=True)
    t.start()
    
    print("🎵 Mesh Music Web UI starting on :8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
