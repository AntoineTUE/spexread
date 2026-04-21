"""Tests specific sample files to monitor if there are breaking changes.

The sample files are preferably small, but showcase unique features.

They include files recorded by LightField in SPE3.0 format, but also SPE2.x files created by Andor SOLIS.

Some files contain multiple ROIs, others are the result of a Step & Glue measurement.
"""

import pytest
from pathlib import Path
import numpy as np
from numpy.testing import assert_allclose
from spexread import read_spe_file


def test_step_and_glue_andor():
    """Test a step&glue spectrum in a SPE v2.x format, likely saved by Andor SOLIS.

    Unique features:
        * step & glue file: so data (4711 samples) extends beyond the sensor size (1024 pixels wide)
        * Andor data files report reverse order of (endx,startx) and (endy, starty) for ROIs (see commit: #7f598cb)
        * Even though the file reports that there are 0 calibrations, it includes a wavelength calibration polynomial
    """
    sample = read_spe_file(Path("./tests/test_files/step_and_glue_v2_Andor.spe"))

    assert sample.version == 2.5
    assert sample["ROI 0"].shape == (1, 1, 4711)
    assert len(sample) == 1
    assert tuple(sample.dims) == ("frame", "y", "x")
    assert tuple(sample.coords) == ("frame", "y", "x", "wavelength")
    assert_allclose([sample["ROI 0"].min(), sample["ROI 0"].mean(), sample["ROI 0"].max()], [0.0, 2324.5513, 2338.5261])
    assert_allclose(
        [sample.wavelength.min(), sample.wavelength.mean(), sample.wavelength.max()],
        [149.851379, 499.851396, 849.85141],
    )
    assert_allclose(
        sample.Calibrations["WavelengthCalib"]["coefficients"], [1.49851379e2, 1.48619965e-1, 0.0, 0.0, 0.0, 0.0]
    )
    assert_allclose(
        sample.wavelength.data,
        np.polynomial.polynomial.polyval(sample.x, sample.Calibrations["WavelengthCalib"]["coefficients"]),
    )
    assert sample.Calibrations["SensorInformation"]["width"] == 1024
    assert sample.Calibrations["SensorMapping"][0]["width"] == 4711
    assert sample.wavelength.dtype == np.dtype("float64")
    assert sample.FrameInfo["calibrations"] == 0

    assert sample.frame[0] == 0
    assert sample.y[0] == 63

    # Check if ROI has been flipped correctly w.r.t. inverted order used by file.
    roi = sample.FrameInfo["ROIs"][0]
    assert roi["width"] == 4711
    assert roi["height"] == 1
    assert roi["sensor_mapping"]["x"] == 0
    assert roi["sensor_mapping"]["width"] == 4711
    assert roi["sensor_mapping"]["xBin"] == 1
    assert roi["sensor_mapping"]["y"] == 0
    assert roi["sensor_mapping"]["height"] == 127
    assert roi["sensor_mapping"]["yBin"] == 127


def test_lightfield_demo():
    """A file recorded with LightField 6.17 using both a simulated camera and spectrometer (FERGIE).

    Unique features:
        * Two regions of interest, 1024 pixels wide, 77 high.
        * Ten frames
        * Includes tracking of: 'exposure_start', 'exposure_end', 'frame_track', 'gate_delay'
    """

    sample = read_spe_file(Path("./tests/test_files/lightfield_demo.spe"))
    assert sample.version >= 3
    assert tuple(sample.sizes.values()) == (10, 154, 1024)
    assert tuple(sample.data_vars) == ("ROI 0", "ROI 1")

    assert_allclose(
        [sample.exposure_start.min(), sample.exposure_start.mean(), sample.exposure_start.max()],
        [0.0109296, 0.32802938, 0.6448022],
    )
    assert sample.exposure_start.dims == ("frame",)
    assert_allclose(
        [sample.exposure_end.min(), sample.exposure_end.mean(), sample.exposure_end.max()],
        [0.0259296, 0.34302938, 0.6598022],
    )
    assert sample.exposure_end.dims == ("frame",)
    assert_allclose(
        [sample.gate_delay.min(), sample.gate_delay.mean(), sample.gate_delay.max()], [1000000.0, 3000000.0, 5000000.0]
    )
    assert sample.gate_delay.dims == ("frame",)
    assert_allclose(
        [sample.wavelength.min(), sample.wavelength.mean(), sample.wavelength.max()],
        [431.66588745, 500.01599341, 568.16352595],
    )
    assert sample.wavelength.dims == ("x",)
    assert len(sample.Calibrations["SensorMapping"]) == 2
    for i, mapping in enumerate(sample.Calibrations["SensorMapping"]):
        other_mapping = sample.FrameInfo["ROIs"][i]["sensor_mapping"]
        assert mapping["id"] == int(3 + i)
        assert mapping["x"] == 0
        assert mapping["width"] == 1024
        assert mapping["height"] == 77
        assert mapping == other_mapping
    tracking_stride = (
        sum([v.get("bitDepth", 0) for k, v in sample.MetaFormat["MetaBlock"][0].items() if isinstance(v, dict)]) // 8
    )
    assert sample.FrameInfo["stride"] == sum([roi["stride"] for roi in sample.FrameInfo["ROIs"]]) + tracking_stride

    assert_allclose([sample["ROI 0"].min(), sample["ROI 0"].mean(), sample["ROI 0"].max()], [8265, 9527.662, 12345.0])
    assert_allclose([sample["ROI 1"].min(), sample["ROI 1"].mean(), sample["ROI 1"].max()], [8265.0, 9547.362, 12345.0])


