from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.signing_service import ensure_keypair


if __name__ == "__main__":
    result = ensure_keypair()
    print(f"Private key: {result['private_key_path']}")
    print(f"Public key:  {result['public_key_path']}")
