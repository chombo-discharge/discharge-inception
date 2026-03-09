.. _install_venv:

Create and activate a virtual environment
==========================================

A virtual environment isolates the project's Python dependencies from the
system Python and from other projects on the same machine.  This is especially
important on HPC clusters, where the system Python may be managed by
administrators and ``pip install`` into it is either forbidden or inadvisable.

The virtual environment directory is conventionally named ``.venv`` and placed
at the repository root.  Because compute nodes need to activate the same
environment, the ``.venv`` directory must live on a shared filesystem that is
accessible from all nodes — typically your home directory or a project scratch
space, both of which are usually network-mounted on HPC clusters.  Do **not**
place ``.venv`` on a node-local scratch directory (e.g. ``/tmp``), as it will
not be visible to other nodes.

From the repository root:

.. code-block:: bash

   python -m venv .venv
   source .venv/bin/activate        # Linux / macOS
   # .venv\Scripts\activate         # Windows
