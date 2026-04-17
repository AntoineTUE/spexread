import pytest

from datetime import datetime, timedelta, timezone
from numpy.testing import assert_allclose

from spexread.data_models import SPEType


def test_SPEType_from_v3_footer(footer_lightfield_demo_mode):
    """Test the footer of a SPE v3.0 file that includes data from a spectrometer (e.g. wavelength calibration)."""
    metadata = SPEType.from_xml(footer_lightfield_demo_mode)
    assert metadata.version == 3.0
    assert metadata.GeneralInfo.created == datetime(
        2025, 6, 3, 17, 4, 3, 487711, tzinfo=timezone(timedelta(seconds=7200))
    )
    assert metadata.FrameInfo.count == 1
    assert metadata.FrameInfo.pixelFormat == "uint16"
    assert metadata.FrameInfo.size == 524288
    assert metadata.FrameInfo.stride == metadata.FrameInfo.size
    assert metadata.FrameInfo.calibrations == 1
    assert len(metadata.FrameInfo.ROIs) == 1
    roi = metadata.FrameInfo.ROIs[0]
    assert roi.count == 1
    assert roi.width == 1024
    assert roi.height == 256
    assert roi.size == metadata.FrameInfo.size
    assert roi.stride == metadata.FrameInfo.stride
    calib = metadata.Calibrations
    assert calib.WavelengthCalib.orientation == "Normal"
    assert calib.WavelengthCalib.date == datetime(1970, 1, 1, 1, 0)
    assert_allclose(calib.WavelengthCalib.wavelength, calib.wl)
    assert_allclose([calib.wl.min(), calib.wl.max()], [431.665887, 568.163526])
    assert_allclose(calib.WavelengthCalib.coefficients, [1.0, 0.0, 0.0, 0.0, 0.0])
    assert calib.wl.shape == (1024,)
    assert calib.SensorInformation.id == 2
    assert calib.SensorInformation.orientation == "FlippedHorizontally, FlippedVertically"
    assert calib.SensorInformation.width == 1024
    assert calib.SensorInformation.height == 256
    assert len(calib.SensorMapping) == 1
    mapping = calib.SensorMapping[0]
    assert mapping.id == 3
    assert mapping.x == 0
    assert mapping.y == 0
    assert mapping.height == 256
    assert mapping.width == 1024
    assert mapping.xBin == 1
    assert mapping.yBin == 1
    assert mapping == roi.sensor_mapping


def test_SPEType_from_step_and_glue_footer(footer_step_and_glue):
    """Test the footer of a SPE v3.0 file that includes data from a spectrometer (e.g. wavelength calibration)."""
    metadata = SPEType.from_xml(footer_step_and_glue)
    assert metadata.version == 3.0
    assert metadata.GeneralInfo.created == datetime(
        2025, 12, 15, 11, 33, 32, 243488, tzinfo=timezone(timedelta(seconds=3600))
    )
    assert metadata.FrameInfo.count == 116
    assert metadata.FrameInfo.pixelFormat == "uint16"
    assert metadata.FrameInfo.size == 2048
    assert metadata.FrameInfo.stride == 2072
    assert metadata.FrameInfo.calibrations == 1
    assert metadata.FrameInfo.metaformat_index == 1
    assert len(metadata.FrameInfo.ROIs) == 1
    roi = metadata.FrameInfo.ROIs[0]
    assert roi.count == 1
    assert roi.width == 1024
    assert roi.height == 1
    assert roi.size == metadata.FrameInfo.size
    assert roi.stride == 2048
    metablock = metadata.MetaFormat.MetaBlock[0]
    assert metablock.id == 1
    assert metablock.exposure_start.type == "int64"
    assert metablock.exposure_start.bitDepth == 64
    assert metablock.exposure_start.event == "ExposureStarted"
    assert metablock.exposure_start.resolution == 1000000
    assert metablock.exposure_end.type == "int64"
    assert metablock.exposure_end.bitDepth == 64
    assert metablock.exposure_end.event == "ExposureEnded"
    assert metablock.exposure_end.resolution == 1000000
    assert metablock.frame_track.type == "int64"
    assert metablock.frame_track.bitDepth == 64
    assert metablock.gate_width is None
    assert metablock.gate_delay is None
    calib = metadata.Calibrations
    assert calib.WavelengthCalib.id == 1
    assert calib.WavelengthCalib.orientation == "Normal"
    assert calib.WavelengthCalib.date == datetime(
        2025, 4, 4, 14, 3, 31, 183120, tzinfo=timezone(timedelta(seconds=7200))
    )
    assert_allclose(calib.WavelengthCalib.wavelength, calib.wl)
    assert_allclose([calib.wl.min(), calib.wl.max()], [446.138672, 513.588459])
    assert_allclose(calib.WavelengthCalib.coefficients, [1.0, 0.0, 0.0, 0.0, 0.0])
    assert calib.wl.shape == (1024,)
    assert calib.SensorInformation.id == 2
    assert calib.SensorInformation.orientation == "Normal"
    assert calib.SensorInformation.width == 1024
    assert calib.SensorInformation.height == 1024
    assert len(calib.SensorMapping) == 1
    mapping = calib.SensorMapping[0]
    assert mapping.id == 3
    assert mapping.x == 0
    assert mapping.y == 0
    assert mapping.height == 1024
    assert mapping.width == 1024
    assert mapping.xBin == 1
    assert mapping.yBin == 1024
    assert mapping == roi.sensor_mapping


def test_SPEType_from_v2_converted_footer(footer_converted_from_v2):
    """Test the footer of a SPE v3.0 file that includes data from a spectrometer (e.g. wavelength calibration)."""
    metadata = SPEType.from_xml(footer_converted_from_v2)
    now = datetime.now()
    assert metadata.version == 3.0
    assert metadata.GeneralInfo.created.isoformat(timespec="minutes") == now.isoformat(timespec="minutes")
    assert metadata.FrameInfo.count == 1
    assert metadata.FrameInfo.pixelFormat == "float32"
    assert metadata.FrameInfo.size == 18844
    assert metadata.FrameInfo.stride == metadata.FrameInfo.size
    assert metadata.FrameInfo.calibrations == 0
    assert len(metadata.FrameInfo.ROIs) == 1
    roi = metadata.FrameInfo.ROIs[0]
    assert roi.count == 1
    assert roi.width == 4711
    assert roi.height == 1
    assert roi.size == metadata.FrameInfo.size
    assert roi.stride == metadata.FrameInfo.stride
    calib = metadata.Calibrations
    assert calib.WavelengthCalib is None

    assert calib.SensorInformation.id == 1
    assert calib.SensorInformation.orientation == "Normal"
    assert calib.SensorInformation.width == 1024
    assert calib.SensorInformation.height == 127
    assert len(calib.SensorMapping) == 0
