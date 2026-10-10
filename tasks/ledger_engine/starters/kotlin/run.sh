#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec java -cp target/ledger.jar:/usr/share/java/gson.jar MainKt
