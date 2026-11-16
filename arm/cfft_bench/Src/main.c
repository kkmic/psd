/**
 * Benchmark: arm_cfft_f32 / arm_cmplx_mag_f32, 4096 complex samples.
 * Base project: STM32CubeF4 Projects/STM32F4-Discovery/Examples/ADC/ADC_RegularConversion_DMA
 * RCC modified per request: HSE 8 MHz, M=4, N=168, P=2, Q=7 -> SYSCLK = 168 MHz.
 *   - PLL input = 8/4 = 2 MHz (RM0090: 1..2 MHz, 2 MHz recommended)
 *   - VCO = 2 * 168 = 336 MHz (RM0090: 100..432 MHz)
 *   - SYSCLK = 336/2 = 168 MHz; PLL48CK = 336/7 = 48 MHz
 *   - required side effects: regulator scale 1 (scale 2 caps at 144 MHz),
 *     flash latency 5 WS (was 4).
 *
 * Timing via DWT CYCCNT. Output via semihosting SYS_WRITE0 (works under
 * QEMU and under an ST-Link/GDB debug session on real hardware).
 *
 * BENCH_QEMU: skips HAL clock setup (QEMU's stm32f405 machine does not
 * model RCC oscillators); the DSP functions and DWT measurement are
 * unaffected - cycles counted are the same code bytes.
 */
#include "stm32f4xx_hal.h"
#include "arm_math.h"

#define FFT_LEN   4096
#ifndef ITERS
#define ITERS     20
#endif

/* Trace markers: called immediately before/after each measured call.
 * Under `qemu -d nochain,exec` each call shows up as exactly one TB
 * execution in the trace log, bracketing the measured function. */
#define MARK_NOINLINE __attribute__((noinline, used))
static void MARK_NOINLINE mark_cfft_begin(void) { __asm volatile("nop"); }
static void MARK_NOINLINE mark_cfft_end(void)   { __asm volatile("nop"); }
static void MARK_NOINLINE mark_mag_begin(void)  { __asm volatile("nop"); }
static void MARK_NOINLINE mark_mag_end(void)    { __asm volatile("nop"); }

#ifndef BENCH_QEMU
static void SystemClock_Config(void);
#endif

/* ---- DWT / semihosting helpers ---- */
#define DEMCR      (*(volatile uint32_t *)0xE000EDFC)
#define DWT_CTRL   (*(volatile uint32_t *)0xE0001000)
#define DWT_CYCCNT (*(volatile uint32_t *)0xE0001004)

static void sh_write0(const char *s)
{
    register uint32_t r0 __asm("r0") = 0x04; /* SYS_WRITE0 */
    register uint32_t r1 __asm("r1") = (uint32_t)s;
    __asm volatile("bkpt 0xab" : "+r"(r0) : "r"(r1) : "memory");
}

static void sh_exit(void)
{
    register uint32_t r0 __asm("r0") = 0x18;      /* SYS_EXIT */
    register uint32_t r1 __asm("r1") = 0x20026;   /* ADP_Stopped_ApplicationExit */
    __asm volatile("bkpt 0xab" : "+r"(r0) : "r"(r1) : "memory");
}

static void print_line(const char *label, uint32_t v)
{
    char buf[64];
    int i = 0, j;
    while (label[i] && i < 40) { buf[i] = label[i]; i++; }
    buf[i++] = '=';
    /* decimal itoa */
    char tmp[12];
    int n = 0;
    if (v == 0) tmp[n++] = '0';
    while (v > 0) { tmp[n++] = '0' + (v % 10); v /= 10; }
    for (j = n - 1; j >= 0; j--) buf[i++] = tmp[j];
    buf[i++] = '\n';
    sh_write0(buf);
    (void)buf;
}

static void Error_Handler(void)
{
    sh_write0("ERROR_HANDLER\n");
    sh_exit();
    while (1) { }
}

/* ---- benchmark state ---- */
static arm_cfft_instance_f32 S;
static float32_t fft_buf[2 * FFT_LEN];   /* 32 KB, in-place FFT */
static float32_t mag_buf[FFT_LEN];       /* 16 KB */

static uint32_t best, worst, sum;
static uint32_t t0, t1;

static void fill_input(void)
{
    /* 50 Hz sine, 8192 Hz sample rate -> exact FFT bin 25 for N=4096 */
    for (int k = 0; k < FFT_LEN; k++) {
        fft_buf[2 * k]     = arm_sin_f32(2.0f * 3.14159265358979f * 50.0f * (float)k / 8192.0f);
        fft_buf[2 * k + 1] = 0.0f;
    }
}

