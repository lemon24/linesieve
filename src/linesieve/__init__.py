"""
An unholy blend of grep, sed, awk, and Python.

Read standard input, process it, and write to standard output.

Split input into sections, and output selected sections.
Filter output lines, globally or per-section.
Compress runs of blank lines.

All patterns use the Python regular expression syntax.

Example:

\b
    $ cat simple.txt
    0
    one:
    1...
    two:
    2 (two)
    three:
    3, three
    fail

\b
    $ cat simple.txt \\
    | linesieve --section '(\\S+):$' --failure fail \\
      show --ignore-case ^O \\
      match --section one --only-matching '\\d+' \\
      sub '([a-z])' '\\1\\1\\1'
    one  # dim
    1
    ..  # dim
    three  # dim
    3, ttthhhrrreeeeee
    fail  # red

"""

__version__ = '1.0a10'
