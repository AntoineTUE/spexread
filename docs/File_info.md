# SPE file structure

`spexread` is made to read data from Princeton Instruments SPE files, supporting both the modern format made by LightField (SPE version 3.0) and legacy files created by WinSpec (SPE version 2.x).

The main difference between the modern version 3.0 format are:

* Structured metadata is stored in an XML footer at the end of the file
* Each binary `Frame` block can now contain tracking metadata at the end.

```mermaid
%%{init: { "theme":"neutral","themeVariables": { "fontSize":"32px" }}}%%
block-beta
columns 3
  block:File:3
    Header("Binary header")
    Binary("Binary data")
    Footer("XML footer")
  end
  Header--> HeaderBlock("4100 Bytes")
  block:Bin
    Frame1("Frame 0")
    Frame2("Frame ...")
    Frame3("Frame N")
  end
  block:XMLMeta
    FrameInfo
    Calibrations
    FrameTrackInfo
  end
  Binary --> Bin
  block:HeaderInfo
    Frames
    Dimension
    XMLOffset
    etc.
  end
  block:Frameblock
    ROI1("ROI 0")
    ROI2("ROI ...")
    Frametrack
  end
  Bin --> Frameblock
  space
  space
  block:FrameMeta
  exsposure_start("Exposure start")
  exsposure_end("Exsposure end")
  gate_start("Gate start")
  gate_end("Gate end")
  modulation("Modulation")
  end
  Frametrack-->FrameMeta
```
