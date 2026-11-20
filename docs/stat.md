# STM32F407 @ 168 MHz — arm_cfft_f32 / arm_cmplx_mag_f32 measurements (N = 4096)

## 1. Clock configuration

Board: **STM32F4-Discovery** (schematic MB997 rev B2) — MCU STM32F407VGT6,
HSE crystal **X2 = 8 MHz** on PH0/PH1 (LCE 32.768 kHz not fitted).

RCC values, checked against RM0090 Rev 22 (docs/stm32f407-reference-manual.pdf):

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

## 2. Methodology

Measured **on the real board** with the DWT cycle counter (CMSIS core_cm4.h
definitions: 
```c
CoreDebug->DEMCR |= TRCENA
DWT->CTRL |= CYCCNTENA
```
read
`DWT->CYCCNT` around each call). 20 iterations per measurement; the program
prints best/worst/average via semihosting, captured by openocd
(`board/stm32f4discovery.cfg`, ST-LINK/V2.1).

Build: CMSIS-DSP 1.10.0 sources from STM32CubeF4, `arm-none-eabi-gcc 10.3.1 -Os`
(the reference project's optimization level):
```c++
-mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard
```
Code in flash (5 WS + ART prefetch). Functional check: a
50 Hz sine at 8192 Hz sample rate puts the spectral peak in bin 25 — the run
prints `peak bin (expect 25) = 25`. OK.

## 3. Results (hardware DWT, SYSCLK = 168 MHz)

| Function (N = 4096) | Best | Average | Time @ 168 MHz |
|---|---:|---:|---:|
| `arm_cfft_f32` forward + bit reversal | 522,810 | **523,150** | **3.113 ms** |
| `arm_cfft_f32` forward, no bit reversal | 467,771 | **468,136** | 2.786 ms |
| bit-reversal share (difference) | — | 55,014 | 0.327 ms |
| `arm_cmplx_mag_f32` | 237,703 | **237,725** | **1.415 ms** |
| both, one after the other (psd pipeline) | — | **760,875** | **4.529 ms** |

Best-to-worst spread is ≈ 0.08 % (SysTick at 1 kHz lands inside some windows).

Cross-check with the earlier QEMU instruction-trace + Cortex-M4 TRM timing
model (zero-wait-memory assumption): the model gave 446,720 cycles for the FFT
(17 % below hardware — the flash wait-state effect it explicitly could not
model) and 266,265 for the magnitude (11 % above hardware — the model
over-costed streaming loads and VSQRT pipelining). The board numbers above are
the authoritative ones.

## 4. Notes

* **sqrtf wrapper dominates the magnitude**: from the earlier instruction-level
  analysis, 40 of 65 cycles per sample are the sqrt path and 26 of those are
  newlib's errno checks rather than arithmetic. `-ffast-math` /
  `-fno-math-errno` would cut `arm_cmplx_mag_f32` to ≈ 1.0 ms.
* Bit reversal costs 10.5 % of the FFT here; `bitReverseFlag = 0` saves
  55k cycles (0.33 ms) when natural-order output can be tolerated.
* Timing includes execution from flash with 5 wait states and the ART
  prefetch/branch cache active — exactly what a firmware build of psd sees.
* Raw DWT register readout via gdb (while an openocd server is attached):
  `DWT_CTRL = 0x40000001` (CYCCNTENA set), `DEMCR = 0x01000000` (TRCENA).

## 5. Reproducing

Project: `arm/cfft_bench/` (self-contained; sources copied from STM32CubeF4).

```bash
cd arm/cfft_bench
make all            # build build/hw_Os.elf (~931 KB, fits the 1 MB flash)
make flash          # flash + run; DWT results print via semihosting
# alternative DWT access: in one terminal `make server`, in another:
make dwt            # gdb-multiarch reads DWT_CTRL / DWT_CYCCNT / DEMCR
```
