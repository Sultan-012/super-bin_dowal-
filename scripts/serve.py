"""Serve the built React UI and FastAPI under one origin; no external deployment."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--host', default='127.0.0.1')
parser.add_argument('--port', default=os.environ.get('PORT', '8000'))
args = parser.parse_args()
venv_python = root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
python = str(venv_python) if venv_python.exists() else sys.executable
if not (root / 'frontend' / 'dist' / 'index.html').is_file():
    raise SystemExit('Build frontend first: cd frontend && npm ci && npm run build')
raise SystemExit(subprocess.call([python, '-m', 'uvicorn', 'app.main:create_app', '--factory',
                                 '--host', args.host, '--port', str(args.port)], cwd=root / 'backend'))
