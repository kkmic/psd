// Example: compute and print PSD from synthetic ADC data
// Compile: clang++ -O2 -o example example.cpp -lm

#include "psd.h"
#include <iostream>
#include <cstdlib>
#include <vector>

int main() {
    const size_t N = 512;
    const double sample_rate = 10000.0; // 10 kHz
  //  const double freq = 500.0;          // 500 Hz tone
    const double mean = 32768.0;

    // Simulate ADC output: 500 Hz sine + noise, centered at ADC midpoint
    std::vector<uint16_t> adc(N);
    int sign = 1;
    for (size_t i = 0; i < N; i++) {
//        double t = (double)i / sample_rate;
        // double signal = 2000.0 * sin(2.0 * M_PI * freq * t);
        double signal = 2000.0 * sign;
        if ( i % 10 == 0 ) sign = -sign;

        // double noise = (double)(rand() % 200 - 100);
        // double val = mean + signal + noise;
        double val = mean + signal;
        if (val < 0) val = 0;
        if (val > 65535) val = 65535;
        adc[i] = (uint16_t)val;
    }

    // Compute PSD
    std::vector<double> psd = psd::compute_psd(adc.data(), N, sample_rate, mean);
    std::vector<double> freqs = psd::freq_axis(N, sample_rate);

    // // Print first 50 bins (show the 500 Hz peak)
    std::cout << "Freq (Hz)\tPSD (counts^2/Hz)" << std::fixed << std::endl;
    // for (size_t i = 0; i < psd.size(); i++) {
    //     // std::cout << i << " : " << freqs[i] << "\t" << psd[i] << std::endl;
    //     std::cout << i << " : " << std::setprecision (1) << freqs[i] << "\t" << std::setprecision (2) << psd[i] << std::endl;
    //     // printf("%zu: %.1f\t\t%.2f\n", i, freqs[i], psd[i]);
    // }

    // Find peak frequency
    size_t peak = 0;
    for (size_t i = 1; i < psd.size(); i++) {
        if (psd[i] > psd[peak]) peak = i;
    }

    std::cout << std::endl << "Peak at: " << std::setprecision (1) << freqs[peak] << " Hz, PSD = " << std::setprecision (2) << psd[peak] << std::endl;

    return 0;
}
