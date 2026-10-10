#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p target
PYTHONPYCACHEPREFIX="$PWD/target/pycache" python3 -m py_compile src/*.py
