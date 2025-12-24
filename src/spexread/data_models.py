"""Module containing the core data models to describe SPE-file metadata, powered by [pydantic](https://docs.pydantic.dev) for data validation and serialization.

This ensures that the retrieved metadata will have the same structure and datatypes regardless of the SPE version.

The only difference will stem from the fact that the newer SPE v3.0 format supports more information, due to it being more extensible.

For older formats, there will be less information available, or fields may simply not be set.

In the modelling of the hierarchical structure, the XML structure and SPE v3.0 File Format specification are taken as reference.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict, StringConstraints
from typing import ClassVar, Optional, Any, Annotated
import numpy as np
from numpy.polynomial.polynomial import polyval
from datetime import datetime, timezone
from numpydantic import NDArray, Shape

# import spexread.structdef as structdef
from spexread.structdef import EnumDataType, EnumOrientation, SPEInfoHeader

NS = "http://www.princetoninstruments.com/spe/2009"
"""The default SPE file namespace"""
PRE = "spe"
"""SPE namespace prefix for use with xpath."""
NS_EXP = "http://www.princetoninstruments.com/experiment/2009"
"""Experiment namespace"""
PRE_EXP = "exp"
"""Experiment namespace prefix"""

dtype_mapping = {"unsigned16": "uint16", "unsigned32": "uint32", "floating32": "float32"}
"""Maps SPE 3.0 datatype strings (without default monochrome suffix) to more conventional dtype names that can be understood by `numpy`."""


class XMLBaseModel(BaseModel):
    """Base model for representing XML data."""

    ns: ClassVar = {PRE: NS, PRE_EXP: NS_EXP}
    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)


class RegionType(XMLBaseModel):
    """A model for representing information about a Region Of Interest (ROI).

    When available, the corresponding `SensorMapType` for the region will be set as well.

    This provides additional usefull information such as binning and location of the ROI on the sensor.
    """

    type: str = Field(repr=False, default="Region")
    count: int = Field(repr=False, default=1)
    width: int
    height: int
    size: int
    stride: int
    sensor_mapping: Optional["SensorMapType"] = Field(repr=False, default=None)

    @field_validator("type", mode="after")
    def validate_type(cls, value) -> str:
        """Validate the `type` field; only `Region` is correct."""
        if "Region" not in value:
            raise ValueError(f"{value} is not `Region`, invalid xml object passed")
        return value

    @classmethod
    def from_xml_node(cls, node) -> "RegionType":
        """Extract fields from an XML node to create a `RegionType`.

        The `node` must be a `DataBlock[@type='Region']` element such as retrieved by xpath.

        For each such block, the corresponding `SensorMapping` element is retrieved using the `id` tag.

        See also [`SensorMapType`][spexread.data_models.SensorMapType]

        Note:
            For Step-and-Glue spectra, this `SensorMapping` will be absent, as there exists no direct mapping between the overlapped data region and the sensor dimensions.
        """
        calib_ids = node.attrib["calibrations"].split(",")
        root = node.getroottree()
        _mappings = next(
            (
                elem[0]
                for elem in [root.xpath(f"//{PRE}:SensorMapping[@id='{id}']", namespaces=cls.ns) for id in calib_ids]
                if elem != []
            ),
            None,
        )
        sensor_mapping = SensorMapType(**_mappings.attrib) if _mappings is not None else _mappings

        return RegionType(**node.attrib, sensor_mapping=sensor_mapping)

    @classmethod
    def from_struct(cls, cstruct: SPEInfoHeader, index: int) -> "RegionType":
        """Create a `RegionType` model from a SPE C Struct."""
        dtype_name = EnumDataType(cstruct.datatype).name
        bitlen = getattr(np, dtype_name)().itemsize
        width = np.abs(
            (cstruct.ROIinfblk[index].endx - cstruct.ROIinfblk[index].startx + 1) // cstruct.ROIinfblk[index].groupx
        )
        height = np.abs(
            (cstruct.ROIinfblk[index].endy - cstruct.ROIinfblk[index].starty + 1) // cstruct.ROIinfblk[index].groupy
        )
        size = width * height * bitlen
        return RegionType(
            width=width, height=height, size=size, stride=size, sensor_mapping=SensorMapType.from_struct(cstruct, index)
        )


class FrameType(XMLBaseModel):
    """A model representing information about frames captured by the camera."""

    type: str = Field(default="Frame", repr=False)
    count: int
    pixelFormat: str
    size: int
    stride: int
    calibrations: int = Field(default=0)
    metaformat_index: int | None = Field(default=None, alias="metaFormat")
    ROIs: list[RegionType] = Field(default=[])

    @field_validator("type")
    def validate_type(cls, value: str) -> str:
        """Validate the `type` field; only `Frame` is allowed."""
        if "frame" not in value.lower():
            raise ValueError(f"{value} is not `Frame`")
        return value

    @field_validator("pixelFormat")
    def validate_pixel_format(cls, value: str) -> str:
        """Validate the `pixelFormat` field, mapping it to a string that can be interpreted as a datatype by numpy."""
        value = str(value).lower().replace("monochrome", "")
        if value in dtype_mapping:
            value = dtype_mapping[value]
        return value

    @classmethod
    def from_xml(cls, element) -> "FrameType":
        """Create a `FrameType` model from an XML element."""
        node = element.getroottree().xpath(f"*/{PRE}:DataBlock[@type='Frame']", namespaces=cls.ns)[0]
        return FrameType(
            **node.attrib,
            # ROIs=[RegionType(**r.attrib) for r in node.xpath(f"./{PRE}:DataBlock[@type='Region']", namespaces=cls.ns)],
            ROIs=[
                RegionType.from_xml_node(r) for r in node.xpath(f"./{PRE}:DataBlock[@type='Region']", namespaces=cls.ns)
            ],
        )

    @classmethod
    def from_struct(cls, cstruct: SPEInfoHeader):
        """Create a `FrameType` model from a C Struct."""
        dtype_name = EnumDataType(cstruct.datatype).name
        bitlen = getattr(np, dtype_name)().itemsize
        size = cstruct.xdim * cstruct.ydim * bitlen
        pixel_fmt = f"Monochrome{dtype_name.capitalize()}"
        rois = [RegionType.from_struct(cstruct, i) for i in range(cstruct.NumROI)]
        # stride = size  # No tracking metadata block in legacy format
        stride = sum([r.stride for r in rois])
        return FrameType(count=cstruct.NumFrames, pixelFormat=pixel_fmt, size=size, stride=stride, ROIs=rois)


class TrackType(XMLBaseModel):
    """A model representing a generic implementation of per-frame tracking metadata, such as gate time.

    Note: Not supported by SPE v2.x files
        Since this type of per-frame metadata is not supported by SPE v2.x files, this class and it's children do not implement a `from_struct` method or similar.
    """

    type: Annotated[str, StringConstraints(to_lower=True)] = Field(repr=False)
    bitDepth: Annotated[int, Field(repr=False, multiple_of=8)]

    @classmethod
    def from_xml_by_attrib(cls, node, tag, attrib: tuple[str, str]):
        """Create a `TrackType` from an XML node, given a tag and attribute."""
        node = node.getroottree().xpath(f"*/*/{PRE}:{tag}[@{attrib[0]}='{attrib[1]}']", namespaces=cls.ns)
        # print(node, f"*/*/{PRE}:{tag}[@{attrib[0]}='{attrib[1]}']")
        if len(node) < 1:
            return None
        return cls(**node[0].attrib)


class TimeTrackType(TrackType):
    """A model of the `TimeStamp` XML element that describes the metadata format of exposure events in the binary data blob.

    The `resolution` field describes the resolution of the timestamp in ticks-per-second.
    """

    event: str
    resolution: int = Field(repr=False)
    dt: datetime = Field(alias="absoluteTime", default_factory=datetime.fromtimestamp(0))


class GateTrackType(TrackType):
    """A model of the `GateTracking` XML element that describes the metadata format of gating events in the binary data blob."""

    component: str
    monotonic: bool


class ModulationTrackType(TrackType):
    """A model of the `ModulationTracking` XML element that describes the metadata format of RF modulation in the binary data blob."""

    component: str
    monotonic: bool


class MetaBlockType(XMLBaseModel):
    """A model for the `MetaBlock` XML element that describes the dataformat of per-frame tracking metadata.

    These metadata fields are stored in the binary data blob as the last part of each `frame_stride`.

    When particular per-frame information is tracked, the associated model (a subclass of the [TrackType][^TrackType] model) field can be used to extract this information.

    In all other cases these fields will be `None`.

    Note: Not supported by SPE v2.x files
        SPE v2.x files do not allow storing per-frame metadata in the binary blob and this information therefore cannot be extracted.

        For this reason there is no [`from_struct`] method, as the parent [`MetaFormatType`][^.MetaFormatType] will be empty.
    """

    field_order: ClassVar = ("exposure_start", "exposure_end", "frame_track", "gate_width", "gate_delay", "modulation")
    id: int = Field(default=0, ge=0)
    exposure_start: TimeTrackType | None = Field(default=None)
    exposure_end: TimeTrackType | None = Field(default=None)
    frame_track: TrackType | None = Field(default=None)
    gate_width: GateTrackType | None = Field(default=None)
    gate_delay: GateTrackType | None = Field(default=None)
    modulation: ModulationTrackType | None = Field(default=None)

    @classmethod
    def from_xml(cls, element, id) -> "MetaBlockType":
        """Create a `MetaBlockType` from an XML element."""
        node = element.getroottree().xpath(f"/*/*/{PRE}:MetaBlock[@id='{id}']", namespaces=cls.ns)[0]
        kwargs = {}
        kwargs["exposure_start"] = TimeTrackType.from_xml_by_attrib(node, "TimeStamp", ("event", "ExposureStarted"))
        kwargs["exposure_end"] = TimeTrackType.from_xml_by_attrib(node, "TimeStamp", ("event", "ExposureEnded"))
        kwargs["gate_width"] = GateTrackType.from_xml_by_attrib(node, "GateTracking", ("component", "Width"))
        kwargs["gate_delay"] = GateTrackType.from_xml_by_attrib(node, "GateTracking", ("component", "Delay"))
        return MetaBlockType(
            **node.attrib,
            frame_track=TrackType(**node.xpath(f"./{PRE}:FrameTrackingNumber", namespaces=cls.ns)[0].attrib),
            **{k: v for k, v in kwargs.items() if v is not None},
        )


class MetaFormatType(XMLBaseModel):
    """A model for the `MetaFormat` XML element that acts as a container for multiple [MetaBlockType][^.MetaBlockType] models.

    For SPE v3.0 files, per-frame metadata is stored in the binary data block, which can be retrieved based on the `MetaBlockType` information.

    There will however only be one `MetaFormat` element per SPE file.

    Note: Not supported by SPE v2.x files
        SPE v2.x files do not store per-frame metadata in the binary block, and this `MetaFormatType` will be empty.
    """

    MetaBlock: list[MetaBlockType] = Field(default=[])

    @classmethod
    def from_xml(cls, element) -> "MetaFormatType":
        """Create a `MetaFormatType` from an XML element."""
        nodes = element.getroottree().xpath(f"/*/{PRE}:MetaFormat", namespaces=cls.ns)
        if len(nodes) < 1:
            return None
        node = nodes[0]
        return MetaFormatType(
            MetaBlock=[
                MetaBlockType.from_xml(elem, i + 1)
                for i, elem in enumerate(node.xpath(f"./{PRE}:MetaBlock", namespaces=cls.ns))
            ]
        )

    @classmethod
    def from_struct(cls, cstruct: SPEInfoHeader) -> "MetaFormatType":
        """Create a `MetaFormatType` model from a C Struct."""
        return MetaFormatType()  # No tracking metadata is stored in header or binary block for legacy files


class SensorType(XMLBaseModel):
    """A model for information about the camera sensor."""

    id: int
    orientation: str
    width: int
    height: int

    @classmethod
    def from_struct(cls, cstruct: SPEInfoHeader) -> "SensorType":
        """Create a `SensorType` model from a C Struct."""
        name: str = EnumOrientation(cstruct.geometric).name
        orient = name.replace("|", ",")
        return SensorType(id=2, width=cstruct.xDimDet, height=cstruct.yDimDet, orientation=orient)


class SensorMapType(XMLBaseModel):
    """A model for mapping ROIs to regions on the sensor.

    Tracks position and binning information.

    Using the `id` attribute, it can be matched to the corresponding ROI.

    See also [`RegionType.from_xml_node`][spexread.data_models.RegionType.from_xml_node]
    """

    id: int = Field(repr=False)
    x: int
    y: int
    height: int
    width: int
    xBin: int = Field(alias="xBinning")
    yBin: int = Field(alias="yBinning")

    @classmethod
    def from_struct(cls, cstruct: SPEInfoHeader, index: int) -> "SensorMapType":
        """Create a `SensorMapType` model from a C Struct."""
        roi = cstruct.ROIinfblk[index]
        # Correct x and y to zero-indexed, and account for inverted order of start vs end.
        x = roi.startx - 1 if roi.startx < roi.endx else roi.endx - 1
        y = roi.starty - 1 if roi.starty < roi.endy else roi.endy - 1
        width = np.abs(roi.endx - roi.startx) + 1
        height = np.abs(roi.endy - roi.starty) + 1
        return SensorMapType(
            id=index + 3,
            x=x,
            y=y,
            height=height,
            width=width,
            xBin=roi.groupx,
            yBin=roi.groupy,
        )


class WavelengthCalibType(XMLBaseModel):
    """A data model for containing wavelength calibration information."""

    id: int = Field(repr=False)
    date: datetime = Field(default_factory=lambda: datetime.fromtimestamp(0))
    orientation: str
    wavelength: NDArray[Shape["* x"], float] = Field(repr=False)  # noqa: F722
    coefficients: NDArray[Shape["* x"], float] = Field(default=np.array([1, 0, 0, 0, 0], dtype=float), repr=False)  # noqa: F722

    @field_validator("wavelength", mode="before")
    def parse_wavelength(cls, value: Any) -> NDArray:
        """Parse string-formatted wavelength arrays to a 1D numpy array of floats.

        If input `value` is already a numpy array, it is assumed to be correct already.
        """
        if isinstance(value, np.ndarray):
            return value
        return np.array(value.split(",")).astype(float)

    @classmethod
    def from_xml(cls, element) -> "WavelengthCalibType":
        """Create a `WavelengthCalibType` from an XML element."""
        xpath = element.getroottree().xpath(f"/*/*/{PRE}:WavelengthMapping", namespaces=cls.ns)
        if len(xpath) < 1:
            return None
        else:
            node = xpath[0]
        wls = node.xpath("./spe:Wavelength", namespaces=cls.ns)[0].text
        return WavelengthCalibType(**node.attrib, wavelength=wls)

    @classmethod
    def from_struct(cls, cstruct: SPEInfoHeader) -> "WavelengthCalibType":
        """Create a `WavelengthCalibType` model from a C Struct."""
        if cstruct.xcalibration.calib_valid == 1:
            calib_poly = np.array(cstruct.xcalibration.polynom_coeff, dtype=np.double)
            # pix_num = cstruct.xdim
            pix_num = cstruct.xDimDet
        else:
            calib_poly = np.array(cstruct.ycalibration.polynom_coeff, dtype=np.double)
            # pix_num = cstruct.ydim
            pix_num = cstruct.yDimDet
        wavelength = polyval(np.arange(pix_num), calib_poly)

        # TODO: support y calibration, or other orientation
        # TODO: Implement support for glued spectra
        # TODO: expose the calibration polynomial. Note that SPE stores an empirical one, SPE3 one based on spectrometer geometry etc.
        # TODO: Find a way to support both cass where ROI is smaller than sensor and must be sliced, and when spectrum is stiched and thus larger than detector.
        return WavelengthCalibType(id=1, orientation="Normal", wavelength=wavelength, coefficients=calib_poly)


class CalibrationsType(XMLBaseModel):
    """A model representing calibration data.

    Contains wavelenght calibration (if present when using a spectrograph), sensor information, and ROI-to-sensor-mapping information.

    Calibration data is understood to be "supplemental information associated with a region or frame that does not vary" (SPE v3.0 Format specification, Teledyne Princeton Intruments).

    """

    WavelengthCalib: WavelengthCalibType | None = Field(alias="WavelengthMapping")
    SensorInformation: SensorType
    SensorMapping: list[SensorMapType]

    @property
    def wl(self):
        """Property accessor to the underlying wavelength calibration array.

        If no wavelength calibration array is available, simply returns a range of indices.
        """
        if self.WavelengthCalib is not None:
            return self.WavelengthCalib.wavelength
        else:
            return np.arange(self.SensorInformation.width)

    @classmethod
    def from_xml(cls, element) -> "CalibrationsType":
        """Create a `CalibrationsType` from an XML element."""
        node = element.getroottree().xpath(f"/*/{PRE}:Calibrations", namespaces=cls.ns)[0]
        wl_calib = WavelengthCalibType.from_xml(element)
        sensor_info = SensorType(**node.find("SensorInformation", node.nsmap).attrib)
        sensor_mapping = [
            SensorMapType(**elem.attrib) for elem in node.xpath(f"./{PRE}:SensorMapping", namespaces=cls.ns)
        ]

        return CalibrationsType(WavelengthMapping=wl_calib, SensorInformation=sensor_info, SensorMapping=sensor_mapping)

    @classmethod
    def from_struct(cls, cstruct: SPEInfoHeader) -> "CalibrationsType":
        """Create a `CalibrationsType` model from a C Struct."""
        return CalibrationsType(
            WavelengthMapping=WavelengthCalibType.from_struct(cstruct),
            SensorInformation=SensorType.from_struct(cstruct),
            SensorMapping=[SensorMapType.from_struct(cstruct, i) for i in range(cstruct.NumROI)],
        )


class GeneralInfoType(XMLBaseModel):
    """Model for containing general information about the file, such as creation date, etc."""

    creator: str = Field(default="")
    created: datetime = Field(default_factory=datetime.now)
    last_modified: datetime = Field(default_factory=datetime.now, repr=False)
    notes: str = Field(default="", repr=False)

    @classmethod
    def from_xml(cls, element):
        """Create a `GeneralInfoType` from an XML element."""
        node = element.getroottree().xpath(f"./{PRE}:GeneralInformation", namespaces=cls.ns)[0]
        return GeneralInfoType(**node.find("FileInformation", node.nsmap).attrib)

    @classmethod
    def from_struct(cls, cstruct: SPEInfoHeader):
        """Create a `GeneralInfoType` model from a C Struct."""
        fmt_time = "%d%b%Y %H%M%S"
        dt_local = datetime.strptime(f"{cstruct.date.decode()} {cstruct.ExperimentTimeLocal.decode()}", fmt_time)
        dt_utc = datetime.strptime(f"{cstruct.date.decode()} {cstruct.ExperimentTimeUTC.decode()}", fmt_time)
        tz = timezone(dt_local - dt_utc)
        dt_local = dt_local.replace(tzinfo=tz)
        return GeneralInfoType(created=dt_local, last_modified=dt_local, notes=cstruct.Comments)


class SPEType(XMLBaseModel):
    """The root datamodel for SPE metadata, based on the SPE v3.0 XML structure.

    This model is the top level container for the hierarchic structure of metadata, with support for either SPE v3.0 XML metadata footer, or SPE v2.x metadata structs.

    In general, it should not be instantiated by the user, but rather be created from either the [SPEType.from_xml][(c).from_xml] or [SPEType.from_struct][(c).from_struct] class methods.

    It provides a universal data model and serialization for both data formats, which makes them largely equivalent.

    Nevertheless, v3.0 files will still support more diverse metadata and ROIs, since the XML footer allows for much more data to be stored.

    Once an instance of `SPEType` is created, you can use attribute access to retrieve relevant metadata.

    If you prefer a dictionary, it is easily converted using the `model_dump()` method, and vice-versa via `SPEType.model_validate(my_dict)`.

    Note: SPE v3.0 support
        While many properties relevant to the acquisition of data are supported, the `Experiment` XML element is not yet supported.

        This element contains the full LightField setup used for an experiment and is deeply nested.

        This makes parsing it with models inconvenient, plus, quite a bit of the contained information is redundant.
    """

    version: float
    FrameInfo: FrameType
    MetaFormat: MetaFormatType | None = Field(default=MetaFormatType())
    Calibrations: CalibrationsType | None = Field(default=None)
    GeneralInfo: GeneralInfoType = Field(default=GeneralInfoType())

    @classmethod
    def from_xml(cls, root):
        """Create a `SPEType` model from an XML root node.

        It traverses the XML document starting from the root node to build the model.
        """
        base = root.xpath(f"/{PRE}:SpeFormat", namespaces=cls.ns)[0]
        frame_info = FrameType.from_xml(base)
        kwargs = {}
        kwargs["MetaFormat"] = MetaFormatType.from_xml(base)
        kwargs["Calibrations"] = CalibrationsType.from_xml(base)
        kwargs["GeneralInfo"] = GeneralInfoType.from_xml(base)
        return SPEType(**base.attrib, FrameInfo=frame_info, **{k: v for k, v in kwargs.items() if v is not None})

    @classmethod
    def from_struct(cls, cstruct: SPEInfoHeader) -> "SPEType":
        """Create a `SPEType` model from a C Struct."""
        return SPEType(
            version=cstruct.file_header_ver,
            FrameInfo=FrameType.from_struct(cstruct),
            MetaFormat=MetaFormatType.from_struct(cstruct),
            Calibrations=CalibrationsType.from_struct(cstruct),
            GeneralInfo=GeneralInfoType.from_struct(cstruct),
        )
