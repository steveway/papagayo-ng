# Papagayo-NG 
![alt text](https://github.com/morevnaproject-org/papagayo-ng/raw/master/rsrc/papagayo-ng.png "Papagayo-NG")


To work with the Papagayo-NG source code, you need some special software installed. This software is not necessary to run the installer-based version of Papagayo-NG, but you do need it if you want to use this source code package.

## Requirements:

* sounddevice>=0.3.13
* cffi>=1.12.2
* numpy>=1.16.2
* pydub>=0.23.1
* anytree>=2.6.0
* PySide6

You can use the included requirements.txt with pip to install these, like this for example:  
``pip install -r requirements.txt``

## Running
To run Papagayo-NG, double-click the papagayo-ng.py file, or run the following command:  
``python3 papagayo-ng.py``

## Building (Windows)
Papagayo-NG ships with a self-contained build script (`build_windows.py`) that
produces a standalone `.exe` with [Nuitka](https://nuitka.net/) and an MSI
installer with the [WIX Toolset v4](https://wixtoolset.org/).

### Prerequisites
* Python 3.9+ with the project dependencies installed:
  ``pip install -r requirements.txt`` (this also pulls in Nuitka and PyYAML).
* The WIX v4 CLI (`wix.exe`) on your PATH, downloadable from
  https://wixtoolset.org/releases/ — only needed for the installer step.

All build settings (version, icon, data folders, installer metadata) live in
`build_config.yaml`, so that file is the single source of truth.

### Build everything (exe + installer)
``py build_windows.py``

### Build only the standalone exe
``py build_windows.py --target exe``
The exe is written to `dist/papagayo-ng.exe`.

### Build only the MSI installer
``py build_windows.py --target installer``
This expects the exe to already exist under `dist/` (build it first with
`--target exe` if it doesn't). The installer is written to
`dist/papagayo-ng_installer.msi`.

### Clean previous artefacts before building
``py build_windows.py --clean``

### Notes
* If Nuitka is missing, the script will offer to install it via pip
  (pass `--no-auto-install` to disable that).
* Every exe build is smoke-tested from an isolated working directory. The build
  fails if the packaged application cannot initialize; use `--skip-smoke-test`
  only when a launch test is not possible (for example, in a headless runner).
* Nuitka writes a dependency report to `build/nuitka-report.xml`.
* Startup failures are recorded in
  `%LOCALAPPDATA%/Morevna Project/PapagayoNG/startup-crash.log` and displayed to
  users even though the release exe has no console.
* The installer stages `rsrc/`, `phonemes/`, `translations/` and `breakdowns/`
  alongside the exe so users can customise resources after installing.
* The WIX source template lives in `wix/papagayo-ng.wxs`; the per-file
  component fragment is generated automatically into `build/PapagayoFiles.wxs`.

## Contents
The Papagayo-NG source package includes the following files:

- readme.md - this file
- gpl.txt - the user license for Papagayo-NG
- papagayo-ng.py - the main program file
- phonemes/*.json - phoneme sets in a JSON format
- LipsyncDoc.py - the document structure, including voices, phoneme breakdown, etc.
- breakdowns/*.py - code to break down words using language specific pronunciations
- LipsyncFrameQT.py - the main Papagayo-NG window
- WaveformViewRewrite.py - the waveform view in the main window
- MouthViewQT.py - the mouth view in the main window
- PronunciationDialogQT.py - a dialog to provide manual phoneme breakdown
- AboutBoxQT.py - about box
- rsrc/papagayo-ng2.ui - the QT Design File for the UI
- rsrc/ - various resources for Papagayo-NG, including button pictures, mouths, and language configuration/data
- rsrc/mouths/ - a folder containing the mouth pictures
- rsrc/languages/ - a folder containing the configuration and data for different languages
- papagayo-ng.ico - Windows icons
- papagayo-ng.icns - MacOS X icons
- setup.py - a script to build Papagayo-NG as a standalone Windows application
- setup_mac.py - a script to build Papagayo-NG as a standalone MacOS X application
- test/rsrc/ - Resource files used for testing language breakdown scripts in `breakdowns/`. Some breakdown scripts can be run directly (ex. `python -m breakdowns.korean_breakdown`) as a series of tests.

## Tips
Here are a couple tips for source code that you may want to modify:

By default, Papagayo-NG uses the Preston Blair phoneme set. There is also Fleming & Dobbs phoneme set available. The phoneme sets are stored in the phonemes sub folder. If you want to add a different set of phonemes, you can use existing sets as examples.

To add breakdowns for other languages create a new language configuration in `rsrc/languages/<language>` inside you need to place a configuration file (see italian for an example of how to configure a breakdown)  You will also need to create a breakdown class.  These live in breakdowns.  The naming convention is `<language>_breakdown.py`. Just examine one of the existing ones for how to make it work.  Make sure the function to call your breakdown processing is called **`breakdown_word`**.

Papagayo-NG now only works with Moho, but support could be added for other animation software, 2D or 3D. To add support for other export formats, look in the `LipsyncDoc.py` file for the function `LipsyncVoice:Export` - this is where Papagayo-NG exports switch data for Moho. You will also need to modify the file `LipsyncFrame.py` to add a user interface for exporting the new format.

-----------------------------

Original Copyright &copy; 2005 Mike Clifton  
Contact: http://www.lostmarble.com

Modifications &copy; 2010 Benjamin Lau  
Contact: http://code.google.com/p/papagayo/

Papagayo-NG &copy; 2020
- Konstantin Dmitriev
- Stefan Murawski
- Azia Giles Abuara
- Owen Gallagher
>TODO: Add People currently working on Papagayo-NG

https://github.com/morevnaproject/papagayo-ng
