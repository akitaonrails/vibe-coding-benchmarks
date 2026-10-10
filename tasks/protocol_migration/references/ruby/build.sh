#!/bin/sh
set -eu
cd "$(dirname "$0")"
for f in src/*.rb; do ruby -c "$f" >/dev/null; done
