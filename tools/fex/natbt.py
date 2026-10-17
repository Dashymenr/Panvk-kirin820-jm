#!/usr/bin/env python3
# natbt.py <pid> <tid> <samples>: sample a thread with gdb (registers only),
# walk the native frame-pointer chain through /proc/pid/mem and count the
# distinct call chains (lib+offset). gdb can't read memory under proot, but
# /proc/pid/mem works.
import collections, re, struct, subprocess, sys, time

pid, tid, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = []
for line in open(f'/proc/{pid}/maps'):
    p = line.split()
    lo, hi = (int(x, 16) for x in p[0].split('-'))
    rows.append((lo, hi, int(p[2], 16), ' '.join(p[5:])))
base = {}
for lo, hi, off, name in rows:
    if name.startswith('/'):
        base[name] = min(base.get(name, lo), lo - off)

def where(a):
    for lo, hi, off, name in rows:
        if lo <= a < hi:
            if name.startswith('/'):
                return f'{name.split("/")[-1]}+{a - base[name]:#x}'
            return name or 'anon'
    return 'unmapped'

mem = open(f'/proc/{pid}/mem', 'rb')
def rd(a):
    try:
        mem.seek(a); return struct.unpack('<Q', mem.read(8))[0]
    except Exception:
        return None

chains = collections.Counter()
t0 = time.time()
for i in range(n):
    if time.time() - t0 > 22:
        break
    out = subprocess.run(['timeout', '8', 'gdb', '-q', '-batch', '-p', pid,
                          '-ex', 'thread apply all info registers pc x29 x30',
                          '-ex', 'detach'], capture_output=True, text=True).stdout
    regs, c = {}, None
    for line in out.splitlines():
        m = re.match(r'Thread \d+ .*LWP (\d+)', line)
        if m:
            c = m.group(1); regs[c] = {}; continue
        m = re.match(r'(pc|x29|x30)\s+(0x[0-9a-f]+)', line)
        if m and c:
            regs[c][m.group(1)] = int(m.group(2), 16)
    r = regs.get(tid)
    if not r:
        continue
    frames = [where(r['pc']), 'lr ' + where(r['x30'])]
    fp = r['x29']
    for k in range(12):
        if not fp:
            break
        nfp, ret = rd(fp), rd(fp + 8)
        if ret is None:
            break
        frames.append(where(ret))
        if nfp is None or nfp <= fp:
            break
        fp = nfp
    chains[tuple(frames)] += 1
for ch, k in chains.most_common(8):
    print(k, '\n   ' + '\n   '.join(ch))
