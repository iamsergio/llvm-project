#!/bin/bash

set -e

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

if [[ ! -d "$1" ]]; then
	echo "First argument should be the build dir"
	exit 1
fi

cd $1

ninja llvm-symbolizer
ninja clangd
ninja clangd-indexer