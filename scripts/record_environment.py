#!/usr/bin/env python3
"""Record the software and hardware environment for a reproducible run.

Writes a JSON manifest with the Python, OS and CPU details, Solidity compiler
settings from foundry.toml, Foundry/solc/OPA versions, the pinned forge-std
revision, installed Python packages, and the source commit. Tools that are not
installed are recorded as null rather than guessed.

Foundry and OPA are looked up on PATH; set FOUNDRY_BIN or OPA_BIN to a
directory or executable to use a specific installation.
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def find_tool(name: str, env_var: str) -> str | None:
    override = os.environ.get(env_var)
    if override:
        path = Path(override)
        candidate = path / name if path.is_dir() else path
        return str(candidate) if candidate.exists() else None
    return shutil.which(name)


def cpu_model() -> str | None:
    system = platform.system()
    if system == 'Darwin':
        return run(['sysctl', '-n', 'machdep.cpu.brand_string'])
    if system == 'Linux':
        try:
            for line in Path('/proc/cpuinfo').read_text().splitlines():
                if line.startswith('model name'):
                    return line.split(':', 1)[1].strip()
        except OSError:
            return None
    return platform.processor() or None


def os_version() -> str:
    if platform.system() == 'Darwin':
        version = run(['sw_vers', '-productVersion'])
        build = run(['sw_vers', '-buildVersion'])
        if version:
            return f'macOS {version} ({build})' if build else f'macOS {version}'
    return platform.platform()


def tool_versions() -> dict:
    forge = find_tool('forge', 'FOUNDRY_BIN')
    anvil = find_tool('anvil', 'FOUNDRY_BIN')
    opa = find_tool('opa', 'OPA_BIN')
    solc = shutil.which('solc')
    return {
        'forge': run([forge, '--version']) if forge else None,
        'anvil': run([anvil, '--version']) if anvil else None,
        'solc_on_path': run([solc, '--version']) if solc else None,
        'opa': run([opa, 'version']) if opa else None,
    }


def compiler_settings() -> dict:
    with (ROOT / 'foundry.toml').open('rb') as f:
        profile = tomllib.load(f)['profile']['default']
    keys = ('solc_version', 'evm_version', 'optimizer', 'optimizer_runs', 'src', 'test')
    return {key: profile.get(key) for key in keys}


def submodules() -> dict:
    status = run(['git', 'submodule', 'status']) or ''
    result = {}
    for line in status.splitlines():
        parts = line.strip().lstrip('+-U').split()
        if len(parts) >= 2:
            result[parts[1]] = {
                'commit': parts[0],
                'describe': parts[2].strip('()') if len(parts) > 2 else None,
            }
    return result


def python_packages() -> dict:
    packages = {dist.metadata['Name']: dist.version for dist in metadata.distributions()}
    return dict(sorted(packages.items(), key=lambda item: item[0].lower()))


def pinned_requirements() -> dict:
    pins = {}
    for line in (ROOT / 'requirements.txt').read_text().splitlines():
        line = line.split('#', 1)[0].strip()
        if '==' in line:
            name, version = line.split('==', 1)
            pins[name.strip()] = version.strip()
    return pins


def requirement_mismatches(installed: dict, pins: dict) -> dict:
    normalize = lambda name: name.lower().replace('_', '-')
    installed_norm = {normalize(k): v for k, v in installed.items()}
    missing, different = [], {}
    for name, version in pins.items():
        found = installed_norm.get(normalize(name))
        if found is None:
            missing.append(name)
        elif found != version:
            different[name] = {'pinned': version, 'installed': found}
    return {'not_installed': sorted(missing), 'version_differs': different}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, default=ROOT / 'results' / 'validation' / 'environment.json')
    args = parser.parse_args()

    commit = run(['git', 'rev-parse', 'HEAD'])
    dirty = run(['git', 'status', '--porcelain'])
    installed = python_packages()
    pins = pinned_requirements()

    manifest = {
        'recorded_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'source_commit': commit,
        'working_tree_clean': dirty == '' if dirty is not None else None,
        'python': {
            'version': platform.python_version(),
            'implementation': platform.python_implementation(),
            'executable': Path(sys.executable).name,
        },
        'os': os_version(),
        'machine': platform.machine(),
        'cpu': cpu_model(),
        'cpu_count': os.cpu_count(),
        'solidity': compiler_settings(),
        'tools': tool_versions(),
        'submodules': submodules(),
        'python_packages': installed,
        'requirements_check': requirement_mismatches(installed, pins),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Environment written to {args.output.relative_to(ROOT)}')
    missing_tools = [name for name, value in manifest['tools'].items() if value is None]
    if missing_tools:
        print('Not found (recorded as null): ' + ', '.join(missing_tools))
    check = manifest['requirements_check']
    if check['not_installed'] or check['version_differs']:
        print(f"Requirements: {len(check['not_installed'])} not installed, "
              f"{len(check['version_differs'])} with a different version (see the JSON).")


if __name__ == '__main__':
    main()
