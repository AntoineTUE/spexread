"""Module for handling the parsing of SPE files.

SPE files have a binary header that contains the offset in the file where the actual data starts.

Depending on the SPE file version format, this header can contain more elaborate metadata (legacy SPE v2.x) format, or an offset for a flexible XML footer (for SPE v3.0).

All SPE files use a 4100 byte header for storing metadata, though for SPE v3.0 files this is mainly intended to retrieve the offset for the XML footer that contains rich metadata.

Based on the information obtained from the header and (optional) footer, the actual data per ROI and frame is read from the file, along with optional per-frame tracking metadata (e.g. exposure time, gate delay).
"""

from pathlib import Path
import struct
import numpy as np
from numpy.polynomial.polynomial import polyval
import xarray as xr
from lxml import etree
from typing import Union, BinaryIO, TYPE_CHECKING
from io import BufferedReader

from .data_models import SPEType
from .transformation import (
    apply_transformations,
    parse_orientation,
    transformation_mapping,
    map_calibration_to_current_coordinate_system,
)
from .structdef import SPEInfoHeader, HEADERSIZE, WINVIEW_ID, LASTVALUE

FilePathOrBinaryBuffer = str | Path | BinaryIO
"""Type definition for functions that can accept either a file path, or a file handle (openend in binary mode)."""


class SPEValidationError(Exception):
    """Exception raised when validating SPE files in `strict` mode fails.

    Files that cause this exception to be raised, may not adhere to the SPE v2.x or SPE 3.0 specifition.
    Or at least be different than what is documented in the SPE 3.0 specification about legacy compatibility.

    Attempting to read these files with `strict` set to `False` may still result in them being read correctly.
    """


def _parse_xml_footer(buff: "BufferedReader", offset: int) -> etree:
    """Parse the XML footer from a file, by reading from the position `offset` in the file.

    This offset can be found by reading the file header into an [`SPEInfoHeader`][spexread.structdef.SPEInfoHeader], with the `XMLOffset` attribute.

    This will only work for SPE v3.0 files, since the `XMLOffset` field is not defined for older file formats.

    Because of this, it will only make sense to use this function if you know you are dealing with a file that has an xml footer.
    """
    buff.seek(offset)
    return etree.fromstring(buff.readline())


