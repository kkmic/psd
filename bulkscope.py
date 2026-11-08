import argparse
import os
import numpy as np
import matplotlib.pyplot as plt
import cmsisdsp as dsp
import matplotlib.animation as animation

#################################################################################

nb = 4096 # samples
sampleRate = 48800 # Samples/s

C = sampleRate / nb
FFT_MAX_FREQ=1000
N = int(FFT_MAX_FREQ / C)

fftX = np.linspace(0, FFT_MAX_FREQ, N)

#################################################################################
def imToReal(a):
    ar=np.zeros(2 * np.array(a.shape))
    ar[0::2]=a.real
    ar[1::2]=a.imag
    return ar

def realToIm(ar):
    return(ar[0::2] + 1j * ar[1::2])

def parseWaveform(filePath, baseTime):
    t = []
    signal = []
    
    with open(filePath) as f:
        for _ in range(3):
            f.readline()
        for line in f:
            timeStr, mVStr = line.split(";")
            t.append(float(timeStr.replace(",", ".")))
            signal.append(float(mVStr.replace(",", ".")))

    if len(t) > 0:
        offsetTime = t[0]

        if (offsetTime != 0.0): # Align timestamps if they are shifted behind 0
            for i in range(len(t)):
                t[i] = t[i] - offsetTime + baseTime

    return (np.array(t), np.array(signal))

def scanDir(dirPath):
    fileNames = sorted(f for f in os.listdir(dirPath) if f.endswith(".csv"))

    waveforms = []
    baseTime = 0
    counter = 1
    for fileName in fileNames:
        waveform = parseWaveform(os.path.join(dirPath, fileName), baseTime)
        waveforms.append(waveform)
        baseTime = waveform[0][-1] + 0.02048
        print ("+" if(counter %5 == 0) else ".", end="", flush=True)
        counter += 1

    print (" Done", flush=True)
    return waveforms

is_paused = False

def animate(t, signal):
    cfftf32 = dsp.arm_cfft_instance_f32()
    status = dsp.arm_cfft_init_f32(cfftf32, nb)

    if (status != 0):
        print (f"arm_cfft_init_f32 status = {status}")
        return

    signalR = imToReal(signal[:nb])
    resultR = dsp.arm_cfft_f32(cfftf32, signalR, 0, 1)

    fig, (signalPlot, fftPlot, magPlot) = plt.subplots(3, 1, layout="constrained", figsize=(15, 10))
    # Signal
    signalArtist = signalPlot.plot(t[:nb], signal[:nb], '-', color="#2a78d6", linewidth=1)
    signalPlot.grid(True, color="#e1e0d9", linewidth=0.8)

    # Complex DFFT
    fftRealArtist = fftPlot.plot(fftX, resultR[0:N*2:2], '.-', color="#2a78d680", label="FFT Real", linewidth=1)
    fftImgArtist = fftPlot.plot(fftX, resultR[1:N*2:2], '.-', color="#ff78d680", label="FFT Img", linewidth=1)
    fftPlot.axhline(y=0, color="#d0000080", label="0", linewidth = 0.5)
    fftPlot.grid(True, color="#e1e0d9", linewidth=0.5)
    fftPlot.legend(loc="upper right")
    fftPlot.set_xlabel("F, Hz", color="#000000")
    fftPlot.set_ylim(-60000, 60000)
    fftPlot.grid(True, color="#e1e0d9", linewidth=0.5)

    # Square Magnitutes
    mag = dsp.arm_cmplx_mag_f32(resultR)[:N]
    max, fIndex = dsp.arm_max_f32(mag)

    magArtist = magPlot.plot(fftX, mag, '.-', color="#2a78d6", label="Square Magnitude")
    magVArtist = magPlot.axvline(x=fftX[fIndex], color="#00d000", label=f"{fftX[fIndex]:.2f} Hz", linewidth = 0.5)
    magHArtist = magPlot.axhline(y=max, color="#ffd000", label=f"{max:.2f}", linewidth = 0.5)
    magPlot.grid(True, color="#e1e0d9", linewidth=0.5)
    magPlot.set_xlabel("F, Hz", color="#000000")
    magPlot.set_ylim(0, 52000)
    magLegendArtist = magPlot.legend(loc="upper right")

    def updateFrame(frame):
        signalArtist[0].set_data(t[frame:frame+nb], signal[frame:frame+nb])
        signalPlot.set_xlim(t[frame], t[frame + nb])

        signalR = imToReal(signal[frame:frame+nb])
        resultR = dsp.arm_cfft_f32(cfftf32, signalR, 0, 1)

        fftRealArtist[0].set_ydata(resultR[0:N*2:2])
        fftImgArtist[0].set_ydata(resultR[1:N*2:2])
        
        mag = dsp.arm_cmplx_mag_f32(resultR)[:N]
        max, fIndex = dsp.arm_max_f32(mag)

        magArtist[0].set_ydata(mag)
        magVArtist.set_xdata([fftX[fIndex], fftX[fIndex]])
        magHArtist.set_ydata([max, max])
        magLegendArtist.get_texts()[1].set_text(f"{fftX[fIndex]:.2f} Hz")
        magLegendArtist.get_texts()[2].set_text(f"{max:.2f}")

        return *signalArtist, *fftRealArtist, *fftImgArtist, *magArtist, magVArtist, magHArtist, magLegendArtist

    maxRange = (len(signal) // nb) * nb
    ani = animation.FuncAnimation(fig=fig, func=updateFrame, frames=range(0, maxRange, nb), interval=200, blit=True, repeat=False)

    # 3. Define the event handler to toggle pause/resume
    def on_key_press(event):
        global is_paused
        if event.key == ' ':
            if is_paused:
                ani.resume()  # Resume the framework timer
            else:
                ani.pause()   # Pause the framework timer
            is_paused = not is_paused

    # 4. Connect the click event to the handler
    fig.canvas.mpl_connect('key_press_event', on_key_press)

    plt.show()

def main():
    parser = argparse.ArgumentParser(description = "PicoScope bulk waveform viewer")
    parser.add_argument("-d", "--dir",
                        help = "relative path to the directory with waveform files (e.g. pico/raw-2lamps)")
    parser.add_argument("default", nargs = "?",
                        help = "waveform directory to open (alternative to -d)")
    args = parser.parse_args()

    dirPath = args.default if args.dir is None else args.dir

    if dirPath is None:
        parser.print_help()
        return

    waveforms = scanDir(dirPath)

    fullT = np.concatenate([waveform[0] for waveform in waveforms])
    fullSignal = np.concatenate([waveform[1] for waveform in waveforms])

    animate(fullT, fullSignal)

if __name__ == "__main__":
    main()
