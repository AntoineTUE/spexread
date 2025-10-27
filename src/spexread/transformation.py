"""Simple transformations of data for rotation and flipping operations."""

import numpy as np
from typing import Any, Literal, TYPE_CHECKING
from numpy.typing import ArrayLike

if TYPE_CHECKING:
    from .data_models import SPEType


def Hflip(x, y):
    """Flip data along horizontal axis.

    This causes the x-axis to be inverted.
    """
    return x[::-1], y


def Vflip(x, y):
    """Flip data along vertical axis.

    This causes the y axis to be inverted.
    """
    return x, y[::-1]


def rotate_clockwise(x, y):
    """Rotate data clockwise by 90 degrees.

    This swaps the order of the two axes and inverts the order of the y-axis.
    """
    return y[::-1], x


def apply_transformations(x: Any, y: Any, flip_h: bool = False, flip_v: bool = False, rotate: bool = False):
    """Apply flip(s) then rotation to axes.

    This order is consistent with how LightField applies these transformations.
    It allows for a total of 8 ($=2^3$) different orientations to be represented by these operations.
    """
    if flip_h:
        x, y = Hflip(x, y)
    if flip_v:
        x, y = Vflip(x, y)
    if rotate:
        x, y = rotate_clockwise(x, y)
    return x, y


def transformation_mapping(
    from_orientation: tuple[bool, bool, bool], to_orientation: tuple[bool, bool, bool]
) -> tuple[bool, bool, bool]:
    """Determine the transformations needed to map from one orientation to another.

    Flip operations use XOR (exclusive or) and rotations are determined from difference.

    Args:
        from_orientation (tuple[bool, bool, bool]): The current orientation as (flip_h, flip_v, rotate).
        to_orientation (tuple[bool, bool, bool]): The target orientation as (flip_h, flip_v, rotate).

    Returns:
        tuple[bool, bool, bool]: The transformations needed as (flip_h, flip_v, rotate).
    """
    flip_h = from_orientation[0] ^ to_orientation[0]
    flip_v = from_orientation[1] ^ to_orientation[1]
    rotate = from_orientation[2] != to_orientation[2]
    return (flip_h, flip_v, rotate)


def parse_orientation(orientation: str) -> tuple[bool, bool, bool]:
    """Parse a string with orientation information, returning a tuple of atomic transformation operations."""
    return ("Horiz" in orientation, "Vert" in orientation, "Rot" in orientation)


def map_calibration_to_current_coordinate_system(
    info: "SPEType",
) -> tuple[Literal["x"] | Literal["y"], ArrayLike, tuple[str, str], tuple[str, str]]:
    """Compute the mapping of a wavelength calibration to the current sensor orientation.

    Wavelength calibrations are stored in the SPE file, along with the orientation that was used when it was taken.

    When transformations are applied to the sensor frames, this information can be used to map the calibration to the new orientation.

    Note that no guarantee can be made that the calibration in still valid, as this depends also on physical factors.

    These transformations should be considered best-effort and nothing more than a convenience for the case that they remain valid.

    Note:
        Without any transformation the order of the data stored on disk is (`frame`,`y`,`x`).
        For clarity, `frame` is omitted in transformations, as different orientations don't affect this.

    Returns:
        calib_coordinate_name:      The name of the axis that is wavelength calibrated, either "x" or "y"
        calibration:                The array of calibration values for the corresponding axis
        calibration_order:          The order of the dimensions of the calibration, when it was calibrated, before subsequent transformations.
        dimension_order:            The order of the dimensions of the frame after applying tranformation.
    """
    orient_calib = parse_orientation(
        info.Calibrations.WavelengthCalib.orientation if info.Calibrations.WavelengthCalib is not None else "Normal"
    )
    # print(f"{info.Calibrations.WavelengthCalib.orientation} -> {info.Calibrations.SensorInformation.orientation}")

    orient_current = parse_orientation(info.Calibrations.SensorInformation.orientation)
    default_order = ("x", "y")
    calibration_order = apply_transformations(*default_order, *orient_calib)  #
    calib_coordinate_name = calibration_order[0]  # Assume calibrated axis is at 0th index
    coordinate_order_current = apply_transformations(*default_order, *orient_current)  # noqa: F841
    transform = transformation_mapping(orient_calib, orient_current)
    calib = apply_transformations(info.Calibrations.wl, np.array([0, 1]), *transform)  # noqa: F841
    dimension_order = apply_transformations("y", "x", *transform)
    # print(
    #     f"{coordinate_order_calib}, {coordinate_order_current}, {coordinate_order_current.index(calib_coordinate_name)}"
    # )
    # return calib_coordinate_name, calib[coordinate_order_current.index(calib_coordinate_name)]
    return calib_coordinate_name, info.Calibrations.wl, calibration_order, dimension_order
