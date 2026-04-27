# Copyright (C) 2026 Project Librarian contributors
#
# This file is part of Project Librarian.
#
# Project Librarian is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Project Librarian is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Project Librarian. If not, see <https://www.gnu.org/licenses/>.

"""Cross-platform build script for Project Librarian distributions.

Supports building Windows EXE and Ubuntu DEB packages from source.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


class BuildConfig:
    """Configuration for build operations."""

    def __init__(self) -> None:
        """Initialize build configuration from project structure."""
        self.repo_root = Path(__file__).parent.absolute()
        self.venv_python = self._find_venv_python()
        self.dist_dir = self.repo_root / "dist"
        self.build_dir = self.repo_root / "build"
        self.scripts_dir = self.repo_root / "scripts"
        self.pyinstaller_tmp = self.repo_root / ".pyinstaller_tmp"
        self.main_entrypoint = self.repo_root / "main.py"
        self.forms_dir = self.repo_root / "app" / "ui" / "forms"
        self.assets_dir = self.repo_root / "app" / "ui" / "assets"
        self.requirements_packaging = self.repo_root / "requirements-packaging.txt"

        # Project metadata
        self.app_name = "ProjectLibrarian"
        self.app_display_name = "Project Librarian"
        self.version = self._read_version()

    def _find_venv_python(self) -> Path:
        """Locate the venv Python interpreter."""
        repo_root = Path(__file__).parent.absolute()
        if platform.system() == "Windows":
            venv_python = repo_root / ".venv" / "Scripts" / "python.exe"
        else:
            venv_python = repo_root / ".venv" / "bin" / "python"

        if not venv_python.exists():
            raise FileNotFoundError(
                f"Virtual environment Python not found at {venv_python}. "
                "Create it with: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
            )
        return venv_python

    def _read_version(self) -> str:
        """Extract version from main.py or return default."""
        try:
            content = (self.repo_root / "main.py").read_text(encoding="utf-8")
            # Look for version string in main file or app init
            app_init = self.repo_root / "app" / "__init__.py"
            if app_init.exists():
                app_content = app_init.read_text(encoding="utf-8")
                # Try to extract __version__ if present
                for line in app_content.split("\n"):
                    if "__version__" in line and "=" in line:
                        version = line.split("=")[1].strip().strip("\"'")
                        return version
            return "1.0.0"
        except Exception:
            return "1.0.0"


class WindowsBuilder:
    """Builds Windows EXE executables using PyInstaller."""

    def __init__(self, config: BuildConfig) -> None:
        """Initialize Windows builder."""
        self.config = config

    def build(self) -> Path:
        """Build Windows EXE package.

        Returns:
            Path to the built executable directory.

        Raises:
            RuntimeError: If build fails.
        """
        print("=" * 70)
        print("Building Windows EXE Package")
        print("=" * 70)

        if platform.system() != "Windows":
            raise RuntimeError(
                "Windows builder requires Windows platform. Use --deb for Linux."
            )

        # Install packaging dependencies
        self._install_packaging_deps()

        # Clean previous builds
        self._clean_build_files()

        # Run PyInstaller
        self._run_pyinstaller()

        # Validate build output
        exe_dir = self.config.dist_dir / self.config.app_name
        exe_file = exe_dir / f"{self.config.app_name}.exe"

        if not exe_file.exists():
            raise RuntimeError(f"PyInstaller failed: {exe_file} not created")

        print(f"\n✓ Windows EXE build complete: {exe_dir}")
        print(f"  Executable: {exe_file}")
        return exe_dir

    def _install_packaging_deps(self) -> None:
        """Install PyInstaller and related dependencies."""
        print("\n[1/3] Installing packaging dependencies...")
        cmd = [
            str(self.config.venv_python),
            "-m",
            "pip",
            "install",
            "-q",
            "-r",
            str(self.config.requirements_packaging),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to install packaging deps: {result.stderr}")

    def _clean_build_files(self) -> None:
        """Remove previous PyInstaller outputs."""
        print("\n[2/3] Cleaning previous build files...")
        for path in [self.config.dist_dir, self.config.build_dir, self.config.pyinstaller_tmp]:
            if path.exists():
                shutil.rmtree(path)
                print(f"  Removed: {path}")

    def _run_pyinstaller(self) -> None:
        """Execute PyInstaller with proper configuration."""
        print("\n[3/3] Running PyInstaller...")
        cmd = [
            str(self.config.venv_python),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--windowed",
            "--name",
            self.config.app_name,
            "--add-data",
            f"{self.config.forms_dir};app\\ui\\forms",
            "--add-data",
            f"{self.config.assets_dir};app\\ui\\assets",
            "--workpath",
            str(self.config.pyinstaller_tmp),
            "--distpath",
            str(self.config.dist_dir),
            str(self.config.main_entrypoint),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print("STDERR:", result.stderr)
            raise RuntimeError(f"PyInstaller failed with return code {result.returncode}")


class DebBuilder:
    """Builds Ubuntu DEB packages."""

    def __init__(self, config: BuildConfig) -> None:
        """Initialize DEB builder."""
        self.config = config
        self.temp_dir: Path | None = None

    def build(self) -> Path:
        """Build Ubuntu DEB package.

        Returns:
            Path to the built DEB file.

        Raises:
            RuntimeError: If build fails.
        """
        print("=" * 70)
        print("Building Ubuntu DEB Package")
        print("=" * 70)

        # Create temporary working directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix="librarian_deb_"))
        print(f"\nUsing temp directory: {self.temp_dir}")

        try:
            # Install packaging dependencies
            self._install_packaging_deps()

            # Build binary with PyInstaller
            binary_dir = self._build_binary()

            # Create DEB structure
            deb_root = self._create_deb_structure(binary_dir)

            # Build DEB package
            deb_file = self._build_deb_package(deb_root)

            print(f"\n✓ Ubuntu DEB build complete: {deb_file}")
            return deb_file

        finally:
            # Preserve DEB file before cleanup
            if self.temp_dir and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)

    def _install_packaging_deps(self) -> None:
        """Install PyInstaller and related dependencies."""
        print("\n[1/5] Installing packaging dependencies...")
        cmd = [
            str(self.config.venv_python),
            "-m",
            "pip",
            "install",
            "-q",
            "-r",
            str(self.config.requirements_packaging),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to install packaging deps: {result.stderr}")

    def _build_binary(self) -> Path:
        """Build binary using PyInstaller.

        Returns:
            Path to the built binary directory.
        """
        print("\n[2/5] Building binary with PyInstaller...")

        # Clean previous builds
        for path in [self.config.dist_dir, self.config.build_dir, self.config.pyinstaller_tmp]:
            if path.exists():
                shutil.rmtree(path)

        # Run PyInstaller
        cmd = [
            str(self.config.venv_python),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--windowed",
            "--name",
            self.config.app_name,
            "--add-data",
            f"{self.config.forms_dir}:app/ui/forms",
            "--add-data",
            f"{self.config.assets_dir}:app/ui/assets",
            "--workpath",
            str(self.config.pyinstaller_tmp),
            "--distpath",
            str(self.config.dist_dir),
            str(self.config.main_entrypoint),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print("STDERR:", result.stderr)
            raise RuntimeError(f"PyInstaller failed with return code {result.returncode}")

        binary_dir = self.config.dist_dir / self.config.app_name
        if not binary_dir.exists():
            raise RuntimeError(f"PyInstaller output not found: {binary_dir}")

        return binary_dir

    def _create_deb_structure(self, binary_dir: Path) -> Path:
        """Create DEB package directory structure.

        Args:
            binary_dir: Path to the built binary directory.

        Returns:
            Path to the DEB package root.
        """
        print("\n[3/5] Creating DEB package structure...")

        deb_root = self.temp_dir / "projectlibrarian-deb"
        deb_root.mkdir(parents=True, exist_ok=True)

        # Create DEBIAN metadata directory
        debian_dir = deb_root / "DEBIAN"
        debian_dir.mkdir(exist_ok=True)

        # Create usr/bin directory for executable
        usr_bin = deb_root / "usr" / "bin"
        usr_bin.mkdir(parents=True, exist_ok=True)

        # Create usr/lib directory for application files
        usr_lib = deb_root / "usr" / "lib" / "projectlibrarian"
        usr_lib.mkdir(parents=True, exist_ok=True)

        # Copy binary and dependencies to usr/lib
        print(f"  Copying binary to {usr_lib}...")
        for item in binary_dir.iterdir():
            if item.is_dir():
                shutil.copytree(item, usr_lib / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, usr_lib / item.name)

        # Create wrapper script in usr/bin
        wrapper_script = usr_bin / "projectlibrarian"
        self._create_wrapper_script(wrapper_script, usr_lib)

        # Create desktop file for menu integration
        applications_dir = deb_root / "usr" / "share" / "applications"
        applications_dir.mkdir(parents=True, exist_ok=True)
        self._create_desktop_file(applications_dir)

        # Create DEBIAN/control file
        self._create_control_file(debian_dir)

        # Create DEBIAN/postinst for post-installation tasks
        self._create_postinst(debian_dir)

        print(f"  DEB structure created at: {deb_root}")
        return deb_root

    def _create_wrapper_script(self, script_path: Path, app_lib_dir: Path) -> None:
        """Create shell wrapper script for the application."""
        script_content = f"""#!/bin/bash
