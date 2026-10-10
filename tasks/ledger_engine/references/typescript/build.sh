#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec tsc -p tsconfig.json
