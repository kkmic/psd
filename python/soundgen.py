# Source - https://stackoverflow.com/a/37423879
# Posted by mdornfe1
# Retrieved 2026-06-04, License - CC BY-SA 3.0

import numpy as np
import matplotlib.pyplot as plt
# import sounddevice as sd

sampleRate = 44100
seconds = 3
f = 440
f2 = 10
t = np.linspace(0, seconds, seconds*sampleRate)
# signal = 0.5 * np.sin(2*np.pi*f*t) * np.sin(2*np.pi*f2*t)
signal = 0.5 * np.sin(2*np.pi*f*t) / np.exp(t*3*np.e)

# sd.play(signal, sampleRate, blocking=False)

fig, ax = plt.subplots()
ax.plot(t, signal)
ax.axhline(y=0, color="grey", linestyle=":")
ax.set_xlim(0, 0.5)
plt.show()

