import argparse
import matplotlib.pyplot as plt
import cmsisdsp as dsp
import numpy as np
import matplotlib.animation as animation

sampleRate = 8192
nb = 4096 # int(fragmentLength * sampleRate) // Source/TransformFunctions/arm_cfft_init_f32.c

#################################################################################
def imToReal(a):
    ar=np.zeros(2 * np.array(a.shape))
    ar[0::2]=a.real
    ar[1::2]=a.imag
    return ar

def realToIm(ar):
    return(ar[0::2] + 1j * ar[1::2])

def signalGenerator(amplitude, f, t, alpha):
    # return amplitude * np.sin(2 * np.pi * f * t / nb + alpha)
    # return amplitude * np.sin(2*np.pi*f*t/nb) + np.sin(2*np.pi*10*t/nb)
#    return amplitude * np.sin(2*np.pi*f*t/nb) / np.exp(t*3*np.e/nb)
    coeff = sampleRate // nb
    i = sampleRate // (2 * f * coeff) # 2 sides
    return np.array([amplitude if (n % (2*i) < i) else -amplitude for n in t])


#################################################################################
F = 50 # Hz
t = np.arange(nb)
A = 1
PHASE_ANGLE = 0
FREQ_SWEEP = range(50, 100) # Hz, frames of updateFrequency

signal = signalGenerator(amplitude = A,
                            f = F, # Hz
                            t = t,
                            alpha = PHASE_ANGLE)

cfftf32 = dsp.arm_cfft_instance_f32()
status = dsp.arm_cfft_init_f32(cfftf32, nb)

if (status != 0):
    print (f"arm_cfft_init_f32 status = {status}")
    exit(1)

signalR = imToReal(signal)

resultR = dsp.arm_cfft_f32(cfftf32, signalR, 0, 1)

mag = dsp.arm_cmplx_mag_f32(resultR)
# mag = dsp.arm_cmplx_mag_squared_f32(resultR)

#################################################################################

fig, (signalPlot, fftPlot, magPlot) = plt.subplots(3, 1, figsize=(15, 10))
# fig.patch.set_facecolor("#fcfcfb")

sl = signalPlot.plot(t, signal, '.-', color="#2a78d6", linewidth=1, label=f"alpha={PHASE_ANGLE} deg, f={F} Hz")
signalPlot.set_facecolor("#fcfcfb")
sll = signalPlot.legend(loc="center right")

signalPlot.set_ylabel("Amplitude", color="#898781")

signalPlot.grid(True, color="#e1e0d9", linewidth=0.8)
signalPlot.tick_params(colors="#898781", labelcolor="#898781")

# end = len(signal)

