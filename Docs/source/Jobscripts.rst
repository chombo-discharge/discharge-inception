Writing Jobscripts
******************

*Configurator.py* schedules slurm jobs through `sbatch` expecting the bash script ``GenericArrayJob.sh``. This should edited to suit the system configuration, and added as a ``job_script_dependency`` to the studies:

.. code-block:: bash
    :caption: GenericArrayJob.sh

    #!/bin/bash
    # Author André Kapelrud
    # Copyright © 2025 SINTEF Energi AS

    #SBATCH --account=<cluster account>
    #SBATCH --output=R-%x.%A-%a.out
    #SBATCH --error=R-%x.%A-%a.err

    # typical options needed for running on cluster
    # remove leading '#' to use
    ##SBATCH --nodes=4 --ntasks-per-node=128
    ##SBATCH --partition=normal
    ##SBATCH --time=0-00:10:00

    # Local slurm testing,
    # add extra '#' to comment out
    #SBATCH --ntasks=5 --cpus-per-task=1
    #SBATCH --time=0-00:25:00

    set -o errexit
    set -o nounset

    # example sigma2, module loading code
    if command -v module > /dev/null 2>&1
    then
        module restore system
        module load foss/2023a
        module load HDF5/1.14.0-gompi-2023a  # needed by chombo-discharge
        module load Python/3.11.3-GCCcore-12.3.0  # needed by jobscripts
    fi

    python ./jobscript_symlink  # run python through job-script
    exit $?

The script configures the resource requirements, sets error conditions and loads sigma2 system modules (c.f. `Lmod <https://lmod.readthedocs.io/en/latest/>`_).

