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
