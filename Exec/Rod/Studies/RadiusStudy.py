#!/usr/bin/env python
"""
Author André Kapelrud, Robert Marskar
Copyright © 2026 SINTEF Energi AS
"""

import json
import os
import numpy as np

_di_home = os.environ['DISCHARGE_INCEPTION_HOME']

rod_dir = '../'

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

## PDIV database specifications.
inception_stepper = {
    'identifier': 'inception_stepper',
    'job_script': '../../../Scripts/DischargeInceptionJobscript.py',
    'program': rod_dir + 'main{DIMENSIONALITY}d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex',
    'output_directory': 'pdiv_database',
    'job_script_dependencies': [
        f'{_di_home}/Util/GenericArrayJob.sh',
        '../../../Scripts/ExtractElectronPositions.py',
    ],
    'required_files': [
        rod_dir + 'master.inputs',
        rod_dir + 'chemistry.json',
        rod_dir + 'electron_transport_data.dat',
        rod_dir + 'ion_transport_data.dat',            
        rod_dir + 'detachment_rate.dat',
    ],
    'input_overrides': {
        'mode': {
            'target': 'master.inputs',
            'uri': 'app.mode',
            'value': "inception"
        },
        "limit_max_K": {
            "target": "master.inputs",
            "uri": "DischargeInceptionStepper.limit_max_K",
            "value": 12
        },
        "max_steps": {
            "target": "master.inputs",
            "uri": "Driver.max_steps",
            "value": 0
        },
        "plot_interval": {
            "target": "master.inputs",
            "uri": "Driver.plot_interval",
            "value": -1
        },
    }
}

## Study specifications
plasma_study = {
    'identifier': 'radius',
    'enable_study': True,
    'program': rod_dir + 'main{DIMENSIONALITY}d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex',
    'job_script': '../../../Scripts/PlasmaJobscript.py',
    'job_script_dependencies': [
        f'{_di_home}/Util/GenericArrayJob.sh',
        '../../../Scripts/ExtractElectronPositions.py',
    ],
    'required_files': [
        rod_dir + 'master.inputs',
        rod_dir + 'chemistry.json',
        rod_dir + 'detachment_rate.dat',
        rod_dir + 'electron_transport_data.dat',
        rod_dir + 'ion_transport_data.dat',
        f'{_di_home}/Util/GenericArrayJob.sh',  # used at voltage step level
        f'{_di_home}/GenericArrayJobJobscript.py'  # used at voltage step level
    ],
    'output_directory': 'plasma_simulations',
    'output_dir_prefix': 'run_',
    'input_overrides' : {
        'mode': {
            'target': 'master.inputs',
            'uri': 'app.mode',
            'value': "plasma"
        },
        "max_steps": {
            "target": "master.inputs",
            "uri": "Driver.max_steps",
            "value": 500
        },        
    },
    'job_script_options': {
        'K_min': 6,
        'K_max': 12.0,
        'plasma_polarity': 'positive',
        # --- particle seeding (optional) ------------------------------------
        # 'particle_mode': 'single',   # default: one seed electron at the
        #                              # critical position from the DB
        # 'num_particles': 1,          # weight (single) or count (sphere)
        #
        # Sphere mode — seed from a volumetric distribution instead:
        # 'particle_mode': 'sphere',
        # 'sphere_radius': 50e-6,      # required for sphere mode
        # 'sphere_center': [0, 0.02, 0],  # optional; defaults to DB position
        #
        # Interpolated voltage points (optional; default: all report rows):
        # 'N_voltages': 10,            # exactly N runs per polarity
    },
    'parameter_space': {
        "geometry_radius": {
            "database": "inception_stepper",  # database dependency
            "target": "master.inputs",
            "uri": "Rod.radius",
            "values": [100E-6, 500E-6, 1e-3] #, 2e-3, 3e-3]
        },
        "pressure": {
            "database": "inception_stepper",  # database dependency
            "target": "chemistry.json",
            "uri": ["gas", "law", "ideal_gas", "pressure"],
            "values": [1e5]  # np.arange(1e5, 11e5, 10e5).tolist()
        },
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

top_object = dict(databases=[inception_stepper], studies=[plasma_study])

if __name__ == '__main__':
    with open('runs.json', 'w') as f:
        json.dump(top_object, f, indent=4)
