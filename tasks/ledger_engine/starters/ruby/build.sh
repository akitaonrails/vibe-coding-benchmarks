#!/bin/sh
set -eu
cd "$(dirname "$0")"
for file in src/*.rb; do ruby -c "$file" >/dev/null; done
