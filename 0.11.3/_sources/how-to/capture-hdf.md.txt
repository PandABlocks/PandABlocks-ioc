# Capture data

The `:DATA` PVs are used to capture data from the panda.
These can be viewed from the DATA screen.

```{image} /images/data_bobfile.png
:align: center
:alt: The data screen
```

- The file directory and name are chosen with `:DATA:HDFDirectory` and `:DATA:HDFFileName`.
- The number of directories that the IOC is allowed to create provided they don't exist is determined by `:DATA:CreateDirectory`. The behavior of this signal is the same as the identical PV in [`areaDetector`](https://areadetector.github.io/areaDetector/ADCore/NDPluginFile.html).
- `DATA:DirectoryExists` represents whether or not the directory specified exists and is writable by the user under which the IOC is running.
- `:DATA:NumCapture` is the number of frames to capture in the file.
- `:DATA:NumCaptured` is the number of frames written to file.
- `:DATA:NumReceived` is the number of frames received from the panda.
- `:DATA:FlushPeriod` is the frequency that the data is flushed into frames in the client.
- `:DATA:Capture` will begin capturing data.
- `:DATA:CaptureMode` is one of the three capture modes listed below.

## First N mode

Begin capturing data and writing it to file as soon as it is received. Stop capturing once `NumCapture`
frames have been written or the panda has been disarmed.

## Last N mode

Begin capturing data in a buffer, once capturing has finished write the last `NumCapture` frames to disk.

## Forever mode

Keep capturing and writing frames. Once the panda has been disarmed wait for it to be armed again and continue writing.
