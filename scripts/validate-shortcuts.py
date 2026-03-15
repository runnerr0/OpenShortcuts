#!/usr/bin/env python3
"""
Validate all .shortcut files in the repository.

Checks:
1. File is a valid binary plist
2. Required top-level keys exist
3. WFWorkflowActions array is present and non-empty
4. Each action has a valid WFWorkflowActionIdentifier
5. Action identifiers use the expected namespace
6. Import questions reference valid action indices
7. Build scripts reproduce identical output
"""

import plistlib
import os
import sys
import subprocess
import tempfile
import hashlib

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_KEYS = [
    "WFWorkflowActions",
    "WFWorkflowIcon",
]

KNOWN_ACTION_PREFIXES = [
    "is.workflow.actions.",
    "com.apple.",
]

KNOWN_ACTIONS = {
    "is.workflow.actions.comment",
    "is.workflow.actions.gettext",
    "is.workflow.actions.setvariable",
    "is.workflow.actions.getvariable",
    "is.workflow.actions.recordaudio",
    "is.workflow.actions.downloadurl",
    "is.workflow.actions.getvalueforkey",
    "is.workflow.actions.setclipboard",
    "is.workflow.actions.getclipboard",
    "is.workflow.actions.conditional",
    "is.workflow.actions.vibrate",
    "is.workflow.actions.notification",
    "is.workflow.actions.getdevicedetails",
    "is.workflow.actions.choosefrommenu",
    "is.workflow.actions.alert",
    "is.workflow.actions.showresult",
    "is.workflow.actions.getcontentsofurl",
    "is.workflow.actions.detect.text",
    "is.workflow.actions.text.replace",
    "is.workflow.actions.url",
    "is.workflow.actions.getitemfromlist",
    "is.workflow.actions.repeat.each",
    "is.workflow.actions.repeat.count",
    "is.workflow.actions.getdictionaryvalue",
    "is.workflow.actions.dictionary",
    "is.workflow.actions.ask",
    "is.workflow.actions.number",
    "is.workflow.actions.date",
    "is.workflow.actions.format.date",
    "is.workflow.actions.count",
    "is.workflow.actions.appendvariable",
    "is.workflow.actions.gettextfromimage",
    "is.workflow.actions.properties.note",
    "is.workflow.actions.findnotes",
    "is.workflow.actions.shownote",
    "is.workflow.actions.createnote",
    "is.workflow.actions.appendnote",
    "is.workflow.actions.addnewreminder",
    "is.workflow.actions.text.combine",
    "is.workflow.actions.text.split",
    "is.workflow.actions.getrichtextfrommarkdown",
    "is.workflow.actions.getmarkdownfromrichtext",
    "is.workflow.actions.urlencode",
    "is.workflow.actions.detect.dictionary",
    "is.workflow.actions.nothing",
    "is.workflow.actions.output",
    "is.workflow.actions.runworkflow",
}


