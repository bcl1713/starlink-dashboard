"""Functional verification of the private verifier environment; no test suite added."""
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from rpds import HashTrieMap
import rpds.rpds as native

assert platform.python_version() == '3.11.16'
assert sys.prefix != sys.base_prefix
assert not os.environ.get('PYTHONPATH')
assert not any('/usr/lib/python3/dist-packages' in p for p in sys.path)
schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'integer'}
registry = Registry().with_resource('urn:private:integer', Resource.from_contents(schema))
validator = Draft202012Validator({'$ref': 'urn:private:integer'}, registry=registry)
validator.validate(42)
assert not validator.is_valid('wrong')
original = HashTrieMap({'a': 1})
assert original.insert('b', 2)['b'] == 2 and 'b' not in original
packages = {}
for dist in sorted(metadata.distributions(), key=lambda d: d.metadata['Name']):
    root = Path(dist.locate_file('')).resolve()
    assert root.is_relative_to(Path(sys.prefix).resolve())
    packages[dist.metadata['Name']] = {'version': dist.version, 'root': str(root), 'requires': dist.requires}
path = Path(native.__file__)
checks = {}
for argv in (['file', str(path)], ['readelf', '-h', str(path)], ['ldd', str(path)]):
    p = subprocess.run(argv, capture_output=True, text=True, check=True, timeout=10)
    checks[argv[0]] = p.stdout
assert 'X86-64' in checks['readelf'] and platform.machine() == 'x86_64'
assert 'not found' not in checks['ldd']
print(json.dumps({'status': 'PASS', 'python': sys.version, 'executable': sys.executable, 'base_executable_sha256': hashlib.sha256(Path(sys._base_executable).read_bytes()).hexdigest(), 'prefix': sys.prefix, 'sys_path': sys.path, 'packages': packages, 'native_extension': str(path), 'native_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'native_checks': checks, 'functional_checks': ['Draft202012Validator valid and invalid $ref resolution through referencing Registry', 'HashTrieMap persistent insert']}, indent=2))
