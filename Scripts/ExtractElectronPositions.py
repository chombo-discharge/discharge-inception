#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExtractElectronPositions — parser for inception-stepper report files.

The chombo-discharge inception stepper writes a space-delimited ``report.txt``
after each simulation run. Each row records scalar and vector quantities for a
given simulation step, including the applied voltage, the peak ionisation
coefficients K(+) and K(-), and the spatial positions of those peaks.

This module provides :func:`parse_report_file`, which reads such a file and
returns the requested columns as a typed list of tuples. It handles:

- Comment lines (``#``-prefixed) used for the column header
- Mixed scalar / vector columns (vectors formatted as ``(x, y, z)``)
- Automatic detection of vector dimensionality from the first data row
- Optional column filtering via the ``interesting`` parameter

Typical usage::

    from ExtractElectronPositions import parse_report_file

    columns, rows = parse_report_file(
        'report.txt',
        interesting=['+/- Voltage', 'Max K(+)', 'Pos. max K(+)'])

Author André Kapelrud, Robert Marskar
Copyright © 2026 SINTEF Energi AS
"""

import sys
from itertools import groupby, tee


def _take_vec(iterator, d):
    """Consume *d* tokens from *iterator* and return them as a float tuple.

    The inception-stepper report file encodes spatial vectors as a sequence of
    whitespace-separated tokens with embedded punctuation, for example a 3-D
    vector ``(1.0, 2.0, 3.0,)`` appears as three adjacent tokens::

        (1.0,   2.0,   3.0,)

    The leading ``(`` is attached to the first token and the trailing ``)`` is
    attached to the last token (which also carries a trailing ``,``).  Interior
    tokens each carry a trailing ``,``.

    Parameters
    ----------
    iterator : iterator of str
        Token stream positioned immediately before the first component of the
        vector.  Exactly *d* tokens are consumed.
    d : int
        Number of components (dimensionality).  Must be greater than 1.

    Returns
    -------
    tuple of float
        The *d* floating-point components of the vector.

    Raises
    ------
    AssertionError
        If *d* is not greater than 1.
    """
    assert d > 1
    vec = []
    for i in range(d):
        if i == 0:  # discard leading '(' and trailing ','
            vec.append(float(next(iterator)[1:-1]))
        else:  # discard trailing ',' and ')'
            vec.append(float(next(iterator)[0:-1]))
    return tuple(vec)


def parse_report_file(
    filename: str,
    interesting: list[str] = None,
) -> tuple[list[str], list[tuple[float, list[float]]]]:
    """Parse an inception stepper report file containing e.g. optimal starting
    positions for electrons.

    The file mixes comment lines (``#``-prefixed) with space-delimited data
    rows.  The column header is taken from the second-to-last comment block
    preceding the first data row.  Vectors are stored as ``(x, y, z,)``-style
    token sequences; their dimensionality is auto-detected from the first data
    row and assumed to be consistent throughout the file.

    Parameters
    ----------
    filename : str
        Path to the ``report.txt`` file produced by the inception stepper.
    interesting : list of str, optional
        Column names to include in the output.  If ``None``, all columns are
        returned.  Names must match the header strings exactly.

    Returns
    -------
    columns : list of str
        Ordered list of column names that were selected (intersection of the
        file's header and *interesting*).
    rows : list of tuple
        One tuple per data row.  Each element is either a ``float`` (scalar
        column) or a ``tuple`` of floats (vector column), in the same order as
        *columns*.
    """
    with open(filename) as f:
        previous_lines = ['', '']
        header = None

        columns = []  # header fields
        dimensionality = 0  # dimensionality of vectors
        rows = []

        for line in f:
            if line[0] == '#':
                previous_lines[1] = previous_lines[0]
                previous_lines[0] = line
                continue

            if not header:
                header = previous_lines[1]

                # use the 1st data row to get field positions and
                # dimensionality (assuming this is consistent for the header as
                # well
                field_positions = []
                field_dims = []
                vector_started = False
                for k, g in groupby(enumerate(line),
                                    lambda x: not x[1].isspace()):
                    if k:
                        pos, first_item = next(g)
                        field = first_item + ''.join([x for _, x in g])

                        if not vector_started:
                            dim = 1
                        if field[-1] == ',':
                            dim += 1
                            if field[0] != '(':
                                continue
                            vector_started = True
                        elif field[-1] == ')':
                            if not dimensionality:
                                dimensionality = dim
                            field_dims.append(dim)
                            vector_started = False
                            continue

                        if dim == 1:
                            field_dims.append(dim)
                        field_positions.append(pos)

                # rearrange to header ranges
                field_positions.append(-1)
                a, b = tee(field_positions)
                next(b, None)

                for pos_pair in zip(a, b):
                    field = header[pos_pair[0]:pos_pair[1]].strip()
                    if field[0] == '#':
                        field = field[1:].lstrip()
                    columns.append(field)

                if interesting is None:
                    interesting = columns

            # parse data rows as normal
            row = []
            fields = line.split()
            it = iter(fields)
            for col, d in zip(columns, field_dims):
                if col in interesting:
                    if d == 1:
                        row.append(float(next(it)))
                    elif d > 1:
                        row.append(_take_vec(it, d))
                else:
                    for _ in range(d):  # skip ahead
                        next(it)
            rows.append(tuple(row))
        return ([col for col in columns if col in interesting], rows)


def main():
    """Entry point: parse a report file and print the result to stdout."""
    filename = 'report.txt'
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    result = parse_report_file(
        filename,
        ['+/- Voltage', 'Max K(+)', 'Max K(-)', 'Pos. max K(+)', 'Pos. max K(-)'],
    )
    print(result)


if __name__ == '__main__':
    main()
