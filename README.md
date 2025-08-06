# spexread

<!-- [![DOI](https://zenodo.org/badge/DOI/)](https://doi.org/) -->
[![GitHub License](https://img.shields.io/github/license/AntoineTUE/spexread)](https//www.github.com/AntoineTUE/spexread/blob/main/LICENSE)
[![GitHub Workflow Status build](https://img.shields.io/github/actions/workflow/status/AntoineTUE/spexread/build.yml?label=PyPI%20build)](https://pypi.python.org/pypi/spexread)
[![GitHub Workflow Status docs](https://img.shields.io/github/actions/workflow/status/AntoineTUE/spexread/documentation.yml?label=Documentation%20build)](https://antoinetue.github.io/spexread)
[![PyPI - Version](https://img.shields.io/pypi/v/spexread)](https://pypi.python.org/pypi/spexread)
[![PyPI - Python versions](https://img.shields.io/pypi/pyversions/spexread.svg)](https://pypi.python.org/pypi/spexread)
[![PyPI - Downloads](https://img.shields.io/pypi/dw/spexread)](https://pypistats.org/packages/spexread)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch)

A package for reading Princeton Instruments SPE files (version 2.x and 3.0) captured by WinSpec or LightField respectively.

It relies on [`xarray`](https://docs.xarray.dev) to handle the many different possible image shapes, ROIs, etc. that can be stored in an SPE file and reads them into a single `xarray.Dataset`, or a list of `xarray.DataArrays`.

Important metadata for both format versions is parsed and validated to a consistent schema using [`pydantic`](https://docs.pydantic.dev) and stored in the `attrs` attribute of the dataset.

This has a number of key benefits:

- [x] Data is described and indexed as a function of dimensions or coordinates.

- [x] Access per-frame tracking information such as `exposure_time` or `gate_width` trivially (when stored, SPE v3.0 only) as coordinates of your data, alongside the core dimension `x`,`y` and `frame`. A kinetic series with changing gate time (and gate-tracking enabled) and can be plotted as:
      * Total signal per frame: `data['ROI 0'].mean(['x','y']).plot(x='gate_width')`
      * Binned over `y` dimension: `data['ROI 0'].groupby('x').sum('y').plot(x='gate_width',y='wavelength')`

- [x] The `xarray.Dataset` supports multiple regions of interest (ROI's) that can be accessed like a python `dict`.
    * You can handle files in the same way, regardless of amount of ROI's.

- [x] Metadata remains closely associated with the data and can be easily accessed.


> [!IMPORTANT]
> `spexread` is functional, but some features and metadata that you use may be missing.
> Please file an issue and provide a sample file to add support for them.
> Found a bug? Please raise an issue as well!


## Installing

`spexread` can be installed easily with `pip`.

To install the latest version from GitHub, you can run the following command:

```console
pip install git+https://github.com/AntoineTUE/spexread
```

## Example usage

```python
from spexread import read_spe_file
from spexread.data_models import SPEType
from pathlib import Path
import matplotlib.pyplot as plt

# read data as a xarray.Dataset
data = read_spe_file(Path("./my_data.spe"))
print(data.coords._names) # lists available coordinate names

# plot spectra and trends over time
plt.figure()
for name,roi in data.items():
    roi.mean(['frame','y']).plot(x='wavelength', label=name)

plt.figure()
for name,roi in data.items():
    roi.mean(['y','x']).plot(x='frame',label=name)

# easily convert to numpy arrays if needed, other formats possible as well, see xarray docs.
image = data['ROI 0'].mean('frame').to_numpy()
plt.figure()
plt.imshow(image)

# Convert the SPE metadata to a SPEType pydantic model, allowing attribute access
metadata = SPEType.model_validate(data.attrs)
print(metadata.GeneralInfo)
print(metadata.Calibrations.WavelengthCalib)
print(metadata.Calibrations.WavelengthCalib.wavelength)
```

## License

spexread is licensed under the MIT license.
