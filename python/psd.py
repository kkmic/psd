import numpy as np
from scipy import signal
import matplotlib.pyplot as plt
rng = np.random.default_rng()


fs = 10e3
N = 1e5
amp = 2*np.sqrt(2)
print (amp)

freq = 1234.0
noise_power = 0.001 * fs / 2
time = np.arange(N) / fs
x = amp*np.sin(2*np.pi*freq*time)
x += rng.normal(scale=np.sqrt(noise_power), size=time.shape)

f, Pxx_den = signal.periodogram(x, fs)

iPMax = np.argmax(Pxx_den)

print (iPMax, f[iPMax], Pxx_den[iPMax], np.sqrt(Pxx_den[iPMax]))

# plt.semilogy(f, Pxx_den)
plt.plot(f, Pxx_den)
plt.axvline(x=freq, color='grey', linestyle=":")
plt.ylim([0, 1e2])
plt.xlim([1220, 1240])
plt.xlabel('frequency [Hz]')
plt.ylabel('PSD [V**2/Hz]')
plt.show()

