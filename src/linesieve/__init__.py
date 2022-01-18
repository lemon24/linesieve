"""
Read standard input, process it, and write to standard output.

Split input into sections, and output selected sections.
Filter output lines, globally or per-section.
Compress runs of blank lines.

All patterns use the Python regular expression syntax.

Example:

\b
  $ cat file.txt
  0
  one:
  1...
  two:
  2 (two)
  three:
  3, three
  fail

\b
  $ cat file.txt | linesieve --section '(\\S+):$' --failure fail \\
  > show --ignore-case ^O \\
  > match --section one --only-matching '\\d+' \\
  > sub '([a-z])' '\\1\\1\\1'
  d\bone
  1
  d\b..
  d\bthree
  3, ttthhhrrreeeeee
  r\bfail

"""

__version__ = '1.0a6'