# Wrapper script for Project Librarian

exec "{app_lib_dir}/ProjectLibrarian" "$@"
"""
        script_path.write_text(script_content, encoding="utf-8")
        os.chmod(script_path, 0o755)
        print(f"  Created wrapper script: {script_path}")

    def _create_desktop_file(self, applications_dir: Path) -> None:
        """Create .desktop file for application menu."""
        desktop_content = """[Desktop Entry]
Version=1.0
Type=Application
Name=Project Librarian
Comment=Local source code search and indexing tool
Exec=projectlibrarian
Icon=projectlibrarian
Categories=Development;Utility;
Terminal=false
"""
        desktop_file = applications_dir / "projectlibrarian.desktop"
        desktop_file.write_text(desktop_content, encoding="utf-8")
        os.chmod(desktop_file, 0o644)
        print(f"  Created desktop file: {desktop_file}")

    def _create_control_file(self, debian_dir: Path) -> None:
        """Create DEBIAN/control metadata file."""
        control_content = f"""Package: projectlibrarian
Version: {self.config.version}
Architecture: amd64
Maintainer: Project Librarian Contributors <https://github.com/project-librarian>
Homepage: https://github.com/project-librarian
Description: Local source code search and indexing tool
 Project Librarian is a standalone desktop application that provides
 fast local search across Python and C source files, Excel spreadsheets,
 and other indexed content. It maintains a complete search library in
 memory for near-instant query responses.
