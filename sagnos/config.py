"""
sagnos/config.py
Project config — reads/writes sagnos.json
"""

import json
from pathlib import Path
from dataclasses import dataclass, asdict


CONFIG_FILE = "sagnos.json"


@dataclass
class SagnosConfig:
    name:         str  = "my_app"
    version:      str  = "0.1.0"
    port:         int  = 8000
    host:         str  = "127.0.0.1"
    backend_entry: str = "backend/main.py"
    ui_dir:       str  = "ui"
    dart_output:  str  = "ui/lib/sagnos"

    @classmethod
    def load(cls, root: Path = None) -> "SagnosConfig":
        root        = root or Path.cwd()
        config_path = root / CONFIG_FILE
        if not config_path.exists():
            raise FileNotFoundError(
                f"No sagnos.json found in {root}.\n"
                "Run `sagnos new <name>` to create a project."
            )
        with open(config_path) as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, root: Path = None):
        root = root or Path.cwd()
        with open(root / CONFIG_FILE, "w") as f:
            json.dump(asdict(self), f, indent=2)