fft = np.arange(nb//2)
re = resultR[0:nb:2]
im = resultR[1:nb:2]

flr = fftPlot.plot(fft, re, '.', color="#2a78d680", label="FFT Real", linewidth=1)
fli = fftPlot.plot(fft, im, '.', color="#ff78d680", label="FFT Img", linewidth=1)
fftPlot.grid(True, color="#e1e0d9", linewidth=0.5)

# yMax = np.max(re)
# fftPlot.axhline(y=yMax, color="#d00000", label=f"{yMax:.2f}", linewidth = 0.5)
# fftPlot.axvline(x=F, color="#00d000", label=f"{F} Hz", linewidth = 0.5)
fftPlot.legend(loc="center right")
fftPlot.set_ylim(-nb*A - 20, nb*A + 20)
# fftPlot.tick_params(colors="#898781", labelcolor="#898781")

# scan the plotted half only: the spectrum is symmetric, so a full-array argmax can
# return the mirror bin nb-k, which lies outside the plotted 0..nb/2 range
max, fMax = dsp.arm_max_f32(mag[0:nb//2])
rms = dsp.arm_rms_f32(resultR)
norm = rms / np.sqrt(2)
ml = magPlot.plot(fft, mag[0:nb//2], '.', color="#2a78d6", label="Square Magnitude")
# axvline/axhline return a plain Line2D (not a container), so keep the handles:
# they are what the update functions move via set_xdata/set_ydata.
mlv = magPlot.axvline(x=fMax, color="#00d000", label=f"{fMax} Hz", linewidth = 0.5)
mlh = magPlot.axhline(y=max, color="#ffd000", label=f"{max:.2f}", linewidth = 0.5)
mlr = magPlot.axhline(y=rms, color="#d00000", label=f"RMS: {rms:.2f}, Norm: {norm:.2f}", linewidth = 0.5)
magPlot.grid(True, color="#e1e0d9", linewidth=0.5)
magPlot.set_xlabel("Sample", color="#000000")
mll = magPlot.legend(loc="center right")

# blit=True freezes the axes background, so the y-limits must already cover every
# frame before the animation starts: scan the sweep the markers will walk.
sweepPeak = 0.0
for fr in FREQ_SWEEP:
    frMag = dsp.arm_cmplx_mag_f32(dsp.arm_cfft_f32(cfftf32, imToReal(signalGenerator(A, fr, t, PHASE_ANGLE)), 0, 1))
    sweepPeak = np.max([sweepPeak, np.max(frMag[0:nb//2])])
magPlot.set_ylim(-sweepPeak * 0.02, sweepPeak * 1.1)

def updatePhase(phaseAngle):
    signal = signalGenerator(amplitude = A,
                            f = F, # Hz
                            t = t,
                            alpha = phaseAngle)

    signalR = imToReal(signal)
    resultR = dsp.arm_cfft_f32(cfftf32, signalR, 0, 1)
    mag = dsp.arm_cmplx_mag_f32(resultR)

    sl[0].set_ydata(signal)
    sll.get_texts()[0].set_text(f"alpha={phaseAngle} deg, f={F}Hz")
    flr[0].set_ydata(resultR[0:nb:2])
    fli[0].set_ydata(resultR[1:nb:2])
    ml[0].set_ydata(mag[0:nb//2])

    return *sl, sll, *flr, *fli, *ml

def updateFrequency(frequency):
    signal = signalGenerator(amplitude = A,
                            f = frequency, # Hz
                            t = t,
                            alpha = PHASE_ANGLE)

    print (f"Call updateFrequency to {frequency}")

    signalR = imToReal(signal)
    resultR = dsp.arm_cfft_f32(cfftf32, signalR, 0, 1)
    mag = dsp.arm_cmplx_mag_f32(resultR)[0:nb//2]
    rms = dsp.arm_rms_f32(resultR)
    sq = rms / np.sqrt(2)
    mx, fmax = dsp.arm_max_f32(mag)

    sl[0].set_ydata(signal)
    sll.get_texts()[0].set_text(f"alpha={PHASE_ANGLE} deg, f={frequency}Hz")
    flr[0].set_ydata(resultR[0:nb:2])
    fli[0].set_ydata(resultR[1:nb:2])
    ml[0].set_ydata(mag)

    # # A vline is a two-point Line2D spanning y in axes coordinates, so only its x
    # # is data and both points must be given; an hline is the mirror image.
    mlv.set_xdata([fmax, fmax])
    mlh.set_ydata([mx, mx])
    mlr.set_ydata([rms, rms])

    # # legend texts follow artist insertion order: 0 plot, 1 vline, 2 max, 3 rms
    mll.get_texts()[1].set_text(f"{fmax} Hz")
    mll.get_texts()[2].set_text(f"{mx:.2f}")
    mll.get_texts()[3].set_text(f"RMS: {rms:.2f}, Norm: {sq:.2f}")

    return *sl, sll, *flr, *fli, *ml, mlv, mlh, mlr, mll

is_paused = False

def main():
    parser = argparse.ArgumentParser(description = "CMSIS-DSP CFFT test/visualization")
    parser.add_argument("-phase", action = "store_true",
                        help = "run the alpha phase sweep animation")
    args = parser.parse_args()

    if args.phase:
        ani = animation.FuncAnimation(fig=fig, func=updatePhase, frames=range(-90, 91), interval=200, blit=True)
    else:
        ani = animation.FuncAnimation(fig=fig, func=updateFrequency, frames=range(50, 100), interval=100, blit=True)

    # 3. Define the event handler to toggle pause/resume
    def on_click(event):
        global is_paused
        if is_paused:
            ani.resume()  # Resume the framework timer
            print("Animation Resumed")
        else:
            ani.pause()   # Pause the framework timer
            print("Animation Paused")
        is_paused = not is_paused

    # 4. Connect the click event to the handler
    fig.canvas.mpl_connect('button_press_event', on_click)

    plt.show()


if __name__ == "__main__":
    main()
