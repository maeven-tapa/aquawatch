# AquaWatch

## Run locally on Windows

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python aquawatch\manage.py migrate
python aquawatch\manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

If PowerShell blocks virtual-environment activation, activation is optional. Run
the project directly with the environment's Python instead:

```powershell
.\.venv\Scripts\python.exe aquawatch\manage.py migrate
.\.venv\Scripts\python.exe aquawatch\manage.py runserver
```
