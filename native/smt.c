/*
 * psd_compute_psd() — C port of psd::compute_psd() from psd.h for the
 * STM32F407 (Cortex-M4F). The FFT is done by CMSIS-DSP (arm_cfft_f32),
 * which is built on the Cortex-M4 single-precision FPU and DSP
 * instructions; doubles are avoided (software-emulated on the M4F).
 *
 * Build requirements:
 *   - STM32F4 HAL project (stm32f4xx_hal.h)
 *   - CMSIS-DSP library linked (arm_math.h), ARM_MATH_CM4 defined
 *   - -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard
 *
 * Differences from the C++ original: float32 instead of double, no debug
 * file dumps (no filesystem), output written to a caller buffer, FFT
 * length limited to the CMSIS-DSP table range 16..4096.
 */

#include <stddef.h>
#include <stdint.h>

#include "stm32f4xx_hal.h"

#ifndef ARM_MATH_CM4
#define ARM_MATH_CM4
#endif
#include "arm_math.h"

/* Maximum FFT length (power of two); CMSIS-DSP covers 16..4096.
 * Static work buffer costs 2 * PSD_MAX_FFT_LEN floats of RAM. */
#ifndef PSD_MAX_FFT_LEN
#define PSD_MAX_FFT_LEN 2048
#endif

/* Interleaved re/im FFT work buffer [re0, im0, re1, im1, ...] */
static float32_t psd_fft_buf[2 * PSD_MAX_FFT_LEN];

/*
 * Compute Power Spectral Density from ADC samples.
 *
 * input:       raw ADC samples
 * n:           number of samples (truncated to largest power of two)
 * sample_rate: sampling frequency in Hz (kept for API parity; unused
 *              while scale == 1.0, as in psd.h)
 * mean:        DC offset removed from the samples before the FFT
 * psd_out:     caller buffer for N/2 + 1 PSD values (DC..Nyquist)
 *
 * Returns the number of bins written (N/2 + 1), or 0 if the truncated
 * length is outside 16..PSD_MAX_FFT_LEN. Not reentrant (static buffer).
 */
size_t psd_compute_psd(const uint16_t *input, size_t n,
                       float32_t sample_rate, float32_t mean,
                       float32_t *psd_out)
{
    (void)sample_rate;

    /* Truncate to the largest power of 2 that fits */
    size_t N = 1;
    while (N * 2 <= n)
        N <<= 1;

    if (N < 16 || N > PSD_MAX_FFT_LEN)
        return 0;

    /* Remove DC offset, pack into interleaved re/im buffer */
    for (size_t i = 0; i < N; i++) {
        psd_fft_buf[2 * i]     = (float32_t)input[i] - mean; /* re */
        psd_fft_buf[2 * i + 1] = 0.0f;                       /* im */
    }

    /* Forward FFT, unnormalized output (same as psd::fft) */
    arm_cfft_instance_f32 cfft;
    if (arm_cfft_init_f32(&cfft, (uint16_t)N) != ARM_MATH_SUCCESS)
        return 0;
    arm_cfft_f32(&cfft, psd_fft_buf, 0 /* forward */, 1 /* bit-reverse */);

    /* Scale is 1.0, as in psd.h (window/Parseval/density scaling disabled) */
    for (size_t k = 0; k <= N / 2; k++) {
        float32_t re = psd_fft_buf[2 * k];
        float32_t im = psd_fft_buf[2 * k + 1];
        float32_t mag2 = re * re + im * im;

        /* DC and Nyquist bins are not doubled */
        psd_out[k] = (k == 0 || k == N / 2) ? mag2 : 2.0f * mag2;
    }

    return N / 2 + 1;
}
