#!/usr/bin/env python3

import json
import sys

def main():
    if len(sys.argv) != 2:
        print("Usage: clean_compile_commands.py <compile_commands.json>")
        sys.exit(1)

    file_path = sys.argv[1]

    with open(file_path, 'r') as f:
        data = json.load(f)

    flags_to_remove = [
        '-Wno-class-memaccess',
        '-Wno-dangling-reference',
        '-Wno-stringop-overread',
        '-Wno-stringop-truncation',
        '-Werror=missing-declarations',
        '-Werror=builtin-declaration-mismatch'
    ]

    for entry in data:
        if 'command' in entry:
            for flag in flags_to_remove:
                entry['command'] = entry['command'].replace(flag, '')
        if 'arguments' in entry:
            entry['arguments'] = [arg for arg in entry['arguments'] if arg not in flags_to_remove]

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == '__main__':
    main()