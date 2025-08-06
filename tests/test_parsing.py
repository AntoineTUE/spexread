import pytest
from hypothesis import given, strategies as st
from spexread.structdef import SPEInfoHeader, ROIInfo
from spexread.parsing import parse_spe_metadata, parse_spe_data, read_spe_file
import datetime
import numpy as np
import io
from pathlib import Path
from numpy.testing import assert_allclose

rng = np.random.default_rng()


@given(
    xdim=st.integers(64, 256).filter(lambda x: (x % 2 == 0) & (x % 4 == 0)),
    ydim=st.integers(64, 256).filter(lambda x: (x % 2 == 0) & (x % 4 == 0)),
    xbin=st.sampled_from([1, 2, 4]),
    ybin=st.sampled_from([1, 2, 4]),
    frames=st.integers(1, 10),
    roi_count=st.integers(1, 3),
)
def test_SPEv2_file(tmp_path_factory, xdim, ydim, xbin, ybin, frames: int, roi_count):
    """Strategy to create SPE v2 files"""
    header = SPEInfoHeader()
    header.file_header_ver = 2.2
    header.lastvalue = 21845
    header.lnoscan = -1
    header.WinView_id = 19088743
    header.xcalibration.calib_valid = 1
    header.xcalibration.polynom_coeff = np.ctypeslib.as_ctypes(np.array([0, 1, 0, 0, 0, 0], dtype=float))
    header.xdim = xdim // xbin
    header.ydim = ydim // ybin
    header.datatype = 1
    header.NumROI = roi_count
    for i in range(roi_count):
        roi = ROIInfo()
        roi.startx = 1
        roi.endx = xdim
        roi.groupx = xbin
        roi.starty = 1
        roi.endy = ydim
        roi.groupy = ybin
        header.ROIinfblk[i] = roi
    header.NumFrames = frames
    header.geometric = 0  # Horizontal
    header.xDimDet = xdim
    header.yDimDet = ydim
    header.date = datetime.date.today().strftime("%d%b%Y").encode()
    header.ExperimentTimeLocal = datetime.datetime.today().strftime("%H%M%S").encode()
    header.ExperimentTimeUTC = (datetime.datetime.today() - datetime.timedelta(hours=1)).strftime("%H%M%S").encode()

    values = rng.normal(100, 20, xdim // xbin * ydim // ybin * roi_count * frames).astype(int).reshape(-1, ydim // ybin)

    p = tmp_path_factory.getbasetemp().joinpath(f"tmp_v2_{xdim}-{ydim}-{frames}-{roi_count}.spe")
    with p.open("wb") as fo:
        fo.write(header)
        fo.write(values.tobytes())
    data = read_spe_file(p)
    # for i, (_, roi) in enumerate(data.items()):
    #     assert_allclose(roi.data, values[:, i, :, :])

    assert data.FrameInfo["count"] == frames
    assert len(data.FrameInfo["ROIs"]) == roi_count
    for roi in data.FrameInfo["ROIs"]:
        assert roi["width"] == xdim // xbin
        assert roi["height"] == ydim // ybin
        assert roi["size"] == xdim // xbin * ydim // ybin * 4
    assert data.FrameInfo["stride"] == xdim // xbin * ydim // ybin * 4 * roi_count
