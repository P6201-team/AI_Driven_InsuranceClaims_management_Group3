#!/usr/bin/env python3
"""Refresh the final bundle SHA-256 manifest after all artifacts exist."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


OUT = Path(__file__).resolve().parents[2] / "PE6201_A2_Final_Deliverables"
manifest = {}
for path in sorted(OUT.rglob("*")):
    rel = path.relative_to(OUT)
    is_user_junk = (
        path.name == ".DS_Store"
        or ".ipynb_checkpoints" in rel.parts
        or path.name.endswith("的副本")
    )
    if path.is_file() and path.name != "MANIFEST_SHA256.json" and not is_user_junk:
        manifest[str(path.relative_to(OUT))] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
(OUT / "MANIFEST_SHA256.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
)
print(f"manifest files={len(manifest)}")
