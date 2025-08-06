"""`spexread` is a module to ingest Priceton Instruments SPE files, recorded with LightField or WinSpec software.

It mainly supports SPE files adhering to the version 3.0 or 2.x specification.

Older legacy file types can work, but correct (meta)data parsing is not guaranteed.

## Contents

* [`spexread.data_models`][spexread.data_models]: Data models to describe the hierarchical metadata in a file
* [`spexread.parsing`][spexread.parsing]: Functions to parse the contents of a file
* [`spexread.structdef`][spexread.structdef]: Definitions of C-structures to read the file header
* [`spexread.transformation`][spexread.transformation]: Helper functions for performing transformation mappings between different sensor orientations
"""

__all__ = ["read_spe_file", "__version__", "__version_tuple__", "version", "version_tuple"]

from spexread.parsing import read_spe_file

from ._version import __version__, __version_tuple__, version, version_tuple
