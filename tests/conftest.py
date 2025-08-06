"""
Test configuration for `SPEXRead`
"""

# import pytest
from pathlib import Path
import datetime
from lxml import etree
from spexread.structdef import SPEInfoHeader, ROIInfo
import numpy as np


# @pytest.fixture(scope="session")
def xmlfooter():
    yield etree.fromstring(Path("./footer.xml").read_text())


# @pytest.fixture
def SPEFile_v2():
    header = SPEInfoHeader()
    header.file_hdeader_ver = 2.2
    header.lastvalue = 21845
    header.lnoscan = -1
    header.WinView_id = 19088743
    header.xcalibration.calib_valid = 1
    header.xcalibration.polynom_coeff = np.ctypeslib.as_ctypes(np.array([1, 1, 0, 0, 0, 0], dtype=float))
    header.xdim = 1024
    header.ydim = 1024
    header.datatype = 1
    header.NumROI = 1

    roi = ROIInfo()
    roi.startx = 1
    roi.endx = 1024
    roi.groupx = 1
    roi.starty = 1
    roi.endy = 1024
    roi.groupy = 1024

    header.ROIinfblk[0] = roi

    # general info
    header.date = datetime.date.today().strftime("%d%b%Y").encode()
    header.ExperimentTimeLocal = datetime.datetime.today().strftime("%H%M%S").encode()
    header.ExperimentTimeUTC = (datetime.datetime.today() - datetime.timedelta(hours=1)).strftime("%H%M%S").encode()

    return header
