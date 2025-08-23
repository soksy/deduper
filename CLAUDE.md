# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python GUI application for deleting duplicate files based on SHA256 checksums. The application uses PyQt5 for the GUI interface and allows users to prioritize directories when deciding which duplicate files to keep vs delete.

## Core Architecture

The application consists of:
- `MainApp` class: PyQt5 GUI with dual-pane interface (directory selection + priority ordering)
- `File` class: Handles file checksum generation using SHA256
- Core workflow: Add directories → Scan for duplicates → Set directory priorities → Execute deduplication

The deduplication logic preserves files from lower-priority directories (higher index in priority list) and deletes duplicates from higher-priority directories.

## Development Setup

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the application:
```bash
python newdeduper.py
```

## Key Implementation Details

- Uses SHA256 checksums for duplicate detection (newdeduper.py:182)
- Skips zero-byte files during scanning (newdeduper.py:101)
- Directory priority is determined by list position - lower in list = preferred (newdeduper.py:139)
- File deletion happens in deDupeFunction() at newdeduper.py:145
- GUI uses drag-drop reordering for priority setting