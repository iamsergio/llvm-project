#!/usr/bin/env python3

import sys
import os
import subprocess
import json
import time

def main():
    if not os.path.exists("compile_commands.json"):
        print("Error: compile_commands.json not found in the current directory.")
        sys.exit(1)

    # 1. Determine clangd binary
    clangd_path = None
    if len(sys.argv) > 1:
        clangd_path = sys.argv[1]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidate = os.path.join(script_dir, "build-dev", "bin", "clangd")
        if os.path.exists(candidate):
            clangd_path = candidate
    
    if not clangd_path:
        print("Error: clangd binary not found. Pass it as argument or ensure ./build-dev/bin/clangd exists.")
        sys.exit(1)

    # 2. Launch clangd
    cmd = ["heaptrack", clangd_path, "-lit-test", "--background-index", "-j=16", "--background-index-priority=normal"]
    print(f"Launching: {" ".join(cmd)}", file=sys.stderr)
    
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr
    )

    # 6. Open compile_commands.json and send didOpen for each .cpp file
    with open("compile_commands.json", "r") as f:
        commands = json.load(f)

    # Filter out unsupported flags
    flags_to_remove = ["-Wno-class-memaccess", "-Wno-dangling-reference", "-Wno-stringop-overread"]
    modified = False
    for entry in commands:
        if "arguments" in entry:
            original_len = len(entry["arguments"])
            entry["arguments"] = [arg for arg in entry["arguments"] if arg not in flags_to_remove]
            if len(entry["arguments"]) != original_len:
                modified = True
        elif "command" in entry:
            for flag in flags_to_remove:
                if flag in entry["command"]:
                    entry["command"] = entry["command"].replace(flag, "")
                    modified = True

    if modified:
        print("Writing filtered compile_commands.json...", file=sys.stderr)
        with open("compile_commands.json", "w") as f:
            json.dump(commands, f, indent=2)

    # 3. Send initialize
    initialize_msg = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "processId": 123,
            "rootUri": "file:///pub_data/sources/llvm-project/llvm",
            "capabilities": {
                "workspace": {
                    "workspaceEdit": {
                        "documentChanges": True
                    }
                }
            },
            "trace": "off"
        }
    }
    
    send_message(process, initialize_msg)
    
    # 4. Read response to initialize
    response = read_message(process)
    print("Received response:", json.dumps(response, indent=2), file=sys.stderr)

    # 5. Send initialized
    initialized_msg = {
        "jsonrpc": "2.0",
        "method": "initialized",
        "params": {}
    }
    send_message(process, initialized_msg)

    for entry in commands:
        file_path = entry.get("file")
        if file_path and file_path.endswith(".cpp"):
            # Ensure absolute path for URI
            if not os.path.isabs(file_path):
                file_path = os.path.abspath(file_path)
            
            did_open_msg = {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": f"file://{file_path}",
                        "languageId": "cpp",
                        "text": "#include <iostream>\\nint main() { return 0; }"
                    }
                }
            }
            send_message(process, did_open_msg)
            break
    
    # Keep alive
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()

def send_message(process, msg_dict):
    body = json.dumps(msg_dict)
    print(f"Sending: {body}", file=sys.stderr)
    process.stdin.write(body.encode("utf-8"))
    process.stdin.write(b"\n---\n")
    process.stdin.flush()

def read_message(process):
    content_length = None
    while True:
        line = process.stdout.readline()
        if not line:
            break
        line = line.decode("utf-8").strip()
        if not line:
            break
        if line.startswith("Content-Length:"):
            content_length = int(line.split(":", 1)[1].strip())
    
    if content_length is None:
        return None

    body = process.stdout.read(content_length)
    return json.loads(body.decode("utf-8"))

if __name__ == "__main__":
    main()
