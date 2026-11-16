#!/usr/bin/env python3
"""Cycle-count a QEMU single-step execution trace against the Cortex-M4
timing model.

Inputs:
  qemu1.log  - `qemu -d nochain,exec -accel tcg,one-insn-per-tb=on` output;
               every Trace line is exactly one executed guest instruction.
  ELF        - the same binary, disassembled with arm-none-eabi-objdump -d.

Method: map every executed PC to its instruction, apply Cortex-M4 (FPv4-SP)
cycle costs, resolve branch taken/not-taken from the successor PC, and sum
cycles inside marker windows.
"""
import re
import subprocess
import sys

LOG = '/tmp/qemu1.log'
ELF = 'build/qemu_I1.elf'

# marker windows: (name, first_pc_of_end_marker, last_pc_of_begin_marker)
MARKERS = {
    'cfft_f32(4096) fwd+bitrev': (0x080002e2, 0x080002e4),  # after begin.bx lr, at end.nop
    'cmplx_mag_f32(4096)':       (0x080002ea, 0x080002ec),
}

TRACE_RE = re.compile(r'^Trace \d+: 0x[0-9a-f]+ \[[0-9a-f]+/([0-9a-f]+)/')
INSN_RE = re.compile(r'^\s*([0-9a-f]+):\s+(?:[0-9a-f]{4}\s+)+\s*([a-z][a-z0-9.]*)\s*(.*)$', re.I)

def load_disasm(elf):
    out = subprocess.run(['arm-none-eabi-objdump', '-d', elf],
                         capture_output=True, text=True).stdout
    insns = {}
    for line in out.splitlines():
        m = INSN_RE.match(line)
        if not m:
            continue
        pc = int(m.group(1), 16)
        mnem = m.group(2).lower()
        ops = m.group(3).strip()
        size = 2
        hexpart = line.split(':')[1].strip().split()[0]
        size = 2 * len(hexpart) // 4
        insns[pc] = (mnem, ops, size)
    return insns

def is_branch(m):
    return (m.startswith('b') and m not in ('bic', 'bfi', 'bfc')) or \
           m.startswith('cbz') or m.startswith('cbnz')

def cond_branch(m):
    # conditional: b<cc>, cbz, cbnz; b.w/b.n bare and bal are unconditional
    if m.startswith('cbz') or m.startswith('cbnz'):
        return True
    base = m.split('.')[0]
    return base not in ('b', 'bal', 'bl', 'bx', 'blx', 'bkpt')

def cost_of(mnem, ops, size, next_pc, pc, targets):
    """Cortex-M4 cycles for one executed instruction."""
    m = mnem
    if m.startswith('vldr'):
        return 2
    if m.startswith('vstr'):
        return 2
    if m.startswith('vpush') or m.startswith('vpop'):
        mm = re.search(r'd(\d+)-d(\d+)', ops)
        n = 2 * (int(mm.group(2)) - int(mm.group(1)) + 1) if mm else 2
        return 1 + n
    if m in ('vsqrt.f32', 'vsqrt'):
        return 14
    if m in ('vdiv.f32', 'vdiv', 'vdiv.f64'):
        return 14
    if m.startswith('vmrs'):
        return 1
    if m.startswith('vcvt') or m.startswith('vmov.f32') or m.startswith('vmov.32'):
        return 1
    if m.startswith('vmov') or m.startswith('vdup'):
        return 1
    if '.f32' in m or '.f64' in m:
        return 1                     # vadd/vsub/vmul/vfma/vfms/vcmp/vabs/vneg
    if m.startswith('vldm') or m.startswith('vstm'):
        n = len(ops.split(',')) - 1
        return 1 + max(n, 1)
    if m in ('ldm', 'ldmia', 'ldmia.w', 'ldmfd', 'pop', 'pop.w'):
        return 1 + max(len(ops.split(',')), 1)
    if m in ('stm', 'stmia', 'stmia.w', 'stmfd', 'push', 'push.w'):
        return 1 + max(len(ops.split(',')), 1)
    if m.startswith('ldr') or m.startswith('str'):
        return 2                      # includes ldrb/h, strb/h, .w forms, ldrd/strd(n=2 -> keep 2)
    if m == 'ldrd' or m == 'strd':
        return 3
    if m.startswith('bl'):
        return 3                      # bl / blx: pipeline redirect
    if m == 'bx' or m.startswith('bx'):
        return 2
    if m == 'bkpt':
        return 4                      # exception entry cost is outside window anyway
    if m.startswith('dmb') or m.startswith('dsb') or m.startswith('isb'):
        return 1
    if m.startswith('sdiv') or m.startswith('udiv'):
        return 4
    if m.startswith('mul') or m.startswith('mla') or m.startswith('mls'):
        return 1
    if is_branch(m):
        tgt = targets.get(pc)
        taken = (tgt is not None and next_pc == tgt) or \
                (tgt is None and next_pc != pc + size)   # fallback heuristic
        if cond_branch(m) and not taken:
            return 1
        return 3
    if m.startswith('msr') or m.startswith('mrs') or m.startswith('cps'):
        return 1
    if m in ('wfi', 'wfe', 'nop', 'yield'):
        return 1
    return 1                          # ordinary ALU

