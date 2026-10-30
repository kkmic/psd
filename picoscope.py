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

    t = np.empty(nb)
    signal = np.empty(nb)
    count = 0
    
    with open(filePath) as f:
        for _ in range(3):
            f.readline()
        for line in f:
            if (count >= nb): break

            timeStr, mVStr = line.split(";")
            t[count] = float(timeStr.replace(",", "."))
            signal[count] = float(mVStr.replace(",", "."))
            count += 1

    if count > 0:
        baseTime = t[0]

        if (baseTime != 0.0): # Align timestamps if they are shifted behind 0
            for i in range(len(t)):
                t[i] -= baseTime
    
    return (t, signal)

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

    t, signal = parseWaveform(filePath)

    cfftf32 = dsp.arm_cfft_instance_f32()
    status = dsp.arm_cfft_init_f32(cfftf32, nb)

    if (status != 0):
        print (f"arm_cfft_init_f32 status = {status}")
        return

    signalR = imToReal(signal)
    resultR = dsp.arm_cfft_f32(cfftf32, signalR, 0, 1)

    mag = dsp.arm_cmplx_mag_f32(resultR)[:nb//2]

    fig, (signalPlot, fftPlot, magPlot) = plt.subplots(3, 1, figsize=(15, 10))

    signalPlot.plot(t, signal, '-', color="#2a78d6", linewidth=1, label=f"{filePath}")
    signalPlot.set_ylabel("mV", color="#898781")
    signalPlot.legend(loc="upper right")
    signalPlot.grid(True, color="#e1e0d9", linewidth=0.5)

    fft = np.arange(nb//2)
    re = resultR[0:nb:2]
    im = resultR[1:nb:2]

    fftPlot.plot(fft, re, '.-', color="#2a78d680", label="FFT Real", linewidth=1)
    fftPlot.plot(fft, im, '.-', color="#ff78d680", label="FFT Img", linewidth=1)
    fftPlot.grid(True, color="#e1e0d9", linewidth=0.5)
    fftPlot.legend(loc="upper right")

    max, fMax = dsp.arm_max_f32(mag)
    rms = dsp.arm_rms_f32(resultR)
    norm = rms / np.sqrt(2)
    magPlot.plot(fft, mag, '.-', color="#2a78d6", label="Square Magnitude")
    
    magPlot.axvline(x=fMax, color="#00d000", label=f"{fMax} Hz", linewidth = 0.5)
    magPlot.axhline(y=max, color="#ffd000", label=f"{max:.2f}", linewidth = 0.5)
    magPlot.axhline(y=rms, color="#d00000", label=f"RMS: {rms:.2f}, Norm: {norm:.2f}", linewidth = 0.5)
    magPlot.grid(True, color="#e1e0d9", linewidth=0.5)
    magPlot.set_xlabel("Sample", color="#000000")
    magPlot.legend(loc="upper right")

    plt.show()



if __name__ == "__main__":
    main()
