#!/usr/bin/env python3
"""
TUI para Network Music Mesh Node
Muestra indicadores en tiempo real usando curses.
"""

import curses, os, sys, json, time, threading, signal, subprocess
from datetime import datetime
from pathlib import Path

# ============================
# CONFIG
# ============================
API_BASE = "http://localhost:8000"
STATE_FILE = "/var/lib/mesh/node_state.json"
LOG_FILE = "/var/lib/mesh/mesh.log"

# ============================
# STATUS CACHE
# ============================
cache = {
    'status': None,
    'nodes': {},
    'songs': [],
    'last_update': 0,
    'log_lines': [],
    'error': None
}

def fetch_status():
    """Obtiene status del agente local"""
    try:
        r = subprocess.run(['curl', '-s', '--max-time', '3', f'{API_BASE}/api/status'],
            capture_output=True, text=True)
        if r.returncode == 0:
            data = json.loads(r.stdout)
            cache['status'] = data
            cache['last_update'] = time.time()
            cache['error'] = None
            
            # Guardar log
            ts = datetime.now().strftime('%H:%M:%S')
            line = f"{ts} | {'MASTER' if data.get('is_master') else 'SLAVE'}"
            nodes = data.get('node_details', {})
            line += f" | Nodes: {len(nodes)}"
            line += f" | Song: {data.get('current_song', 'N/A')}"
            cache['log_lines'].append(line)
            if len(cache['log_lines']) > 50:
                cache['log_lines'] = cache['log_lines'][-50:]
        else:
            cache['error'] = f"curl failed: {r.stderr[:100]}"
    except Exception as e:
        cache['error'] = str(e)

def api_loop():
    while True:
        fetch_status()
        time.sleep(3)

# ============================
# TUI
# ============================
def draw_header(stdscr, y, data):
    stdscr.attron(curses.color_pair(1))
    title = "🎵 NETWORK MUSIC MESH - Node TUI"
    stdscr.addstr(y, 0, "=" * curses.COLS)
    stdscr.addstr(y+1, 2, f" {title}")
    stdscr.addstr(y+2, 0, "=" * curses.COLS)
    stdscr.attroff(curses.color_pair(1))

def draw_node_info(stdscr, y, data):
    y += 4
    y = max(y, 4)
    stdscr.attron(curses.color_pair(3))
    stdscr.addstr(y, 1, "🖥️ THIS NODE")
    stdscr.attroff(curses.color_pair(3))
    
    lines = [
        f"  Node ID:     {data.get('node_id', 'N/A')}",
        f"  Master:      {'⚡ YES (me)' if data.get('is_master') else '❌ NO'}",
        f"  Network:     {data.get('current_network', 'None')}",
        f"  Modulation:  {data.get('modulation', 'unknown')}",
        f"  Signal:      {data.get('signal_dbm', -99)} dBm",
        f"  TX Bitrate:  {data.get('tx_bitrate_kbps', 0)} kbps",
        f"  CPU Cores:   {data.get('resources', {}).get('cpu_cores', 1)}",
        f"  RAM:         {data.get('resources', {}).get('ram_mb', 512)} MB",
        f"  Current Song:{data.get('current_song', 'N/A')}",
        f"  Uptime:      {data.get('uptime', 0)/60:.1f} min",
    ]
    for i, line in enumerate(lines):
        stdscr.addstr(y+2+i, 2, line)

def draw_nodes(stdscr, y, data):
    y += 4
    y += 12  # after node info
    height, width = stdscr.getmaxyx()
    nodes = data.get('node_details', {})
    
    stdscr.attron(curses.color_pair(4))
    stdscr.addstr(y, 1, f"👁️ VISIBLE NODES ({len(nodes)})")
    stdscr.attroff(curses.color_pair(4))
    
    if not nodes:
        stdscr.attron(curses.color_pair(2))
        stdscr.addstr(y+1, 2, "  (no nodes visible)")
        stdscr.attroff(curses.color_pair(2))
        return y + 3
    
    hdr = f"  {'IP':<16} {'ID':<10} {'Songs':<6} {'Master':<7} {'RSSI':<8}"
    stdscr.addstr(y+1, 1, hdr)
    
    for i, (ip, info) in enumerate(nodes.items()):
        master_str = '⭐YES' if info.get('is_master') else 'no'
        line = f"  {ip:<16} {info.get('node_id','?'):<10} {info.get('songs_count',0):<6} {master_str:<7} {info.get('signal_dbm',-99)}dBm"
        if i+1 < (height - y - 2):
            stdscr.addstr(y+2+i, 1, line)

def draw_songs(stdscr, y, data):
    height, width = stdscr.getmaxyx()
    songs = data.get('local_songs', [])
    
    y += 15  # after node info + nodes section
    stdscr.attron(curses.color_pair(5))
    stdscr.addstr(y, 1, f"🎵 LOCAL SONGS ({len(songs)})")
    stdscr.attroff(curses.color_pair(5))
    
    max_songs = min(len(songs), height - y - 3)
    for i in range(max_songs):
        s = songs[i]
        line = f"  {i+1:3d}. {s.get('artist','?')} - {s.get('title','?')}"
        stdscr.addstr(y+1+i, 1, line[:width-2])

def draw_log(stdscr, y, data):
    height, width = stdscr.getmaxyx()
    stdscr.attron(curses.color_pair(6))
    stdscr.addstr(height-2, 1, "📋 ACTIVITY LOG (last 50 entries)")
    stdscr.attroff(curses.color_pair(6))
    
    log_lines = cache.get('log_lines', [])
    lines = log_lines[-(height//2-2):]
    for i, line in enumerate(lines):
        stdscr.addstr(height - len(lines) -1 + i, 1, line[:width-2])

def main_tui(stdscr):
    curses.curs_set(0)
    curses.start_color()
    stdscr.nodelay(True)
    stdscr.timeout(100)
    
    # Colors
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)    # Header
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)      # Error/Warning
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)   # Node info
    curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)    # Visible nodes
    curses.init_pair(5, curses.COLOR_BLUE, curses.COLOR_BLACK)      # Songs
    curses.init_pair(6, curses.COLOR_MAGENTA, curses.COLOR_BLACK)   # Log
    
    # Start API fetch thread
    t = threading.Thread(target=api_loop, daemon=True)
    t.start()
    time.sleep(2)  # initial fetch
    
    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        
        if cache['error']:
            stdscr.attron(curses.color_pair(2))
            stdscr.addstr(1, 1, f"  ⚠️ {cache['error'][:width-4]}")
            stdscr.addstr(2, 1, "  Is the agent running? (mesh_agent.py)")
            stdscr.addstr(3, 1, "  Press 'q' to exit")
            stdscr.attroff(curses.color_pair(2))
        elif cache['status']:
            draw_header(stdscr, 0, cache['status'])
            draw_node_info(stdscr, 2, cache['status'])
            draw_nodes(stdscr, 14, cache['status'])
            draw_songs(stdscr, 20, cache['status'])
            draw_log(stdscr, 0, cache['status'])
        else:
            stdscr.addstr(1, 1, "  Loading...")
        
        try:
            stdscr.addstr(height-1, 1, " q=quit | r=refresh | f=force song | h=help ".center(width-2)[:width-1])
        except:
            pass
        
        stdscr.refresh()
        
        key = stdscr.getch()
        if key == ord('q'):
            break
        elif key == ord('r'):
            fetch_status()

if __name__ == '__main__':
    curses.wrapper(main_tui)
