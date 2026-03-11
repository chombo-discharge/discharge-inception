.. _example_compile:

Compiling the executable
========================

.. code-block:: bash

   cd Exec/Rod
   make -j4

This produces a single binary in ``Exec/Rod/``:

.. code-block:: text

   main2d.Linux.64.mpic++.gfortran.OPTHIGH.MPI.ex   (or main3d... for 3-D)

The binary handles **both** pipeline stages.  The active mode is selected at
runtime via ``app.mode`` in the ``.inputs`` file (``inception`` or ``plasma``).
The ``{N}`` in the filename is replaced by the dimensionality supplied via
``--dim``.

.. note::

   Both pipeline stages share the same ``chemistry.json`` as their single
   source of truth for gas properties and transport data.  In ``inception``
   mode, :math:`\alpha` and :math:`\eta` are computed via ``ItoKMCJSON::computeAlpha/computeEta``,
   which derives them from the reaction network in ``chemistry.json`` — the
   same path used by ``plasma`` mode.  No separate ``transport_data.txt`` is
   needed.
