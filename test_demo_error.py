#!/usr/bin/env python3
"""Test demo.py execution to find error"""
import subprocess
import time
import os
import sys

# Kill any existing demo processes
subprocess.run(["pkill", "-f", "demo.py"], capture_output=True)
time.sleep(1)

# Run demo.py with error output
env = os.environ.copy()
env['PYTHONPATH'] = '/home/hwilson/quiet-python-poc-3'

print("Starting demo.py...")
process = subprocess.Popen(
    [sys.executable, "/home/hwilson/quiet-python-poc-3/protocols/message_via_tor/demo/demo.py"],
    env=env,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Wait a bit for startup
time.sleep(2)

# Check if process is still running
if process.poll() is not None:
    # Process terminated
    stdout, stderr = process.communicate()
    print("Demo.py terminated!")
    print("\nSTDOUT:")
    print(stdout)
    print("\nSTDERR:")
    print(stderr)
else:
    print("Demo.py is running. Terminating...")
    process.terminate()
    stdout, stderr = process.communicate()
    print("\nPartial STDOUT:")
    print(stdout[:1000] if stdout else "")
    print("\nPartial STDERR:")
    print(stderr[:1000] if stderr else "")