"""Initialize research native libraries in their verified loading order."""
import sys


def initialize_native() -> None:
    """Call before scientific imports in each fresh source worker/test process.

    The pinned eckit and pyproj wheels bundle different PROJ releases. Loading
    eckit first can interpose its symbols into pyproj and corrupt native state.
    This supported bootstrap does not repair an already mixed process.
    """
    if 'eccodes' in sys.modules and 'pyproj' not in sys.modules:
        raise RuntimeError('native bootstrap must precede ecCodes import')
    import pyproj

    if pyproj.proj_version_str != pyproj.__proj_version__:
        raise RuntimeError('pyproj loaded a different native PROJ release')
