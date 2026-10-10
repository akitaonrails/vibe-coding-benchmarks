#!/bin/sh
set -eu
cd "$(dirname "$0")"
ruby -c src/main.rb >/dev/null
ruby -c src/solution.rb >/dev/null
