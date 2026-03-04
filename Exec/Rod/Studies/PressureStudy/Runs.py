#!/usr/bin/env python
"""
Author André Kapelrud
Copyright © 2025 SINTEF Energi AS
"""

import json
import numpy as np

stepper_dir = '../../DischargeInception/'
plasma_dir = '../../ItoKMC/'

inception_stepper = {
        'identifier': 'inception_stepper',
        'job_script': '../DischargeInceptionJobscript.py',
        'program': stepper_dir + 'main{DIMENSIONALITY}d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex',
        'output_directory': 'PDIV_DB',
        'job_script_dependencies': [
            '../../../../Util/GenericArrayJob.sh',
            '../ParseReport.py',
            '../../../../ConfigUtil.py',
            '../../../../JsonRequirement.py'
            ],
        'required_files': [
            'master.inputs',
            stepper_dir + 'transport_data.txt'
            ],
        'parameter_space': {
            "pressure": {
                "target": "master.inputs",
                "uri": "DischargeInception.pressure"
                },
            "geometry_radius": {
                "target": "master.inputs",
                "uri": "Rod.radius",
                },
            'K_max': {
                "target": "master.inputs",
                "uri": "DischargeInceptionStepper.limit_max_K"
                }
            }
        }

plasma_study_1 = {
        'identifier': 'photoion',
        'program': plasma_dir+'main{DIMENSIONALITY}d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex',
        'job_script': '../PlasmaJobscript.py',
        'job_script_dependencies': [
            '../../../../Util/GenericArrayJob.sh',
            '../ParseReport.py',
            '../../../../ConfigUtil.py',
            '../../../../JsonRequirement.py',
            ],
        'required_files': [
            'master.inputs',
            plasma_dir+'Analyze.py',
            plasma_dir+'chemistry.json',
            plasma_dir+'detachment_rate.dat',
            plasma_dir+'electron_transport_data.dat',
            '../../../../Util/GenericArrayJob.sh',  # used at voltage step level
            '../../../../GenericArrayJobJobscript.py'  # used at voltage step level
            ],
        'output_directory': 'study0',
        'output_dir_prefix': 'run_',
        'parameter_space': {
            "geometry_radius": {
                "database": "inception_stepper",  # database dependency
                "target": "master.inputs",
                "uri": "Rod.radius",
                "values": [1e-3] #, 2e-3, 3e-3]
                },
            "pressure": {
                "database": "inception_stepper",  # database dependency
                "target": "chemistry.json",
                "uri": ["gas", "law", "ideal_gas", "pressure"],
                "values": [1e5]  # np.arange(1e5, 11e5, 10e5).tolist()
                },
            "K_min": { "values": [6] }, # needed by jobscript, written to parameters.json for each run
            "K_max": {
                "database": "inception_stepper",
                "values": [12.0]
                },
            "plasma_polarity": { "values": ["positive"] },  # used by jobscript
            "photoionization": {
                "target": "chemistry.json",
                "uri": [
                    "photoionization",
                    [
                        '+["reaction"=<chem_react>"Y + (O2) -> e + O2+"]',  # non-optional match
                        '*["reaction"=<chem_react>"Y + (O2) -> (null)"]'  # optional match (create-if-not-exists)
                        ],
                    "efficiency"
                    ],
                "values": [[1.0, 0.0]]  #[[float(v), float(1.0-v)] for v in np.arange(0.0, 1.0, 1.0)]
                },
            }
        }

top_object = dict(
        databases=[inception_stepper],
        studies=[plasma_study_1]
        )

if __name__ == '__main__':
    with open('runs.json', 'w') as f:
        json.dump(top_object, f, indent=4)