.. note::
    It is possible to submit python scripts to sbatch directly if the python script has the correct shebang (``#! /usr/bin/env python``), the ``#SBATCH``-specific comment directives also works from a python script. Routing through an intermediate bash-script made it somewhat easier to configure module-loading on sigma2.

    A simple way of having two different versions of this bash script is to just make ``GenericArrayJob.sh`` a symlink to a correct system-tailored version, or even copy it in similar to the way chombo-discharge deals with the library makefiles.

Template jobscripts
-------------------

At this stage the work is not done, because alot of of the heavy lifting has to be done by your jobscripts. Regard the *Configurator.py* script as setting up the infrastructure. It is now up to you to start meaningful simulations. This section gives some examples on how to accomplish this.

Generic python jobscript example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A vanilla, quite simple python-based jobscript might look like this:

.. code-block:: python
    :caption: GenericArrayJobJobscript.py
    :linenos:

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
    import subprocess

    # local imports
    sys.path.append(os.getcwd())  # needed for local imports from slurm scripts
    from ConfigUtil import get_slurm_array_task_id

    if __name__ == '__main__':

        log = logging.getLogger(sys.argv[0])
        formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s :: %(message)s')
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        log.addHandler(sh)
        log.setLevel(logging.INFO)

        task_id = get_slurm_array_task_id()
        log.info(f'found task id: {task_id}')

        with open('index.json') as index_file:
            index_dict = json.load(index_file)
        job_prefix = index_dict['prefix']

        dpattern = f'^({job_prefix}[0]*{task_id:d})$'  # account for possible leading zeros
        dname = [f for f in os.listdir() if (os.path.isdir(f) and re.match(dpattern, f))][0]
        log.info(f'chdir: {dname}')
        os.chdir(dname)

        input_file = None
        for f in os.listdir():
            if os.path.isfile(f) and f.endswith('.inputs'):
                input_file = f
                break

        if not input_file:
            raise ValueError('missing *.inputs file in run directory')

        cmd = f"mpirun main {input_file} Random.seed={task_id:d}"
        log.info(f"cmdstr: '{cmd}'")
        p = subprocess.Popen(cmd, shell=True, executable="/bin/bash")

        while True:
            res = p.poll()
            if res is not None:
                break

.. _ex_database:

Database-dependent jobscript examples
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This section contains two example jobscripts.

* One for a database where the simulation (chombo discharge) is rerun under some condition.
* One for a study that needs to extract some dataset from a database and set up sub directories per parameter space run.

The jobscripts depend on two python scripts: ``ParseReport.py`` and ``ConfigUtil.py`` that needs to be included as ``job_script_dependencies`` in the *run_definition*.

.. warning::
   These are not *ready-to-run*, but illustrates a concept. For specific examples see the actual source code listings of this project.

.. code-block:: python
    :caption: Example database (python) jobscript
    :linenos:

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
    import subprocess
    import time
    import math
    import shutil

    # local imports
    sys.path.append(os.getcwd())  # needed for local imports from slurm scripts
    from ParseReport import parse_report_file  # noqa: E402
    from ConfigUtil import (  # noqa: E402
                             get_slurm_array_task_id,
                             handle_combination,
                             read_input_float_field
                             )

    if __name__ == '__main__':

        log = logging.getLogger(sys.argv[0])
        formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s :: %(message)s')
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        log.addHandler(sh)
        log.setLevel(logging.INFO)

        task_id = get_slurm_array_task_id()
        log.info(f'found task id: {task_id}')

        with open('index.json') as index_file:
            index_dict = json.load(index_file)

        # extract the directory prefix of run directories (default is 'run_',
        # but make no assumptions.
        job_prefix = index_dict['prefix']

        # find the directory corresponding to this array task id
        dpattern = f'^({job_prefix}[0]*{task_id:d})$'  # account for possible leading zeros
        dname = [f for f in os.listdir() if (os.path.isdir(f) and re.match(dpattern, f))][0]

        # step into directory
        log.info(f'chdir: {dname}')
        os.chdir(dname)

        # find chombo-discharge *.inputs file
        input_file = None
        for f in os.listdir():
            if os.path.isfile(f) and f.endswith('.inputs'):
                input_file = f
                break

        if not input_file:
            raise ValueError('missing *.inputs file in run directory')

        # We are now ready to run mpi on our chombo-discharge executable
        # through the main symlink. Any ParmParse key can be overridden on the
        # command line; overrides take precedence over the *.inputs file.
        # A common use-case is to force a specific mode when a single binary
        # supports multiple execution paths, e.g.:
        #   App.mode=inception
        # The Rod case uses exactly this pattern via DischargeInceptionJobscript.py.

        cmd = f"mpirun main {input_file} Random.seed={task_id:d} App.mode=inception"
        log.info(f"cmdstr: '{cmd}'")
        p = subprocess.Popen(cmd, shell=True, executable="/bin/bash")
        while p.poll() is None:
            time.sleep(0.5)
        # propagate nonzero exit code to calling jobscript
        if p.returncode != 0:
            sys.exit(p.returncode)

        # First simulation step done.
        # We are free to do whatever is necessary here. One likely scenario is
        # to parse some results, alter some parameters and rerun the invocation
        # above.

        result_fn = "result-file-name"

        def parse_some_result_file(result_filename):
            """ meaningless stub """
            return None

        data = parse_some_result_file(result_fn)
        log.info("Some description of this step...")

        def calculate_interresting_value(data):
            """ meaningless stub """
            return None  # stub
        iv = calculate_interresting_value(data)

        # If we need to read something from a *.inputs file we can of course do that:
        orig_iv = read_input_float_field(input_file, 'SomeNamespace.interrestingvariable')
        if orig_iv is None:
            raise RuntimeError(f"'{input_file}' does not contain 'SomeNamespace.interrestingvariable' field")

        # some decision point
        if orig_iv != iv:
            log.info(f'renaming: {result_fn} -> {result_fn}.0')
            shutil.move(result_fn, f'{result_fn}.0')

            # You might want to back up other results here.

            # update input file, this mirrors the run_definition file syntax
            handle_combination({
                "interresting_parameter": {  # parameter name
                    "target": input_file,  # file target
                    "uri": "SomeNamespace.interrestingvariable"
                    }
                }, dict(interresting_parameter=iv))

            # rerun the simulation!
            log.info('Rerunning calculations')
            p = subprocess.Popen(cmd, shell=True, executable="/bin/bash")
            while p.poll() is None:
                time.sleep(0.5)
            sys.exit(p.returncode)

Study (database-dependent) jobscript example
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is a rather long example where we traverse the database directories to find relevant data and then set up detailed simulations to use that data. This can be a single simulation, or a complex-subhierarchy of simulations. The last part is only pseudo-code, so the reader is advised to check out some of the checked in example studies in the main repository.

.. code-block:: python
    :linenos:

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
    import itertools
    import shutil

    from subprocess import Popen, PIPE

    from pathlib import Path

    # local imports
    sys.path.append(os.getcwd())  # needed for local imports from slurm scripts
    from ParseReport import parse_report_file  # noqa: E402
    from ConfigUtil import (  # noqa: E402
                             copy_files, backup_file,
                             get_slurm_array_task_id,
                             handle_combination,
                             DEFAULT_OUTPUT_DIR_PREFIX
                             )


    if __name__ == '__main__':

        log = logging.getLogger(sys.argv[0])
        formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s :: %(message)s')
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        log.addHandler(sh)
        log.setLevel(logging.INFO)

        task_id = get_slurm_array_task_id()
        log.info(f'found task id: {task_id}')

        with open('structure.json') as structure_file:
            structure = json.load(structure_file)

        # extract the directory prefix of run directories (default is 'run_',
        # but make no assumptions.
        job_prefix = 'run_'
        if 'output_dir_prefix' in structure:
            job_prefix = structure['output_dir_prefix']

        dpattern = f'^({job_prefix}[0]*{task_id:d})$'  # account for possible leading zeros
        dname = [f for f in os.listdir() if (os.path.isdir(f) and re.match(dpattern, f))][0]
        log.info(f'chdir: {dname}')
        os.chdir(dname)

        # locate .inputs file (should be in the required_files list, and copied to the
        # current directory):
        input_file = None
        for f in os.listdir():
            if os.path.isfile(f) and f.endswith('.inputs'):
                input_file = f
                break
        if not input_file:
            raise ValueError('missing *.inputs file in run directory')
        log.info(f"input file: {input_file}")

        # get access to structure of dependent database through symlink
        with open('../inception_stepper/structure.json') as db_structure_file:
            db_structure = json.load(db_structure_file)

        # determine order of parameters in database (might differ from the order in this study)
        if 'space_order' not in db_structure:
            raise ValueError("missing field 'space_order' in database 'inception_stepper'")
        db_param_order = db_structure['space_order']

        # load this run's parameters (radius, pressure, etc.)
        with open('parameters.json') as param_file:
            parameters = json.load(param_file)

        # we can add run-time checks:
        if 'geometry_radius' not in parameters:
            raise RuntimeError("'geometry_radius' is missing from 'parameters.json'")

        # put the parameters in the same order as the database index needs them
        db_search_index = []
        for db_param in db_param_order:
            db_search_index.append(parameters[db_param])

        # Now, we need to locate the corresponding data in the 'database':
        with open('../inception_stepper/index.json') as db_index_file:
            db_index = json.load(db_index_file)

        # linear search through index, which is a dictionary.
        index = -1
        for db_i, params in db_index['index'].items():
            if params == db_search_index:
                index = int(db_i)
                break
        if index < 0:
            raise RuntimeError(f'Unable to find db parameter_set: {db_param_order} = ' +
                               f'{db_search_index}')
        log.info(f"Found database parameters {db_param_order} = {db_search_index} "
                 f"at index: {index}")

        # we have the index, now locate the correct subdirectory:
        db_run_path = Path('../inception_stepper')
        if 'prefix' in db_index:
            db_run_path /= db_index['prefix'] + str(index)
        else:
            db_run_path /= DEFAULT_OUTPUT_DIR_PREFIX + str(index)


        def parse_and_get_interresting_data(filename):
            """ stub """
            return None

        data = parse_and_get_interresting_data(db_run_path / '<some-database-result-file>')

        # Maybe we need to do some selective picking of data based on a dummy-parameter?
        # here we can for easily check a 'dummy' parameter
        if 'dummy-parameter' in parameters:
            data = some_filter_action(parameters['dummy-parameter'])  # do something meaningful

        #----------------------------------------------------------------------------
        # At this point we can do whatever we like with the data.

        # Maybe the database study gave an estimate of a parameter and we just
        # want to write that parameter to an *.inputs file or *.json file and run
        # a detailed simulation.
        # If so, use the handle_combination() function to write the data and
        # launch the job using mpirun. See database example.

        # If on the other hand, the database produces e.g. a voltage list and some
        # other associated input data, then we need to create a sub-file
        # hierarchy in the run-directory and submit those simulation jobs to slurm.

        # We utilize helper functions from the configurator to alleviate the burden.

        # We will use the GenericArrayJobJobscript.py script at the leaf directory level.
        #----------------------------------------------------------------------------

        # let us enumerate the interresting data, assuming some known structure:
        #   data[i] corresponds to the (new) parameters ["voltage", "some-other-parameter"]
        enum_table = list(enumerate(data))

        output_prefix = "voltage_"

        # first we have to create an index for the sub-directories:

        # guard for reposting of the job
        MAX_BACKUPS = 10
        index_path = Path('index.json')
        backup_file(index_path, max_backups=MAX_BACKUPS)

        # write voltage index
        with open(index_path, 'w') as voltage_index_file:
            json.dump(dict(
                key=["voltage", "some-other-parameter"],
                prefix=output_prefix,
                index={i: item for i, item in enum_table}
                ),
                      voltage_index_file, indent=4)

        # recreate the generic job-script symlink, so that the actual .sh jobscript work:
        if not os.path.islink('jobscript_symlink'):
            os.symlink('GenericArrayJobJobscript.py', 'jobscript_symlink')

        # create run directories, copy files, set voltage and parameters, etc.
        for i, row in enum_table:
            voltage_dir = Path(f'{output_prefix}{i:d}')
            # don't delete old invocations
            backup_dir(voltage_dir, max_backups=MAX_BACKUPS)
            os.makedirs(voltage_dir, exist_ok=False)

            # further symlink program executable to this directory's program-symlink
            link_path = voltage_dir / 'program'
            if not link_path.is_symlink():
                os.symlink(Path('../program'), link_path)

            # grab original file names from structure
            required_files = [Path(f).name for f in structure['required_files']]
            copy_files(log, required_files, voltage_dir)

            # reuse the combination writing code from the configurator / ConfigUtil, by
            # building a fake combination and parameter space:
            # populate values
            comb_dict = dict(
                    voltage=row[0],
                    some_other_parameter=row[1]
                    )
            pspace = {
                    "voltage": {
                        "target": voltage_dir/input_file,
                        "uri": "SomeNamespace.potential",
                        },
                    "some_other_parameter": {
                        "target": voltage_dir/'chemistry.json',
                        'uri': [ ... ]  # some very complex JSON traversing uri
                        },
                    }
            handle_combination(pspace, comb_dict)

        # all voltage_* directories are now ready, and we can post a (new!) slurm array job:
        cmdstr = f'sbatch --array=0-{len(enum_table)-1} ' + \
                f'--job-name="{structure["identifier"]}_voltage" ' + \
                'GenericArrayJob.sh'
        log.debug(f'cmd string: \'{cmdstr}\'')
        p = Popen(cmdstr, shell=True, stdout=PIPE, encoding='utf-8')

        job_id = -1
        while True:  # wait until sbatch is complete
            # try to capture the job id
            line = p.stdout.readline()
            if line:
                m = re.match('^Submitted batch job (?P<job_id>[0-9]+)', line)
                if m:
                    job_id = m.groupdict()['job_id']

                    array_job_id_path = Path('array_job_id')
                    # backups for previously posted runs:
                    backup_file(array_job_id_path, max_backups=MAX_BACKUPS)

                    # write array index file
                    with open(array_job_id_path, 'w') as job_id_file:
                        job_id_file.write(job_id)
                    log.info(f"Submitted array job (for '{structure['identifier']}" +
                             f"_voltage' combination set). [slurm job id = {job_id}]")

            if p.poll() is not None:
                break
