"""
One-shot monitor for cloud execution (GitHub Actions).
Runs pipeline + position check + journal if 8am, then exits.
"""
import sys
from datetime import datetime
import subprocess


def run_script(name):
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running {name}...")
    try:
        result = subprocess.run([sys.executable, name], check=False, timeout=600)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"[Monitor] {name} timed out")
        return False
    except Exception as e:
        print(f"[Monitor] {name} failed: {e}")
        return False


def main():
    print("=" * 60)
    print(f"  CRYPTO AGENCY — One-shot run at {datetime.now()}")
    print("=" * 60)

    # 1. Always run pipeline
    run_script("main.py")

    # 2. Always check positions
    run_script("check_positions.py")

    # 3. Send journal if it's 8am UTC
    now = datetime.utcnow()
    if now.hour == 8:
        print(f"\n[Monitor] 8am UTC — sending daily journal")
        run_script("agents/journal.py")

    print("\n" + "=" * 60)
    print("  One-shot complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
