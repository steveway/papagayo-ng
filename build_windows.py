#!/usr/bin/env python3
"""
build_windows.py - Build Papagayo-NG into a Windows .exe (Nuitka) and an
MSI installer (WIX v4).

This is a single, self-contained entry point that reads settings from
build_config.yaml so there is one source of truth for version, icon, data
folders and installer metadata.

Typical usage
-------------
    # Build everything (exe + installer):
    py build_windows.py

    # Only build the standalone exe:
    py build_windows.py --target exe

    # Only build the MSI installer (assumes the exe already exists):
    py build_windows.py --target installer

    # Clean previous build artefacts first:
    py build_windows.py --clean

Prerequisites
-------------
    * Python 3.9+ with the project's requirements.txt installed
      (``pip install -r requirements.txt`` - this pulls in Nuitka + PyYAML).
    * The WIX Toolset v4 CLI (``wix.exe``) on PATH. Get it from
      https://wixtoolset.org/releases/ (the "WiX v4" command-line package).
      On first run ``wix build`` will auto-restore the WixUI extension
      NuGet package that provides the install UI.

The script prints clear, actionable messages whenever a prerequisite is
missing rather than dumping a raw traceback.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - friendly message
    sys.exit(
        "PyYAML is required to read build_config.yaml.\n"
        "Install it with:  pip install PyYAML"
    )


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "build_config.yaml"
WIX_TEMPLATE = ROOT / "wix" / "papagayo-ng.wxs"

# Build artefact directories (kept under build/ to keep the tree clean).
BUILD_DIR = ROOT / "build"
STAGING_DIR = BUILD_DIR / "staging"
WIX_FRAGMENT = BUILD_DIR / "PapagayoFiles.wxs"
WIX_OBJ_DIR = BUILD_DIR / "wixobj"


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
class BuildError(Exception):
    """Raised for user-facing build failures with a helpful message."""


def info(msg: str) -> None:
    print(f"[build] {msg}", flush=True)


def step(msg: str) -> None:
    print(f"\n=== {msg} ===", flush=True)


def run(cmd: list[str], **kwargs) -> None:
    """Run a command, streaming output. Raise BuildError on non-zero exit."""
    info("running: " + " ".join(str(c) for c in cmd))
    kwargs.setdefault("cwd", str(ROOT))
    result = subprocess.run([str(c) for c in cmd], **kwargs)
    if result.returncode != 0:
        raise BuildError(
            f"command failed with exit code {result.returncode}:\n"
            + " ".join(str(c) for c in cmd)
        )


def find_executable(name: str) -> str | None:
    """Locate an executable on PATH (without raising)."""
    return shutil.which(name)


def load_config(path: Path) -> dict:
    if not path.exists():
        raise BuildError(f"build config not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise BuildError(f"{path} does not contain a YAML mapping")
    return data


def normalize_version(version: str) -> str:
    """MSI requires a four-part x.y.z.w version. Pad/truncate as needed."""
    parts = re.split(r"[.\-]", str(version).strip())
    parts = [p for p in parts if p.isdigit()]
    if len(parts) < 2:
        raise BuildError(
            f"version '{version}' is not a recognizable x.y[.z[.w]] version"
        )
    while len(parts) < 4:
        parts.append("0")
    return ".".join(parts[:4])


# --------------------------------------------------------------------------- #
# Prerequisite checks
# --------------------------------------------------------------------------- #
def resolve_python() -> str:
    """Use the same interpreter we're running under."""
    return sys.executable


def ensure_nuitka(python: str, *, auto_install: bool) -> None:
    probe = subprocess.run(
        [python, "-m", "nuitka", "--version"],
        capture_output=True, text=True,
    )
    if probe.returncode == 0:
        version = probe.stdout.splitlines()[0] if probe.stdout else "unknown"
        info(f"Nuitka {version} found")
        return
    if not auto_install:
        raise BuildError(
            "Nuitka is not installed in the current Python environment.\n"
            f"Install it with:  {python} -m pip install Nuitka"
        )
    info("Nuitka not found - installing it via pip")
    run([python, "-m", "pip", "install", "Nuitka"])


def resolve_wix() -> str:
    """Locate the WIX CLI (wix.exe). Tested with WIX v7."""
    wix = find_executable("wix")
    if wix:
        return wix
    # Common install location (dotnet global tool).
    candidate = Path(os.environ.get("USERPROFILE", "")) / ".dotnet" / "tools" / "wix.exe"
    if candidate.exists():
        return str(candidate)
    raise BuildError(
        "WIX CLI ('wix.exe') was not found on PATH.\n"
        "Install it as a dotnet global tool with:\n"
        "  dotnet tool install --global wix\n"
        "or download from https://wixtoolset.org/releases/ and add its\n"
        "'bin' folder to PATH, then re-run this script."
    )


