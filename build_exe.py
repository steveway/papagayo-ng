#!/usr/bin/env python3
import os
import sys
import yaml
import subprocess
from pathlib import Path
from typing import Dict, Any
from build_installer import build_wix_installer

def find_venv_python() -> str:
    """Find the Python interpreter in the virtual environment."""
    venv_dirs = ['.venv', 'venv', 'env']
    python_exe = "python.exe" if sys.platform == "win32" else "python"
    python_path = os.path.join("Scripts" if sys.platform == "win32" else "bin", python_exe)
    
    current_dir = Path.cwd()
    for venv_dir in venv_dirs:
        # Check current directory
        venv_python = current_dir / venv_dir / python_path
        if venv_python.exists():
            return str(venv_python)
        
        # Check parent directory
        parent_venv_python = current_dir.parent / venv_dir / python_path
        if parent_venv_python.exists():
            return str(parent_venv_python)
    
    return sys.executable

def load_config(config_file: str = 'build_config.yaml') -> Dict[str, Any]:
    """Load and validate the build configuration."""
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    required_keys = ['project', 'build']
    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required key '{key}' in config file")
    
    return config

def build_nuitka_command(config: Dict[str, Any], python_exe: str) -> list:
    """Construct the Nuitka command from configuration."""
    project = config['project']
    build = config['build']
    main_file = project['main_file']
    
    cmd = [
        python_exe,
        "-m",
        "nuitka",
        main_file,
    ]

    # Basic options
    if build['options']['standalone']:
        cmd.append("--standalone")
    if build['options']['onefile']:
        cmd.append("--onefile")

    # Project metadata
    if project.get('icon'):
        cmd.append(f"--windows-icon-from-ico={project['icon']}")
    cmd.extend([
        f"--company-name={project['company']}",
        f"--product-name={project['name']}",
        f"--product-version={project['version']}",
        f"--file-description={project['description']}"
    ])

    # Splash screen
    if build['options'].get('splash_screen') and sys.platform == "win32":
        cmd.append(f"--onefile-windows-splash-screen-image={build['options']['splash_screen']}")

    # Distribution metadata
    for meta in build['include'].get('distribution_metadata', []):
        cmd.append(f"--include-distribution-metadata={meta}")

    # Packages
    for package in build['include'].get('packages', []):
        cmd.append(f"--include-package={package}")
        if package == "PySide6":
            cmd.append("--enable-plugin=pyside6")

    # Data directories
    for data_dir in build['include'].get('data_dirs', []):
        source_path = data_dir['source']
        target_path = data_dir['target']
        cmd.append(f"--include-data-dir={source_path}={target_path}")

    # External data
    for data in build['include'].get('external_data', []):
        cmd.append(f"--include-onefile-external-data={data}")

    # External files
    for file in build['include'].get('files', []):
        cmd.append(f"--include-data-file={file}={file}")

    # Remove .exe from output filename if we are not on Windows
    if sys.platform == "win32":
        file_name = build['output']['filename']
    else:
        file_name = build['output']['filename'][:-4]
    # Output settings
    cmd.extend([
        f"--output-dir={build['output']['directory']}",
        f"--output-filename={file_name}"
    ])

    # Debug settings
    debug = config.get('debug', {})
    if debug.get('enabled', False):
        cmd.extend([
            "--windows-console-mode=force",
            "--force-stdout-spec={PROGRAM_BASE}.out.txt",
            "--force-stderr-spec={PROGRAM_BASE}.err.txt"
        ])
    else:
        cmd.append("--windows-console-mode=disable")

    return cmd

def main():
    try:
        # Load configuration
        config = load_config()
        
        # Find virtual environment Python
        python_exe = find_venv_python()
        
        # Build the Nuitka command
        cmd = build_nuitka_command(config, python_exe)
        
        print("Building executable with Nuitka...")
        subprocess.run(cmd, check=True)
        print("Executable built successfully!")
        
        # Build installer if enabled
        if config.get('installer', {}).get('enabled', False):
            print("\nBuilding WiX installer...")
            build_wix_installer(config)
    
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
