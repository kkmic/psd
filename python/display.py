from matplotlib import pyplot
import numpy as np


# https://matplotlib.org/stable/gallery/lines_bars_and_markers/csd_demo.html

# w = np.loadtxt("hanning.txt", usecols=0, skiprows=0, dtype=float, delimiter=":", comments="#") # Set skiprows to 1 if there are heading comments
val = np.loadtxt("hanning.txt", usecols=0, skiprows=0, dtype=float, delimiter=":", comments="#") # Set skiprows to 1 if there are heading comments
signal = np.loadtxt("hanning.txt", usecols=1, skiprows=0, dtype=float, delimiter=":", comments="#") # Set skiprows to 1 if there are heading comments

fig, ((wp, rep), (sp, imp), (vp, psdp)) = pyplot.subplots(3, 2)

# wp.plot(w, linewidth=1, color='blue', label=r"$w_{n} = \frac{1}{2}\left[1 -  {\rm cos}(\frac{2\pi n}{N-1})\right]$")
# wp.legend(fontsize=8)
# # ax1.axhline(y=0, color="grey", linestyle="--")
# wp.set_ylabel('w')

sp.plot(signal, linewidth=1, color='magenta')
sp.axhline(y=32768, color="grey", linestyle=":")
# ax2.legend(fontsize=8)
sp.set(ylabel='signal') # xlim=(0, 500),

vp.plot(val, linewidth=1, color='green', label=r"$v_{i} = \left(signal_{n} - \bar M\right) w_{n}$")
vp.legend(fontsize=8)
vp.axhline(y=0, color="grey", linestyle=":")
vp.set_ylabel('val')
vp.set_xlabel('n (samples)')

re = np.loadtxt("fft.txt", usecols=0, skiprows=0, dtype=float, delimiter=":", comments="#")
rep.plot(re, linewidth=1, color='blue')
rep.set_ylabel('Re(fft)')
rep.set(ylabel='Re(fft)')

im = np.loadtxt("fft.txt", usecols=1, skiprows=0, dtype=float, delimiter=":", comments="#")
imp.plot(im, linewidth=1, color='red')
imp.set(xlabel='n (samples)', ylabel='Im(fft)')

psd_f = np.loadtxt("psd.txt", usecols=0, skiprows=1, dtype=float, delimiter=":", comments="#")
psd_v = np.loadtxt("psd.txt", usecols=1, skiprows=1, dtype=float, delimiter=":", comments="#")

psdp.plot(psd_f, psd_v, color='green', label='PSD')
psdp.legend(fontsize=8)
psdp.axvline(x=500, color='grey', linestyle=":")
psdp.axvline(x=1500, color='grey', linestyle=":")
psdp.axvline(x=2500, color='grey', linestyle=":")
psdp.axvline(x=3500, color='grey', linestyle=":")
psdp.axvline(x=4500, color='grey', linestyle=":")
psdp.set(xlabel='HZ', ylabel='PSD') # xlim=(0, 550),

pyplot.show()
