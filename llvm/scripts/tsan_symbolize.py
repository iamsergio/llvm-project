#!/usr/bin/env python3
"""Symbolize TSan/ASan stack traces using addr2line (or llvm-addr2line).

Usage:
    tsan_symbolize.py <binary> [file]
    cat tsan.txt | tsan_symbolize.py <binary>
    tsan_symbolize.py <binary> tsan_crash.txt

For traces that reference shared libraries, add extra mappings:
    tsan_symbolize.py build-tsan/bin/clangd-indexer \\
        -b libc.so.6=/lib/x86_64-linux-gnu/libc.so.6

The binary name in the trace (e.g. "clangd-indexer") is matched against the
basename of the paths you provide.  Frames from unrecognized binaries are
printed unchanged.

addr2line flags used: -f (function names) -C (demangle) -i (expand inlines)
"""

import argparse
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

# Matches TSan/ASan/MSan frame lines in two forms:
#   #N <null> <null> (binary+0xOFFSET) (BuildId: ...)
#   #N some::func /path/file.cpp:10 (binary+0xOFFSET)
_FRAME_RE = re.compile(
    r'^(\s+#\d+)'                           # indented frame index
    r'(?:\s+\S+\s+\S+)?'                    # optional existing func + location
    r'\s+\(([^+)]+)\+(0x[0-9a-f]+)\)'      # (binary_name+offset)
    r'(.*)'                                  # remainder (BuildId etc.)
)

# Resolved at startup
_addr2line_bin: str = ''
_binaries: dict[str, str] = {}


def _find_addr2line() -> str:
    # Prefer llvm-addr2line from the same build tree if available
    script_dir = Path(__file__).parent
    for candidate in [
        script_dir.parent / 'build-tsan' / 'bin' / 'llvm-addr2line',
        script_dir.parent / 'build-asan' / 'bin' / 'llvm-addr2line',
        script_dir.parent / 'build-dev'  / 'bin' / 'llvm-addr2line',
        script_dir.parent / 'build'      / 'bin' / 'llvm-addr2line',
    ]:
        if candidate.exists():
            return str(candidate)
    for name in ('llvm-addr2line', 'addr2line'):
        found = shutil.which(name)
        if found:
            return found
    return 'addr2line'


@lru_cache(maxsize=None)
def _resolve(binary_path: str, addr: str) -> list[str]:
    """Returns a flat list [func0, loc0, func1, loc1, ...] for inlined frames."""
    try:
        out = subprocess.check_output(
            [_addr2line_bin, '-e', binary_path, '-f', '-C', '-i', addr],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        lines = [l.strip() for l in out.strip().splitlines()]
        # addr2line emits pairs: function\nfile:line
        if len(lines) >= 2 and lines[0] != '??':
            return lines
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        pass
    return ['??', '??:0']


def _emit_frames(frame_idx: str, binary_path: str, addr: str) -> list[str]:
    raw = _resolve(binary_path, addr)
    bin_name = Path(binary_path).name
    result = []
    for i in range(0, len(raw) - 1, 2):
        func = raw[i] or '??'
        loc  = raw[i + 1] or '??:0'
        tag  = ' [inlined]' if i > 0 else ''
        result.append(f'{frame_idx}{tag} {func} at {loc} ({bin_name}+{addr})')
    return result or [f'{frame_idx} ?? at ??:0 ({Path(binary_path).name}+{addr})']


def symbolize(lines):
    for line in lines:
        m = _FRAME_RE.match(line)
        if not m:
            print(line, end='')
            continue

        frame_idx, bin_name, addr, _rest = m.groups()
        binary_path = _binaries.get(bin_name)
        if not binary_path:
            print(line, end='')
            continue

        for formatted in _emit_frames(frame_idx, binary_path, addr):
            print(formatted)


def main():
    parser = argparse.ArgumentParser(
        description='Symbolize TSan/ASan traces with addr2line',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('binary', help='Path to the primary binary')
    parser.add_argument('input', nargs='?', help='Input file (default: stdin)')
    parser.add_argument(
        '-b', '--extra-binary', metavar='NAME=PATH', action='append', default=[],
        help='Additional binary mapping, e.g. libc.so.6=/lib/.../libc.so.6',
    )
    parser.add_argument(
        '--addr2line', metavar='PATH',
        help='Override addr2line binary (default: auto-detect llvm-addr2line)',
    )
    args = parser.parse_args()

    global _addr2line_bin
    _addr2line_bin = args.addr2line if args.addr2line else _find_addr2line()

    primary = Path(args.binary)
    if not primary.exists():
        print(f'error: binary not found: {primary}', file=sys.stderr)
        sys.exit(1)
    _binaries[primary.name] = str(primary)

    for mapping in args.extra_binary:
        if '=' not in mapping:
            print(f'error: -b expects NAME=PATH, got: {mapping!r}', file=sys.stderr)
            sys.exit(1)
        name, path = mapping.split('=', 1)
        _binaries[name] = path

    print(f'# addr2line: {_addr2line_bin}', file=sys.stderr)
    print(f'# binaries:  {_binaries}', file=sys.stderr)

    src = open(args.input) if args.input else sys.stdin
    try:
        symbolize(src)
    finally:
        if args.input:
            src.close()


if __name__ == '__main__':
    main()
