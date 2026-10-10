#!/bin/sh
set -eu
cd "$(dirname "$0")"
DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 dotnet build Ledger.csproj --configuration Release --output target/bin --disable-build-servers --nologo -v quiet
