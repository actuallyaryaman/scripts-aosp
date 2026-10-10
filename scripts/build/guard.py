import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

G = 1024**3
HELPERS = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('ROM_ROOT', '.')).resolve()
BASE = ROOT / '.local-build'

def available():
    return next(int(l.split()[1])*1024 for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))

def main():
    rel = next(l.split(':', 2)[2] for l in Path('/proc/self/cgroup').read_text().splitlines() if l.startswith('0::'))
    cg = Path('/sys/fs/cgroup') / rel.lstrip('/')
    for key in ['memory.high','memory.max','memory.swap.max']:
        value = (cg/key).read_text().strip()
        print(f'Service {key}={value}',flush=True)
    swap = str(BASE/'swap'/'swapfile')
    rows = [l.split() for l in Path('/proc/swaps').read_text().splitlines()[1:]]
    if not any(r[0]==swap and int(r[2])>=63*1024**2 for r in rows):
        raise RuntimeError('Activate 64 GiB SSD swap: sudo bash rom-tools/scripts/build/swap.sh enable')
    print('SSD swap active; no launcher-imposed memory limits or memory-triggered stops.',flush=True)
    for tool in ['git','make','zip','unzip','rsync','bc','bison','flex','openssl','perl','patch','taskset']:
        if not shutil.which(tool): raise RuntimeError(f'Missing {tool}')
    # This kernel places legacy Perl on PATH; check its shared libraries now.
    subprocess.run([str(ROOT/'prebuilts/tools-lineage/linux-x86/bin/perl'),'-e','exit 0'],check=True)
    if sys.argv[1]=='check':
        for tool in ['prebuilts/jdk/jdk21/linux-x86/bin/java','prebuilts/clang/host/linux-x86/clang-r596125/bin/clang']:
            subprocess.run([str(ROOT/tool),'--version'],check=True)
        print('Prerequisites passed.',flush=True)
        return 0
    if shutil.disk_usage(BASE).free<100*G: raise RuntimeError('Need at least 100 GiB free disk')
    cpus=','.join(map(str,sorted(os.sched_getaffinity(0))[:8]))
    child=subprocess.Popen([shutil.which('taskset'),'-c',cpus,shutil.which('bash'),str(HELPERS/'worker.sh'),sys.argv[1]],cwd=ROOT,start_new_session=True)
    reason=None
    def stop(msg):
        nonlocal reason
        if reason is None:
            reason=msg
            print('PROTECTIVE STOP: '+msg,flush=True)
            try: os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError: pass
    signal.signal(signal.SIGTERM,lambda *_:stop('termination requested'))
    signal.signal(signal.SIGINT,lambda *_:stop('interrupted'))
    try:
        while child.poll() is None:
            if shutil.disk_usage(BASE).free<20*G: stop('free disk below 20 GiB')
            if reason:
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: pass
                try: os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                child.wait()
                return 75
            time.sleep(0.5)
        return child.returncode if child.returncode>=0 else 128-child.returncode
    finally:
        if child.poll() is None:
            stop('monitor exiting')
            try: os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            child.wait()

if __name__=='__main__':
    try: sys.exit(main())
    except Exception as exc:
        print('Refusing build: '+str(exc),file=sys.stderr)
        sys.exit(1)
