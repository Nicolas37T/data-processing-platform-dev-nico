import shutil
import os

base = r'C:\Users\DATAX\Documents\Nicolas\Taiga\webhook_reader\services'
files = [
    'db_lookup.py',
    'log_fetcher.py',
    'dag_incident_interpreter.py',
    'dag_incident_manager.py',
    'dag_incident_scanner.py'
]

for f in files:
    src = os.path.join(base, f)
    dst = os.path.join(base, f + '.bak')
    if os.path.exists(src):
        shutil.copyfile(src, dst)
        print(f"Backed up {f} -> {f}.bak")

print("All Taiga services backed up successfully!")
