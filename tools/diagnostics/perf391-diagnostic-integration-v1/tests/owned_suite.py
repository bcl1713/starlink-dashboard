"""Run unittest with descendant adoption in the test process itself.

Nested legacy runner tests create their own process sessions. A subreaper in
this process allows their existing waitpid cleanup to reap those descendants.
This changes only test-process adoption, grants no host capability/privilege.
"""

import ctypes
import sys
import unittest

libc = ctypes.CDLL(None, use_errno=True)
if libc.prctl(36, 1, 0, 0, 0) != 0:
    raise OSError(ctypes.get_errno(), "test subreaper")
suite = unittest.defaultTestLoader.discover(
    "tests", pattern=sys.argv[1] if len(sys.argv) > 1 else "test_*.py"
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
