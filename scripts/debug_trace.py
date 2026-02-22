"""Captures the summary endpoint traceback from a temp uvicorn server."""
import subprocess, sys, time, urllib.request, urllib.error, os

# Kill anything on 8001 first
try:
    import socket
    s = socket.socket()
    s.connect(('localhost', 8001))
    s.close()
except Exception:
    pass

proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'app.main:app', '--port', '8001', '--no-access-log'],
    stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

time.sleep(6)
try:
    urllib.request.urlopen('http://localhost:8001/api/summary/sales_data', timeout=20)
except Exception as e:
    print(f"HTTP result: {e}")

time.sleep(2)
proc.terminate()
time.sleep(1)
out = proc.stdout.read() + proc.stderr.read()

print("=" * 60)
lines = out.splitlines()
# Print lines containing ERROR or Traceback or Exception
important = [l for l in lines if any(k in l for k in ['ERROR', 'Traceback', 'Exception', 'Error', 'error'])]
for l in important[:80]:
    print(l)

print("=" * 60)
print("LAST 50 lines:")
for l in lines[-50:]:
    print(l)
