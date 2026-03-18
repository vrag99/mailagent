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
