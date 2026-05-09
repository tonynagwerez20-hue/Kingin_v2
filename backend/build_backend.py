import os
import subprocess
import sys
from pathlib import Path

def build():
    print("=== BUILDING STANDALONE BACKEND ===")
    
    # Define files to package
    api_script = "kingin_api.py"
    engine_script = os.path.join("Engine", "main_loop.py")
    
    # PyInstaller flags
    # --onefile: Create a single executable
    # --noconsole: No console window (useful for background API)
    # --add-data: Include directories (models, config, etc.)
    
    # Note: On Windows, add-data separator is ';'
    # Format: "src_path;dest_path"
    
    # We include directories that are required for startup
    # BUT we want some (like config and storage) to remain as loose files
    # so the user can edit them if needed.
    
    # For now, let's just package the API into a single EXE.
    # We'll tell PyInstaller to include hidden imports for libraries that might be missed.
    
    hidden_imports = [
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "fastapi",
        "lightgbm",
        "zmq",
        "pandas",
        "joblib",
        "dotenv",
        "Engine.main_loop" # Bundle the main loop as well
    ]
    
    # Modules to explicitly exclude to save space
    excludes = [
        "torch",
        "matplotlib",
        "scipy",
        "notebook",
        "PIL",
        "PyQt5",
        "PySide2",
        "tkinter",
        "numpy.distutils",
        "IPython",
        "jedi"
    ]
    
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--console", 
        "--name", "kingin_api",
    ]
    
    # Add essential packages so they aren't missed during dynamic imports
    essential_dirs = ["Engine", "support", "execution", "utils", "networking", "data_feed", "config", "mt5", "risk"]
    for edir in essential_dirs:
        if os.path.exists(edir):
            cmd.extend(["--add-data", f"{edir}{os.pathsep}{edir}"])
            cmd.extend(["--collect-submodules", edir])

    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])
        
    for exc in excludes:
        cmd.extend(["--exclude-module", exc])
    
    cmd.append(api_script)
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    
    print("\n=== BACKEND BUILD COMPLETE ===")
    print("Executable created at: dist/kingin_api.exe")

if __name__ == "__main__":
    build()
