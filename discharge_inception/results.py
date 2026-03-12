#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Shared utilities for redirecting PostProcess tool output to a ``Results/``
directory tree that mirrors the study directory layout.

Authors:
    André Kapelrud, Robert Marskar

Copyright © 2026 SINTEF Energi AS
"""

import os
from pathlib import Path
from typing import Optional

RESULT_SUFFIXES = {".png", ".csv", ".nc", ".dat", ".out"}


def find_study_root(path: Path) -> Optional[Path]:
    """
    Walk upward from *path* and return the highest directory containing
    ``index.json``.  This reliably returns the study root whether the caller
    passes a run directory or a voltage subdirectory.
    """
    d = path.resolve()
    if d.is_file():
        d = d.parent
    study_root = None
    while True:
        if (d / "index.json").exists():
            study_root = d
        parent = d.parent
        if parent == d:
            break
        d = parent
    return study_root


def get_results_dir(db_path: Path) -> Path:
    """
    Return the target ``Results/`` sub-directory for a given db_dir or input file.

    ``Results/`` is placed *inside* the study root, mirroring the subdirectory
    structure: ``<study_root>/Results/<relative_path>``.
    """
    path = db_path.resolve()
    if path.is_file():
        path = path.parent
    study_root = find_study_root(path)
    if study_root is None:
        return path / "Results"
    rel = path.relative_to(study_root)
    return study_root / "Results" / rel


def ensure_results_dir(db_path: Path) -> Path:
    """Create and return the Results sub-directory for *db_path*."""
    d = get_results_dir(db_path)
    d.mkdir(parents=True, exist_ok=True)
    return d


def link_metadata(source_dir: Path, results_dir: Path) -> None:
    """
    Create relative symlinks for ``parameters.json``, ``index.json``, and
    ``structure.json`` in *results_dir* if they exist in *source_dir* and
    are not already present in *results_dir*.
    """
    for name in ("parameters.json", "index.json", "structure.json"):
        src = source_dir / name
        dst = results_dir / name
        if src.exists() and not dst.exists():
            dst.symlink_to(os.path.relpath(src, results_dir))


def list_results(study_dir: Path) -> dict:
    """
    Scan the Results/ directory for *study_dir* and return
    ``{relative_folder: [filenames]}`` for all non-symlink files with
    extensions in ``RESULT_SUFFIXES``, sorted.
    """
    results_root = get_results_dir(study_dir)
    if not results_root.exists():
        return {}
    grouped: dict = {}
    for p in sorted(results_root.rglob("*")):
        if p.is_file() and not p.is_symlink() and p.suffix in RESULT_SUFFIXES:
            rel_dir = str(p.parent.relative_to(results_root))
            grouped.setdefault(rel_dir, []).append(p.name)
    return grouped
