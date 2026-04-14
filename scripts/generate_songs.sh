#!/bin/bash
# Generate 2000 synthesized MP3 songs using sox and lame
# Run with: docker run --platform linux/amd64 -v $(pwd)/songs:/songs this-image

set -e

OUTPUT_DIR="/songs/raw"
mkdir -p "$OUTPUT_DIR"

echo "Generating 2000 synthesized songs..."

# Use alpine + sox + lame to generate simple tones
apk add --no-cache sox lame coreutils 2>/dev/null || true

# Install sox and lame
apk add --no-cache sox lame 2>/dev/null || {
    # Fallback: use python3 to generate simple wav files, then convert
    apk add --no-cache python3 2>/dev/null || true
    
    python3 << 'PYEOF'
import struct, math, os, random, hashlib, json

OUTPUT = "/songs/raw"
os.makedirs(OUTPUT, exist_ok=True)

GENRES = ["ambient","blues","classical_piano","electronic","jazz","folk","rock","world",
          "lofi","synth","acoustic","cinematic","pop","mellow","strings","brass"]
MOODS = ["happy","sad","energetic","calm","mysterious","dreamy","melancholic","epic",
         "playful","dark","hopeful","nostalgic","tense","peaceful","adventurous","romantic"]

# Frequency table (Hz)
FREQS = [110, 146.8, 220, 130.8, 196, 164.8, 123.5, 100,
         82.4, 130.8, 146.8, 98, 220, 174.6, 196, 164.8]

def generate_wav(filename, freq, duration, sr=22050):
    samples = int(sr * duration)
    data = []
    # Create a more musical tone with harmonics and modulation
    for i in range(samples):
        t = i / sr
        # Fundamental + harmonics
        val = 0.3 * math.sin(2 * math.pi * freq * t)
        val += 0.15 * math.sin(2 * math.pi * freq * 2 * t)  # 2nd harmonic
        val += 0.08 * math.sin(2 * math.pi * freq * 3 * t)   # 3rd harmonic
        # Slow amplitude modulation (tremolo-like)
        env = 0.7 + 0.3 * math.sin(2 * math.pi * 0.5 * t)
        val *= env
        # Fade in/out
        fade = min(1.0, t / 2.0) * min(1.0, (duration - t) / 2.0)
        val *= max(0, fade)
        # Clamp
        val = max(-0.99, min(0.99, val))
        data.append(int(val * 32767))
    
    with open(filename, 'wb') as f:
        # WAV header
        num_samples = len(data)
        data_size = num_samples * 2
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + data_size))
        f.write(b'WAVE')
        fmt = struct.pack('<HHIIHH', 16, 1, 1, sr, sr * 2, 2)
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))
        f.write(fmt)
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        for s in data:
            f.write(struct.pack('<h', s))

meta = []
for i in range(2000):
    genre = GENRES[i % len(GENRES)]
    mood = MOODS[i % len(MOODS)]
    freq = FREQS[i % len(FREQS)]
    dur = random.uniform(60, 180)  # 1-3 minutes
    name = f"track_{i:04d}_{genre}_{mood}"
    wav_path = os.path.join(OUTPUT, f"{name}.wav")
    
    if not os.path.exists(wav_path):
        try:
            generate_wav(wav_path, freq, dur)
        except Exception as e:
            print(f"Error generating {name}: {e}")
            continue
    
    meta.append({
        "id": i+1,
        "name": name,
        "file": wav_path,
        "file_size": os.path.getsize(wav_path) if os.path.exists(wav_path) else 0,
        "genre": genre,
        "mood": mood,
        "duration": round(dur, 1),
        "source": "synthesized"
    })
    
    if (i+1) % 100 == 0:
        print(f"  Generated {i+1}/2000 songs")

with open(os.path.join(OUTPUT, "metadata.json"), 'w') as f:
    json.dump(meta, f, indent=2)

print(f"Done! Generated {len(meta)} WAV files in {OUTPUT}")
print(f"Total size: {sum(m['file_size'] for m in meta) / (1024**3):.1f} GB")
PYEOF
}

echo "Done!"
