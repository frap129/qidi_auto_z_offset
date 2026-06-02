#!/usr/bin/env python3
"""Static checks that auto_z_offset.py tracks upstream Klipper's probe.py API.

Run from the repo root:
    python3 scripts/check_upstream_api.py
"""

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGET = REPO / "auto_z_offset.py"

# Regexes that must NOT appear in the plugin (renamed/removed in upstream).
# Each pattern is anchored on the specific call/symbol so that legitimate
# uses of the substring (e.g. add_object("auto_z_offset", ...)) are allowed.
FORBIDDEN_PATTERNS = [
    (
        r"\bprobe\.ProbeSessionHelper\b",
        "ProbeSessionHelper was renamed to SampleAveragingHelper",
    ),
    (r"\bprobe\.ProbeEndstopSessionHelper\b", "ProbeEndstopSessionHelper was removed"),
    (
        r"\bmulti_probe_begin\b",
        "multi_probe_begin was removed; use start_probe_session",
    ),
    (r"\bmulti_probe_end\b", "multi_probe_end was removed; use end_probe_session"),
    (
        r"\b_handle_homing_move_begin\b",
        "HomingViaProbeHelper no longer registers these event handlers",
    ),
    (
        r"\b_handle_homing_move_end\b",
        "HomingViaProbeHelper no longer registers these event handlers",
    ),
    (
        r"\b_handle_home_rails_begin\b",
        "HomingViaProbeHelper no longer registers these event handlers",
    ),
    (
        r"\b_handle_home_rails_end\b",
        "HomingViaProbeHelper no longer registers these event handlers",
    ),
    (
        r'register_chip\(\s*["\']auto_z_offset["\']',
        "register_chip('auto_z_offset', ...) conflicts with [probe] section",
    ),
    (
        r"\bprobe\.HomingViaProbeHelper\(",
        "Plugin must not instantiate HomingViaProbeHelper (chip name conflict "
        "with [probe] section); homing is done via AUTO_Z_HOME_Z gcode command",
    ),
]

# Symbols that MUST appear at least once (proves we adopted the new API).
REQUIRED_SYMBOLS = [
    "probe.SampleAveragingHelper",
    "probe.ProbeOffsetsHelper",
    "probe.ProbeParameterHelper",
    "probe.ProbeEndstopWrapper",
    "start_probe_session",
]


def main() -> int:
    src = TARGET.read_text()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        print(f"FAIL: {TARGET} does not parse: {e}")
        return 1

    failures = []
    for pattern, why in FORBIDDEN_PATTERNS:
        if re.search(pattern, src):
            failures.append(f"forbidden pattern {pattern!r} present: {why}")
    for sym in REQUIRED_SYMBOLS:
        if sym not in src:
            failures.append(f"required symbol missing: {sym!r}")

    # The wrapper class must extend probe.ProbeEndstopWrapper and pass 3 args.
    wrapper_init = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "AutoZOffsetEndstopWrapper":
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == "__init__":
                    wrapper_init = child
                    break
    if wrapper_init is None:
        failures.append("AutoZOffsetEndstopWrapper.__init__ not found")
    else:
        args = [a.arg for a in wrapper_init.args.args]
        if len(args) < 4:
            failures.append(
                f"AutoZOffsetEndstopWrapper.__init__ should accept "
                f"(config, probe_offsets, param_helper); got {args}"
            )

    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: auto_z_offset.py uses the current upstream probe.py API")
    return 0


if __name__ == "__main__":
    sys.exit(main())
