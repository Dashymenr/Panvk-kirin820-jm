#!/usr/bin/env python3
# gstk.py <pid> <tid> [reg|auto|all] [bytes]: guest (x86) stack scan for a
# Wine process running x86-64 code through FEX arm64ec (Hangover, Proton
# arm64ec builds).
#  - PE images are found by their MZ/PE headers at 64 KiB aligned mappings
#    (Proton maps them anonymously) and named from their export directory.
#  - Registers come from gdb (registers work under proot, memory reads don't);
#    memory is read from /proc/<pid>/mem.
#  - The x86 RSP is host x23 while the thread runs JIT code and sp while it is
#    in arm64ec code; "auto" picks one from the pc, "all" tries every
#    register and prints the four with the most image pointers.
# Prints values on the stack that point into images (heuristic call stack).
import re, struct, subprocess, sys

pid, tid = sys.argv[1], sys.argv[2]
reg = sys.argv[3] if len(sys.argv) > 3 else 'x23'
nbytes = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0x2000

rows = []
for line in open(f'/proc/{pid}/maps'):
    p = line.split()
    lo, hi = (int(x, 16) for x in p[0].split('-'))
    rows.append((lo, hi, p[1], int(p[2], 16), ' '.join(p[5:])))
images = []  # (lo, hi, name, [(lo, hi)])
memf = open(f'/proc/{pid}/mem', 'rb')
def rdm(a, n):
    try:
        memf.seek(a); return memf.read(n)
    except Exception:
        return None
for lo, hi, perm, off, name in rows:
    if lo & 0xffff or 'r' not in perm:
        continue
    h = rdm(lo, 0x400)
    if not h or h[:2] != b'MZ':
        continue
    e = struct.unpack_from('<I', h, 0x3c)[0]
    if e > 0x300 or h[e:e + 4] != b'PE\0\0':
        continue
    opt = e + 24
    magic = struct.unpack_from('<H', h, opt)[0]
    if magic != 0x20b:
        continue
    size = struct.unpack_from('<I', h, opt + 56)[0]
    exp_rva = struct.unpack_from('<I', h, opt + 112)[0]
    nm = name.split('/')[-1] or f'image@{lo:#x}'
    if exp_rva:
        ed = rdm(lo + exp_rva, 40)
        if ed:
            nrva = struct.unpack_from('<I', ed, 12)[0]
            sn = rdm(lo + nrva, 64)
            if sn:
                nm = sn.split(b'\0')[0].decode(errors='replace') or nm
    images.append((lo, lo + size, nm, [(lo + 0x1000, lo + size)]))

def sym(a):
    for lo, hi, name, ex in images:
        if lo <= a < hi and any(e0 <= a < e1 for e0, e1 in ex):
            return f'{name}+{a - lo:#x}'
    return None

out = subprocess.run(['timeout', '12', 'gdb', '-q', '-batch', '-p', pid,
                      '-ex', 'thread apply all info registers', '-ex', 'detach'],
                     capture_output=True, text=True).stdout
regs, c = {}, None
for line in out.splitlines():
    m = re.match(r'Thread \d+ .*LWP (\d+)', line)
    if m:
        c = m.group(1); regs[c] = {}; continue
    m = re.match(r'(x\d+|fp|lr|sp|pc)\s+(0x[0-9a-f]+)', line)
    if m and c:
        regs[c][m.group(1)] = int(m.group(2), 16)
r = regs.get(tid)
if not r:
    sys.exit(f'no regs for {tid}')
if reg == 'all':
    mem = open(f'/proc/{pid}/mem', 'rb')
    best = []
    for rn, v in r.items():
        d = b''
        for off in range(0, 0x4000, 0x1000):
            try:
                mem.seek((v & ~7) + off); d += mem.read(0x1000)
            except Exception:
                break
        hits = [sym(struct.unpack_from('<Q', d, i)[0]) for i in range(0, len(d) - 7, 8)]
        hits = [h for h in hits if h]
        if hits:
            best.append((len(hits), rn, v, hits[:12]))
    for n, rn, v, h in sorted(best, reverse=True)[:4]:
        print(f'{rn}={v:#x} hits {n}:', ' '.join(h))
    sys.exit(0)
if reg == 'auto':
    pcw = [x for x in rows if x[0] <= r['pc'] < x[1]]
    pcname = pcw[0][4] if pcw else ''
    if 'FEXMemJIT' in pcname:
        reg = 'x23'
    elif sym(r['pc']) or any(lo <= r['pc'] < hi for lo, hi, n, e in images):
        reg = 'sp'
    else:
        sys.exit(f'native pc in {pcname.split("/")[-1]}, retry')
start = r[reg] & ~7
mem = open(f'/proc/{pid}/mem', 'rb')
data = b''
for off in range(0, nbytes, 0x1000):  # page by page, stop at the end of the mapping
    try:
        mem.seek(start + off); data += mem.read(min(0x1000, nbytes - off))
    except Exception:
        break
print(f'tid {tid} {reg}={start:#x} read {len(data):#x} bytes; images {len(images)}')
n = 0
for i in range(0, len(data) - 7, 8):
    s = sym(struct.unpack_from('<Q', data, i)[0])
    if s:
        print(f'  +{i:#06x} {s}'); n += 1
        if n >= 40:
            break
