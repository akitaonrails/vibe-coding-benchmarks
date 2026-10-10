#!/bin/sh
set -eu
cd "$(dirname "$0")"
mkdir -p target
ghc -dynamic -O1 -Wall -isrc -outputdir target -o target/ledger src/Main.hs -package aeson
