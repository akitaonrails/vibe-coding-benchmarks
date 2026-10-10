#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec ruby src/main.rb
