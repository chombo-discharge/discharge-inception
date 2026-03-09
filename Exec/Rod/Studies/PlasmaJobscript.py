#!/usr/bin/env python
"""
Author André Kapelrud
Copyright © 2025 SINTEF Energi AS
"""

import os
import sys
import json
import re
import logging

from subprocess import Popen, PIPE

from pathlib import Path

# local imports
sys.path.append(os.getcwd())  # needed for local imports from slurm scripts
from ParseReport import parse_report_file  # noqa: E402
from discharge_inception.config_util import (  # noqa: E402
    copy_files, backup_file, backup_dir,
    read_input_float_field,
    setup_jobscript_logging_and_dir, load_slurm_config, build_sbatch_resource_args,
    handle_combination,
    DEFAULT_OUTPUT_DIR_PREFIX
)


def find_database_run(parameters: dict, db_structure: dict, db_index: dict) -> Path:
    """Locate the database run directory matching *parameters*.

    Searches *db_index* for the parameter combination defined by
    *db_structure['space_order']* and returns the path to the matched run
    directory inside the database study.
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
        raise RuntimeError(f'Unable to find db parameter_set: {db_param_order} = '
                           f'{db_search_index}')
    log.info(f"Found database parameters {db_param_order} = {db_search_index} "
             f"at index: {index}")

    db_run_path = db_path
    if 'prefix' in db_index:
        db_run_path /= db_index['prefix'] + str(index)
    else:
        db_run_path /= DEFAULT_OUTPUT_DIR_PREFIX + str(index)
    return db_run_path


def extract_voltage_table(report_path: Path, polarity: int,
                          K_min: float, K_max: float) -> list:
    """Read *report_path* and return a voltage table filtered to [K_min, K_max].

    *polarity*: 1 = positive only, -1 = negative only, 0 = both.

    Returns a list of ``(voltage, K, position)`` tuples sorted by voltage.
    """
    report_data = parse_report_file(report_path,
                                    ['+/- Voltage',
                                     'Max K(+)',
                                     'Max K(-)',
                                     'Pos. max K(+)',
                                     'Pos. max K(-)'])
    report_data = report_data[1]  # discard column names

    def pick_data(data):
        imin, iMax = (0, 0)
        for i, (_, K, _) in enumerate(data):
            if K <= K_min:
                imin = i
            if K <= K_max:
                iMax = i
        if data[iMax][1] != K_max and iMax + 1 < len(data):
            iMax += 1  # round to nearest K higher than K_max
        return data[imin:iMax + 1]

    table = []
    if polarity >= 0:
        table.extend(pick_data([(v, Kp, pos_p)
                                for v, Kp, _, pos_p, _ in report_data]))
    if polarity <= 0:
        table.extend(pick_data([(v, Km, pos_n)
                                for v, _, Km, _, pos_n in report_data]))

    return sorted(table, key=lambda t: t[0])


def create_voltage_directories(table: list, structure: dict,
                               input_file: str, parameters: dict) -> None:
    """Create per-voltage run directories, copy files, and inject parameters.

    Writes ``index.json`` for the voltage array, creates ``voltage_<i>/``
    directories, symlinks the executable, copies required files, and injects
    the voltage and particle-position parameters into each run's input files.
    """
    log = logging.getLogger(sys.argv[0])

    if 'geometry_radius' not in parameters:
        raise RuntimeError("'geometry_radius' is missing from 'parameters.json'")

    output_prefix = "voltage_"
    MAX_BACKUPS = 10

    enum_table = list(enumerate(table))

    index_path = Path('index.json')
    # guard for reposting of the job
    backup_file(index_path, max_backups=MAX_BACKUPS)

    # write voltage index
    with open(index_path, 'w') as voltage_index_file:
        json.dump(dict(
            key=["voltage", "K", "particle_position"],
            prefix=output_prefix,
            index={i: item for i, item in enum_table}
        ), voltage_index_file, indent=4)

    if not os.path.islink('jobscript_symlink'):
        # recreate the generic job-script symlink, so that the actual .sh jobscript works:
        os.symlink('GenericArrayJobJobscript.py', 'jobscript_symlink')

    # grab original file names from structure
    required_files = [Path(f).name for f in structure['required_files']]

    for i, row in enum_table:
        voltage_dir = Path(f'{output_prefix}{i:d}')

        # don't delete old invocations
        backup_dir(voltage_dir, max_backups=MAX_BACKUPS)
        os.makedirs(voltage_dir, exist_ok=False)

        # further symlink program executable
        link_path = voltage_dir / 'main'
        if not link_path.is_symlink():
            os.symlink(Path('../main'), link_path)

        copy_files(log, required_files, voltage_dir)

        # reuse the combination writing code from the configurator / ConfigUtil, by
        # building a fake combination and parameter space:
        particle_pos = [0.0, row[2][1], 0.0]  # strip X and Z coords
        comb_dict = dict(
            voltage=row[0],
            sphere_dist_props=[
                particle_pos,                          # center position
                0.5 * parameters['geometry_radius']    # half the tip's radius
            ],
            single_particle_position=particle_pos      # center position
        )
        distribution_type = 'sphere distribution'
        pspace = {
            "voltage": {
                "target": voltage_dir / input_file,
                "uri": "plasma.voltage",
            },
            "sphere_dist_props": {
                "target": voltage_dir / 'chemistry.json',
                'uri': [
                    'plasma species',
                    '+["id"="e"]',  # find electrons in list
                    'initial particles',
                    f'+["{distribution_type}"]',
                    distribution_type,  # TODO: fix duplicity here
                    ['center', 'radius']  # NB! two parameters
                ]
            },
            "single_particle_position": {
                "target": voltage_dir / 'chemistry.json',
                'uri': [
                    'plasma species',
                    '+["id"="e"]',  # find electrons in list
                    'initial particles',
                    f'+["single particle"]',
                    "single particle",  # TODO: fix duplicity here
                    'position'  # NB! two parameters
                ]
            }
        }
        handle_combination(pspace, comb_dict)


def submit_voltage_array(num_voltages: int, identifier: str, slurm: dict) -> int:
    """Submit a SLURM voltage array job and return the job ID (-1 on failure)."""
    log = logging.getLogger(sys.argv[0])
    MAX_BACKUPS = 10

    sbatch_args = ([f'--array=0-{num_voltages - 1}',
                    f'--job-name="{identifier}_voltage"']
                   + build_sbatch_resource_args(slurm, stage='plasma'))

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

                array_job_id_path = Path('array_job_id')
                backup_file(array_job_id_path, max_backups=MAX_BACKUPS)

                with open(array_job_id_path, 'w') as job_id_file:
                    job_id_file.write(job_id_str)
                log.info(f"Submitted array job (for '{identifier}_voltage' "
                         f"combination set). [slurm job id = {job_id}]")

        if p.poll() is not None:
            break

    return job_id


if __name__ == '__main__':

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
        log.warning("'plasma_polarity' was not found in parameters.json, running for both polarities")
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
            raise RuntimeError(f"'{input_file}' does not contain 'DischargeInceptionStepper.limit_max_K' field")
        log.info(f"Using K_max={K_max}")
    else:
        K_max = parameters['K_max']

    # --- 4. Run the four-step plasma setup pipeline --------------------------
    db_run_path = find_database_run(parameters, db_structure, db_index)
    table = extract_voltage_table(db_run_path / 'report.txt', polarity, K_min, K_max)
    create_voltage_directories(table, structure, input_file, parameters)

    slurm = load_slurm_config()
    submit_voltage_array(len(table), structure['identifier'], slurm)
