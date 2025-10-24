"""Definitions of C structures in the SPE file header.

The format of these structures is based on the legacy SPE v2.5 header format specification (from 2004/03/23).

Note that even older header formats (namely v1.43 and v1.6) will be compatible for the most part as they use the same 4100 byte header size, but will have occasional different fields.

As such, reading data is backwards compatible, but the available metadata should not be considered fully compatible.

In case you really need support for these ancient formats, refer to the WinView/WinSpec manuals for changes.
"""

import enum
import numpy as np
from ctypes import (
    Structure,
    c_int32,
    c_uint32,
    c_int16,
    c_uint16,
    c_int8,
    c_uint8,
    c_float,
    c_double,
    c_uint64,
    c_ushort,
    c_uint,
    c_char,
    c_short,
    c_byte,
)
import ctypes

s8 = c_int8
u8 = c_uint8
s16 = c_int16
u16 = c_ushort
s32 = c_int32
u32 = c_uint32
f32 = c_float
d64 = c_double
u64 = c_uint64

HEADERSIZE = 4100
"""Header size in bytes of SPE files, going all the way back to version 1."""
WINVIEW_ID = 19088743
"""Fixed value for legacy reasons from WinSpec software, expected value is fixed, equal to 0x1234567"""
LASTVALUE = 21845
"""Last value of the header, fixed at 21845 (or 0x5555) for legacy reasons."""
DATAMAX = 10
TIMEMAX = 7
COMMENTMAX = 80
ROIMAX = 10
LABELMAX = 16
FILEVERMAX = 16
HDRNAMEMAX = 120
USERINFOMAX = 1000


class EnumDataType(enum.Enum):
    """Enum for data types of recorded data."""

    float32 = 0
    int32 = 1  # SPEv2 only
    int16 = 2  # SPEv2 only
    uint16 = 3
    float64 = 5  # SPEv2 only
    int8 = 6  # SPEv2 only
    uint8 = 7  # SPEv1 only
    uint32 = 8


class EnumOrientation(enum.Flag):
    """Enum for camera sensor orientation."""

    Normal = 0
    Rotate = 1
    Horizontal = 2
    Vertical = 4


class SPEStructure(Structure):
    """A generic class for a C structure that can be converted to a dictionary."""

    def to_dict(self):
        """Convert a C structure to a dictionary, applying type coercion for nested data types such as structures and arrays."""
        content = {}
        for k in self._fields_:
            v = getattr(self, k[0])
            if isinstance(v, SPEStructure):
                v = v.to_dict()
            elif isinstance(v, ctypes.Array):
                elemType = k[1]._type_
                if elemType == c_char:
                    v = bytes(v).decode("utf-8", errors="ignore").rstrip("\x00")
                elif elemType == c_byte:
                    v = bytes(v).rstrip(b"\x00")
                else:
                    v = np.array(v)
            content[k[0]] = v
        return content


class ROIInfo(SPEStructure):
    """Structure containing size, position and binning info about a region of interest."""

    _pack_ = 1
    _fields_ = [
        ("startx", u16),
        ("endx", u16),
        ("groupx", u16),
        ("starty", u16),
        ("endy", u16),
        ("groupy", u16),
    ]


class CalibrationStruct(SPEStructure):
    """Structure containing calibration information for a spectrometer."""

    _pack_ = 1
    _fields_ = [
        ("offset", d64),
        ("factor", d64),
        ("current_unit", s8),
        ("reserved1", s8),
        ("string", c_char * 40),
        ("reserved2", s8 * 40),
        ("calib_valid", s8),
        ("input_unit", s8),
        ("polynom_unit", s8),
        ("polynom_order", s8),
        ("calib_count", s8),
        ("pixel_position", d64 * 10),
        ("calib_value", d64 * 10),
        ("polynom_coeff", d64 * 6),
        ("laser_position", d64),
        ("reserved3", s8),
        ("new_calib_flag", u8),
        ("calib_label", c_char * 81),
        ("expansion", s8 * 87),
    ]


