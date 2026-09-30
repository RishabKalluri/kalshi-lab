import subprocess
import sys
from pathlib import Path


def main(argv=None):
    app = Path(__file__).with_name("app.py")
    port = (argv or ["8501"])[0] if argv else "8501"
    root = Path(__file__).resolve().parents[3]
    print(f"dashboard: http://localhost:{port}")
    sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app), "--server.port", port,
                              "--server.headless", "true", "--browser.gatherUsageStats", "false"], cwd=root))
