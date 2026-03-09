.. _install_package:

Install the package
===================

Install in *editable* mode so that local edits to the ``discharge_inception/``
source directory take effect immediately without reinstalling.  Editable mode
also means that the ``discharge-inception`` command-line entry point is
registered in the virtual environment and will always run the current state of
the checked-out source.

The ``[plot]`` optional dependency group adds ``matplotlib`` and ``scipy``,
which are used by the post-processing scripts in ``PostProcess/`` but are not
required to run the configurator or submit SLURM jobs:

.. code-block:: bash

   pip install -e .                 # core only
   pip install -e ".[plot]"         # with matplotlib + scipy
