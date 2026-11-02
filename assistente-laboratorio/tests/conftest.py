import pytest


def pytest_addoption(parser):
    parser.addoption("--lmstudio", action="store_true", help="esegue le prove reali con LM Studio")
    parser.addoption("--docker", action="store_true", help="esegue le prove reali con Docker")


def pytest_collection_modifyitems(config, items):
    for marcatore in ("lmstudio", "docker"):
        if config.getoption(f"--{marcatore}"):
            continue
        salta = pytest.mark.skip(reason=f"prova reale: usare --{marcatore}")
        for item in items:
            if marcatore in item.keywords:
                item.add_marker(salta)
