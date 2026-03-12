#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plasma study jobscript — sets up and submits the per-voltage SLURM array.

This script runs once per parameter combination in the plasma study stage
(invoked as a SLURM array task via ``GenericArrayJob.sh``).  Its job is to
bridge the inception-stepper database with a set of full plasma simulations
at the voltages where the ionisation integral K is meaningful.

Execution flow
--------------
1. **Navigate to run directory** — reads ``structure.json`` to find the run
   prefix, then uses ``setup_jobscript_logging_and_dir`` to change into the
   correct ``run_<i>/`` subdirectory for this SLURM task ID.

2. **Load database metadata** — reads ``../inception_stepper/structure.json``
   (to get the parameter key order) and the corresponding ``index.json`` (to
   map parameter values to run indices).

3. **Resolve K range and polarity** — reads ``plasma_polarity``, ``K_min``,
   and ``K_max`` from ``parameters.json``; falls back to reading
   ``DischargeInceptionStepper.limit_max_K`` from the ``.inputs`` file if
   ``K_max`` is absent.

4. **Build and submit the voltage array** — calls the four helpers in sequence:

   a. :func:`find_database_run` — resolves which ``PDIV_DB/run_<j>/``
      directory contains results for these parameters.
   b. :func:`extract_voltage_table` — reads ``report.txt`` from that database
      run and returns the (voltage, K, position) rows within [K_min, K_max].
   c. :func:`create_voltage_directories` — creates one ``voltage_<i>/``
      directory per table row, writes ``index.json``, copies required files,
      and injects voltage + electron seed position into each run's input files.
   d. :func:`submit_voltage_array` — submits the resulting array to SLURM and
      records the job ID.

