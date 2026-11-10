import numpy as np
from matplotlib import pyplot

# a = np.array([10+3j, 20-23.7j, -30+0.78j])

# print (a)
# print (a.shape)

# b = 2 * np.array(a.shape)
# print (b, len(b))

# c = np.zeros(2 * np.array(a.shape))

# print (c, len(c))

# c[0] = 12
# c[5] = 34


nb = 128
nbx = 2 * np.pi * np.arange(nb)
x = nbx / nb

signal = np.cos(x)

plx = np.arange(nb)
# pyplot.plot(plx, nbx, ".-", color="#ff5030", label="nbx")
pyplot.plot(plx, x, ".-", color="#50ff30", label="x")
pyplot.plot(plx, signal, ".-", color="#5030ff", label="signal")
pyplot.legend()

pyplot.show()
