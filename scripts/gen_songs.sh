#!/bin/sh
set -e
apk add --no-cache sox python3

OUTPUT="/songs/raw"
mkdir -p "$OUTPUT"
TOTAL=0

for i in $(seq 277 1999); do
    case $((i % 16)) in
        0) G="ambient" ;; 1) G="blues" ;; 2) G="classical" ;; 3) G="electronic" ;;
        4) G="jazz" ;; 5) G="folk" ;; 6) G="rock" ;; 7) G="world" ;;
        8) G="lofi" ;; 9) G="synth" ;; 10) G="acoustic" ;; 11) G="cinematic" ;;
        12) G="pop" ;; 13) G="mellow" ;; 14) G="strings" ;; 15) G="brass" ;;
    esac

    case $((i % 12)) in
        0) M="happy" ;; 1) M="sad" ;; 2) M="energetic" ;; 3) M="calm" ;;
        4) M="mysterious" ;; 5) M="dreamy" ;; 6) M="epic" ;; 7) M="playful" ;;
        8) M="dark" ;; 9) M="hopeful" ;; 10) M="tense" ;; 11) M="peaceful" ;;
    esac

    D=$((30 + (i % 61)))
    F=$((80 + (i * 7) % 500))
    N=$(printf "track_%04d_%s_%s" "$i" "$G" "$M")

    if ! sox -n -r 8000 -c 1 "$OUTPUT/$N.wav" synth "${D}s" sine "$F" tremolo "0.3" "0.3" 2>/dev/null; then
        python3 -c "
import struct
n=8000*$D
with open('$OUTPUT/$N.wav','wb') as f:
 ds=n*2
 f.write(b'RIFF'+struct.pack('<I',36+ds)+b'WAVEfmt '+struct.pack('<IHHIIHH',16,1,1,8000,16000,2)+b'data'+struct.pack('<I',ds)+b'\x00'*ds)
" 2>/dev/null || true
    fi

    TOTAL=$((TOTAL + 1))
    if [ $((TOTAL % 100)) -eq 0 ]; then
        echo "Generated $TOTAL songs so far..." >&2
    fi
done

echo "ALL_DONE: $(ls "$OUTPUT" 2>/dev/null | wc -l)"