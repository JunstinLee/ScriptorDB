from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

_LOGS_DIR = Path(os.environ.get("SCRIPTORDB_LOG_DIR", "logs"))
_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
_LOG_PATH = _LOGS_DIR / f"run_{_TIMESTAMP}.log"

_LOGS_DIR.mkdir(parents=True, exist_ok=True)

_log_file = open(str(_LOG_PATH), "w", buffering=1)

sys.stderr.write(f"[log_to_file] redirecting stdout+stderr to {_LOG_PATH}\n")
sys.stderr.flush()

sys.stdout = _log_file
sys.stderr = _log_file

print(f"=== ScriptorDB log started at {datetime.now().isoformat()} ===")
print(f"=== Log file: {_LOG_PATH.absolute()} ===")
print()
