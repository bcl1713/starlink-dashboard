"""Offline exact-source slices: no import/startup of the application's main module.

Functions/methods compile directly from guarded files with original bodies and
instrumentation decorators. External managers are supplied by explicit fixtures;
FrameStore, RepositoryGate, input-admission decorator and AnyIO remain real.
"""

import ast
import atexit
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import backend_probe as probe  # noqa: E402
import build  # noqa: E402
import workers  # noqa: E402

REPO = PACKAGE.parents[2]
_temp = tempfile.TemporaryDirectory(prefix="perf391-stage2-slices-")
atexit.register(_temp.cleanup)


@lru_cache(None)
def roots(role):
    parent = Path(_temp.name) / role
    control = parent / "control"
    build.export_source(REPO, role, build.PINS[role], control)
    patched = parent / "patched"
    shutil.copytree(control, patched)
    patch_path = PACKAGE / "patches" / (role + ".patch")
    if patch_path.exists() and not os.getenv("PERF391_TEST_UNPATCHED"):

        spec = json.loads(patch_path.with_suffix(".json").read_text())
        build.apply_patch(patched, patch_path.read_bytes(), spec)
    return control / "backend/starlink-location", patched / "backend/starlink-location"


def module_at(root, relative):
    name = "slice_" + str(id(root)) + "_" + relative.replace("/", "_").replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, root / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def functions(root, relative, names, env=None, *, cls=None):
    tree = ast.parse((root / relative).read_text())
    nodes = tree.body
    if cls:
        nodes = next(
            n for n in nodes if isinstance(n, ast.ClassDef) and n.name == cls
        ).body
    selected = [
        n
        for n in nodes
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names
    ]
    if len(selected) != len(names):
        raise AssertionError("missing exact-source function")
    namespace = {
        "probe": probe,
        "invoke_sync": workers.invoke_sync,
        "await_pool": workers.await_pool,
        **(env or {}),
    }
    prefix = ast.ImportFrom(
        module="__future__", names=[ast.alias(name="annotations")], level=0
    )
    code = ast.fix_missing_locations(
        ast.Module(body=[prefix, *selected], type_ignores=[])
    )
    exec(compile(code, str(root / relative), "exec"), namespace)
    return namespace


def modules(**entries):
    """Fixture manager modules; preserve production function imports and order."""
    result = {}
    for dotted, values in entries.items():
        components = dotted.split(".")
        for i in range(1, len(components) + 1):
            name = ".".join(components[:i])
            if name not in result:
                result[name] = types.ModuleType(name)
                result[name].__path__ = []
            if i > 1:
                setattr(
                    result[".".join(components[: i - 1])],
                    components[i - 1],
                    result[name],
                )
        result[dotted].__dict__.update(values)
    return patch.dict(sys.modules, result)
