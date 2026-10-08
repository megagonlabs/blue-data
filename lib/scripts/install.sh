#!/bin/bash
set -e
echo 'Installing blue-data lib...'

# Resolve the lib/ directory (parent of this script's scripts/ dir) so the
# install works from any working directory, e.g. `bash lib/scripts/install.sh`.
cd "$(dirname "$0")/.." || exit 1

# install
python3 -m pip install -e '.[dev]'
