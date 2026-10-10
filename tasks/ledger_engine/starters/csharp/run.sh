#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec dotnet target/bin/Ledger.dll
