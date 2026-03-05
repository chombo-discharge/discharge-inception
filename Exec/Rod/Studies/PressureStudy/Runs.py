#!/usr/bin/env python
"""
Author André Kapelrud
Copyright © 2025 SINTEF Energi AS
"""

import json
import numpy as np

rod_dir = '../../'

# ---------------------------------------------------------------------------
# URI conventions used in parameter_space entries
# ---------------------------------------------------------------------------
# .inputs files  — "uri" is a dot-separated string matching the field name at
#                  the start of a line, e.g. "Rod.radius" or
#                  "DischargeInception.pressure".
#
# .json files    — "uri" is a list of nested dictionary keys forming a path
#                  into the JSON tree:
#                    ["gas", "law", "ideal_gas", "pressure"]
#                  List elements within the JSON can be matched by a
#                  requirement expression:
#                    '+["id"="e"]'  — required match on field "id" == "e"
#                    '*["id"="e"]'  — optional match (creates element if absent)
#                    '+["reaction"=<chem_react>"..."]'  — chemical reaction match
#                  An inner Python list at any level produces multiple parallel
#                  paths (one per entry), e.g. ["center", "radius"] yields two
#                  simultaneous writes.
#
# "database" field — marks a parameter as shared with a database study.
#                  The configurator ensures only combinations that exist in the
#                  named database are used, so the plasma runs stay in sync
#                  with the corresponding inception-voltage database entry.
# ---------------------------------------------------------------------------

inception_stepper = {
    'identifier': 'inception_stepper',
    'job_script': '../DischargeInceptionJobscript.py',
    'program': rod_dir + 'main{DIMENSIONALITY}d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex',
    'output_directory': 'PDIV_DB',
    'job_script_dependencies': [
        '../../../../Util/GenericArrayJob.sh',
        '../ParseReport.py',
    ],
    'required_files': [
        rod_dir + 'master.inputs',
        rod_dir + 'chemistry.json',
        rod_dir + 'electron_transport_data.dat',
        rod_dir + 'ion_transport_data.dat',            
        rod_dir + 'detachment_rate.dat',
    ],
    'parameter_space': {
        "pressure": {
            "target": "chemistry.json",
            "uri": ["gas", "law", "ideal_gas", "pressure"]
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
    'program': rod_dir + 'main{DIMENSIONALITY}d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex',
    'job_script': '../PlasmaJobscript.py',
    'job_script_dependencies': [
        '../../../../Util/GenericArrayJob.sh',
        '../ParseReport.py',
    ],
    'required_files': [
        rod_dir + 'master.inputs',
        rod_dir + 'chemistry.json',
        rod_dir + 'detachment_rate.dat',
        rod_dir + 'electron_transport_data.dat',
        rod_dir + 'ion_transport_data.dat',                        
        '../../../../Util/GenericArrayJob.sh',  # used at voltage step level
        '../../../../GenericArrayJobJobscript.py'  # used at voltage step level
    ],
    'output_directory': 'study0',
    'output_dir_prefix': 'run_',
    'parameter_space': {
        "app_mode": {
            "target": "master.inputs",
            "uri": "app.mode",
            "values": ["plasma"]
        },
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

top_object = dict(databases=[inception_stepper], studies=[plasma_study_1])

if __name__ == '__main__':
    with open('runs.json', 'w') as f:
        json.dump(top_object, f, indent=4)