Author André Kapelrud, Robert Marskar
Copyright © 2026 SINTEF Energi AS
"""

import json
import logging
import os
import re
import sys
from pathlib import Path
from subprocess import PIPE, Popen

import numpy as np

# local imports
sys.path.append(os.getcwd())  # needed for local imports from slurm scripts
from ExtractElectronPositions import parse_report_file  # noqa: E402
from discharge_inception.config_util import (  # noqa: E402
    DEFAULT_OUTPUT_DIR_PREFIX,
    backup_dir, backup_file,
    build_sbatch_resource_args, copy_files,
    handle_combination, load_slurm_config,
    read_input_float_field, setup_jobscript_logging_and_dir,
)

MAX_BACKUPS = 10
VOLTAGE_DIR_PREFIX = "voltage_"


def find_database_run(parameters: dict, db_structure: dict, db_index: dict) -> Path:
    """Locate the database run directory matching *parameters*.

    Searches *db_index* for the parameter combination defined by
    *db_structure['space_order']* and returns the path to the matched run
    directory inside the database study.

    Parameters
    ----------
    parameters : dict
        The current run's parameter dict, typically loaded from
        ``parameters.json``.  Must contain every key listed in
        ``db_structure['space_order']``.
    db_structure : dict
        The parsed ``structure.json`` of the inception database stage.
        Must contain ``'space_order'`` (ordered list of parameter keys)
        and ``'identifier'`` (the database directory name relative to
        the parent of the current working directory).
    db_index : dict
        The parsed ``index.json`` of the inception database stage.
        Expected keys: ``'index'`` (mapping str(i) → parameter list)
        and optionally ``'prefix'`` (run directory name prefix,
        defaults to ``DEFAULT_OUTPUT_DIR_PREFIX``).

    Returns
    -------
    Path
        Relative path ``../identifier/prefix<i>`` pointing to the
        matching database run directory.

    Raises
    ------
    ValueError
        If ``db_structure`` does not contain ``'space_order'``.
    RuntimeError
        If no entry in *db_index* matches the required parameter
        combination.
    """
    log = logging.getLogger(sys.argv[0])

    if 'space_order' not in db_structure:
        raise ValueError("missing field 'space_order' in database "
                         f"'{db_structure['identifier']}'")
    db_param_order = db_structure['space_order']
    db_path = Path('..') / db_structure['identifier']

    db_search_index = [parameters[p] for p in db_param_order]

    # build a reverse lookup map for O(1) search (JSON-serialised list as key)
    reverse_index = {json.dumps(params): int(db_i)
                     for db_i, params in db_index['index'].items()}
    index = reverse_index.get(json.dumps(db_search_index), -1)
    if index < 0:
        raise RuntimeError(
            f'Unable to find db parameter_set: {db_param_order} = {db_search_index}'
        )
    log.info(
        f"Found database parameters {db_param_order} = {db_search_index} "
        f"at index: {index}"
    )

    db_run_path = db_path
    if 'prefix' in db_index:
        db_run_path /= db_index['prefix'] + str(index)
    else:
        db_run_path /= DEFAULT_OUTPUT_DIR_PREFIX + str(index)
    return db_run_path


def _clamp_K_range(data: list, K_min: float, K_max: float) -> tuple[float, float]:
    """Warn and clamp K_min/K_max to the range available in *data*.

    Parameters
    ----------
    data : list of (voltage, K, position)
        Full table for one polarity, sorted by voltage.
    K_min, K_max : float
        User-requested ionisation-integral bounds.

    Returns
    -------
    tuple of (effective_K_min, effective_K_max)
        Possibly clamped values; a warning is logged for each bound that
        was out of range.
    """
    log = logging.getLogger(sys.argv[0])
    K_vals = [row[1] for row in data]
    actual_min, actual_max = min(K_vals), max(K_vals)

    eff_min, eff_max = K_min, K_max
    if K_max > actual_max:
        log.warning(
            f"K_max={K_max} exceeds the maximum K in the report "
            f"({actual_max:.4g}); clamping to {actual_max:.4g}"
        )
        eff_max = actual_max
    if K_min < actual_min:
        log.warning(
            f"K_min={K_min} is below the minimum K in the report "
            f"({actual_min:.4g}); clamping to {actual_min:.4g}"
        )
        eff_min = actual_min
    return eff_min, eff_max


def _pick_data(data: list, K_min: float, K_max: float) -> list:
    """Slice *data* to rows where K ∈ [K_min, K_max].

    *data* is a list of (voltage, K, position) triples sorted by voltage
    (equivalently, by K, since K is monotone in voltage).  The function
    keeps the last row at or below K_min as the lower boundary, and the
    first row above K_max as the upper boundary (rounding up).
    """
    imin, i_max = 0, 0
    for i, (_, K, _) in enumerate(data):
        if K <= K_min:
            imin = i
        if K <= K_max:
            i_max = i
    if data[i_max][1] != K_max and i_max + 1 < len(data):
        i_max += 1
    return data[imin:i_max + 1]


def extract_voltage_table(report_path: Path, polarity: int,
                          K_min: float, K_max: float) -> list:
    """Read *report_path* and return a voltage table filtered to [K_min, K_max].

    Parses the data table in the inception stepper ``report.txt`` via
    ``parse_report_file``, then trims each polarity's rows to the voltage
    range where K lies within [K_min, K_max], rounding the upper bound up
    to the nearest available row above K_max.  Both polarity tables are
    merged and sorted by ascending voltage before returning.

    Parameters
    ----------
    report_path : Path
        Path to the ``report.txt`` produced by the inception stepper for
        the matching database run.
    polarity : int
        Which voltage polarities to include.  Use ``1`` for positive only,
        ``-1`` for negative only, or ``0`` for both.
    K_min : float
        Lower bound on the ionisation integral K.  Rows with K below this
        value are excluded (the last row at or below K_min is kept as the
        lower boundary).
    K_max : float
        Upper bound on the ionisation integral K.  Rows with K above this
        value are excluded, except that the first row above K_max is
        included to bracket the range from above.

    Returns
    -------
    list of tuple
        Each entry is ``(voltage, K, position)`` where *voltage* is the
        applied voltage (V), *K* is the ionisation integral value, and
        *position* is the spatial coordinate tuple of the maximum-K point.
        The list is sorted by ascending voltage.
    """
    report_data = parse_report_file(report_path,
                                    ['+/- Voltage',
                                     'Max K(+)',
                                     'Max K(-)',
                                     'Pos. max K(+)',
                                     'Pos. max K(-)'])
    report_data = report_data[1]  # discard column names

    table = []
    if polarity >= 0:
        pos_data = [(v, Kp, pos_p) for v, Kp, _, pos_p, _ in report_data]
        eff_min, eff_max = _clamp_K_range(pos_data, K_min, K_max)
        table.extend(_pick_data(pos_data, eff_min, eff_max))
    if polarity <= 0:
        neg_data = [(v, Km, pos_n) for v, _, Km, _, pos_n in report_data]
        eff_min, eff_max = _clamp_K_range(neg_data, K_min, K_max)
        table.extend(_pick_data(neg_data, eff_min, eff_max))

    return sorted(table, key=lambda t: t[0])


def interpolate_table(report_path: Path, polarity: int,
                      K_min: float, K_max: float, n: int) -> list:
    """Return *n* interpolated (voltage, K, position) tuples per polarity.

    For polarity=0, interpolates *n* points for positive AND *n* points for
    negative polarity, returning 2*n* tuples total sorted by voltage.

    Voltage and all position coordinates are linearly interpolated at *n*
    evenly-spaced K values from K_min to K_max (inclusive).

    Parameters
    ----------
    report_path : Path
        Path to the inception stepper's report.txt.
    polarity : int
        1 = positive only, -1 = negative only, 0 = both.
    K_min, K_max : float
        Ionisation-integral bounds for interpolation.
    n : int
        Number of interpolated voltage points per polarity.

    Returns
    -------
    list of tuple
        Each entry is (voltage, K_interp, position) sorted by ascending
        voltage.  position is a tuple of floats matching the dimensionality
        in the report file.
    """
    report_data = parse_report_file(report_path,
                                    ['+/- Voltage', 'Max K(+)', 'Max K(-)',
                                     'Pos. max K(+)', 'Pos. max K(-)'])[1]

    def _interp_group(data):
        eff_K_min, eff_K_max = _clamp_K_range(data, K_min, K_max)
        sliced = _pick_data(data, eff_K_min, eff_K_max)
        if not sliced:
            return []
        K_vals = np.array([row[1] for row in sliced])
        v_vals = np.array([row[0] for row in sliced])
        pos_vals = [row[2] for row in sliced]
        ndim = len(pos_vals[0])

        K_targets = np.linspace(eff_K_min, eff_K_max, n)
        result = []
        for K_t in K_targets:
            v_t = float(np.interp(K_t, K_vals, v_vals))
            pos_t = tuple(
                float(np.interp(K_t, K_vals, [p[j] for p in pos_vals]))
                for j in range(ndim)
            )
            result.append((v_t, float(K_t), pos_t))
        return result

    table = []
    if polarity >= 0:
        table.extend(_interp_group([(v, Kp, pos_p)
                                    for v, Kp, _, pos_p, _ in report_data]))
    if polarity <= 0:
        table.extend(_interp_group([(v, Km, pos_n)
                                    for v, _, Km, _, pos_n in report_data]))
    return sorted(table, key=lambda t: t[0])


def parse_particle_config(parameters: dict) -> dict:
    """Parse and validate particle-seeding configuration from *parameters*.

    Reads the following keys from *parameters* (all sourced from
    ``job_script_options`` in the study definition):

    ``particle_mode`` : str, optional
        ``'single'`` (default) — place W single-particle seed electrons.
        ``'sphere'`` — seed electrons from a sphere distribution.
    ``num_particles`` : int, optional
        For ``'single'`` mode: the ``weight`` field on the single-particle
        entry (number of physical electrons one computational particle
        represents).  Default 1.
        For ``'sphere'`` mode: ``num particles`` in the sphere distribution.
        Default 1.
    ``sphere_radius`` : float
        Sphere radius in metres.  Required when ``particle_mode='sphere'``.
    ``sphere_center`` : list of float, optional
        Explicit sphere centre [x, y, z].  When omitted in sphere mode,
        the interpolated critical position from the database is used.

    Returns
    -------
    dict with keys: ``mode``, ``num_particles``, and (sphere only)
    ``radius`` and optionally ``center``.

    Raises
    ------
    RuntimeError
        If ``particle_mode='sphere'`` but ``sphere_radius`` is absent.
    ValueError
        If ``particle_mode`` is not ``'single'`` or ``'sphere'``.
    """
    mode = parameters.get('particle_mode', 'single')
    if mode not in ('single', 'sphere'):
        raise ValueError(
            f"'particle_mode' must be 'single' or 'sphere', got {mode!r}"
        )
    cfg = {'mode': mode, 'num_particles': int(parameters.get('num_particles', 1))}
    if mode == 'sphere':
        if 'sphere_radius' not in parameters:
            raise RuntimeError(
                "'sphere_radius' is required in job_script_options "
                "when particle_mode='sphere'"
            )
        cfg['radius'] = parameters['sphere_radius']
        if 'sphere_center' in parameters:
            cfg['center'] = parameters['sphere_center']
    return cfg


def create_voltage_directories(table: list, structure: dict,
                               input_file: str, particle_cfg: dict) -> None:
    """Create per-voltage run directories, copy files, and inject parameters.

    Writes ``index.json`` for the voltage array, creates ``voltage_<i>/``
    directories, symlinks the executable, copies required files, and injects
    the voltage and particle-position parameters into each run's input files.

    For each entry in *table* this function:

    1. Backs up any pre-existing ``voltage_<i>/`` directory (up to
       ``MAX_BACKUPS`` generations) to avoid silently overwriting prior runs.
    2. Creates the directory skeleton: ``voltage_<i>/`` and
       ``voltage_<i>/logs/``.
    3. Symlinks ``voltage_<i>/main`` → ``../main`` (the shared executable).
    4. Copies all ``required_files`` from *structure* into the new directory.
    5. Builds a parameter combination from the voltage value and the
       electron seed position, then calls ``handle_combination`` to write
       those values into the target ``.inputs`` and ``chemistry.json`` files.

    The seeding mode (single particle or sphere distribution) is controlled
    by *particle_cfg* as produced by :func:`parse_particle_config`.

    Parameters
    ----------
    table : list of tuple
        Voltage table as returned by :func:`extract_voltage_table` or
        :func:`interpolate_table`.  Each entry is ``(voltage, K, position)``.
    structure : dict
        Parsed ``structure.json`` for the current plasma study stage.
        Must contain ``'required_files'`` (list of file names to copy
        into each voltage directory).
    input_file : str
        Name of the ``.inputs`` file inside the voltage directory that
        receives the ``plasma.voltage`` field.
    particle_cfg : dict
        Particle-seeding configuration as returned by
        :func:`parse_particle_config`.
    """
    log = logging.getLogger(sys.argv[0])

    enum_table = list(enumerate(table))

    index_path = Path('index.json')
    # guard for reposting of the job
    backup_file(index_path, max_backups=MAX_BACKUPS)

    # write voltage index
    with open(index_path, 'w') as voltage_index_file:
        json.dump(dict(
            key=["voltage", "K", "particle_position"],
            prefix=VOLTAGE_DIR_PREFIX,
            index={i: item for i, item in enum_table}
        ), voltage_index_file, indent=4)

    if not os.path.islink('jobscript_symlink'):
        # recreate the generic job-script symlink, so that the actual .sh jobscript works:
        os.symlink('GenericArrayJobJobscript.py', 'jobscript_symlink')

    # grab original file names from structure
    required_files = [Path(f).name for f in structure['required_files']]

    for i, row in enum_table:
        voltage_dir = Path(f'{VOLTAGE_DIR_PREFIX}{i:d}')

        # don't delete old invocations
        backup_dir(voltage_dir, max_backups=MAX_BACKUPS)
        os.makedirs(voltage_dir, exist_ok=False)
        os.makedirs(voltage_dir / 'logs')

        # further symlink program executable
        link_path = voltage_dir / 'main'
        if not link_path.is_symlink():
            os.symlink(Path('../main'), link_path)

        copy_files(log, required_files, voltage_dir)

        # reuse the combination writing code from the configurator / ConfigUtil, by
        # building a fake combination and parameter space:

        # Build 3-D position from report-file coordinates (Y only for 2-D runs;
        # all components for 3-D runs).
        report_pos = row[2]
        if len(report_pos) == 2:  # 2-D run: pad X=0, Z=0
            seed_pos = [0.0, report_pos[1], 0.0]
        else:
            seed_pos = list(report_pos)

        mode = particle_cfg['mode']
        W = particle_cfg['num_particles']

        comb_dict = {'voltage': row[0]}
        pspace = {
            'voltage': {
                'target': voltage_dir / input_file,
                'uri': 'plasma.voltage',
            },
        }

        _EP = ['plasma species', '+["id"="e"]', 'initial particles']

        if mode == 'single':
            comb_dict['single_position'] = seed_pos
            comb_dict['single_weight'] = W
            pspace['single_position'] = {
                'target': voltage_dir / 'chemistry.json',
                'uri': _EP + ['+["single particle"]', 'single particle', 'position'],
            }
            pspace['single_weight'] = {
                'target': voltage_dir / 'chemistry.json',
                'uri': _EP + ['+["single particle"]', 'single particle', 'weight'],
            }
        else:  # sphere
            center = particle_cfg.get('center', seed_pos)
            comb_dict['sphere_center'] = center
            comb_dict['sphere_radius'] = particle_cfg['radius']
            comb_dict['sphere_num_particles'] = W
            pspace['sphere_center'] = {
                'target': voltage_dir / 'chemistry.json',
                'uri': _EP + ['+["sphere distribution"]', 'sphere distribution', 'center'],
            }
            pspace['sphere_radius'] = {
                'target': voltage_dir / 'chemistry.json',
                'uri': _EP + ['+["sphere distribution"]', 'sphere distribution', 'radius'],
            }
            pspace['sphere_num_particles'] = {
                'target': voltage_dir / 'chemistry.json',
                'uri': _EP + ['+["sphere distribution"]', 'sphere distribution',
                               'num particles'],
            }

        handle_combination(pspace, comb_dict)


def submit_voltage_array(num_voltages: int, identifier: str, slurm: dict) -> int:
    """Submit a SLURM voltage array job and return the job ID.

    Calls ``sbatch`` with ``--array=0-<num_voltages-1>`` and resource
    arguments derived from the ``plasma`` stage of *slurm*.  Parses the
    "Submitted batch job <id>" line from sbatch's stdout to capture the
    job ID, then writes it to ``logs/array_job_id`` (backing up any
    previous file first).

    Parameters
    ----------
    num_voltages : int
        Total number of voltage directories created by
        :func:`create_voltage_directories`.  Determines the SLURM array
        size: tasks are indexed ``0`` through ``num_voltages - 1``.
    identifier : str
        Human-readable name for the study (from ``structure['identifier']``).
        Used to label the SLURM job as ``<identifier>_voltage``.
    slurm : dict
        SLURM resource configuration as returned by ``load_slurm_config``.
        The ``'plasma'`` sub-dict is passed to ``build_sbatch_resource_args``
        to produce flags such as ``--nodes``, ``--ntasks``, etc.

    Returns
    -------
    int
        The SLURM job ID of the submitted array job, or ``-1`` if the job
        ID could not be parsed from sbatch's output (e.g. dry-run or
        submission failure).
    """
    log = logging.getLogger(sys.argv[0])

    sbatch_args = (
        [f'--array=0-{num_voltages - 1}',
         f'--job-name="{identifier}_voltage"']
        + build_sbatch_resource_args(slurm, stage='plasma')
    )

    cmdstr = 'sbatch ' + ' '.join(sbatch_args) + ' GenericArrayJob.sh'
    log.debug(f'cmd string: \'{cmdstr}\'')
    p = Popen(cmdstr, shell=True, stdout=PIPE, encoding='utf-8')

    job_id = -1
    while True:  # wait until sbatch is complete
        # try to capture the job id
        line = p.stdout.readline()
        if line:
            m = re.match('^Submitted batch job (?P<job_id>[0-9]+)', line)
            if m:
                job_id_str = m.groupdict()['job_id']
                job_id = int(job_id_str)

                array_job_id_path = Path('logs') / 'array_job_id'
                os.makedirs('logs', exist_ok=True)
                backup_file(array_job_id_path, max_backups=MAX_BACKUPS)

                with open(array_job_id_path, 'w') as job_id_file:
                    job_id_file.write(job_id_str)
                log.info(f"Submitted array job (for '{identifier}_voltage' "
                         f"combination set). [slurm job id = {job_id}]")

        if p.poll() is not None:
            break

    return job_id


def main():
    """Entry point: run the four-step plasma setup pipeline."""

    # --- 1. Read study structure and navigate to this run's directory --------
    with open('structure.json') as f:
        structure = json.load(f)
    prefix = structure.get('output_dir_prefix', DEFAULT_OUTPUT_DIR_PREFIX)
    log, task_id, run_dir, input_file = setup_jobscript_logging_and_dir(prefix=prefix)

    # --- 2. Load inception database metadata and this run's parameters -------
    with open('../inception_stepper/structure.json') as f:
        db_structure = json.load(f)

    # derive all subsequent database paths from the identifier stored in structure.json
    # so that renaming the database study doesn't silently break this script.
    db_path = Path('..') / db_structure['identifier']

    with open(db_path / 'index.json') as f:
        db_index = json.load(f)

    with open('parameters.json') as f:
        parameters = json.load(f)

    # --- 3. Resolve K range and polarity from parameters / .inputs -----------
    polarity = 0  # 1, 0, or -1
    if 'plasma_polarity' not in parameters:
        log.warning(
            "'plasma_polarity' was not found in parameters.json, "
            "running for both polarities"
        )
    else:
        if parameters['plasma_polarity'] == 'positive':
            polarity = 1
        elif parameters['plasma_polarity'] == 'negative':
            polarity = -1
        log.info(f'Running with polarity {polarity} (0:both, 1:positive, -1:negative)')

    K_min = 0
    if 'K_min' not in parameters:
        log.warning("'K_min' not found in parameters, using K_min=0")
    else:
        K_min = parameters['K_min']

    if 'K_max' not in parameters:
        log.warning("'K_max' not found in parameters, trying to read from .inputs file")
        K_max = read_input_float_field(input_file, 'DischargeInceptionStepper.limit_max_K')
        if K_max is None:
            raise RuntimeError(
                f"'{input_file}' does not contain "
                "'DischargeInceptionStepper.limit_max_K' field"
            )
        log.info(f"Using K_max={K_max}")
    else:
        K_max = parameters['K_max']

    # --- 3b. Resolve particle-seeding configuration --------------------------
    particle_cfg = parse_particle_config(parameters)
    log.info(f"Particle seeding mode: {particle_cfg}")

    # --- 3c. Resolve N_voltages (optional; None = use all report rows) --------
    N_voltages = parameters.get('N_voltages', None)
    if N_voltages is not None:
        N_voltages = int(N_voltages)
        log.info(f"Interpolating {N_voltages} voltage points per polarity")

    # --- 4. Run the four-step plasma setup pipeline --------------------------
    db_run_path = find_database_run(parameters, db_structure, db_index)
    if N_voltages is not None:
        table = interpolate_table(
            db_run_path / 'report.txt', polarity, K_min, K_max, N_voltages
        )
    else:
        table = extract_voltage_table(
            db_run_path / 'report.txt', polarity, K_min, K_max
        )
    create_voltage_directories(table, structure, input_file, particle_cfg)

    slurm = load_slurm_config()
    submit_voltage_array(len(table), structure['identifier'], slurm)


if __name__ == '__main__':
    main()
