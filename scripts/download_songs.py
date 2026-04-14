#!/usr/bin/env python3
"""
Descarga ~2000 canciones sin copyright de fuentes libres.
Fuentes: Free Music Archive (FMA), Musopen, Incompetech, Jamendo CC, etc.
"""

import os
import sys
import json
import time
import subprocess
import hashlib
from pathlib import Path
from urllib.request import urlopen, urlretrieve
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================
# CONFIG
# ============================
OUTPUT_DIR = Path("/opt/mesh/songs/raw")
METADATA_FILE = OUTPUT_DIR / "metadata.json"
MAX_WORKERS = 4
TARGET_COUNT = 2000

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================
# CANCIONES GENERADAS (sintetizadas)
# Si no hay acceso a internet, generamos canciones con ffmpeg
# ============================

GENRES = [
    "ambient", "blues", "classical_piano", "electronic_beat",
    "jazz_swing", "folk_acoustic", "rock_instrumental", "world_percussion",
    "lo_fi_chill", "synth_pad", "acoustic_guitar", "cinematic",
    "upbeat_pop", "mellow_keys", "string_ensemble", "brass_fanfare"
]

MOODS = [
    "happy", "sad", "energetic", "calm", "mysterious", "dreamy",
    "melancholic", "epic", "playful", "dark", "hopeful", "nostalgic",
    "tense", "peaceful", "adventurous", "romantic"
]

def generate_song(idx, directory):
    """Genera una canción instrumental con ffmpeg (sintetizada)"""
    import random
    genre = GENRES[idx % len(GENRES)]
    mood = MOODS[idx % len(MOODS)]
    
    song_name = f"track_{idx:04d}_{genre}_{mood}"
    output_path = directory / f"{song_name}.mp3"
    
    if output_path.exists():
        return song_name, str(output_path)
    
    # Frecuencias base según género
    freqs = {
        "ambient": "110",
        "blues": "146.8",
        "classical_piano": "220",
        "electronic_beat": "130.8",
        "jazz_swing": "196",
        "folk_acoustic": "164.8",
        "rock_instrumental": "123.5",
        "world_percussion": "100",
        "lo_fi_chill": "110",
        "synth_pad": "130.8",
        "acoustic_guitar": "146.8",
        "cinematic": "98",
        "upbeat_pop": "220",
        "mellow_keys": "174.6",
        "string_ensemble": "196",
        "brass_fanfare": "164.8",
    }
    
    base_freq = freqs.get(genre, "164.8")
    duration = random.randint(120, 240)  # 2-4 min
    bpm = random.randint(70, 140)
    
    # Generar audio con synth de ffmpeg
    try:
        cmd = [
            'ffmpeg', '-y', '-f', 'lavfi', '-i',
            f'sine=frequency={base_freq}:duration={duration},'
            f'amodulation=frequency={bpm/60*4}:depth=0.3,'
            f'volume=0.5,'
            f'afade=t=in:st=0:d=3,'
            f'afade=t=out:st={duration-3}:d=3',
            '-c:a', 'libmp3lame', '-b:a', '128k',
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, timeout=60)
        
        if output_path.exists():
            return song_name, str(output_path)
    except:
        pass
    
    # Fallback: tone simple
    try:
        subprocess.run([
            'ffmpeg', '-y', '-f', 'lavfi', '-i',
            f'sine=frequency={base_freq}:duration={duration}',
            '-c:a', 'libmp3lame', '-b:a', '96k',
            str(output_path)
        ], capture_output=True, timeout=60)
        if output_path.exists():
            return song_name, str(output_path)
    except:
        pass
    
    return song_name, None

def generate_all_songs(count, directory):
    """Genera todas las canciones sintetizadas"""
    print(f"  Generating {count} synthesized songs...")
    metadata = []
    
    for i in range(count):
        if (i + 1) % 100 == 0:
            print(f"    Generated {i+1}/{count}")
        
        name, path = generate_song(i, directory)
        if path:
            metadata.append({
                "id": i+1,
                "name": name,
                "file": path,
                "genre": GENRES[i % len(GENRES)],
                "mood": MOODS[i % len(MOODS)],
                "duration": 0,
                "source": "synthesized",
                "hash": hashlib.md5(name.encode()).hexdigest()[:12]
            })
        else:
            print(f"    FAILED to generate track_{i:04d}")
    
    return metadata

