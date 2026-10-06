"""One-command build for an episode of Instinct Service.

  python make.py ep01_no_milk            # everything: voices -> timeline -> graphics -> bake -> render -> mix -> mp4 -> verify
  python make.py ep01_no_milk --from mix # resume from a step (tts|timeline|graphics|bake|render|mix|compose|verify)

Rendering is resumable: frames already in build/<ep>/frames are skipped. Delete frames to re-render them.
Change BLENDER / WHISPER_PYTHON below or via environment variables for another machine.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
# optional .env (see .env.example): KEY=value lines, existing environment wins
if os.path.exists(os.path.join(ROOT, ".env")):
    for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())
BLENDER = os.environ.get("BLENDER", r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
PY = sys.executable
STEPS = ["tts", "timeline", "graphics", "bake", "render", "mix", "compose", "verify"]


def run(cmd):
    print(">", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT)


def main():
    ep = sys.argv[1] if len(sys.argv) > 1 else "ep02_eyes_closed"
    start = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else "tts"
    src = os.path.join(ROOT, "src")
    blend = os.path.join(ROOT, "build", ep, "scene.blend")
    for step in STEPS[STEPS.index(start):]:
        if step == "tts":
            run([PY, os.path.join(src, "tts.py"), ep])
        elif step == "timeline":
            run([PY, os.path.join(src, "timeline.py"), ep])
        elif step == "graphics":
            run([PY, os.path.join(src, "graphics.py"), ep])
        elif step == "bake":
            # OpenGL backend: the Vulkan backend produced shadow artifacts on the Adreno GPU this was built on
            run([BLENDER, "-b", "--factory-startup", "--gpu-backend", "opengl", "-P", os.path.join(src, "blender", "main.py"), "--", ep, "bake"])
        elif step == "render":
            run([BLENDER, "-b", blend, "--gpu-backend", "opengl", "-P", os.path.join(src, "blender", "main.py"), "--", ep, "render", "0", "2699"])
        elif step == "mix":
            run([PY, os.path.join(src, "sound.py"), ep])
        elif step == "compose":
            run([PY, os.path.join(src, "compose.py"), ep])
        elif step == "verify":
            run([PY, os.path.join(src, "verify.py"), ep])


if __name__ == "__main__":
    main()
