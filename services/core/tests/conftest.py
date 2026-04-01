import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def plain_text_eml(fixtures_dir: Path) -> Path:
    return fixtures_dir / "plain_text.eml"


@pytest.fixture
def html_only_eml(fixtures_dir: Path) -> Path:
    return fixtures_dir / "html_only.eml"


@pytest.fixture
def multipart_eml(fixtures_dir: Path) -> Path:
    return fixtures_dir / "multipart.eml"


@pytest.fixture
def non_utf8_eml(fixtures_dir: Path) -> Path:
    return fixtures_dir / "non_utf8.eml"


@pytest.fixture
def mailing_list_eml(fixtures_dir: Path) -> Path:
    return fixtures_dir / "mailing_list.eml"


@pytest.fixture
def api_config_path(fixtures_dir: Path, tmp_path: Path) -> Path:
    """Copy the API fixture config to a writable tmp location."""
    src = fixtures_dir / "api_config.yml"
    dst = tmp_path / "mailagent.yml"
    shutil.copy(src, dst)
    return dst


@pytest.fixture
def api_client(api_config_path: Path):
    """TestClient backed by the fixture YAML config."""
    httpx = pytest.importorskip("httpx")
    tc = pytest.importorskip("fastapi.testclient")

    from mailagent.config import ConfigManager, load_config
    from mailagent.api import create_app

    result = load_config(api_config_path)
    cm = ConfigManager(result.config, api_config_path)
    app = create_app(cm)
    return tc.TestClient(app)
