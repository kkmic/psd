# STM32F407 — clock facts and CMSIS-DSP timing measurements

Durable conclusions from the psd project investigation (Nov 2026).
Sources: STM32F4-Discovery schematic (MB997 rev B2), RM0090 Rev 22,
STM32CubeF4 CMSIS-DSP 1.10.0, on-board measurements via openocd + DWT
(`arm/cfft_bench/` → `docs/stat.md`).

## Final results (real board, DWT CYCCNT, SYSCLK = 168 MHz, -Os, gcc 10.3.1)

| Function (N = 4096) | Cycles (avg) | Time @ 168 MHz |
|---|---:|---:|
| arm_cfft_f32 fwd + bitrev | 523,150 | 3.113 ms |
| arm_cfft_f32 fwd, no bitrev | 468,136 | 2.786 ms |
| → bit-reversal cost | 55,014 | 0.327 ms |
| arm_cmplx_mag_f32 | 237,725 | 1.415 ms |
| both (psd pipeline) | 760,875 | 4.529 ms |

* Correctness check on target: 50 Hz sine @ 8192 Hz → spectral peak in bin 25. OK.
* QEMU instruction-trace + TRM-timing model had estimated 446,720 (FFT, −17 %:
  flash wait states not modeled) and 266,265 (mag, +11 %: streaming loads /
  VSQRT pipelining over-costed). Board numbers are authoritative.
* sqrtf insight: 40 of 65 cycles/sample of arm_cmplx_mag_f32 are the sqrt
  path, 26 of them newlib errno checks; `-ffast-math` would give ≈ 1.0 ms.

## Hardware / clock facts (verified)

* STM32F4-Discovery: STM32F407VGT6, HSE crystal X2 = **8 MHz** on PH0/PH1
  (fitted); LSE 32.768 kHz **not fitted**; ST-LINK can be clocked from target MCO.
* RM0090 PLL constraints (pp. 164–165): PLLM 2–63 with **VCO input 1–2 MHz**
  (2 MHz recommended); PLLN 50–432 with **VCO output 100–432 MHz**;
  **PLLP ∈ {2, 4, 6, 8}**; PLLQ 2–15 (USB OTG FS / SDIO / RNG need exactly
  48 MHz). STM32F407 SYSCLK max = **168 MHz** (RM's "180 MHz" caution text is
  the F42x/43x variant in the same chapter).
* Formula: `SYSCLK = (HSE / M) × N / P`; VCO = `(HSE / M) × N`.
* With 8 MHz HSE (M=8 → 1 MHz): every **integer MHz from 13 to 168** is
  reachable (P=8 → 12.5–54, P=6 → 16.7–72, P=4 → 25–108, P=2 → 50–168),
  plus 12.5 MHz exactly; HSE direct = 8 MHz, HSI = 16 MHz.
* Canonical 168 MHz config: **M=4, N=168, P=2, Q=7** → PLL input 2 MHz,
  VCO 336 MHz, PLL48CK = 48 MHz exact. Required companions: **voltage scale 1**
  (scale 2 caps at 144 MHz), **flash latency 5 WS**, APB1 /4 = 42 MHz (limit),
  APB2 /2 = 84 MHz (limit), prefetch on.
* ST's Discovery examples ship at 144 MHz / scale 2 / 4 WS — not the max.

## CMSIS-DSP arm_cfft_f32 structure (v1.10.0, non-MVE / Cortex-M4F path)

* Dispatch: 64/512/4096 → pure `arm_radix8_butterfly_f32`; 32/256/2048 →
  radix8by4 first pass; 16/128/1024 → radix8by2 first pass; then
  `arm_bitreversal_32` if bitReverseFlag=1. IFFT adds two O(N) loops.
* In ST's CubeF4 packaging the radix-8 kernel lives in
  `Source/TransformFunctions/arm_cfft_radix8_f32.c` (upstream name
  `arm_radix8_butterfly_f32.c`); a hand-written `arm_bitreversal2.S` also
  exists as an alternative bitrev implementation.
* For N=4096: 4 radix-8 stages = 585 plain + 1463 twiddle butterflies;
  bit-reversal = 2016 index swaps (table length 4032).

## Reproducing on the real board (full command list)

Board: STM32F4-Discovery attached via ST-LINK/V2.1 (`lsusb` → `0483:374b`).
Project: `~/work/psd/arm/cfft_bench` (firmware: `Src/main.c` — HAL clock
setup to 168 MHz + DWT measurement of arm_cfft_f32 / arm_cmplx_mag_f32,
semihosting output).

```bash
# 1. build (arm-none-eabi-gcc, -Os, hard float; ~931 KB, fits 1 MB flash)
cd ~/work/psd/arm/cfft_bench
make all                     # -> build/hw_Os.elf

# 2. flash + run; benchmark prints DWT results via semihosting, then exits
make flash
#    = openocd -f board/stm32f4discovery.cfg \
#        -c "init" -c "arm semihosting enable" -c "reset halt" \
#        -c "program build/hw_Os.elf verify" -c "reset run" \
#        -c "sleep 60000" -c "shutdown"

# 3. alternative — read DWT registers directly with gdb while openocd serves:
make server                  # terminal 1: openocd -f board/stm32f4discovery.cfg
make dwt                     # terminal 2: gdb-multiarch -> port 3333:
#    DWT_CTRL  = 0x40000001   (CYCCNTENA set)
#    DWT_CYCCNT = <free-running total since boot>
#    DEMCR     = 0x01000000   (TRCENA set)

# manual equivalents:
openocd -f board/stm32f4discovery.cfg -c init -c "arm semihosting enable" \
        -c "reset halt" -c "program build/hw_Os.elf verify" -c "reset run"
gdb-multiarch -batch -ex "target remote :3333" \
    -ex 'printf "DWT_CYCCNT = %u\n", *(unsigned int*)0xE0001004' -ex detach
echo shutdown | telnet localhost 4444     # stop openocd
```

Gotchas learned:

* If openocd dies mid-session the ST-Link can stay wedged ("Error: open
  failed"); it recovers after USB re-enumeration (replug or wait).
* Firmware built against HAL needs a `SysTick_Handler` (→ `HAL_IncTick()`);
  the startup file's weak Default_Handler would otherwise trap on the first
  1 kHz tick.
* Semihosting prints must be bracketed by openocd's `arm semihosting enable`;
  without it the BKPT 0xAB faults.
* The built benchmark is ~931 KB text because all CMSIS-DSP tables compile
  into one object (no per-table section splitting) — fits the F407VG 1 MB flash.

## Environment notes

* Toolchain on this machine: `arm-none-eabi-gcc` 10.3.1, `gdb-multiarch`
  (no arm-none-eabi-gdb), `openocd` 0.11.0 with `board/stm32f4discovery.cfg`,
  `clang` 15, `poppler-utils`, `python3`. No `jq`.
* CMSIS-DSP 1.10.0 headers use `#include "dsp/transform_functions.h"` —
  needs `-I <DSP>/Include` (the `dsp/` subdir is below it).
* DWT on QEMU (netduinoplus2 / STM32F405 model) is not implemented — CYCCNT
  reads 0; the earlier QEMU measurements used single-instruction execution
  traces + a TRM timing model instead (method retired once the board was used).
