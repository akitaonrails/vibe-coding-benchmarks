#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec target/debug/ledger_engine
