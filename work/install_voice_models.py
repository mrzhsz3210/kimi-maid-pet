from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))

from voice_models import install_models


if __name__ == '__main__':
    install_models()