def test_lightfield_full_frame_sequence():
    """A file recorded with Lightfield in SPE3.0 format, recording the N2 SPS (0,0) band.

    This file has been provided as a test case for the fix in commit #82acf6a.

    Unique features:
        * 4 full frames (no binning) of the full 1024 by 1024 pixel sensor.

        * Stores only the `gate_delay` per-frame metadata, so no frame-tracking or other info.

        * The x dimensions corresponds to the wavelength calibrated axis.

    """
    sample = read_spe_file("./tests/test_files/lightfield_fullframe.spe")
    assert sample.version >= 3
    assert tuple(sample.sizes.values()) == (4, 1024, 1024)
    assert tuple(sample.data_vars) == ("ROI 0",)

    assert sample.gate_delay.dims == ("frame",)
    assert_allclose(sample.gate_delay, [758, 760.67, 763.33, 766])

    assert sample.wavelength.dims == ("x",)
    assert_allclose(
        [sample.wavelength.min(), sample.wavelength.mean(), sample.wavelength.max()],
        [332.39585367, 336.99866056, 341.57822607],
    )

    assert sample.MetaFormat["MetaBlock"][0]["frame_track"] is None
    tracking_stride = (
        sum([v.get("bitDepth", 0) for k, v in sample.MetaFormat["MetaBlock"][0].items() if isinstance(v, dict)]) // 8
    )
    assert sample.FrameInfo["stride"] == sum([roi["stride"] for roi in sample.FrameInfo["ROIs"]]) + tracking_stride

    assert sample.Calibrations["SensorMapping"][0]["xBin"] == 1
    assert sample.Calibrations["SensorMapping"][0]["yBin"] == 1
    assert sample.Calibrations["SensorMapping"][0]["width"] == 1024
    assert sample.Calibrations["SensorMapping"][0]["height"] == 1024
    assert sample.Calibrations["SensorMapping"][0] == sample.FrameInfo["ROIs"][0]["sensor_mapping"]


def test_lightfield_step_and_glue():
    """A file recorded with Lightfield (SPE3.0), recording a step & glue spectrum.

    (Note: step and glue files stitch and overlap multiple sensor exposure into a contiguous spectrum).

    Unique features:
        * Contains only 1 frame and is recorded using full vertical binning.

        * Step & Glue along calibrated x dimension yields 5344 points.

        * The `MetaFormat.MetaBlock` is empty, and `metaformat_index=None` for these files.

        * There is no `SensorMapping` as there is no single mapping for the spectrum to the sensor for these files.

        * Per-frame tracking metadata is absent since each `frame` now represent multiple actual frames.
    """
    sample = read_spe_file("./tests/test_files/lightfield_step_and_glue.spe")
    assert sample.version >= 3
    assert tuple(sample.sizes.values()) == (1, 1, 5344)
    assert tuple(sample.data_vars) == ("ROI 0",)

    # stride and size are the same, no tracking metadata
    assert sample.FrameInfo["size"] == 10688
    assert sample.FrameInfo["stride"] == 10688
    assert sample.FrameInfo["ROIs"][0]["sensor_mapping"] is None
    assert sample.FrameInfo["ROIs"][0]["width"] == 5344
    assert sample.FrameInfo["ROIs"][0]["height"] == 1
    assert sample.FrameInfo["ROIs"][0]["size"] == sample.FrameInfo["size"]

    assert len(sample.MetaFormat["MetaBlock"]) == 0

    calib = sample.Calibrations["WavelengthCalib"]
    assert calib["orientation"] == "Normal"
    assert calib["wavelength"].size == 5344
    assert_allclose(calib["coefficients"], [1, 0, 0, 0, 0])
    assert_allclose(
        [sample.wavelength.min(), sample.wavelength.mean(), sample.wavelength.max()],
        [340.0304015, 516.62033973, 690.05642026],
    )
    assert_allclose(
        [sample["ROI 0"].data.min(), sample["ROI 0"].data.mean(), sample["ROI 0"].data.max()],
        [1154, 11867.446856287424, 65535],
    )

    assert sample.Calibrations["SensorInformation"]["width"] == 1024
    assert sample.Calibrations["SensorInformation"]["height"] == 1024
    assert sample.Calibrations["SensorInformation"]["width"] != sample.FrameInfo["ROIs"][0]["width"]
