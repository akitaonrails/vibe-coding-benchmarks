#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec ./target/release/crash-store
