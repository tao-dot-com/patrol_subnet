import pytest

from patrol.validation.chain.runtime_versions import RuntimeVersions


@pytest.fixture(scope="module")
def runtime_versions():
    return RuntimeVersions()

def test_lookup_runtime_version_from_block_number(runtime_versions):
    assert runtime_versions.runtime_version_for_block(3_157_275) == 151
    assert runtime_versions.runtime_version_for_block(3_179_090) == 151
    assert runtime_versions.runtime_version_for_block(3_160_000) == 151

def test_lookup_runtime_version_from_out_of_range_block_number(runtime_versions):
    assert runtime_versions.runtime_version_for_block(3_014_339) is None
    assert runtime_versions.runtime_version_for_block(5_622_078) is None

def test_lookup_runtime_version_at_extreme_range_boundaries(runtime_versions):
    assert runtime_versions.runtime_version_for_block(3_014_340) == 149
    assert runtime_versions.runtime_version_for_block(5_413_452) == 261
