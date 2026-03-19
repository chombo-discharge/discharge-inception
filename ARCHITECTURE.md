# Architecture: inception

## Overview

This project sets up, submits, and post-processes parametric studies of gas
discharge simulations on SLURM clusters.  A study is declared as a Python
`Runs.py` file and submitted via the `inception` CLI.  The CLI creates run
directories, injects parameters, and hands off to SLURM.  Everything that
happens *inside* a SLURM job is driven by one of the three Python jobscripts.

---

## Full call chain

```
inception run <Runs.py>              [CLI  – discharge_inception/configurator.py]
  │  Creates run directories, writes index.json / parameters.json per run,
  │  symlinks jobscript_symlink → <StudyJobscript.py>, writes slurm.toml path
  │  to DISCHARGE_INCEPTION_SLURM_CONFIG, then submits:
  │
  └─ sbatch --array=0-N GenericArrayJob.sh        [SLURM entry-point]
       │  Loads cluster modules from slurm.toml, activates venv, then runs:
       │
       └─ python ./jobscript_symlink               [jobscript dispatch]
            │
            ├─── DischargeInceptionJobscript.py    [inception database runs]
            │      Navigates to run_<id>/ via index.json, runs the inception
            │      solver, validates max_voltage, optionally reruns.
            │      Output: report.txt in each run directory.
            │
            └─── PlasmaJobscript.py                [plasma study runs]
                   Navigates to run_<id>/ via structure.json prefix, looks up
                   the matching inception database run, reads its report.txt,
                   builds a voltage table, creates voltage_<i>/ subdirectories,
                   and then submits a SECOND sbatch array:
                   │
                   └─ sbatch --array=0-M GenericArrayJob.sh   [voltage array]
                        └─ python ./jobscript_symlink
                             └─── GenericArrayJobJobscript.py  [voltage runs]
                                    Navigates to voltage_<id>/ via index.json,
                                    runs the plasma solver for one voltage.
```

---

## Script roles and file I/O

### `Util/GenericArrayJob.sh`
- **Role**: Portable SLURM wrapper; the only `#SBATCH` script in the project.
  Never called directly — always submitted via `sbatch --array=...`.
- **Reads**: `DISCHARGE_INCEPTION_SLURM_CONFIG` env var → `slurm.toml` (modules, venv); the configurator always sets this env var before invoking `sbatch` (falling back to `slurm.toml` in the CWD if needed), so compute nodes reliably inherit it
- **Executes**: `python ./jobscript_symlink` (the symlink selects the jobscript)

### `GenericArrayJobJobscript.py`
- **Role**: Runs the plasma solver for a single voltage inside a `voltage_<i>/`
  subdirectory created by PlasmaJobscript.py.
- **Reads**: `index.json` (prefix + index), `*.inputs`, `slurm.toml`
- **Writes**: Solver output files (HDF5, `report.txt`, etc.)
- **Called by**: Second `sbatch` in PlasmaJobscript.py (via `jobscript_symlink`)

### `Exec/Rod/Studies/DischargeInceptionJobscript.py`
- **Role**: Runs the inception solver for one parameter set (radius, pressure …).
  Validates the voltage sweep range and reruns if necessary.
- **Reads**: `index.json`, `*.inputs`, `slurm.toml`, `report.txt` (after run)
- **Writes**: `report.txt` (solver output), may rewrite `*.inputs`
- **Called by**: First `sbatch` on the inception database study

### `Exec/Rod/Studies/PlasmaJobscript.py`
- **Role**: Orchestrator for plasma study runs. Connects the inception database
  to the plasma simulation by reading the inception `report.txt`, building a
  voltage sweep table, creating subdirectories, and submitting a child job array.
- **Reads**: `structure.json`, `parameters.json`, `../inception_stepper/structure.json`,
  `<db_path>/index.json`, `<db_run>/report.txt`, `*.inputs`, `slurm.toml`
- **Writes**: `index.json` (voltage table), `array_job_id`, `voltage_<i>/` dirs,
  `voltage_<i>/*.inputs`, `voltage_<i>/chemistry.json`
- **Called by**: First `sbatch` on the plasma study

---

## Core library: `discharge_inception/`

| Module | Role |
|--------|------|
| `configurator.py` | Reads `Runs.py`, expands parameter space, creates run dirs, submits initial sbatch |
| `config_util.py` | URI injection (`.inputs` / `.json`), file helpers, SLURM task ID, jobscript setup |
| `json_requirement.py` | Parses and matches URI requirement syntax (`+["field"="value"]`) |

---

## Key design decisions

**Two-stage pipeline (inception → plasma)**
The inception stepper must complete before the plasma study can determine which
voltages to simulate.  SLURM `--dependency=afterok:<job_id>` enforces this
ordering.  `configurator.py` writes the inception job ID to `array_job_id` and
the plasma study's `sbatch` call adds `--dependency=afterok:$(cat array_job_id)`.

**`jobscript_symlink`**
`GenericArrayJob.sh` is generic; the actual Python logic is selected by the
`jobscript_symlink` symlink that `configurator.py` creates in each study
directory pointing to the appropriate `*Jobscript.py`.

**URI injection**
`config_util.handle_combination()` supports two target types:
- `.inputs` files: in-place line replacement, keyed by dot-separated field name
- `.json` files: nested dict traversal with list-matching requirements (`+[...]`)

See `Exec/Rod/Studies/PressureStudy/Runs.py` for annotated URI examples.

**`index.json` / `parameters.json` per run**
Each run directory contains both files for traceability: `index.json` maps
SLURM array task IDs to run directories; `parameters.json` stores the exact
parameter values for that run.
