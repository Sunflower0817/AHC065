import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent
    input_path = root / "data/input.txt"
    output_path = root / "data/output.txt"
    log_path = root / "data/log.txt"

    with input_path.open("r", encoding="utf-8") as fin, output_path.open("w", encoding="utf-8") as fout, log_path.open("w", encoding="utf-8") as ferr:
        result = subprocess.run([sys.executable, str(root / "main.py")], stdin=fin, stdout=fout, stderr=ferr)

    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
