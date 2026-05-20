#!/bin/bash


# example
# cmake --preset=tsan && cmake --build build-tsan
# ./scripts/run_clangd-tests.sh ./build-tsan/

set -e

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

if [[ ! -d "$1" ]]; then
	echo "First argument should be the build dir"
	exit 1
fi

cd $1

# build tests
ninja ClangdTests

# run tests
ninja check-clangd
