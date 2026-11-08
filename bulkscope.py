import argparse
import os
import numpy as np
import matplotlib.pyplot as plt

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

    # deltaT = []
    # for i in range(1, len(t)):
    #     deltaT.append(t[i] - t[i-1])
    
    # return (np.array(t), np.array(deltaT), np.array(signal))
    return (np.array(t), np.array(signal))

def scanDir(dirPath):
    fileNames = sorted(f for f in os.listdir(dirPath) if f.endswith(".csv"))

    waveforms = []
    for fileName in fileNames:
        waveforms.append(parseWaveform(os.path.join(dirPath, fileName)))

        
    return waveforms


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

    # fullDeltaT = np.concatenate([waveform[1] for waveform in waveforms])
    # fullDeltaT = np.round(fullDeltaT, 5)
    # unique_values, amounts = np.unique(fullDeltaT, return_counts=True)
    
    # plt.bar(unique_values, amounts, color='lightgreen', edgecolor='black', width=5)
    # plt.xticks(unique_values)
    # plt.show()

if __name__ == "__main__":
    main()
