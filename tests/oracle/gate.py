#!/usr/bin/env python3
"""luce-webp's decoder against libwebp, run by tests/oracle/main.lucb (`luc test`, which runs
the module's test blocks itself):

- tools/webpcheck built native, C and with the diagnostic profile (which fills `---`
  storage with 0xaa) into build/tests/oracle, each run over tests/fixtures (Ladybird's WebP
  test inputs and files made with libwebp's own encoders, damaged ones among them) and
  compared line for line with tests/fixtures/expected.txt: libwebp 1.6.0's features, frame
  durations and FNV-1a hashes of every frame, from the C oracle in
  luce-browser-tools/oracles/luce-webp (`tests/oracle/gate.py --expected ORACLE` writes it
  again);
- every third fixture cut short at many lengths and with flipped bytes, decoded without a trap or
  a hang.
"""
import os, random, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = os.environ.get("LUCE_BASE", "luce-base")
BUILD = ROOT / "build/tests/oracle"
FIXTURES = ROOT / "tests/fixtures"
NAMES = sorted(str(p.relative_to(FIXTURES)) for p in FIXTURES.glob("*/*.webp"))
EXPECTED = [line for line in (FIXTURES / "expected.txt").read_text().splitlines() if not line.startswith("#")]


def run(*command, cwd=ROOT, timeout=600):
    result = subprocess.run([str(c) for c in command], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        sys.exit(f"FAIL: {' '.join(map(str, command))}\n{result.stdout}{result.stderr}")
    return result.stdout


def check_fixtures(tool, label):
    found = run(tool, *NAMES, cwd=FIXTURES).splitlines()
    if found != EXPECTED:
        for index, (a, b) in enumerate(zip(found, EXPECTED)):
            if a != b:
                sys.exit(f"FAIL: {label}: line {index + 1} differs from libwebp:\n  got      {a}\n  expected {b}")
        sys.exit(f"FAIL: {label}: {len(found)} lines, libwebp gives {len(EXPECTED)}")
    frames = sum(1 for line in found if line.startswith("frame") and not line.endswith("error"))
    print(f"ok    {label}: {len(NAMES)} files, {frames} frames identical to libwebp")


def check_damage(tool, label):
    rng = random.Random(11)
    count = 0
    with tempfile.TemporaryDirectory(prefix="luce-webp-") as name:
        directory = Path(name)
        cases = []
        for fixture in NAMES[::3]:
            data = (FIXTURES / fixture).read_bytes()
            for cut in range(0, len(data), max(1, len(data) // 12)):
                cases.append(data[:cut])
            for _ in range(4):
                changed = bytearray(data)
                for _ in range(rng.randrange(1, 4)):
                    changed[rng.randrange(len(changed))] = rng.randrange(256)
                cases.append(bytes(changed))
        paths = []
        for index, case in enumerate(cases):
            path = directory / f"{index}.webp"
            path.write_bytes(case)
            paths.append(path.name)
        for start in range(0, len(paths), 200):
            result = subprocess.run([str(tool), *paths[start:start + 200]], cwd=directory, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                sys.exit(f"FAIL: {label}: a damaged file ended the process with {result.returncode}\n{result.stderr[-2000:]}")
            count += len(paths[start:start + 200])
    print(f"ok    {label}: {count} damaged files decoded without a trap")


if len(sys.argv) == 3 and sys.argv[1] == "--expected":
    # Regenerate expected.txt with the C oracle (webp_oracle_scalar) named.
    lines = run(sys.argv[2], *NAMES, cwd=FIXTURES)
    (FIXTURES / "expected.txt").write_text("# libwebp 1.6.0's portable C build on these files (luce-browser-tools/oracles/luce-webp, webp_oracle_scalar)\n" + lines)
    sys.exit(0)

BUILD.mkdir(parents=True, exist_ok=True)
for flags, label in ((["--native"], "native"), (["--backend=c"], "C"), (["--profile", "diagnostic"], "diagnostic")):
    tool = BUILD / f"webpcheck-{label}"
    run(BASE, "build", "tools/webpcheck.lucb", *flags, "-o", tool)
    check_fixtures(tool, f"webpcheck ({label})")
    if label == "native":
        check_damage(tool, f"webpcheck ({label})")
print("PASS luce-webp: fixtures against libwebp")
