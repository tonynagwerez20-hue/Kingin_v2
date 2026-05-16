import os
import subprocess
import sys
from pathlib import Path

def build():
    print("Starting KingIn Trading System Build Process...")
    
    # 1. Define paths
    project_root = Path(__file__).parent
    backend_dir = project_root / "backend"
    main_script = backend_dir / "main.py"
    
    if not main_script.exists():
        print(f"Error: Could not find {main_script}")
        sys.exit(1)
    
    # 2. PyInstaller Command
    # --onefile: Create a single executable
    # --name: Name of the executable
    # --add-data: Include necessary folders
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile", # Single file executable
        "--name", "KingIn_v2",
        "--icon", str(project_root / "frontend" / "its_icon.ico"),
        "--clean",
        f"--paths={backend_dir}",
        f"--workpath={project_root / 'build'}",
        f"--distpath={project_root / 'dist'}",
        f"--specpath={project_root}",
        str(main_script)
    ]
    
    # Add data folders if they exist
    data_folders = ["api", "core", "data", "risk", "signal", "storage", "config", "license", "bridge"]
    for folder in data_folders:
        folder_path = backend_dir / folder
        if folder_path.exists():
            # Syntax: source;dest (Windows)
            cmd.append(f"--add-data={folder_path};{folder}")
    
    print(f"Running command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        print("\nBuild completed successfully!")
        print(f"Executable can be found in: {project_root / 'dist' / 'KingIn_v2'}")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error code: {e.returncode}")
        sys.exit(1)

if __name__ == "__main__":
    build()
