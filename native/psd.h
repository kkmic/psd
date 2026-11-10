#pragma once

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <vector>
#include <iostream>
#include <iomanip>
#include <fstream>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace psd {

// Radix-2 Cooley-Tukey FFT (in-place, length must be power of 2)
// re[] and im[] are interleaved as pairs: [re0, im0, re1, im1, ...]
static void fft(double *data, size_t n) {
    // Bit-reversal permutation
    for (size_t i = 1, j = 0; i < n; i++) {
        size_t bit = n >> 1;
        while (j & bit) {
            j ^= bit;
            bit >>= 1;
        }
        j ^= bit;
        if (i < j) {
            double tmp0 = data[2 * i];
            double tmp1 = data[2 * i + 1];
            data[2 * i] = data[2 * j];
            data[2 * i + 1] = data[2 * j + 1];
            data[2 * j] = tmp0;
            data[2 * j + 1] = tmp1;
        }
    }

    // Butterfly stagesN
    for (size_t len = 2; len <= n; len <<= 1) {
        double ang = -2.0 * M_PI / (double)len;
        double w_re = cos(ang);
        double w_im = sin(ang);

        for (size_t i = 0; i < n; i += len) {
            double cur_re = 1.0, cur_im = 0.0;
            for (size_t j = 0; j < len / 2; j++) {
                size_t u = 2 * (i + j);
                size_t v = 2 * (i + j + len / 2);

                double t_re = cur_re * data[v] - cur_im * data[v + 1];
                double t_im = cur_re * data[v + 1] + cur_im * data[v];

                data[v] = data[u] - t_re;
                data[v + 1] = data[u + 1] - t_im;
                data[u] += t_re;
                data[u + 1] += t_im;

                double new_re = cur_re * w_re - cur_im * w_im;
                cur_im = cur_re * w_im + cur_im * w_re;
                cur_re = new_re;
            }
        }
    }
}

// Compute Power Spectral Density from ADC samples.
//
// input:      array of raw ADC values (unsigned short)
// n:          number of samples (will be truncated to the largest power of 2)
// sample_rate: sampling frequency in Hz
//
// Returns a vector of (N_fft/2 + 1) PSD values in units of (ADC_counts)^2 / Hz,
// from DC up to Nyquist (sample_rate / 2).
static std::vector<double> compute_psd(const uint16_t *input, size_t n,
                                       double sample_rate, double mean) {
    // Truncate to largest power of 2 that fits
    size_t N = 1;
    while (N * 2 <= n) N <<= 1;
    if (N < 2) return {};

    // Interleaved real/imag buffer for FFT
    std::vector<double> buf(2 * N);

    // Compute mean (DC offset) for removal
    // double mean = 0.0;
    // for (size_t i = 0; i < N; i++)
    //     mean += (double)input[i];
    // mean /= (double)N;

    // Remove DC, apply Hanning window, store into FFT buffer
    // double window_norm = 0.0;
    {
        std::ofstream out("hanning.txt");
        out << std::fixed << std::setprecision (5);

        for (size_t i = 0; i < N; i++) {
            // double w = 0.5 * (1.0 - cos(2.0 * M_PI * (double)i / (double)(N - 1)));
            // window_norm += w * w;

            // double val = ((double)input[i] - mean) * w;
            double val = ((double)input[i] - mean);

            // out << w << ":" << val << ":" << input[i] << std::endl;
            out << val << ":" << input[i] << std::endl;
            
            buf[2 * i] = val;      // real
            buf[2 * i + 1] = 0.0;  // imag
        }
    }

    // Forward FFT
    fft(buf.data(), N);
    {
        std::ofstream out("fft.txt");
        out << std::fixed << std::setprecision (5);

        for (size_t i = 0; i < N; i++) {
            out << buf[2 * i] << ":" << buf[2 * i + 1] << std::endl;
        }
    }

    // Frequency resolution
    double df = sample_rate / (double)N;

    // Scale factor: 2 for single-sided spectrum (except DC and Nyquist),
    // 1/(N^2 * window_norm / N) for Parseval, 1/df for density
    double scale = 1.0;// / ((double)N * window_norm * df);

    std::vector<double> psd(N / 2 + 1);
    std::ofstream psdFile("psd.txt");
    psdFile << std::fixed << std::setprecision (5)
            << "# df = " << df << ", scale = " << scale << std::endl;

    for (size_t k = 0; k <= N / 2; k++) {
        double re = buf[2 * k];
        double im = buf[2 * k + 1];
        double mag2 = re * re + im * im;

        // DC and Nyquist bins are not doubled
        if (k == 0 || k == N / 2)
            psd[k] = mag2 * scale;
        else
            psd[k] = 2.0 * mag2 * scale;
        
        psdFile << k * df << ":" << psd[k] << std::endl;
    }

    return psd;
}

// Return the frequency axis corresponding to compute_psd output
static std::vector<double> freq_axis(size_t n, double sample_rate) {
    size_t N = 1;
    while (N * 2 <= n) N <<= 1;
    if (N < 2) return {};

    std::vector<double> freqs(N / 2 + 1);
    double df = sample_rate / (double)N;
    for (size_t k = 0; k <= N / 2; k++)
        freqs[k] = (double)k * df;

    return freqs;
}

} // namespace psd
