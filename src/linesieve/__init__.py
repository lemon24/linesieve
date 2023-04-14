"""
linesieve is a tool for splitting text input into sections,
applying filters to the lines in each section,
and writing results to standard output.

Example:

\b
    $ ls -1 /* | linesieve -s '.*:' show bin match ^d head -n2
    .....  # dim
    /bin:  # dim bold
    dash
    date
    ......  # dim
    /sbin:  # dim bold
    disklabel
    dmesg
    ...  # dim

Here, we
split a file listing for multiple directories,
show only sections whose names contain `bin`,
and for each section only show lines starting with `d`,
but at most the first 2 lines.


You can specify a section marker regex with `--section`,
as well as `--success` and `--failure` markers
which cause linesieve to exit early.
To show only specific sections, use the `show` subcommand;
skipped sections will be marked with a dot on stderr.

\b
    $ ls -1 /* | linesieve -s '.*:' --failure ^cat show bin
    .....  # dim
    /bin:  # dim bold
    [
    bash
    cat  # red

All patterns use the Python regular expression syntax.

You can use subcommands to filter the lines in each section.
To restrict a filter to specific sections,
use their `-s/--section` option;
you can also temporarily restrict all filters
using the `push` and `pop` subcommands.

\b
    $ ls -1 /* | linesieve -s '.*:' show bin \\
    > match -s /bin ^b match -s /sbin ^d head -n1
    .....  # dim
    /bin:  # dim bold
    bash
    ......  # dim
    /sbin:  # dim bold
    disklabel
    ...  # dim

By default, linesieve reads from the standard input,
but it can also read from a file or a command
with the `read` and `read-cmd` subcommands.

\b
    $ linesieve read-cmd echo bonjour
    bonjour
    linesieve: echo exited with status code 0  # green

On output, runs of blank lines are collapsed into a single line.


"""

__version__ = '1.0b1'
