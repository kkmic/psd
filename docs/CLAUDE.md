# psd — Power Spectral Density tools

PC-side reference implementation (C++/Python) plus an embedded C port for
STM32F407.

## Files

- `psd.h` — reference implementation (C++, header-only, namespace `psd`).
  `psd::compute_psd(input, n, sample_rate, mean)` and `psd::freq_axis(n, sample_rate)`.
- `example.cpp` — usage example for the C++ header.
- `smt.c` — C port of `psd::compute_psd` for STM32F407 (Cortex-M4F), uses
  STM32 HAL + CMSIS-DSP.
- `psd.py`, `test.py`, `animation.py`, `display.py`, `soundgen.py` — Python
  helpers/visualizers for the output files.
- `hanning.txt`, `fft.txt`, `psd.txt` — debug dumps written by `compute_psd`
  when run on the PC (not written by the embedded port).

## Algorithm (reference, psd.h)

1. Truncate sample count `n` to the largest power of two `N` (min 2).
2. Remove DC: `val = input[i] - mean` (`mean` passed in by the caller).
   Hanning window exists in the code but is commented out (inactive).
3. Radix-2 Cooley-Tukey FFT, interleaved `[re, im]` doubles, **unnormalized**,
   no window scaling.
4. `psd[k] = 2 * (re^2 + im^2)` for k = 1..N/2-1; DC (k=0) and Nyquist (k=N/2)
   bins are not doubled. `scale = 1.0` (Parseval/density normalization
   disabled). Returns N/2 + 1 bins, DC..Nyquist.
5. Writes debug dumps `hanning.txt`, `fft.txt`, `psd.txt` (PC only).

## smt.c — STM32F407 port

`size_t psd_compute_psd(const uint16_t *input, size_t n, float32_t sample_rate,
float32_t mean, float32_t *psd_out)` — same math/result as `psd::compute_psd`.

Port decisions:

- FFT via CMSIS-DSP `arm_cfft_f32` (same interleaved layout, unnormalized) —
  this is what exercises the M4F DSP/FPU instructions.
- **float32, not double** — the F407 FPU is single-precision only; doubles are
  software-emulated (~20x slower).
- No file dumps (no filesystem on target).
- Static work buffer `psd_fft_buf[2 * PSD_MAX_FFT_LEN]` (default
  `PSD_MAX_FFT_LEN = 2048` → 16 KB RAM), no heap. Output goes to a
  caller-provided buffer of at least N/2 + 1 floats; returns bin count.
- FFT length limited to 16..4096 (CMSIS-DSP table range); lengths 2–8
  accepted by psd.h are rejected with return 0.
- `sample_rate` parameter kept for API parity, unused while `scale == 1.0`.
- Not reentrant (shared static buffer).

Build requirements for smt.c:

- STM32F4 HAL project, CMSIS-DSP library linked, `ARM_MATH_CM4` defined
  (smt.c defines it itself if missing).
- `-mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard`.

Possible speedup: `arm_rfft_fast_f32` (real-input FFT) halves cycles, output
format differs (DC and Nyquist packed as two reals in out[0], out[1], then
complex pairs for k = 1..N/2-1).
