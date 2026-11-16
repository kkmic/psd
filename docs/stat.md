# STM32F407 @ 168 MHz — arm_cfft_f32 / arm_cmplx_mag_f32 measurements (N = 4096)

## 1. Clock configuration

Board: **STM32F4-Discovery** (schematic MB997 rev B2) — MCU STM32F407VGT6,
HSE crystal **X2 = 8 MHz** on PH0/PH1 (LSE 32.768 kHz not fitted).

RCC values as requested, checked against RM0090 Rev 22 (docs/stm32f407-reference-manual.pdf):

| Parameter | Value | Result | RM0090 constraint | Status |
|---|---|---|---|---|
| PLLM | 4 | PLL input = 8/4 = **2 MHz** | 1–2 MHz (2 MHz recommended), p. 165 | OK |
| PLLN | 168 | VCO = 2 × 168 = **336 MHz** | VCO output 100–432 MHz, p. 165 | OK |
| PLLP | 2 | **SYSCLK = 336/2 = 168 MHz** | STM32F407 max system clock | OK (max) |
| PLLQ | 7 | PLL48CK = 336/7 = **48 MHz** | USB OTG FS / SDIO / RNG need exactly 48 MHz, p. 164 | OK |

Required companions of the 168 MHz setting (applied in `arm/cfft_bench/Src/main.c`):

* regulator voltage **scale 1** (scale 2 is only valid up to 144 MHz),
* flash latency **5 wait states** (was 4 in the 144 MHz example),
* AHB /1 (HCLK 168 MHz), APB1 /4 (42 MHz, at limit), APB2 /2 (84 MHz, at limit),
* flash prefetch enabled.

Reference project: `STM32CubeF4/Projects/STM32F4-Discovery/Examples/ADC/ADC_RegularConversion_DMA`
(its original config was M=8, N=288, P=2, Q=6 → 144 MHz, scale 2, 4 WS).

## 2. Measurement methodology

The numbers below are measured from the **exact dynamic instruction trace** of the
real compiled CMSIS-DSP code, costed with the **Cortex-M4 instruction timing table**:

1. Sources: CMSIS-DSP **1.10.0** from /home/kirill/work/STM32CubeF4 (`arm_cfft_f32.c`,
   `arm_cfft_radix8_f32.c`, `arm_cfft_init_f32.c`, `arm_bitreversal2.c`,
   `arm_cmplx_mag_f32.c`, `arm_common_tables.c`, `arm_const_structs.c`).
   Compiled with `arm-none-eabi-gcc 10.3.1 -Os` (the reference project's CubeIDE
   optimization setting), `-mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard`.
2. Executed under QEMU (`qemu-system-arm -M netduinoplus2`, STM32F405 — same
   Cortex-M4F core and clock tree as the F407) with
   `-d nochain,exec -accel tcg,one-insn-per-tb=on`: every executed guest
   instruction produces one trace line, so instruction counts between the
   marker functions are exact.
3. Each traced instruction is costed per the Cortex-M4 TRM:
   FP ALU (`vadd/vsub/vmul/vfma/vfms/vmov/vcvt/vcmp/vmrs`) = 1 cycle,
   `VLDR/VSTR/LDR/STR` = 2, taken branch / `BL` = 3, not-taken conditional = 1,
   `BX` = 2, `PUSH/POP/LDM/STM` = 1+n, **`VSQRT.F32` = 14**.
   Branch direction is taken from the actual successor PC in the trace.
4. Functional check: a 50 Hz sine at 8192 Hz sample rate must put the spectral
   peak in bin 25 — the run prints `peak bin (expect 25) = 25`. OK.

Why not DWT CYCCNT in QEMU: the STM32F405 machine model does not implement the
DWT unit — CYCCNT reads 0 (verified), and QEMU is not cycle-accurate in any
case (it would count instructions, not pipeline behaviour). The instruction
trace + TRM timing model above is the faithful substitute; for hardware-exact
numbers flash `build/hw407_Os.elf` and read DWT CYCCNT in a debug session.

## 3. Results (SYSCLK = 168 MHz)

| Function (N = 4096) | Instructions | CPU cycles | Time @ 168 MHz |
|---|---:|---:|---:|
| `arm_cfft_f32` forward + bit reversal | 323,357 | **446,720** | **2.659 ms** |
| `arm_cmplx_mag_f32` | 106,505 | **266,265** | **1.585 ms** |
| both, one after the other (psd pipeline) | 429,862 | **712,985** | **4.244 ms** |

Breakdown of `arm_cfft_f32` (446,720 cycles):

| Part | Instructions | Cycles | Share |
|---|---:|---:|---:|
| `arm_radix8_butterfly_f32` (all 4 stages: 585 plain + 1463 twiddle butterflies) | 287,029 | 382,131 | 85.5 % |
| `arm_bitreversal_32` (2016 index swaps) | 36,295 | 64,529 | 14.4 % |
| dispatch + call overhead | 33 | 60 | 0.0 % |

Breakdown of `arm_cmplx_mag_f32` (266,265 cycles = 65.0 cycles per sample):

| Part | Cycles | Per sample |
|---|---:|---:|
| loop body (2×VLDR, VMUL+VFMA, range check, VSTR) | 102,419 | 25.0 |
| `sqrtf` newlib wrapper (errno handling) | 98,304 | 24.0 |
| `__ieee754_sqrtf` (`VSQRT.F32` + return) | 65,536 | 16.0 |

## 4. Notes

* **sqrtf wrapper dominates the magnitude**: 40 of 65 cycles per sample are the
  sqrt path, of which 26 are newlib's errno checks rather than arithmetic.
  Compiling with `-ffast-math`/`-fno-math-errno` (or replacing `sqrtf` with
  bare `VSQRT`) would drop `arm_cmplx_mag_f32` to ≈ 168k cycles ≈ 1.0 ms.
* Bit reversal costs 14.4 % of the FFT; `bitReverseFlag = 0` saves 64.5k cycles
  (0.384 ms) when natural-order output can be tolerated.
* The cycle model assumes zero-wait code/data access (SRAM execution, or flash
  with ART prefetch + branch cache, which is close for this loop-heavy code;
  worst case flash-bound adds roughly 10–30 %).
* Numbers are for `-Os`; `-O2` changes scheduling but little overall work.
* Measured on the STM32F405 QEMU machine; F405 and F407 share the same
  Cortex-M4F core, FPU and clock tree, so the counts apply to the F407 at the
  same 168 MHz SYSCLK.

## 5. Reproducing

Project: `arm/cfft_bench/` (self-contained; sources copied from STM32CubeF4).

```bash
cd arm/cfft_bench
make all                 # qemu + hardware (F405/F407) ELFs
make run                 # functional run: prints peak-bin check, DWT probe
make trace1              # single-iteration run, /tmp/qemu1.log (1 insn = 1 line)
python3 trace_cycles.py  # instruction + cycle counts and per-function split
```

`python3 analyze.py <disasm>` contains the standalone static loop analyzer;
`build/hw407_Os.elf` is flashable on the Discovery board (semihosting output in
a debug session) to replace the modeled cycle numbers with hardware DWT counts.