"""
        control_file = debian_dir / "control"
        control_file.write_text(control_content, encoding="utf-8")
        os.chmod(control_file, 0o644)
        print(f"  Created control file: {control_file}")

    def _create_postinst(self, debian_dir: Path) -> None:
        """Create DEBIAN/postinst post-installation script."""
        postinst_content = """#!/bin/bash
set -e

# Update application menu cache
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications
fi

exit 0
"""
        postinst_file = debian_dir / "postinst"
        postinst_file.write_text(postinst_content, encoding="utf-8")
        os.chmod(postinst_file, 0o755)
        print(f"  Created postinst script: {postinst_file}")

    def _build_deb_package(self, deb_root: Path) -> Path:
        """Build DEB package using dpkg-deb.

        Args:
            deb_root: Path to the DEB packaging root directory.

        Returns:
            Path to the built DEB file.

        Raises:
            RuntimeError: If dpkg-deb is not available or build fails.
        """
        print("\n[4/5] Building DEB package with dpkg-deb...")

        # Check if dpkg-deb is available
        result = subprocess.run(
            ["which", "dpkg-deb"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "dpkg-deb not found. Install with: sudo apt-get install dpkg-dev"
            )

        output_dir = self.config.dist_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        deb_filename = f"projectlibrarian_{self.config.version}_amd64.deb"
        deb_file = output_dir / deb_filename

        # Build DEB package
        cmd = ["dpkg-deb", "--build", str(deb_root), str(deb_file)]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print("STDERR:", result.stderr)
            raise RuntimeError(f"dpkg-deb failed: {result.stderr}")

        if not deb_file.exists():
            raise RuntimeError(f"DEB file not created: {deb_file}")

        print(f"\n[5/5] DEB package built: {deb_file}")
        print(f"  File size: {deb_file.stat().st_size / 1024 / 1024:.2f} MB")

        return deb_file


class BuildOrchestrator:
    """Orchestrates the build process."""

    def __init__(self, config: BuildConfig) -> None:
        """Initialize build orchestrator."""
        self.config = config

    def build_windows(self) -> Path:
        """Build Windows EXE.

        Returns:
            Path to the built executable directory.
        """
        builder = WindowsBuilder(self.config)
        return builder.build()

    def build_deb(self) -> Path:
        """Build Ubuntu DEB.

        Returns:
            Path to the built DEB file.
        """
        builder = DebBuilder(self.config)
        return builder.build()

    def build_all(self) -> dict[str, Path]:
        """Build all supported platforms.

        Returns:
            Dictionary mapping platform to built artifact path.
        """
        results: dict[str, Path] = {}

        # Build Windows on Windows
        if platform.system() == "Windows":
            print("\nDetected Windows platform")
            try:
                results["windows"] = self.build_windows()
            except Exception as e:
                print(f"✗ Windows build failed: {e}")
                return results

        # Build DEB on Linux
        if platform.system() == "Linux":
            print("\nDetected Linux platform")
            try:
                results["deb"] = self.build_deb()
            except Exception as e:
                print(f"✗ DEB build failed: {e}")
                if "dpkg-deb" in str(e):
                    print("  Install dpkg-dev: sudo apt-get install dpkg-dev")
                return results

        return results


def main() -> int:
    """Main entry point for build script.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Build Project Librarian for distribution"
    )
    parser.add_argument(
        "--exe",
        action="store_true",
        help="Build Windows EXE (Windows only)",
    )
    parser.add_argument(
        "--deb",
        action="store_true",
        help="Build Ubuntu DEB package (Linux only)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=True,
        help="Build all available platforms (default)",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean build artifacts and exit",
    )

    args = parser.parse_args()

    try:
        config = BuildConfig()
        print(f"\n{config.app_display_name} Build Tool")
        print(f"Repository: {config.repo_root}")
        print(f"Python: {config.venv_python}")
        print(f"Version: {config.version}")

        if args.clean:
            print("\n[CLEAN] Removing build artifacts...")
            for path in [config.dist_dir, config.build_dir, config.pyinstaller_tmp]:
                if path.exists():
                    shutil.rmtree(path)
                    print(f"  Removed: {path}")
            print("✓ Clean complete")
            return 0

        orchestrator = BuildOrchestrator(config)
        results: dict[str, Path] = {}

        # Determine which builds to run
        if args.exe:
            results["windows"] = orchestrator.build_windows()
        elif args.deb:
            results["deb"] = orchestrator.build_deb()
        else:
            # Default: build all available
            results = orchestrator.build_all()

        # Summary
        if results:
            print("\n" + "=" * 70)
            print("BUILD SUMMARY")
            print("=" * 70)
            for platform_name, artifact_path in results.items():
                print(f"✓ {platform_name.upper()}: {artifact_path}")
            print("=" * 70 + "\n")
            return 0
        else:
            print("\n✗ No builds completed successfully")
            return 1

    except KeyboardInterrupt:
        print("\n✗ Build cancelled by user")
        return 1
    except Exception as e:
        print(f"\n✗ Build failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
