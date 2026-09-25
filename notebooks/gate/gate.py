"""Day-1 gate for bpy-drift-bench on Kaggle.

Answers, in one run: does pip install from the repo work, do the apt libraries install, do all four
pinned Linux Blender builds download, extract and start headless, and can each one both pass and
fail an assert? Also lists the models kaggle_benchmarks exposes in this environment.
"""
import os, sys, subprocess, time, platform, shutil

T0 = time.time()


def sh(cmd):
    out = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return (out.stdout + out.stderr).strip()


def mark(label):
    print(f"\n[{time.time() - T0:7.1f}s] {label}", flush=True)


mark("environment")
print(platform.platform(), "| python", sys.version.split()[0])
print(sh("nproc; free -g | head -2; df -h /tmp /kaggle/working 2>/dev/null; cat /etc/os-release | head -2; ldd --version | head -1"))

mark("pip install from GitHub")
# A tarball needs no git on the worker; the git+https form failed to clone on Kaggle (exit 128).
TARBALL = "https://github.com/Rustam335/bpy-drift-bench/archive/refs/heads/main.tar.gz"
pip = subprocess.run([sys.executable, "-m", "pip", "install", "--no-cache-dir", TARBALL], capture_output=True, text=True)
print("pip returncode", pip.returncode)
print((pip.stdout or "")[-800:], (pip.stderr or "")[-2500:])

mark("apt libraries")
print(sh("apt-get update -qq > /dev/null 2>&1; echo update-exit=$?"))
apt = subprocess.run("apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libsm6 libxkbcommon0",
                     shell=True, capture_output=True, text=True)
print("apt returncode", apt.returncode, (apt.stdout + apt.stderr)[-600:])

from bpy_drift import RELEASES, ensure_blender, verify_build, run_script  # noqa: E402
from bpy_drift.blender import cache_root  # noqa: E402

PROBE = "import bpy\nbpy.data.objects['Cube'].location.x = 1.0"
PASSING = "import bpy\nassert bpy.data.objects['Cube'].location.x == 1.0"
FAILING = "import bpy\nassert False, 'deliberate failure'"

verdicts = {}
for version in RELEASES:
    mark(f"Blender {version} ({RELEASES[version]})")
    t = time.time()
    try:
        binary = ensure_blender(version)
        print(f"binary ready in {time.time() - t:.0f}s: {binary}")
        build = verify_build(binary, version)
        print("build:", build)
        t = time.time()
        ok = run_script(binary, PROBE, PASSING)
        bad = run_script(binary, PROBE, FAILING)
        print(f"two probe runs took {time.time() - t:.1f}s")
        print("passing probe -> passed:", ok.passed, "rc:", ok.returncode)
        print("failing probe -> passed:", bad.passed, "rc:", bad.returncode, "| reason:", bad.reason)
        if not ok.passed:
            print("--- stdout tail ---\n", ok.stdout[-1500:], "\n--- stderr tail ---\n", ok.stderr[-2500:])
        verdicts[version] = ok.passed and not bad.passed
    except Exception as e:  # keep going so one broken build does not hide the others
        print("FAILED:", type(e).__name__, e)
        verdicts[version] = False

mark("disk")
print(sh(f"du -sh {cache_root()} 2>/dev/null; df -h /tmp | tail -1"))

mark("kaggle_benchmarks")
try:
    import kaggle_benchmarks as kbench
    names = sorted(kbench.llms)
    print(len(names), "models")
    print("\n".join(names))
except Exception as e:
    print("not available here:", type(e).__name__, e)

mark("verdict")
for v, ok in verdicts.items():
    print(f"  {v}: {'OK' if ok else 'FAIL'}")
print("GATE", "PASSED" if all(verdicts.values()) else "FAILED")
