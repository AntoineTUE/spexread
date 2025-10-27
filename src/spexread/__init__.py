"""`spexread` is a module to ingest Priceton Instruments SPE files, recorded with LightField or WinSpec software.

It mainly supports SPE files adhering to the version 3.0 or 2.x specification.

Older legacy file types can work, but correct (meta)data parsing is not guaranteed.
"""

__all__ = ["read_spe_file", "__version__", "__version_tuple__"]

from spexread.parsing import read_spe_file

from ._version import __version__, __version_tuple__