def ensure_wix_eula(wix: str) -> None:
    """Accept the WIX OSMF EULA if not already accepted.

    WIX v7 requires EULA acceptance. Passing --acceptEula on the command line
    breaks the subcommand parser, so we run 'wix eula accept wix7' once
    instead (idempotent - safe to run repeatedly).
    """
    probe = subprocess.run(
        [wix, "build", "-o", "NUL", "-d", "ProductName=probe"],
        capture_output=True, text=True,
    )
    if "WIX7015" not in probe.stderr and "WIX7015" not in probe.stdout:
        return  # EULA already accepted (or a different WIX version)
    info("accepting WIX OSMF EULA (one-time)")
    result = subprocess.run([wix, "eula", "accept", "wix7"], capture_output=True, text=True)
    if result.returncode != 0:
        raise BuildError(
            f"failed to accept WIX EULA:\n{result.stderr}\n"
            "You can accept it manually with:  wix eula accept wix7"
        )


def ensure_wix_ui_extension(wix: str) -> None:
    """Ensure the WixToolset.UI.wixext extension is available (idempotent).

    Installed globally (-g) so it lives in the user profile rather than a
    local .wix/ folder. This avoids path resolution bugs when the project
    lives on a UNC network share.
    """
    result = subprocess.run([wix, "extension", "list", "-g"], capture_output=True, text=True)
    if "WixToolset.UI.wixext" in (result.stdout + result.stderr):
        return
    info("installing WixToolset.UI.wixext extension globally (one-time)")
    result = subprocess.run(
        [wix, "extension", "add", "-g", "WixToolset.UI.wixext"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise BuildError(
            f"failed to add WixToolset.UI.wixext extension:\n{result.stderr}\n"
            "You can add it manually with:  wix extension add -g WixToolset.UI.wixext"
        )


# --------------------------------------------------------------------------- #
# Step 1 - Build the standalone exe with Nuitka
# --------------------------------------------------------------------------- #
def build_exe(cfg: dict, *, clean: bool, python: str) -> Path:
    step("Building standalone exe with Nuitka")

    project = cfg.get("project", {})
    build = cfg.get("build", {})
    inc = build.get("include", {}) or {}
    debug = cfg.get("debug", {}) or {}

    main_file = ROOT / project.get("main_file", "papagayo-ng.py")
    if not main_file.exists():
        raise BuildError(f"main file not found: {main_file}")

    out_cfg = build.get("output", {}) or {}
    out_dir = ROOT / out_cfg.get("directory", "dist")
    out_name = out_cfg.get("filename", "papagayo-ng.exe")
    out_dir.mkdir(parents=True, exist_ok=True)

    options = build.get("options", {}) or {}
    standalone = options.get("standalone", True)
    onefile = options.get("onefile", True)

    version = normalize_version(project.get("version", "1.0.0.0"))
    icon = ROOT / project.get("icon", "papagayo-ng.ico")

    args: list[str] = [python, "-m", "nuitka"]
    if standalone:
        args.append("--standalone")
    if onefile:
        args.append("--onefile")
    args.append("--assume-yes-for-downloads")
    if options.get("remove_output", True):
        args.append("--remove-output")
    args.append(f"--output-dir={out_dir}")
    args.append(f"--output-filename={out_name}")
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    args.append(f"--report={BUILD_DIR / 'nuitka-report.xml'}")

    if icon.exists():
        args.append(f"--windows-icon-from-ico={icon}")
    else:
        info(f"warning: icon not found at {icon}, skipping")

    # Splash screen (Nuitka onefile splash).
    splash = options.get("splash_screen")
    if splash and onefile:
        splash_path = ROOT / splash
        if not splash_path.is_file():
            raise BuildError(f"splash screen not found: {splash_path}")
        args.append(f"--onefile-windows-splash-screen-image={splash_path}")

    # Console mode. Nuitka accepts: force, disable, attach, hide.
    # Accept common synonyms from the config and normalise them.
    console_mode = (debug.get("console", {}) or {}).get("mode", "disable")
    console_mode = {
        "disabled": "disable",
        "enabled": "force",
        "shown": "force",
        "hidden": "hide",
    }.get(console_mode, console_mode)
    if console_mode not in {"force", "disable", "attach", "hide"}:
        raise BuildError(f"invalid Windows console mode: {console_mode}")
    args.append(f"--windows-console-mode={console_mode}")

    # Version / product metadata embedded into the exe.
    args += [
        f"--company-name={project.get('company', 'Morevna Project')}",
        f"--product-name={project.get('name', 'Papagayo-NG')}",
        f"--file-description={project.get('description', 'Lip-Sync Software')}",
        f"--product-version={version}",
        f"--file-version={version}",
    ]

    # Include packages.
    for pkg in inc.get("packages", []) or []:
        args.append(f"--include-package={pkg}")
    for module in inc.get("modules", []) or []:
        args.append(f"--include-module={module}")

    # Nuitka plugins (e.g. pyside6).
    for plugin in inc.get("plugins", []) or []:
        args.append(f"--enable-plugin={plugin}")

    # Data directories (shipped inside the exe).
    for entry in inc.get("data_dirs", []) or []:
        src = ROOT / entry["source"]
        if not src.is_dir():
            raise BuildError(f"configured data directory not found: {src}")
        args.append(f"--include-data-dir={src}={entry['target']}")

    # Loose data files shipped inside the exe.
    for entry in inc.get("data_files", []) or []:
        src = ROOT / entry["source"]
        if not src.is_file():
            raise BuildError(f"configured data file not found: {src}")
        args.append(f"--include-data-file={src}={entry['target']}")

    # Single-string data files listed directly in the config.
    for f in inc.get("files", []) or []:
        src = ROOT / f
        if not src.is_file():
            raise BuildError(f"configured include file not found: {src}")
        args.append(f"--include-data-file={src}={Path(f).name}")

    # Finally the entry point.
    args.append(str(main_file))

    if clean:
        _clean_nuitka(out_dir, out_name)

    run(args)
    exe_path = out_dir / out_name
    if not exe_path.exists():
        # Nuitka sometimes places output in a subfolder; search for it.
        found = list(out_dir.rglob(out_name))
        if found:
            exe_path = found[0]
        else:
            raise BuildError(
                f"Nuitka finished but {out_name} was not found under {out_dir}"
            )
    info(f"exe ready: {exe_path}")
    return exe_path


def smoke_test_exe(exe_path: Path) -> None:
    step("Smoke-testing packaged application")
    env = os.environ.copy()
    env["PAPAGAYO_BUILD_SMOKE_TEST"] = "1"
    try:
        with tempfile.TemporaryDirectory(prefix="papagayo-smoke-") as work_dir:
            result = subprocess.run(
                [str(exe_path), "--build-smoke-test"],
                cwd=work_dir,
                env=env,
                timeout=90,
            )
    except subprocess.TimeoutExpired as exc:
        raise BuildError(
            "packaged application did not finish its startup smoke test within 90 seconds"
        ) from exc
    if result.returncode != 0:
        crash_log = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Morevna Project" / "PapagayoNG" / "startup-crash.log"
        raise BuildError(
            f"packaged application smoke test failed with exit code {result.returncode}.\n"
            f"Check the startup log: {crash_log}"
        )
    info("packaged application started successfully from an isolated working directory")


def _clean_nuitka(out_dir: Path, out_name: str) -> None:
    """Remove Nuitka intermediate artefacts for a fresh build."""
    info(f"cleaning Nuitka output under {out_dir}")
    exe_path = out_dir / out_name
    if exe_path.exists():
        exe_path.unlink()
    # Nuitka build folders: <name>.build, <name>.dist, <name>.onefile-build
    stem = Path(out_name).stem
    for sub in out_dir.glob(f"{stem}.*"):
        if sub.is_dir():
            shutil.rmtree(sub, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Step 2 - Stage the install tree
# --------------------------------------------------------------------------- #
def stage_files(cfg: dict, exe_path: Path) -> Path:
    step("Staging files for the installer")
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
    STAGING_DIR.mkdir(parents=True)

    # The exe itself.
    shutil.copy2(exe_path, STAGING_DIR / exe_path.name)

    build = cfg.get("build", {}) or {}
    inc = build.get("include", {}) or {}

    # Data directories that should live next to the exe in the install tree
    # (so users can customise mouths / phonemes / resources).
    copy_beside = build.get("copy_beside", []) or []
    # Always make sure rsrc + phonemes are present in the install tree.
    for d in ["rsrc", "phonemes"]:
        if d not in copy_beside:
            copy_beside.append(d)

    for folder in copy_beside:
        src = ROOT / folder
        if src.is_dir():
            shutil.copytree(src, STAGING_DIR / folder, dirs_exist_ok=True)
        else:
            info(f"warning: copy_beside folder not found, skipping: {src}")

    # Extra loose files shipped alongside the exe.
    extra_files = inc.get("files", []) or []
    builtin_extras = [
        "gpl.txt", "readme.md", "papagayo-ng.ico",
        "about_markdown.html", "ipa_cmu.json",
        "version_information.txt",
    ]
    for f in list(extra_files) + builtin_extras:
        src = ROOT / f
        if src.is_file() and not (STAGING_DIR / src.name).exists():
            shutil.copy2(src, STAGING_DIR / src.name)

    # Translations + breakdowns are needed at runtime too.
    for folder in ["translations", "breakdowns"]:
        src = ROOT / folder
        if src.is_dir() and not (STAGING_DIR / folder).exists():
            shutil.copytree(src, STAGING_DIR / folder, dirs_exist_ok=True)

    info(f"staged {sum(1 for _ in STAGING_DIR.rglob('*'))} entries in {STAGING_DIR}")
    return STAGING_DIR


# --------------------------------------------------------------------------- #
# Step 3 - Generate the WIX file-components fragment
# --------------------------------------------------------------------------- #
def _wix_id(prefix: str, *parts: str) -> str:
    """Build a WIX-safe identifier from path parts."""
    raw = "_".join(parts)
    raw = re.sub(r"[^A-Za-z0-9_]", "_", raw)
    return f"{prefix}_{raw}"


def generate_wix_fragment(staging: Path) -> Path:
    """Walk the staging tree and emit a WIX v4 fragment with a
    ComponentGroup named 'PapagayoFiles' anchored at INSTALLDIR."""
    step("Generating WIX file fragment")
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!-- Auto-generated by build_windows.py - do not edit. -->',
        '<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">',
        '  <Fragment>',
        '    <DirectoryRef Id="INSTALLDIR">',
    ]
    component_ids: list[str] = []

    def walk(directory: Path, indent: int) -> None:
        pad = "  " * indent
        # Files in this directory.
        for child in sorted(directory.iterdir()):
            if child.is_file():
                file_id = _wix_id("f", child.relative_to(STAGING_DIR).as_posix())
                comp_id = _wix_id("c", child.relative_to(STAGING_DIR).as_posix())
                lines.append(
                    f'{pad}      <Component Id="{comp_id}" Guid="*">'
                )
                lines.append(
                    f'{pad}        <File Id="{file_id}" '
                    f'Source="{child}" KeyPath="yes" />'
                )
                lines.append(f'{pad}      </Component>')
                component_ids.append(comp_id)
        # Subdirectories.
        for child in sorted(directory.iterdir()):
            if child.is_dir():
                dir_id = _wix_id("d", child.relative_to(STAGING_DIR).as_posix())
                lines.append(f'{pad}      <Directory Id="{dir_id}" Name="{child.name}">')
                walk(child, indent + 1)
                lines.append(f'{pad}      </Directory>')

    walk(staging, 2)
    lines.append('    </DirectoryRef>')
    lines.append('  </Fragment>')
    lines.append('  <Fragment>')
    lines.append('    <ComponentGroup Id="PapagayoFiles">')
    for cid in component_ids:
        lines.append(f'      <ComponentRef Id="{cid}" />')
    lines.append('    </ComponentGroup>')
    lines.append('  </Fragment>')
    lines.append('</Wix>')

    WIX_FRAGMENT.parent.mkdir(parents=True, exist_ok=True)
    WIX_FRAGMENT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    info(f"wrote {WIX_FRAGMENT} ({len(component_ids)} components)")
    return WIX_FRAGMENT


# --------------------------------------------------------------------------- #
# Step 4 - Build the MSI with WIX v4
# --------------------------------------------------------------------------- #
def build_installer(cfg: dict, staging: Path, fragment: Path) -> Path:
    step("Building MSI installer with WIX")
    wix = resolve_wix()

    project = cfg.get("project", {})
    installer = cfg.get("installer", {}) or {}
    if not installer.get("enabled", True):
        raise BuildError("installer is disabled in build_config.yaml")

    meta = installer.get("metadata", {}) or {}
    product_name = project.get("name", "Papagayo-NG")
    manufacturer = meta.get("manufacturer", project.get("company", "Morevna Project"))
    version = normalize_version(project.get("version", "1.0.0.0"))
    upgrade_code = meta.get(
        "upgrade_code", "04604d2c-88b0-58f7-8f26-40a4e4dd239f"
    )

    out_cfg = installer.get("output", {}) or {}
    out_dir = ROOT / out_cfg.get("directory", "dist")
    out_name = out_cfg.get("filename", "papagayo-ng_installer.msi")
    out_dir.mkdir(parents=True, exist_ok=True)
    msi_path = out_dir / out_name

    icon = ROOT / project.get("icon", "papagayo-ng.ico")
    license_rtf = ROOT / installer.get("license_file", "rsrc/license.rtf")
    ui = installer.get("ui", {}) or {}
    banner = ROOT / ui.get("banner_image", "") if ui.get("banner_image") else None
    dialog = ROOT / ui.get("dialog_image", "") if ui.get("dialog_image") else None

    if not icon.exists():
        raise BuildError(f"installer icon not found: {icon}")

    WIX_OBJ_DIR.mkdir(parents=True, exist_ok=True)

    # Ensure the WIX OSMF EULA is accepted (WIX v7 requirement).
    ensure_wix_eula(wix)
    # Ensure the UI extension (WixUI_InstallDir) is available.
    ensure_wix_ui_extension(wix)

    args: list[str] = [wix, "build", "-ext", "WixToolset.UI.wixext"]
    args += ["-o", str(msi_path)]
    # WIX v4 variables passed to the preprocessor. Each -d takes the next
    # token as "NAME=VALUE", so they are emitted as separate list elements.
    def define(name: str, value: object) -> None:
        args.extend(["-d", f"{name}={value}"])

    define("ProductName", product_name)
    define("Manufacturer", manufacturer)
    define("ProductVersion", version)
    define("UpgradeCode", upgrade_code)
    define("HelpLink", "https://github.com/morevnaproject/papagayo-ng")
    define("IconPath", icon)
    if license_rtf.exists():
        define("LicenseRtfPath", license_rtf)
    if banner and banner.exists():
        define("BannerBmpPath", banner)
    if dialog and dialog.exists():
        define("DialogBmpPath", dialog)
    # Source files.
    args += [str(WIX_TEMPLATE), str(fragment)]

    run(args)
    if not msi_path.exists():
        raise BuildError(f"WIX finished but {msi_path} was not produced")
    info(f"installer ready: {msi_path}")
    return msi_path


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def clean_all() -> None:
    step("Cleaning build artefacts")
    if BUILD_DIR.exists():
        info(f"removing {BUILD_DIR}")
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
    dist = ROOT / "dist"
    if dist.exists():
        for p in dist.iterdir():
            if p.name.startswith("papagayo-ng"):
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    p.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build Papagayo-NG for Windows: Nuitka exe + WIX v4 MSI.",
    )
    parser.add_argument(
        "--target", choices=["exe", "installer", "all"], default="all",
        help="what to build (default: all)",
    )
    parser.add_argument(
        "-c", "--config", type=Path, default=DEFAULT_CONFIG,
        help=f"path to build_config.yaml (default: {DEFAULT_CONFIG.name})",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="remove previous build/dist artefacts before building",
    )
    parser.add_argument(
        "--no-auto-install", action="store_true",
        help="do not auto-install Nuitka via pip if missing",
    )
    parser.add_argument(
        "--skip-smoke-test", action="store_true",
        help="skip launching the packaged app after the build",
    )
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
        python = resolve_python()

        if args.clean:
            clean_all()

        exe_path: Path | None = None
        smoke_tested = False
        if args.target in ("exe", "all"):
            ensure_nuitka(python, auto_install=not args.no_auto_install)
            exe_path = build_exe(cfg, clean=args.clean, python=python)
            if not args.skip_smoke_test:
                smoke_test_exe(exe_path)
                smoke_tested = True

        if args.target in ("installer", "all"):
            if exe_path is None:
                # Locate a previously built exe.
                out_cfg = (cfg.get("build", {}) or {}).get("output", {}) or {}
                out_dir = ROOT / out_cfg.get("directory", "dist")
                out_name = out_cfg.get("filename", "papagayo-ng.exe")
                exe_path = out_dir / out_name
                if not exe_path.exists():
                    found = list(out_dir.rglob(out_name))
                    if not found:
                        raise BuildError(
                            f"no exe found at {exe_path}; build the exe first "
                            f"with:  py build_windows.py --target exe"
                        )
                    exe_path = found[0]
            if not args.skip_smoke_test and not smoke_tested:
                smoke_test_exe(exe_path)
            staging = stage_files(cfg, exe_path)
            fragment = generate_wix_fragment(staging)
            build_installer(cfg, staging, fragment)

        step("Done")
        return 0

    except BuildError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nAborted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
