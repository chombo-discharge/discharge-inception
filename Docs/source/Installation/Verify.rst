.. _install_verify:

Verify
======

After installing the package, confirm that the ``discharge-inception`` entry
point is registered in the active virtual environment and that the package
imports correctly.  The ``which`` command should resolve to the ``.venv/bin/``
directory, confirming that the system Python (or another environment) is not
being used by mistake.  Running ``--help`` exercises the full import chain —
including ``configurator`` and ``config_util`` — so any missing dependency or
broken import will surface here rather than at job-submission time.

.. code-block:: bash

   which discharge-inception               # should point into .venv/bin/
   discharge-inception --help
