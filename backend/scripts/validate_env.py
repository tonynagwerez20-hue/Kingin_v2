#!/usr/bin/env python3
"""Simple environment validator for ITS desktop app.

Checks that Python, Node, npm, and key Python packages (pyzmq, MetaTrader5) are available.
Run from repository root: `python scripts/validate_env.py`
"""
import shutil
import subprocess
import sys
import json
import os

def which_any(names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None

def check_py_module(py_exe, module):
    try:
        out = subprocess.check_output([py_exe, '-c', f'import {module}; print(1)'], stderr=subprocess.STDOUT, text=True, timeout=10)
        return True
    except Exception:
        return False

def main():
    res = {}
    res['python'] = which_any(['python', 'python3', 'py'])
    res['node'] = which_any(['node'])
    res['npm'] = which_any(['npm'])
    res['rustc'] = which_any(['rustc'])
    res['cargo'] = which_any(['cargo'])

    py = res['python'] or 'python'
    res['pyzmq'] = check_py_module(py, 'zmq') or check_py_module(py, 'pyzmq')
    res['MetaTrader5'] = check_py_module(py, 'MetaTrader5')
    res['ml_model'] = os.path.exists(os.path.join('models','lgbm_signal_filter.json'))

    print(json.dumps(res, indent=2))

    good = True
    if not res['python']:
        print('ERROR: Python interpreter not found on PATH or via py launcher')
        good = False
    if not res['npm']:
        print('WARNING: npm not found — frontend build may fail')
    if not res['node']:
        print('WARNING: node not found — frontend dev/build may fail')
    if not res['pyzmq']:
        print('WARNING: pyzmq not found — engine ZMQ bridging may fail')
    if not res['MetaTrader5']:
        print('INFO: MetaTrader5 Python package not installed — engine will run in demo mode')
    if not res['ml_model']:
        print('INFO: ML model not found at models/lgbm_signal_filter.json — ML filter will use defaults')

    sys.exit(0 if good else 2)

if __name__ == '__main__':
    main()