def _parse_ROI(file: FilePathOrBinaryBuffer, info_header: SPEType, roi_idx: int) -> np.ndarray:
    """Retrieve all frames recorded with the same Region Of Interest (ROI) on the camera sensor.

    Uses a `SPEType` model containing metadata extracted from the file header and (optional) footer to find chunks of data in the file.

    `SPE` files store frames as a contiguous block of data, where each frame consists of one or more ROI data block, followed by an optional per-frame tracking data block.

    To parse this metadata see [_parse_tracked_metadata][..].

    Args:
        file (Path|str):        A path to a file
        info_header (SPEType):  A metadata model containing file metadata, backed by `pydantic`
        roi_idx (int):          Index of the ROI to extract, starting from 0.
    """
    roi = info_header.FrameInfo.ROIs[roi_idx]
    dtype = np.dtype(info_header.FrameInfo.pixelFormat.lower().replace("monochrome", ""))
    start = HEADERSIZE + sum([r.stride for r in info_header.FrameInfo.ROIs[:roi_idx]])
    end = HEADERSIZE + (info_header.FrameInfo.count) * info_header.FrameInfo.stride
    offset = np.arange(start, end, info_header.FrameInfo.stride)
    data = np.zeros(roi.size // dtype.itemsize * info_header.FrameInfo.count, dtype=dtype)
    element_count = roi.stride // dtype.itemsize
    for frame_idx in range(info_header.FrameInfo.count):
        start_index = frame_idx * roi.stride // dtype.itemsize
        stop_index = (frame_idx + 1) * roi.stride // dtype.itemsize
        data[start_index:stop_index] = np.fromfile(file, dtype=dtype, count=element_count, offset=offset[frame_idx])
    return data


def _parse_tracked_metadata(file_path: Path | str, info: SPEType) -> dict[str, np.ndarray]:
    """Extract all available per-frame tracking metadata.

    This metadata is stored at the end of each frame datablock in an SPE file and varies in length depending on the enabled tracking information in LightField.

    Which properties are tracked (and their datatype/bitlength) are extracted from the first [`MetaBlock`][(p).data_models.MetaBlockType] metadata element.

    Note: Not supported by SPE v2.x files
        This only works for SPE v3.0 files, legacy files don't store this information.

    Args:
        file_path (Path|str): A file path
        info (SPEType): A metadata model containing file metadata, backed by `pydantic`
    """
    file_path = Path(file_path) if isinstance(file_path, str) else file_path
    block_offset = sum([r.stride for r in info.FrameInfo.ROIs])
    tracked_fields = sorted(
        set(info.MetaFormat.MetaBlock[0].field_order) & info.MetaFormat.MetaBlock[0].model_fields_set,
        key=lambda x: info.MetaFormat.MetaBlock[0].field_order.index(x),
    )
    field_offset = 0
    tracked = {}
    with file_path.open("rb") as fo:
        for field in tracked_fields:
            field_model = getattr(info.MetaFormat.MetaBlock[0], field)
            dtype = np.dtype(field_model.type)
            resolution = getattr(field_model, "resolution", 1)
            offsets = np.arange(
                start=HEADERSIZE + block_offset + field_offset,
                stop=HEADERSIZE + info.FrameInfo.stride * info.FrameInfo.count,
                step=info.FrameInfo.stride,
                dtype=int,
            )
            b = b""
            for offset in offsets:
                fo.seek(offset)
                b += fo.read(dtype.itemsize)
            tracked[field] = np.frombuffer(b, dtype=dtype) / resolution
            field_offset += dtype.itemsize
    return tracked


def _spe_metadata_from_buffer(buff: BinaryIO, strict: bool = False) -> SPEType:
    """Retrieve header and/or footer metadata from an opened file handle.

    Low-level method for [parse_spe_metadata][..] for already opened file objects.

    When using `strict=True`, some fields from the binary header are checked to have certain values.
    This serves as an early-warning for files that may be corrupt, or maybe not supported.

    Args:
        buff (BinaryIO):    A file-handle or buffer opened in binary mode.
        strict (bool):      A flag to force validation of the file by checking some fields in the binary header.

    Returns:
        SPEType:            A hierarchical model of the metadata.

    """
    header = SPEInfoHeader()
    buff.readinto(header)
    if strict:
        for attr, correct in zip(["WinView_id", "lastvalue", "lnoscan"], [WINVIEW_ID, LASTVALUE, -1]):  # noqa: B905
            actual = getattr(header, attr)
            if actual != correct:
                raise SPEValidationError(
                    f"Error validating file header for {attr}, expected {correct}, but got {actual}. Try reading this file with `strict` set to `False`."
                )
    metadata = (
        SPEType.from_xml(_parse_xml_footer(buff, header.XMLOffset))
        if header.file_header_ver >= 3
        else SPEType.from_struct(header)
    )
    return metadata


def parse_spe_metadata(f: Path | str, strict: bool = False) -> SPEType:
    """Retrieve header and/or footer metadata for processing `*.SPE` files.

    All SPE files start with a 4100 byte header, which contains the offset to the binary data blob as well as optional further metadata, depending on the file version.

    For SPE v3.0 files, further metadata is extracted from the XML footer, while for older formats it is extracted from the header struct.

    In both cases a [`SPEType`][spexread.data_models.SPEType] data model (backed by [pydantic](https://docs.pydantic.dev) for validation and serialization) is returned.

    This `SPEType` contains most relevant metadata and the required information to parse the binary data blob to extract per-ROI and per-frame data and associated (optional) per-frame metadata.

    Args:
        f (Path|str): A file path.
        strict (bool, optional): Force strict parsing, meaning some validity checks are performed, default=False.

    Returns:
        SPEType                     : A `pydantic` model of metadata contained in the header and footer of the file.

    Note:
        This is a convencience function to read from a file, all actual reading happens by the low-level [_spe_metadata_from_buffer][..] function from an opened file object.
    """
    f = Path(f)
    with f.open("rb") as fo:
        metadata = _spe_metadata_from_buffer(fo, strict=strict)
    return metadata


def parse_spe_data(f: Path, info: SPEType, with_calibration=True) -> list[xr.DataArray]:
    """Parse the data contents of an `*.SPE` file using the metadata from the header and/or footer.

    Will return a list of `DataArray`, with each element corresponding to a Region of Interest (ROI).

    When per-frame metadata blocks are encountered (based on `SPEType.MetaFormat.MetaBlock`) these will be parsed as additional coordinates, containing e.g. the frame number, gate delay or exposure time.

    In case `with_calibration=True`, the wavelenght calibration (if known) will be extracted from the file and added to each DataArray.

    In doing so, we attempt to account for differences in binning and a potential change of orientation of the sensor w.r.t. when the calibration was performed.

    Args:
        f (Path): A file path
        info (SPEType): A metadata model containing file metadata, backed by `pydantic`
    """
    data_arrays = []

    orient_calib = parse_orientation(
        info.Calibrations.WavelengthCalib.orientation if info.Calibrations.WavelengthCalib is not None else "Normal"
    )
    calib_order = apply_transformations("x", "y", *orient_calib)  # assume 0th index is calibration axis
    orient_sensor = parse_orientation(info.Calibrations.SensorInformation.orientation)
    # Compute transformation to map calibration to current orientation
    transform = transformation_mapping(orient_calib, orient_sensor)
    dim_order = apply_transformations("y", "x", *transform)  # Flipped, default order ('frame', 'y','x')
    tracking_data = _parse_tracked_metadata(f, info) if info.FrameInfo.metaformat_index is not None else {}

    for roi_idx, roi in enumerate(info.FrameInfo.ROIs):
        data = _parse_ROI(f, info, roi_idx)
        if roi_idx < len(info.Calibrations.SensorMapping):
            roi_map = info.Calibrations.SensorMapping[roi_idx]
            coord_order = dict(
                zip(
                    dim_order,
                    [
                        np.arange(roi_map.y, roi_map.y + roi_map.height, roi_map.yBin) + roi_map.yBin // 2,
                        np.arange(roi_map.x, roi_map.x + roi_map.width, roi_map.xBin) + roi_map.xBin // 2,
                    ],
                    strict=True,
                )
            )
        else:
            coord_order = dict(zip(dim_order, [np.arange(roi.height), np.arange(roi.width)], strict=True))

        roi_array = xr.DataArray(
            data.reshape(info.FrameInfo.count, roi.height, roi.width),
            dims=("frame", *dim_order),
            coords={
                "frame": np.arange(info.FrameInfo.count),
                **coord_order,
            },
            attrs=info.FrameInfo.ROIs[roi_idx].model_dump(),
            name=f"ROI {roi_idx}",
        )
        roi_array = roi_array.assign_coords(**{k: ("frame", v) for k, v in tracking_data.items()})
        if with_calibration:
            try:
                calib_coords = info.Calibrations.wl[getattr(roi_array, calib_order[0])]
            except IndexError:
                calib_coords = polyval(
                    getattr(roi_array, calib_order[0]).data, info.Calibrations.WavelengthCalib.coefficients
                )
            roi_array = roi_array.assign_coords(wavelength=(calib_order[0], calib_coords))
        data_arrays.append(roi_array)
    return data_arrays


def read_spe_file(file: Path | str, as_dataset=True, strict: bool = False) -> xr.Dataset | list[xr.DataArray]:
    """Read an SPE file including metadata from a file path.

    Args:
        file (Path|str):        A file path
        as_dataset (bool):      Flag to return either an `xarray.Dataset` (True) or a list of `xarray.DataArray` (False). Default: `True`
        strict (bool):          Flag to perform validation check on the file using the binary metadata header, potentially detecting invalid/unsupported files. Default: `False`

    Returns:
        The data per-ROI, as either a joined `xarray.Dataset`, or a list of `xarray.DataArrays`

    For more info, refer to the docs for [`parse_spe_metadata`][(p).parsing.parse_spe_metadata] and [`parse_spe_data`][(p).parsing.parse_spe_data].
    """
    file = Path(file)
    info = parse_spe_metadata(file, strict=strict)

    data_list = parse_spe_data(file, info, with_calibration=not as_dataset)
    if not as_dataset:
        return data_list
    data = xr.combine_by_coords(data_list, join="outer")
    calib_dim_name, calib_coords, *_ = map_calibration_to_current_coordinate_system(info)
    try:
        # coerce to numpy array to avoid ambiguity for xarray
        _calibrated_pixels = getattr(data, calib_dim_name, data.x).data
        calib_coords = calib_coords[_calibrated_pixels]  # slice calibration array with current pixels
    except IndexError:
        # patch for stitched spectra that extend beyond sensor dimension
        # TODO: only likely to work for SPE2 files, as SPE3 files store a different calibration
        calib_coords = polyval(getattr(data, calib_dim_name).data, info.Calibrations.WavelengthCalib.coefficients)
    data = data.assign_coords(wavelength=(calib_dim_name, calib_coords))
    data.attrs = info.model_dump()
    return data