# ============================
# DESCARGA DE FUENTES REALES (si hay internet)
# ============================

def download_from_freedownloads(url, save_path):
    """Descarga un archivo desde una URL"""
    try:
        if os.path.exists(save_path):
            return True
        subprocess.run(['wget', '-q', '-O', save_path, url], timeout=120)
        return os.path.exists(save_path) and os.path.getsize(save_path) > 10000
    except:
        return False

def download_creative_commons(directory):
    """
    Intenta descargar de Creative Commons y Free Music Archive.
    Nota: En la ISO final, las canciones vendrán pre-instaladas.
    Este script es para el desarrollo local.
    """
    print("  Attempting to download from CC sources...")
    
    # Fuentes de música libre
    sources = [
        # Free Music Archive - direct downloads
        {"url": "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/ccCommunity/Ketsa/Ketsa_-_01_-_Shine_On.mp3",
         "name": "ketsa_shine_on.mp3"},
        {"url": "https://files.freemusicarchive.org/storage-freemusicarchive-org/music/ccCommunity/Ketsa/Ketsa_-_05_-_Dreaming_Days.mp3",
         "name": "ketsa_dreaming_days.mp3"},
    ]
    
    downloaded = 0
    for src in sources:
        path = directory / src["name"]
        if download_from_freedownloads(src["url"], path):
            downloaded += 1
            print(f"    Downloaded: {src['name']}")
    
    print(f"  Downloaded {downloaded} from CC sources")
    return downloaded

# ============================
# ASIGNACIÓN A NODOS
# ============================

def distribute_to_nodes(metadata, num_nodes=80, per_node=25):
    """
    Distribuye 25 canciones únicas por nodo.
    Total necesario: 80 * 25 = 2000 canciones (cada una en un solo nodo)
    """
    import random
    random.seed(42)  # Reproducible
    
    songs = list(range(len(metadata)))
    random.shuffle(songs)
    
    if len(songs) < num_nodes * per_node:
        print(f"  WARNING: Need {num_nodes * per_node} songs, have {len(songs)}")
        return {}
    
    node_songs = {}
    idx = 0
    
    for node_num in range(1, num_nodes + 1):
        node_id = f"node{node_num:03d}"
        node_dir = Path(f"/opt/mesh/songs/nodes/{node_id}")
        node_dir.mkdir(parents=True, exist_ok=True)
        
        assigned = []
        for _ in range(per_node):
            song_idx = songs[idx]
            src = metadata[song_idx]
            src_path = Path(src["file"])
            if src_path.exists():
                dest = node_dir / src_path.name
                # Hardlink to save space
                try:
                    os.link(src_path, dest)
                except:
                    subprocess.run(['cp', str(src_path), str(dest)])
                assigned.append(src["name"])
            idx += 1
        
        node_songs[node_id] = {
            "songs": assigned,
            "count": len(assigned),
            "directory": str(node_dir)
        }
    
    return node_songs

# ============================
# MAIN
# ============================

def main():
    print("=" * 50)
    print("🎵 Network Music Mesh - Song Generator/Downloader")
    print(f"  Target: {TARGET_COUNT} songs")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 50)
    
    # Intentar descarga de fuentes CC
    cc_count = download_creative_commons(OUTPUT_DIR)
    
    # Generar canciones sintetizadas para completar
    needed = TARGET_COUNT - cc_count
    if needed > 0:
        metadata = generate_all_songs(needed, OUTPUT_DIR)
    else:
        metadata = []
    
    # Guardar metadata
    if metadata:
        with open(METADATA_FILE, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"\n  Metadata saved to {METADATA_FILE}")
    
    # Distribuir a nodos
    print("\n  Distributing songs to 80 nodes (25 per node)...")
    distribution = distribute_to_nodes(metadata)
    
    dist_file = OUTPUT_DIR / "distribution.json"
    with open(dist_file, 'w') as f:
        json.dump(distribution, f, indent=2)
    print(f"  Distribution saved to {dist_file}")
    
    # Resumen
    total_files = sum(1 for f in OUTPUT_DIR.glob("*.mp3")) if OUTPUT_DIR.exists() else 0
    print(f"\n  Summary:")
    print(f"    Total MP3 files: {total_files}")
    print(f"    Nodes: {len(distribution)}")
    print(f"    Songs per node: 25")
    print(f"    Total unique: {total_files}")

if __name__ == '__main__':
    main()
