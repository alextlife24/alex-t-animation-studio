"""Transcribe an audio file with faster-whisper and print JSON segments with word timings.
Runs under any Python that has faster-whisper (on Windows-on-ARM: the x64 Python).
usage: python asr_check.py <audio> <out.json>
"""
import json
import sys

from faster_whisper import WhisperModel

m = WhisperModel("small", device="cpu", compute_type="int8")
segs, _ = m.transcribe(sys.argv[1], language="en", word_timestamps=True, vad_filter=False,
                       condition_on_previous_text=False)
out = []
for s in segs:
    out.append({"start": s.start, "end": s.end, "text": s.text.strip(),
                "words": [{"w": w.word.strip(), "s": w.start, "e": w.end} for w in (s.words or [])]})
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"{len(out)} segments")
