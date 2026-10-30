"""Archive obsolete v2.1 test modules without deleting application data.

Run from the project root with: backend\\.venv\\Scripts\\python.exe scripts\\prepare-v2_2-tests.py
This script never connects to a database.
"""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parent.parent
old_tests = root / 'backend' / 'shift_tests'
archive = root / 'docs' / 'v2_1_tests_archived'
archive.mkdir(parents=True, exist_ok=True)
for name in ('test_active_chain.py', 'test_opening_reversal.py', 'test_snapshot.py'):
    source = old_tests / name
    if source.is_file():
        target = archive / (name + '.txt')
        if target.exists():
            i = 1
            while (archive / (name + '.' + str(i) + '.txt')).exists():
                i += 1
            target = archive / (name + '.' + str(i) + '.txt')
        shutil.move(str(source), str(target))
        print('Archived obsolete v2.1 test:', source.name)
print('Test preparation complete. No production tables or records modified.')
