import subprocess
import pathlib
import sys


def run_command(cmd):
    print(f"\n[RUNNING] {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"[ERROR] Command failed: {' '.join(cmd)}")
        sys.exit(1)


def main(cue_path, output_folder=None):
    cue_path = pathlib.Path(cue_path).resolve()

    if not cue_path.exists():
        print(f"[ERROR] File not found: {cue_path}")
        sys.exit(1)

    base_name = cue_path.stem
    working_dir = cue_path.parent

    chd_path = working_dir / f"{base_name}.chd"
    dat_path = working_dir / f"{base_name}.dat"

    run_command([
        "chdman", "createcd",
        "-i", str(cue_path),
        "-o", str(chd_path)
    ])

    run_command([
        "python", "chd_to_dat.py",
        str(chd_path)
    ])

    cmd = [
        "python", "ZAassetExtraction.py",
        str(dat_path)
    ]

    if output_folder:
        cmd.append(output_folder)

    run_command(cmd)

    print("\n[DONE] Pipeline complete.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build.py <input.cue> [output_folder]")
        sys.exit(1)

    cue_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    main(cue_file, output_dir)
