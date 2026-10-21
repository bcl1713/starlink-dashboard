"""Verify that measured harness inputs belong to the recorded source SHA."""

import hashlib
import subprocess


def fingerprints(root, directories):
    result = {}
    for directory in directories:
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            relative = str(path.relative_to(root))
            recorded = subprocess.run(
                ["git", "show", "HEAD:" + relative],
                cwd=root,
                check=False,
                capture_output=True,
                timeout=10,
            )
            content = path.read_bytes()
            if recorded.returncode or recorded.stdout != content:
                raise ValueError("Uncommitted harness input: " + relative)
            result[relative] = hashlib.sha256(content).hexdigest()
    return result