class SPEInfoHeader(SPEStructure):
    """Info header of legacy SPE files (version `2.x`) packed as a C Struct.

    Defined verbatim according to the `SPE 3.0 File Format Specification` manual which highlights changes between v3.0 and v2.5.

    This header format is formally defined as the `Version 2.5 Header` according to the WinSpec manual and should be backwards compatible with previous versions.

    For older SPE file headers (namely v1.43 and v1.6), there will be minor differences since some blocks have been redefined and/or repurposed between versions.

    Support for these ancient versions is not guaranteed.
    """

    _pack_ = 1
    _fields_ = [
        ("ControllerVersion", s16),
        ("LogicOutput", s16),
        ("AmpHiCapLowNoise", u16),
        ("xDimDet", u16),
        ("mode", s16),
        ("exp_sec", f32),
        ("VChipXdim", s16),
        ("VChipYdim", s16),
        ("yDimDet", u16),
        ("date", c_char * DATAMAX),  # SPE3 Manual says it's int8, but should be char
        ("VirtualChipFlag", s16),
        ("Spare_1", c_int8 * 2),
        ("noscan", s16),
        ("DetTemperature", f32),
        ("DetType", s16),
        ("xdim", u16),
        ("stdiode", s16),
        ("DelayTime", f32),
        ("ShutterControl", u16),
        ("AbsorbLive", s16),
        ("AbsorpMode", u16),
        ("CanDoVirtualChipFlag", s16),
        ("ThresholdMinLive", s16),
        ("ThresholdMinVal", f32),
        ("ThresholdMaxLive", s16),
        ("ThresholdMaxVal", f32),
        ("SpecAutoSpectroModule", s16),
        ("SpecCenterWlNm", f32),
        ("SpecGlueFlag", s16),
        ("SpecGlueStartWlNm", f32),
        ("SpecGlueEndWlNm", f32),
        ("SpecGlueMinOvrlpNm", f32),
        ("SpecGlueFinalResNm", f32),
        ("PulserType", s16),
        ("CustomChipFlag", s16),
        ("XPrePixels", s16),
        ("XPostPixels", s16),
        ("YPrePixels", s16),
        ("YPostPixels", s16),
        ("asynen", s16),
        ("datatype", s16),
        ("PulserMode", s16),
        ("PulserOnChipAccums", u16),
        ("PulserRepeatExp", u32),
        ("PulseRepWidth", f32),
        ("PulseRepDelay", f32),
        ("PulseSeqStartWidth", f32),
        ("PulseSeqEndWidth", f32),
        ("PulseSeqStartDelay", f32),
        ("PulseSeqEndDelay", f32),
        ("PulseSeqIncMode", s16),
        ("PImaxUsed", s16),
        ("PImaxMode", s16),
        ("PImaxGain", s16),
        ("BackGrndApplied", s16),
        ("PImax2nsBrdUsed", s16),
        ("minblk", u16),
        ("numminblk", u16),
        ("SpecMirrorLocation", s16 * 2),
        ("SpecSlitLocation", s16 * 4),
        ("CustomTimingFlag", s16),
        ("ExperimentTimeLocal", c_char * TIMEMAX),
        ("ExperimentTimeUTC", c_char * TIMEMAX),
        ("ExposUnits", s16),
        ("ADCoffset", u16),
        ("ADCrate", u16),
        ("ADCtype", u16),
        ("ADCresolution", u16),
        ("ADCbitAdjust", u16),
        ("gain", u16),
        ("Comments", c_char * (5 * COMMENTMAX)),
        ("geometric", u16),
        ("xlabel", c_char * LABELMAX),
        ("cleans", u16),
        ("NumSkpPerCln", u16),
        ("SpecMirrorPos", s16 * 2),
        ("SpecSlitPos", f32 * 4),
        ("AutoCleansActive", s16),
        ("UseContCleansInst", s16),
        ("AbsorbStripNum", s16),
        ("SpecSlipPosUnits", s16),
        ("SpecGrooves", f32),
        ("srccmp", s16),
        ("ydim", u16),
        ("scramble", s16),
        ("ContinuousCleansFlag", s16),
        ("ExternalTriggerFlag", s16),
        ("lnoscan", s32),
        ("lavgexp", s32),
        ("ReadoutTime", f32),
        ("TriggeredModeFlag", s16),
        ("XMLOffset", u64),  # Used to be part of "Spare_2" of type char*10 in SPE2.5
        ("NotUsed", u16),  # Used to be part of "Spare_2" of type char*10 in SPE2.5
        ("sw_version", c_char * FILEVERMAX),  # version + date
        ("type", s16),
        ("flatFieldApplied", s16),
        ("Spare_3", c_char * 16),
        ("kin_trig_mode", s16),
        ("dlabel", c_char * LABELMAX),
        ("Spare_4", c_char * 436),
        ("PulseFileName", c_char * HDRNAMEMAX),
        ("AbsorbFileName", c_char * HDRNAMEMAX),
        ("NumExpRepeats", u32),
        ("NumExpAccums", u32),
        ("YT_Flag", s16),
        ("clkspd_us", f32),
        ("HWaccumFlag", s16),
        ("StoreSync", s16),
        ("BlemishApplied", s16),
        ("CosmicApplied", s16),
        ("CosmicType", s16),
        ("CosmicThreshold", f32),
        ("NumFrames", s32),
        ("MaxIntensity", f32),
        ("MinIntensity", f32),
        ("ylabel", c_char * LABELMAX),
        ("ShutterType", u16),
        ("shutterComp", f32),
        ("readoutMode", u16),
        ("WindowSize", u16),
        ("clkspd", u16),
        ("interface_type", u16),
        ("NumROIsInExperiment", s16),
        ("Spare_5", c_char * 16),
        ("controllerNum", u16),
        ("SWmade", u16),
        ("NumROI", s16),
        ("ROIinfblk", ROIInfo * ROIMAX),
        ("FlatField", c_char * HDRNAMEMAX),
        ("background", c_char * HDRNAMEMAX),
        ("blemish", c_char * HDRNAMEMAX),
        ("file_header_ver", f32),
        ("YT_Info", c_char * 1000),
        ("WinView_id", s32),
        ("xcalibration", CalibrationStruct),
        ("ycalibration", CalibrationStruct),
        ("Istring", c_char * 40),
        ("Spare_6", c_char * 25),
        ("SpecType", c_byte),
        ("SpecModel", c_byte),
        ("PulseBurstUsed", c_byte),
        ("PulseBurstCount", u32),
        ("PulseBurstPeriod", d64),
        ("PulseBracketUsed", c_byte),
        ("PulseBracketType", c_byte),
        ("PulseTimeConstFast", d64),
        ("PulseAmplitudeFast", d64),
        ("PulseTimeConstSlow", d64),
        ("PulseAmplitudeSlow", d64),
        ("AnalogGain", s16),
        ("AvGainUsed", s16),
        ("AvGain", s16),
        ("lastvalue", s16),
    ]
