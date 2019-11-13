
import configparser
from pathlib import Path

BASE_DIR: Path = Path(__file__).resolve().parent.parent
CONFIG_FILE = str(BASE_DIR / "config.ini")
DB_FILE = str(BASE_DIR / "mensausers.sqlite")

_parser = configparser.ConfigParser()
_parser.read(CONFIG_FILE)
config = _parser['DEFAULT']