#!/usr/bin/env python3
"""Static cycle analysis of Cortex-M4 disassembly loops.

Parses objdump output, finds loops (backward branches), costs each
instruction with the Cortex-M4 TRM timing model, and reports per-loop
body cycle costs so they can be multiplied by known trip counts.
"""
import re
import sys

# Cortex-M4 (FPv4-SP) instruction cycle costs (throughput-oriented, no dual issue).
# Based on ARM Cortex-M4 TRM Table 15-1 / DDI0439 (FPV4 timings: 1-cycle FP ALU,
# 2-cycle FP load/store, 14-cycle VSQRT).
DEFAULT = 1
COST = {
    # integer ALU
    'mov movs movw movt mvn mvns': 1,
    'add adds adr adc adcs sub subs sbc sbcs rsb rsc': 1,
    'add.w addw sub.w subw rsb.w adc.w sbc.w': 1,
    'and ands orr orrs eor eors bic bics': 1,
    'lsl lsls lsr lsrs asr asrs ror rors rrx': 1,
    'lsl.w lsr.w asr.w ror.w': 1,
    'mul muls mla mls smull umull smlal umlal': 1,   # 32x32 mul: 1-cycle on M4
    'mul.w mla.w mls.w': 1,
    'sdiv udiv': 4,                                    # 2..12, typical 4 (data dep)
    'cmp cmps cmn tst tsts teq': 1,
    'cmp.w cmn.w tst.w': 1,
    'bfc bfi sbfx ubfx': 1,
    'uxtb uxth uxtab sxtb sxth uxtah sxth.w': 1,
    'rev rev16 revsh rbit clz': 1,
    # branches
    'b beq bne bcs bcc bmi bpl bvs bvc bhi bls bge blt bgt ble bal': 3,  # taken
    'b.n beq.n bne.n bcs.n bcc.n bmi.n bpl.n bvs.n bvc.n bhi.n bls.n bge.n blt.n bgt.n ble.n': 3,
    'b.w': 3,
    'cbz cbnz cbz.n cbnz.n': 3,        # taken (loop-continue)
    'it': 1,
    # calls/returns
    'bl bl.w blx': 3,
    'bx bxlr': 2,                       # bx lr: 2 (branch)
    # loads/stores
    'ldr ldrb ldrh ldrsb ldrsh ldrd': 2,
    'ldr.w ldrb.w ldrh.w ldrsb.w ldrsh.w ldrd.w': 2,
    'str strb strh strd': 2,
    'str.w strb.w strh.w strd.w': 2,
    'ldm ldmia ldmdb ldmfd pop': 0,   # special: 1 + n below
    'stm stmia stmdb stmfd push': 0,
    # FPv4-SP
    'vadd.f32 vsub.f32 vmul.f32 vnmul.f32 vmla.f32 vmls.f32 vnmls.f32 vnmla.f32': 1,
    'vfma.f32 vfms.f32 vfnma.f32 vfnms.f32': 1,
    'vmov.f32 vabs.f32 vneg.f32 vcmp.f32 vcmpe.f32': 1,
    'vmrs vmrs APSR_nzcv fpscr': 1,
    'vcvt vcvt.f32 vcvt.s32 vcvt.u32 vcvt.f32.s32 vcvt.f32.u32': 1,
    'vsqrt vsqrt.f32': 14,
    'vdiv vdiv.f32': 14,
    'vldr vldr s0': 2,
    'vstr vstr s0': 2,
    'vmov vmov r3 s15 vmov s15 r3 vmov.f32': 1,   # core<->freg moves: 1
    'vpush vpush d8': 0,   # 1 + 2N below
    'vpop vpop d8': 0,
    'vdup vcgt vcge vceq vcle vclt vzip vuzp': 2,
}

def instr_cost(mnemonic, operands):
    m = mnemonic.lower()
    # normalize: strip .n/.w/.f32 variations handled by table keys
    for keys, cost in COST.items():
        for k in keys.split():
            if m == k or m.startswith(k + '.'):
                return cost
    # ldm/stm/push/pop: 1 + nregs
    if m in ('ldm', 'ldmia', 'ldmdb', 'pop') or m.startswith('ldm'):
        nregs = len(operands.split(',')) if operands else 1
        # base + writeback counted: (n+1)
        return 1 + nregs
    if m in ('stm', 'stmia', 'stmdb', 'push') or m.startswith('stm'):
        nregs = len(operands.split(',')) if operands else 1
        return 1 + nregs
    if m in ('vpush', 'vpop'):
        # e.g. {d8-d15}: 8 double regs = 16 words -> 1 + 16
        mm = re.search(r'd\d+-d(\d+)', operands)
        if mm:
            lo = int(re.search(r'd(\d+)', operands).group(1))
            hi = int(mm.group(1))
            return 1 + 2 * (hi - lo + 1)
        return 3
    if m.startswith('it'):  # it, ite, ittt ...
        return 1
    return DEFAULT

LINE_RE = re.compile(r'^\s*([0-9a-f]+):\s+(?:[0-9a-f]{4}\s+)*\s*\t?\s*([a-z][a-z0-9.]*)\s*(.*)$', re.I)

def parse(path):
    insns = []
    for line in open(path):
        m = LINE_RE.match(line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        mnem = m.group(2)
        ops = m.group(3).strip()
        # branch target?
        tgt = None
        bm = re.match(r'^([a-z.]+)?\s*\t?\s*([0-9a-f]+)\s*<', ops)
        if mnem.startswith(('b', 'cbz', 'cbnz')) and not mnem.startswith('bic'):
            tm = re.search(r'([0-9a-f]{6,})\s*<', ops)
            if tm:
                tgt = int(tm.group(1), 16)
        insns.append((addr, mnem, ops, tgt))
    return insns

def main(path):
    insns = parse(path)
    by_addr = {a: i for i, (a, m, o, t) in enumerate(insns)}
    # find backward branches -> loops
    loops = []
    for idx, (addr, mnem, ops, tgt) in enumerate(insns):
        if tgt is not None and tgt < addr:
            # loop body: [tgt .. addr] inclusive
            body = [(a, m, o) for (a, m, o, t) in insns if tgt <= a <= addr]
            cycles = sum(instr_cost(m, o) for (a, m, o) in body)
            # the back-edge branch itself: count as taken (cost already in table)
            loops.append((tgt, addr, len(body), cycles))
    # merge duplicates (same target): report each
    print(f"{'start':>10} {'end':>10} {'insns':>5} {'cycles':>7}")
    seen = set()
    for tgt, addr, n, cyc in loops:
        key = (tgt, addr)
        if key in seen:
            continue
        seen.add(key)
        print(f"{tgt:10x} {addr:10x} {n:5d} {cyc:7d}")

if __name__ == '__main__':
    main(sys.argv[1])