int main(void)
{
#ifdef BENCH_QEMU
    SystemCoreClock = 168000000u; /* RCC not modeled in QEMU; informational only */
#else
    HAL_Init();
    SystemClock_Config();
#endif

    /* DWT cycle counter */
    DEMCR |= (1u << 24);          /* TRCENA */
    DWT_CYCCNT = 0;
    DWT_CTRL |= 1u;               /* CYCCNTENA */

    sh_write0("\n--- CMSIS-DSP benchmark, fftLen=4096, SYSCLK=168 MHz ---\n");
    print_line("SystemCoreClock", SystemCoreClock);
    print_line("DWT_CYCCNT alive", DWT_CYCCNT);

    if (arm_cfft_init_f32(&S, FFT_LEN) != ARM_MATH_SUCCESS)
        Error_Handler();

    /* warm-up (fill also re-arms the in-place buffer for each run) */
    fill_input();
    arm_cfft_f32(&S, fft_buf, 0, 1);

    /* 1) arm_cfft_f32, forward, bit reversal ON (as used in psd smt.c / cmsis.test.py) */
    best = 0xFFFFFFFFu; worst = 0; sum = 0;
    for (int it = 0; it < ITERS; it++) {
        fill_input();
        t0 = DWT_CYCCNT;
        mark_cfft_begin();
        arm_cfft_f32(&S, fft_buf, 0, 1);
        mark_cfft_end();
        t1 = DWT_CYCCNT;
        uint32_t d = t1 - t0;
        sum += d;
        if (d < best) best = d;
        if (d > worst) worst = d;
    }
    print_line("cfft_f32 4096 fwd+bitrev best", best);
    print_line("cfft_f32 4096 fwd+bitrev worst", worst);
    print_line("cfft_f32 4096 fwd+bitrev avg", sum / ITERS);

    /* correctness: spectral peak must sit in bin 25 (50 Hz * 4096 / 8192) */
    arm_cmplx_mag_f32(fft_buf, mag_buf, FFT_LEN);
    {
        uint32_t max_i = 0; float32_t max_v = 0.0f;
        for (int k = 0; k < FFT_LEN / 2; k++)
            if (mag_buf[k] > max_v) { max_v = mag_buf[k]; max_i = k; }
        print_line("peak bin (expect 25)", max_i);
    }

    /* 2) arm_cfft_f32, forward, bit reversal OFF (isolates bitrev cost) */
    best = 0xFFFFFFFFu; worst = 0; sum = 0;
    for (int it = 0; it < ITERS; it++) {
        fill_input();
        t0 = DWT_CYCCNT;
        arm_cfft_f32(&S, fft_buf, 0, 0);
        t1 = DWT_CYCCNT;
        uint32_t d = t1 - t0;
        sum += d;
        if (d < best) best = d;
        if (d > worst) worst = d;
    }
    print_line("cfft_f32 4096 fwd nobitrev best", best);
    print_line("cfft_f32 4096 fwd nobitrev avg", sum / ITERS);

    /* 3) arm_cmplx_mag_f32 over the full 4096-sample FFT output */
    best = 0xFFFFFFFFu; worst = 0; sum = 0;
    for (int it = 0; it < ITERS; it++) {
        fill_input();
        arm_cfft_f32(&S, fft_buf, 0, 1);   /* fresh spectrum as input */
        t0 = DWT_CYCCNT;
        mark_mag_begin();
        arm_cmplx_mag_f32(fft_buf, mag_buf, FFT_LEN);
        mark_mag_end();
        t1 = DWT_CYCCNT;
        uint32_t d = t1 - t0;
        sum += d;
        if (d < best) best = d;
        if (d > worst) worst = d;
    }
    print_line("cmplx_mag_f32 4096 best", best);
    print_line("cmplx_mag_f32 4096 worst", worst);
    print_line("cmplx_mag_f32 4096 avg", sum / ITERS);

    sh_write0("--- done ---\n");
    sh_exit();
    while (1) { }
}

#ifndef BENCH_QEMU
/**
 * System clock -> 168 MHz from the 8 MHz HSE crystal:
 * PLLM=4, PLLN=168, PLLP=2, PLLQ=7.
 */
static void SystemClock_Config(void)
{
    RCC_ClkInitTypeDef RCC_ClkInitStruct;
    RCC_OscInitTypeDef RCC_OscInitStruct;

    __HAL_RCC_PWR_CLK_ENABLE();

    /* 168 MHz requires regulator voltage scale 1 (scale 2 tops out at 144 MHz) */
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    RCC_OscInitStruct.HSEState = RCC_HSE_ON;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    RCC_OscInitStruct.PLL.PLLM = 4;            /* 8 MHz / 4 = 2 MHz PLL input   */
    RCC_OscInitStruct.PLL.PLLN = 168;          /* VCO = 336 MHz                  */
    RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;/* SYSCLK = 168 MHz               */
    RCC_OscInitStruct.PLL.PLLQ = 7;            /* PLL48CK = 48 MHz               */
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
        Error_Handler();

    RCC_ClkInitStruct.ClockType = (RCC_CLOCKTYPE_SYSCLK | RCC_CLOCKTYPE_HCLK |
                                   RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2);
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;   /* HCLK  = 168 MHz */
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;    /* PCLK1 =  42 MHz (max) */
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;    /* PCLK2 =  84 MHz (max) */
    /* 168 MHz at 2.7..3.6 V needs 5 flash wait states */
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
        Error_Handler();

    if (HAL_GetREVID() >= 0x1001)
        __HAL_FLASH_PREFETCH_BUFFER_ENABLE();
}
#endif
