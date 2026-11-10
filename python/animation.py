import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

f = 50 # HZ
sampleRate = 10000 # samples/sec

fragmentLength = 10 #sec
tfr = np.linspace(0, fragmentLength, fragmentLength * sampleRate)

signals = 5

f1 = np.sin(2 * np.pi * f * tfr)
f2 = 2 * np.sin(2 * np.pi * f * tfr)
f3 = np.full(fragmentLength * sampleRate, 0.5)
f4 = 1.5 * np.sin(2 * np.pi * f * 2 * tfr)

f5 = np.empty(fragmentLength * sampleRate)
sign = 1
for i in range(len(f5)):
    f5[i] = sign * 1.2
    if ((i + 1) % 200 == 0):
        sign = -sign

signalLength = signals * fragmentLength
t = np.linspace(0, signalLength, signalLength * sampleRate)
s = np.concat((f1, f2, f3, f4, f5))
noise = np.random.rand(signalLength * sampleRate) * 0.1 - 0.05

signal = s + noise

frameWidth = 1/5 # sec
frameBounds = int(sampleRate * frameWidth)

fig, ax = plt.subplots()

sl = ax.plot(t[0:frameBounds], signal[0:frameBounds], color='red', linewidth=1.0)
ax.set(xlim=[0, frameWidth], ylim=[-2.5, 2.5], xlabel='Time [s]')

def update(frame):
    x = t[frameBounds*frame : frameBounds*(frame+1)]
    y = signal[frameBounds*frame : frameBounds*(frame+1)]
    sl[0].set_data(x, y)
    ax.set_xlim(frameWidth * frame, frameWidth * (frame +1))
    return sl[0]


ani = animation.FuncAnimation(fig=fig, func=update, frames=int(signalLength / frameWidth), interval=frameWidth*100, blit=True)
plt.show()