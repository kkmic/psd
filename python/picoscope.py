import argparse
import matplotlib.pyplot as plt
import numpy as np
import cmsisdsp as dsp

nb = 4096 # samples

sampleRate = 48800 # Samples/s

#################################################################################
def imToReal(a):
    ar=np.zeros(2 * np.array(a.shape))
    ar[0::2]=a.real
    ar[1::2]=a.imag
    return ar

def realToIm(ar):
    return(ar[0::2] + 1j * ar[1::2])


def parseWaveform(filePath):
    print (filePath)

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
        baseTime = t[0]

        if (baseTime != 0.0): # Align timestamps if they are shifted behind 0
            for i in range(len(t)):
                t[i] -= baseTime
    
    return (np.array(t), np.array(signal))

def main():
    parser = argparse.ArgumentParser(description = "PicoScope waveform viewer")
    parser.add_argument("-f", "--file",
                        help = "relative path to the waveform file (e.g. pico/raw-2lamps/raw-2lamps_01.csv)")
    parser.add_argument("waveform", nargs = "?",
                        help = "waveform file to open (alternative to -f)")
    args = parser.parse_args()

    filePath = args.waveform if args.file is None else args.file

    if filePath is None:
        parser.print_help()
        return

    fullT, fullSignal = parseWaveform(filePath)

    cfftf32 = dsp.arm_cfft_instance_f32()
    status = dsp.arm_cfft_init_f32(cfftf32, nb)

    if (status != 0):
        print (f"arm_cfft_init_f32 status = {status}")
        return

    signalR = imToReal(fullSignal[:nb])
    resultR = dsp.arm_cfft_f32(cfftf32, signalR, 0, 1)

    fig, (signalPlot, fftPlot, magPlot) = plt.subplots(3, 1, layout="constrained")

    signalPlot.plot(fullT[:nb], fullSignal[:nb], '-', color="#2a78d6", linewidth=1, label=f"{filePath}")
    signalPlot.plot(fullT[nb:], fullSignal[nb:], '-', color="#d00000", linewidth=1)
    signalPlot.set_ylabel("mV", color="#898781")
    signalPlot.legend(loc="upper right")
    signalPlot.grid(True, color="#e1e0d9", linewidth=0.5)
    signalPlot.set_xlabel("t, mS", color="#000000")

    C = sampleRate / nb
    N = int(2000 / C) # 2000 Hz is the threshold value

    fft = np.linspace(0, C * N, N)

    re = resultR[0:N*2:2]
    im = resultR[1:N*2:2]

    fftPlot.plot(fft, re, '.-', color="#2a78d680", label="FFT Real", linewidth=1)
    fftPlot.plot(fft, im, '.-', color="#ff78d680", label="FFT Img", linewidth=1)
    fftPlot.axhline(y=0, color="#d0000080", label="0", linewidth = 0.5)
    fftPlot.grid(True, color="#e1e0d9", linewidth=0.5)
    fftPlot.legend(loc="upper right")
    fftPlot.set_xlabel("F, Hz", color="#000000")

    mag = dsp.arm_cmplx_mag_f32(resultR)[:N]
    max, fMax = dsp.arm_max_f32(mag)
    fMax *= C

    rms = dsp.arm_rms_f32(resultR)
    norm = rms / np.sqrt(2)
    magPlot.plot(fft, mag, '.-', color="#2a78d6", label="Square Magnitude")
    
    magPlot.axvline(x=fMax, color="#00d000", label=f"{fMax} Hz", linewidth = 0.5)
    magPlot.axhline(y=max, color="#ffd000", label=f"{max:.2f}", linewidth = 0.5)
    magPlot.axhline(y=rms, color="#d00000", label=f"RMS: {rms:.2f}, Norm: {norm:.2f}", linewidth = 0.5)
    magPlot.grid(True, color="#e1e0d9", linewidth=0.5)
    magPlot.set_xlabel("F, Hz", color="#000000")
    magPlot.legend(loc="upper right")

    plt.show()



if __name__ == "__main__":
    main()
