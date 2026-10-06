"""Fixture routing and runner ownership contract."""
import ast
from pathlib import Path
from acceptance.aviation_weather_proof.run_browser import validate_arguments
import pytest

def test_fixture_mount_only_in_proof_mode():
    source=Path('tools/acceptance/overview-weather/backend_fixture.py').read_text()
    tree=ast.parse(source)
    branches=[n for n in ast.walk(tree) if isinstance(n,ast.If) and 'aviation-proof' in ast.unparse(n.test)]
    assert len(branches)==1
    assert '/api/overview-weather/aviation-proof-assets' in ast.unparse(branches[0])
    assert 'StaticFiles' in ast.unparse(branches[0])

def test_invalid_browser_arguments_rejected():
    with pytest.raises(ValueError):validate_arguments(['--origin','https://example.com'])


def test_private_products_are_readable_only_inside_fixture_mount(tmp_path):
    from acceptance.aviation_weather_proof.runner import prepare_fixture_mount
    parent=tmp_path/'private';parent.mkdir(mode=0o700)
    products=parent/'products';products.mkdir()
    product=products/'gfs';product.mkdir(mode=0o700)
    (product/'descriptor.json').write_text('{}')
    prepare_fixture_mount(products)
    assert product.stat().st_mode & 0o777 == 0o755
    assert parent.stat().st_mode & 0o777 == 0o700


def test_port_cleanup_waits_for_release_and_still_rejects_live_listener():
    import socket
    import threading
    from acceptance.aviation_weather_proof.runner import wait_ports_free
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
    port=listener.getsockname()[1]
    try:
        blocked=wait_ports_free([port],seconds=.02)
        assert blocked['remaining']==[f'listener:{port}']
        assert blocked['observations']
        closer=threading.Timer(.05,listener.close);closer.start()
        try:
            released=wait_ports_free([port],seconds=1)
            assert released['remaining']==[]
        finally:closer.join()
    finally:listener.close()


def test_entrypoint_uses_persistent_actor_lock_and_retains_it_until_exit(tmp_path):
    import os
    import subprocess
    import textwrap
    actor_cache = tmp_path / 'actor-cache'
    lock = actor_cache / 'starlink-acceptance' / 'scientific-decoder.lock'
    bin_dir = tmp_path / 'bin'; bin_dir.mkdir()
    receipt = tmp_path / 'receipt'
    python = bin_dir / 'python3'
    python.write_text(textwrap.dedent('''\
        #!/usr/bin/env bash
        set -euo pipefail
        test "$1" = -m
        test "$2" = acceptance.aviation_weather_proof.runner
        test -f "$PROOF_EXPECTED_LOCK"
        if flock -n "$PROOF_EXPECTED_LOCK" true; then exit 9; fi
        printf 'held' > "$PROOF_LOCK_RECEIPT"
    '''))
    python.chmod(0o700)
    env = {**os.environ, 'XDG_CACHE_HOME': str(actor_cache),
           'PATH': f'{bin_dir}:{os.environ["PATH"]}',
           'PROOF_EXPECTED_LOCK': str(lock), 'PROOF_LOCK_RECEIPT': str(receipt)}
    result = subprocess.run(['bash', 'tools/acceptance/aviation_weather_proof/run.sh',
                             '0' * 40, '/capture', '/profile'], env=env,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert receipt.read_text() == 'held'
    assert subprocess.run(['flock', '-n', str(lock), 'true'], timeout=5).returncode == 0
    assert lock.parent.stat().st_mode & 0o777 == 0o700
