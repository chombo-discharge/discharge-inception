# inception

CLI and jobscript framework for parametric [chombo-discharge](https://github.com/chombo-discharge/chombo-discharge) studies on SLURM HPC clusters.

## What is inception?

inception manages coupled computer simulations using the chombo-discharge code.
It wraps two solver types from chombo-discharge:

- **DischargeInceptionStepper** — a lightweight PDIV (partial discharge inception voltage) database phase that sweeps inception voltages across a parameter space.
- **ItoKMC** — a heavier plasma solver that runs the full simulation study phase.

The CLI injects sweep parameters into per-run directories and submits SLURM array jobs.
The two phases are chained automatically: the database phase runs first, and its results feed the plasma study phase via `--dependency=afterok`.
Post-processing commands (`inception extract-inception-voltages`, etc.) consume the outputs of both phases.

The inception tool exposes parameter spaces, so that users can run the light and heavy weight simulations as a function of free parameters (e..g, pressure).

## Documentation

Documentation is built and published by the GitHub Actions workflow on every push to `main`:

- **HTML docs** (GitHub Pages): https://chombo-discharge.github.io/inception/
- **PDF**: https://chombo-discharge.github.io/inception/inception.pdf

> Note: the PDF and HTML are only deployed when commits are pushed to `main` on the `chombo-discharge/inception` repository. PRs build but do not deploy.

## Configuration and usage

1. **Install** — follow the [Installation guide](https://chombo-discharge.github.io/inception/Installation/Installation.html).
2. **Define the parameter space** — write a `Runs.py` or `Runs.json` file describing the sweep variables and their values.
3. **Submit** — run `inception run <definition>` to create run directories and submit SLURM array jobs.
4. **Monitor** — check job status with `inception ls <study_dir>`.
5. **Post-process** — extract results with `inception extract-inception-voltages` and related commands.

See the [CLI reference](https://chombo-discharge.github.io/inception/Installation/CLI.html) for full option details.

## Compilation

To make both programs (inception-stepper program and itokmc-based program), run
```
$ make -j4
```
where `-j<num>` is the number of cores to use for the compilation. Add `-s` flag to make the compilation silent. This will enter the relevant cases-subfolder and build executables.

