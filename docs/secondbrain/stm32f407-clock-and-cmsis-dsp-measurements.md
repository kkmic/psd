# STM32F407 — clock facts and CMSIS-DSP timing measurements

Durable conclusions from the psd project investigation (Nov 2026).
Sources: STM32F4-Discovery schematic (MB997 rev B2), RM0090 Rev 22,
STM32CubeF4 CMSIS-DSP 1.10.0, measurements in `arm/cfft_bench/` → `docs/stat.md`.

## Hardware / clock facts (verified)

* STM32F4-Discovery board: STM32F407VGT6, HSE crystal X2 = **8 MHz** on PH0/PH1
  (fitted); LSE 32.768 kHz crystal **not fitted**; ST-LINK MCU can be clocked
  from the target's MCO (PA8).
* RM0090 PLL constraints (pp. 164–165): PLLM 2–63 with **VCO input 1–2 MHz**
  (2 MHz recommended); PLLN 50–432 with **VCO output 100–432 MHz**;
  **PLLP ∈ {2, 4, 6, 8}**; PLLQ 2–15 (USB OTG FS / SDIO / RNG need exactly
  48 MHz). STM32F407 SYSCLK max = **168 MHz** (the RM chapter text shows the
  F42x/43x 180 MHz variant — same chapter covers both families).
* Formula: `SYSCLK = (HSE / M) × N / P`; VCO = `(HSE / M) × N`.
* With 8 MHz HSE (M=8 → 1 MHz): every **integer MHz from 13 to 168** is
  reachable (P=8 → 12.5–54, P=6 → 16.7–72, P=4 → 25–108, P=2 → 50–168),
  plus 12.5 MHz exactly; HSE direct = 8 MHz, HSI = 16 MHz (HSI-PLL with
  M=16 reproduces the same set). Fractional ×.5/.25/1/6/1/8-MHz steps also
  exist.
* The canonical 168 MHz config: **M=4, N=168, P=2, Q=7** → PLL input 2 MHz,
  VCO 336 MHz, SYSCLK 168 MHz, PLL48CK = 48 MHz exact. Required companions:
  **voltage scale 1** (scale 2 caps at 144 MHz), **flash latency 5 WS**,
  APB1 /4 = 42 MHz (limit), APB2 /2 = 84 MHz (limit), prefetch on.
* ST's example projects for this board (e.g. ADC_RegularConversion_DMA) ship
  at 144 MHz / scale 2 / 4 WS (M=8, N=288, P=2, Q=6) — not the max.

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

## Measurements (N = 4096, -Os, gcc 10.3.1, hard float)

| Function | Instructions | Cycles | Time @ 168 MHz |
|---|---:|---:|---:|
| arm_cfft_f32 fwd+bitrev | 323,357 | 446,720 | 2.659 ms |
| arm_cmplx_mag_f32 | 106,505 | 266,265 | 1.585 ms |
| both (psd pipeline) | 429,862 | 712,985 | 4.244 ms |

* Bit reversal = 14.4 % of the FFT (64.5k cycles = 0.384 ms); radix-8 kernel
  = 85.5 %.
* `arm_cmplx_mag_f32` = 65 cycles/sample, of which **26 are newlib `sqrtf`
  errno-wrapper overhead** around the actual 14-cycle `VSQRT.F32`.
  `-ffast-math`/`-fno-math-errno` would cut it to ≈1.0 ms.
* Model assumes zero-wait memory (SRAM or flash+ART); flash-bound worst case
  ≈ +10–30 %.

## Measurement technique (reusable)

* **QEMU DWT does not work**: the STM32F405 SoC model (netduinoplus2) does not
  implement the DWT unit — CYCCNT reads 0 — and QEMU is not cycle-accurate
  regardless.
* Working method: single-instruction trace
  `qemu-system-arm -M netduinoplus2 -d nochain,exec -accel tcg,one-insn-per-tb=on -D qemu1.log`
  → every Trace line = exactly one executed instruction. Put noinline marker
  functions around the measured call; count lines between marker PCs =
  exact dynamic instruction count. Then cost each executed instruction with
  the Cortex-M4 TRM table (FP ALU 1, VLDR/VSTR/LDR/STR 2, taken branch 3,
  not-taken 1, BL 3, BX 2, PUSH/POP 1+n, VSQRT 14), branch direction taken
  from the successor PC in the trace. Tool: `arm/cfft_bench/trace_cycles.py`.
* xPack QEMU (9.2.4) quirks: no `-singlestep` flag (removed in QEMU 8.1+) —
  use `-accel tcg,one-insn-per-tb=on`; `--board/--mcu` flags exist but the
  classic `-M netduinoplus2` machine works and is what we used.
* QEMU functional validation: 50 Hz sine @ 8192 Hz, N=4096 → spectral peak
  must land in bin `f·N/fs` = 25. Semihosting output via
  `bkpt 0xab` (SYS_WRITE0) works under QEMU and under ST-Link debug sessions.
* For hardware-exact numbers: flash `arm/cfft_bench/build/hw407_Os.elf`
  (or rebuild with -DSTM32F407xx + F407 startup) and read DWT CYCCNT
  (`DEMCR |= TRCENA; DWT_CTRL |= CYCCNTENA`) in a debug session.

## Environment notes

* Toolchain on this machine: `arm-none-eabi-gcc` 10.3.1, `clang` 15,
  xPack `qemu-system-arm` 9.2.4, `poppler-utils` (pdftotext), `python3`.
  No `jq`.
* CMSIS-DSP 1.10.0 headers use `#include "dsp/transform_functions.h"` —
  needs `-I <DSP>/Include` (the `dsp/` subdir is below it).
* The built benchmark links at ~931 KB text (all CMSIS tables compiled into
  one object without per-table section splitting) — fits the F407VG 1 MB flash.
