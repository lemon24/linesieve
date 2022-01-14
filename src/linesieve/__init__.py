"""
An unholy blend of grep, sed, and awk, with very specific features.

Split input into sections; show:

\b
* all sections (default)
* specific sections (see the include sub-command)
* failing section (if --failure was given)

Stop on success/failure.

Show dots for hidden sections to indicate progress.

Color section and success/failure markers.

Filter lines in (specific) sections by chaining sub-commands.

Deduplicate blank lines.

All patterns are full Python regular expressions.

The section and end markers are shortened to:

\b
* the group named 'name', if any
* the first captured group, if any
* the entire match, otherwise

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
  $ cat file.txt | linesieve -s '(\\S+):$' --failure fail \\
  > show one \\
  > match -s one -o '\\d+' \\
  > sub th þ
  d\bone
  1
  d\b..
  d\bthree
  3, þree
  r\bfail

"""

__version__ = '1.0a4'