def load_symbols(elf):
    """sorted [(addr, size, name)] for text symbols"""
    out = subprocess.run(['arm-none-eabi-nm', '-S', elf],
                         capture_output=True, text=True).stdout
    syms = []
    for line in out.splitlines():
        p = line.split()
        if len(p) == 4 and p[2] in ('t', 'T'):
            try:
                syms.append((int(p[0], 16), int(p[1], 16), p[3]))
            except ValueError:
                pass
    syms.sort()
    return syms

SYMS = []

def sym_of(pc):
    import bisect
    i = bisect.bisect_right(SYMS, (pc, 1 << 30, '\xff')) - 1
    if i >= 0:
        addr, size, name = SYMS[i]
        if addr <= pc < addr + size:
            return name
    return '<unknown>'

def main():
    global SYMS
    SYMS = load_symbols(ELF)
    insns = load_disasm(ELF)
    targets = {}
    for pc, (m, ops, size) in insns.items():
        tm = re.search(r'([0-9a-f]{6,})\s*<', ops)
        if is_branch(m) and tm:
            targets[pc] = int(tm.group(1), 16)

    seq = []
    with open(LOG) as f:
        for line in f:
            m = TRACE_RE.match(line)
            if m:
                seq.append(int(m.group(1), 16))
    print(f"executed instructions in trace: {len(seq)}")

    # per-instruction cycles over the whole run (for the marker windows)
    windows = []
    for name, (bgn_last, end_first) in MARKERS.items():
        try:
            i0 = seq.index(bgn_last)
            i1 = seq.index(end_first, i0)
        except ValueError:
            print(f"{name}: markers not found!")
            continue
        windows.append((name, i0 + 1, i1))

    for name, i0, i1 in windows:
        cyc = 0
        n = i1 - i0
        attr = {}
        for k in range(i0, i1):
            pc = seq[k]
            nxt = seq[k + 1] if k + 1 < len(seq) else pc + 4
            if pc not in insns:
                continue
            m, ops, size = insns[pc]
            c = cost_of(m, ops, size, nxt, pc, targets)
            cyc += c
            fname = sym_of(pc)
            a = attr.setdefault(fname, [0, 0])
            a[0] += 1
            a[1] += c
        print(f"{name}: {n} instructions, {cyc} cycles (M4 model)")
        for fn, (ni, ci) in sorted(attr.items(), key=lambda x: -x[1][1]):
            print(f"    {fn:34s} {ni:8d} insn {ci:8d} cyc")

if __name__ == '__main__':
    main()