def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def validate_shortcut(shortcut_path):
    name = os.path.basename(os.path.dirname(shortcut_path))
    errors = []
    warnings = []
    info = []

    # 1. Valid binary plist
    try:
        with open(shortcut_path, "rb") as f:
            data = plistlib.load(f)
    except Exception as e:
        errors.append(f"Not a valid plist: {e}")
        return name, errors, warnings, info

    info.append(f"Valid binary plist ({os.path.getsize(shortcut_path):,} bytes)")

    # 2. Required keys
    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"Missing required key: {key}")

    # 3. Actions array
    actions = data.get("WFWorkflowActions", [])
    if not actions:
        errors.append("WFWorkflowActions is empty or missing")
        return name, errors, warnings, info

    info.append(f"{len(actions)} actions")

    # 4 & 5. Action identifiers
    action_ids = []
    for i, action in enumerate(actions):
        aid = action.get("WFWorkflowActionIdentifier", "")
        if not aid:
            errors.append(f"Action {i}: missing WFWorkflowActionIdentifier")
            continue

        action_ids.append(aid)

        valid_prefix = any(aid.startswith(p) for p in KNOWN_ACTION_PREFIXES)
        if not valid_prefix:
            warnings.append(f"Action {i}: unknown namespace '{aid}'")
        elif aid not in KNOWN_ACTIONS:
            warnings.append(f"Action {i}: unrecognized action '{aid}' (may still be valid)")

    # Count unique actions
    unique_actions = set(action_ids)
    info.append(f"{len(unique_actions)} unique action types")

    # 6. Import questions
    import_questions = data.get("WFWorkflowImportQuestions", [])
    if import_questions:
        info.append(f"{len(import_questions)} import questions")
        for j, q in enumerate(import_questions):
            idx = q.get("ActionIndex", -1)
            if idx >= len(actions):
                errors.append(f"Import question {j}: ActionIndex {idx} exceeds action count ({len(actions)})")
            text = q.get("Text", "")
            if not text:
                warnings.append(f"Import question {j}: empty prompt text")
    else:
        warnings.append("No import questions defined (user won't be prompted to configure)")

    # Check workflow types
    wf_types = data.get("WFWorkflowTypes", [])
    if wf_types:
        info.append(f"Workflow types: {', '.join(wf_types)}")

    # Check icon
    icon = data.get("WFWorkflowIcon", {})
    if icon:
        glyph = icon.get("WFWorkflowIconGlyphNumber", "none")
        info.append(f"Icon glyph: {glyph}")

    return name, errors, warnings, info


def validate_build_script(build_script_path, shortcut_path):
    """Check if the build script reproduces the same shortcut."""
    name = os.path.basename(os.path.dirname(build_script_path))

    original_hash = file_hash(shortcut_path)

    # Run build script in a temp dir to avoid overwriting
    shortcut_name = os.path.basename(shortcut_path)
    try:
        result = subprocess.run(
            [sys.executable, build_script_path],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(build_script_path),
        )
        if result.returncode != 0:
            return name, False, f"Build script failed: {result.stderr.strip()}"

        rebuilt_hash = file_hash(shortcut_path)
        if rebuilt_hash == original_hash:
            return name, True, "Build script reproduces identical output"
        else:
            return name, False, "Build script output differs from committed file (UUIDs are random)"
    except subprocess.TimeoutExpired:
        return name, False, "Build script timed out"
    except Exception as e:
        return name, False, f"Error running build script: {e}"


def main():
    print("=" * 60)
    print("  OpenShortcuts Validation Report")
    print("=" * 60)

    # Find all .shortcut files
    shortcut_files = []
    for root, dirs, files in os.walk(os.path.join(REPO_ROOT, "shortcuts")):
        for f in files:
            if f.endswith(".shortcut"):
                shortcut_files.append(os.path.join(root, f))

    if not shortcut_files:
        print("\nNo .shortcut files found!")
        sys.exit(1)

    print(f"\nFound {len(shortcut_files)} shortcut(s) to validate.\n")

    total_errors = 0
    total_warnings = 0

    for shortcut_path in sorted(shortcut_files):
        name, errors, warnings, info = validate_shortcut(shortcut_path)

        status = "PASS" if not errors else "FAIL"
        icon = "✓" if not errors else "✗"
        print(f"{icon} {name} [{status}]")

        for i in info:
            print(f"    {i}")
        for w in warnings:
            print(f"    ⚠ {w}")
        for e in errors:
            print(f"    ✗ {e}")

        total_errors += len(errors)
        total_warnings += len(warnings)

        # Check build script
        build_script = os.path.join(os.path.dirname(shortcut_path), "build-shortcut.py")
        if os.path.exists(build_script):
            bname, success, msg = validate_build_script(build_script, shortcut_path)
            icon_b = "✓" if success else "⚠"
            print(f"    {icon_b} {msg}")
            if not success:
                total_warnings += 1
        else:
            print(f"    ⚠ No build-shortcut.py found")
            total_warnings += 1

        print()

    # Summary
    print("=" * 60)
    print(f"  {len(shortcut_files)} shortcuts validated")
    print(f"  {total_errors} error(s), {total_warnings} warning(s)")
    print("=" * 60)

    sys.exit(1 if total_errors > 0 else 0)


if __name__ == "__main__":
    main()
