import sys
import json
import subprocess
import os
import re

def is_ignored(path, repo_root):
    if not path:
        return False
    
    # Clean path (remove trailing slashes, dots at start of command args, etc.)
    path = path.strip().lstrip('.')
    if not path or path == '/':
        return False

    # Normalize path relative to repo root if it's absolute
    if os.path.isabs(path):
        try:
            path = os.path.relpath(path, repo_root)
        except ValueError:
            return False
            
    try:
        # Run git check-ignore to see if the file is ignored
        # -z for null termination (safer), but here we just check-ignore one by one
        result = subprocess.run(['git', 'check-ignore', '-q', path], cwd=repo_root, capture_output=False)
        return result.returncode == 0
    except Exception:
        return False

def extract_potential_paths(text):
    # Regex to find potential file paths: strings with slashes or dots that don't look like flags
    # We look for sequences of chars that often appear in paths.
    return re.findall(r'(?:[a-zA-Z0-9_/.-]+\.[a-zA-Z0-9_-]+|[a-zA-Z0-9_.-]+/[a-zA-Z0-9_/.-]*)', text)

def main():
    repo_root = os.getcwd()
    try:
        # Read from stdin
        input_raw = sys.stdin.read()
        if not input_raw:
            print(json.dumps({"hookSpecificOutput": {"permissionDecision": "allow"}}))
            return
        input_data = json.loads(input_raw)
    except Exception:
        print(json.dumps({"hookSpecificOutput": {"permissionDecision": "allow"}}))
        return

    tool_call = input_data.get("toolCall", {})
    tool_name = tool_call.get("tool")
    arguments = tool_call.get("arguments", {})

    paths_to_check = []
    
    # Extract paths from structured tool arguments
    for key in ["filePath", "path", "dirPath"]:
        if key in arguments:
            paths_to_check.append(arguments[key])
    
    # Handle terminal commands
    is_python_call = False
    is_direct_modify = False
    
    if tool_name == "run_in_terminal":
        command = arguments.get("command", "")
        
        # Check if it's a python call (looking for venv/bin/python or just python)
        if re.search(r'(venv/bin/python|python3?)\b', command):
            is_python_call = True
        
        # Check for blocked CLI tools and operators
        blocked_cli = ["cat", "head", "tail", "grep", "sed", "awk", "rm", "mv", "cp", "tee", "vi", "nano", "vim", "ls"]
        
        # Detect if any blocked CLI tool is used in the command
        # Better: check if the command *starts* with or has a pipe to/from these tools
        has_blocked_tool = any(re.search(rf'\b{cli}\b', command) for cli in blocked_cli)
        has_redirection = any(op in command for op in [">", ">>", "<", "|"])
        
        if has_blocked_tool or has_redirection:
            is_direct_modify = True
        
        # Extract potential paths from the command string
        paths_to_check.extend(extract_potential_paths(command))
    else:
        # Standard file tools are considered "direct"
        direct_tool_list = ["read_file", "create_file", "replace_string_in_file", "edit_notebook_file", "create_directory", "list_dir"]
        if tool_name in direct_tool_list:
            is_direct_modify = True

    # Deduplicate and filter paths that are ignored by git
    ignored_paths = []
    for p in set(paths_to_check):
        if is_ignored(p, repo_root):
            ignored_paths.append(p)
    
    ignored_paths.sort()

    if not ignored_paths:
        decision = "allow"
        reason = "No ignored files involved."
    else:
        path_list = ", ".join(ignored_paths)
        if is_python_call:
            # Requirement: "it is to be asked for permission to run python (from venv) program with the files in .gitignore as parameters"
            decision = "ask"
            reason = f"Python execution involves ignored files: {path_list}. Manual approval required."
        elif is_direct_modify:
            # Requirement: "always deny any direct read/write... to files in .gitignore"
            decision = "deny"
            reason = f"Direct access to ignored files is prohibited: {path_list}."
        else:
            # Catch-all for other tool types targeting ignored files
            decision = "ask"
            reason = f"Tool '{tool_name}' targets ignored files: {path_list}. Manual approval required."

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason
        }
    }
    print(json.dumps(output))

if __name__ == "__main__":
    main()
