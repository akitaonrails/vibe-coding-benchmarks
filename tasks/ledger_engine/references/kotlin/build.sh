#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p target
kotlinc src/*.kt -cp /usr/share/java/gson.jar -include-runtime -d target/ledger.jar
