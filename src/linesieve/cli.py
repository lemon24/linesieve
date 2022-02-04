import os.path
import re
import subprocess
from functools import wraps

import click
from click import echo
from click import style

import linesieve
from .parsing import make_pipeline


# references for common command-line option names:
# https://www.gnu.org/prep/standards/html_node/Option-Table.html
# http://www.catb.org/~esr/writings/taoup/html/ch10s05.html
# all the git options, generated with the script in the README


def color_help(text):

    KWARGS = {
        'd': dict(dim=True),
        'r': dict(fg='red'),
        'g': dict(fg='green'),
        'y': dict(fg='yellow'),
    }

    def repl(match):
        options, line = match.groups()
        kwargs = {}
        for option in options:
            if option == '\b':
                continue
            kwargs.update(KWARGS[option])
        return style(line, **kwargs)

    return re.sub('([drgy]\b)(.*)', repl, text)


def help_all_option():
    return click.option(
        "--help-all",
        is_flag=True,
        expose_value=False,
        is_eager=True,
        help="Show help for all commands and exit.",
        callback=help_all_callback,
    )


def help_all_callback(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return

    formatter = ctx.make_formatter()
    formatter.indent_increment
    commands = list_commands_recursive(ctx.command, ctx)

    for path, command in commands:
        title = style(path.upper(), bold=True)
        if command.short_help:
            short = command.short_help
            first = short.partition(' ')[0]
            if first.istitle():
                short = first.lower() + short[len(first) :]
            short = short.rstrip('.')
            title += style(' - ' + short, dim=True)

        formatter.write(title + '\n\n  ')

        with formatter.indentation():
            if command is ctx.command:
                format_ctx = ctx
            else:
                format_ctx = type(ctx)(command, ctx, command.name)
            command.format_help(format_ctx, formatter)

        formatter.write('\n')

    click.echo_via_pager(formatter.getvalue(), color=ctx.color)
    ctx.exit()


def list_commands_recursive(self, ctx, path=()):
    path = path + (self.name,)
    yield ' '.join(path), self
    if not hasattr(self, 'list_commands'):
        return
    for subcommand in self.list_commands(ctx):
        cmd = self.get_command(ctx, subcommand)
        if cmd is None:
            continue
        if cmd.hidden:
            continue
        yield from list_commands_recursive(cmd, ctx, path)


@click.group(
    name='linesieve',
    chain=True,
    invoke_without_command=True,
    help=color_help(linesieve.__doc__),
    short_help="An unholy blend of grep, sed, awk, and Python.",
)
@click.option(
    '-s',
    '--section',
    metavar='PATTERN',
    help="""
    Consider matching lines the start of a new section.
    The section name is one of: the named group 'name',
    the first captured group, the entire match.
    """,
)
@click.option(
    '--success',
    metavar='PATTERN',
    help="If matched, exit with a status code indicating success.",
)
@click.option(
    '--failure',
    metavar='PATTERN',
    help="""
    If matched, exit with a status code indicating failure.
    Before exiting, output the last section if it wasn't already.
    """,
)
@help_all_option()
@click.pass_context
def cli(ctx, **kwargs):
    # options reserved for future expansion:
    # -s --section --section-start
    # -e --section-end
    # -n --section-name # same as annotate_lines() marker
    ctx.obj = {}


@cli.result_callback()
@click.pass_context
def process_pipeline(ctx, processors, section, success, failure):
    file = ctx.obj.get('file')
    if not file:
        file = click.get_text_stream('stdin')

    process = ctx.obj.get('process')
    show = ctx.obj.get('show')

    processors = [p for p in processors if p]

    status, label = output_sections(
        make_pipeline(file, section, success, failure, show, processors)
    )

    message = None
    returncode = 0

    if status is True:
        message = style(label, fg='green')
        returncode = 0

    elif status is False:
        message = style(label, fg='red')
        returncode = 1

    elif status is None:
        # no success or failure -> end is expected (use returncode if available)
        # failure only          -> end is success (unless returncode says failure)
        # success only          -> end is failure (unless returncode says success)
        # success and failure   -> end is unexpected

        label = label or '<no-section>'
        if success is not None and failure is not None:
            message = style(
                f"unexpected end during {style(label, bold=True)}", fg='red'
            )
            returncode = 1

    if message:
        echo(message, err=status not in {True, False})

    if process:
        process.wait()
        returncode = process.returncode
        if not message:
            message = style(
                f"exited with status code {style(str(returncode), bold=True)}",
                fg=('green' if returncode == 0 else 'red'),
            )
        else:
            message = None

    else:
        if not message:
            assert success is None or failure is None, (success, failure)
            if success is not None:
                message = style("success marker not found", fg='red')
                returncode = 1
            if failure is not None:
                message = style("failure marker not found", fg='green')
                returncode = 0
        else:
            message = None

    if message:
        echo(message, err=True)

    ctx.exit(returncode)

    # TODO after 1.0:
    # hide lines in section after pattern
    # print last section without --failure if exec exits with non-zero (how?)
    # hide section
    # exec time
    # match replace spans of skipped lines with ...
    # collapse any repeated lines
    # runfilter "grep pattern"
    # match -e pattern -e pattern (hard to do with click while keeping arg)
    # short command aliases (four-letter ones)
    # make dedupe_blank_lines optional


def output_sections(groups, section_dot='.'):
    """Print (section, lines) pairs in a fancy way.

    >>> groups = [('', 'ab'), ('', ''), ('', ''), ('one', 'c'), ('', ''), (True, 'xyz')]
    >>> output_sections(groups)  # doctest: +SKIP
    a
    b
    ..
    one
    c
    .
    (True, 'x')

    """
    prev_section = None
    last_was_dot = False

    for section, lines in groups:

        if section == '' and prev_section is not None:
            echo(style(section_dot, dim=True), err=True, nl=False)
            last_was_dot = True
        elif last_was_dot:
            echo(err=True)
            last_was_dot = False

        if section is True or section is False:
            return section, next(iter(lines))

        if section is None:
            return section, prev_section

        if section:
            echo(style(section, dim=True, bold=True))

        line = next(lines, None)
        if line:
            if last_was_dot:
                echo(err=True)
                last_was_dot = False
            echo(line)

        for line in lines:
            echo(line)

        prev_section = section


@cli.command(short_help="Read input from file.")
@click.argument('file', type=click.File('r', lazy=True))
@click.pass_obj
def open(obj, file):
    """Read input from FILE instead of standard input.

    Roughly equivalent to: cat FILE | linesieve

    """
    assert not obj.get('file')
    obj['file'] = file


@cli.command(short_help="Read input from command.")
@click.argument('command')
@click.argument('argument', nargs=-1)
@click.pass_obj
def exec(obj, command, argument):
    """Execute COMMAND and use its output as input.

    Roughly equivalent to: COMMAND | linesieve

    If the command finishes, exit with its status code.

    """
    assert not obj.get('file')
    process = subprocess.Popen(
        (command,) + argument,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    obj['process'] = process
    obj['file'] = process.stdout


def pattern_argument(fn):
    @click.option(
        '-F',
        '--fixed-strings',
        is_flag=True,
        help="Interpret the pattern as a fixed string.",
    )
    @click.option(
        '-i', '--ignore-case', is_flag=True, help="Perform case-insensitive matching."
    )
    @click.argument('PATTERN')
    @wraps(fn)
    def wrapper(*args, pattern, fixed_strings, ignore_case, **kwargs):
        return fn(
            *args,
            pattern=compile_pattern(pattern, fixed_strings, ignore_case),
            fixed_strings=fixed_strings,
            **kwargs,
        )

    return wrapper


def compile_pattern(pattern, fixed_strings, ignore_case):
    if fixed_strings:
        pattern = re.escape(pattern)

    flags = 0
    if ignore_case:
        flags |= re.IGNORECASE

    return re.compile(pattern, flags)


@cli.command(short_help="Show selected sections.")
@pattern_argument
@click.pass_obj
def show(obj, pattern, fixed_strings):
    """Output only sections matching PATTERN.

    '^$' matches the lines before the first section.
    '$none' matches no section.

    """
    obj.setdefault('show', []).append(pattern)


def section_option(fn):
    @click.option(
        '-s', '--section', metavar='PATTERN', help="Apply only to matching sections."
    )
    @wraps(fn)
    def wrapper(*args, section, **kwargs):
        rv = fn(*args, **kwargs)
        if rv is None:
            return None
        section_re = re.compile(section) if section is not None else None
        return section_re, rv

    return wrapper


@cli.command(short_help="Replace pattern.")
@pattern_argument
@click.argument('repl')
@click.option('-o', '--only-matching', is_flag=True, help="Output only matching lines.")
@click.option('--color', is_flag=True, help="Color replacements.")
@section_option
def sub(pattern, repl, fixed_strings, only_matching, color):
    """Replace PATTERN matches with REPL.

    Roughly equivalent to: sed 's/PATTERN/REPL/g'

    Works like re.sub() in Python.

    """
    if fixed_strings:
        repl = repl.replace('\\', r'\\')
    if color:
        repl = style(repl, fg='red')

    def sub(line):
        line, subn = pattern.subn(repl, line)
        if only_matching and not subn:
            return None
        return line

    return sub


@cli.command(short_help="Search for pattern.")
@pattern_argument
@click.option(
    '-o',
    '--only-matching',
    is_flag=True,
    help="""
    Output only the matching part of the line, one match per line.
    Works like re.findall() in Python:
    if there are no groups, output the entire match;
    if there is one group, output the group;
    if there are multiple groups, output all of them (tab-separated).
    """,
)
@click.option(
    '-v',
    '--invert-match',
    is_flag=True,
    help="Output only lines *not* matching the pattern.",
)
@click.option('--color', is_flag=True, help="Color matches.")
@section_option
@click.pass_context
def match(ctx, pattern, fixed_strings, only_matching, invert_match, color):
    """Output only lines matching PATTERN.

    Roughly equivalent to: grep PATTERN

    Works like re.search() in Python.

    """

    if color and not invert_match and not only_matching:
        return ctx.invoke(
            sub,
            pattern=pattern,
            repl=r'\g<0>',
            # pattern is already escaped
            fixed_strings=False,
            only_matching=True,
            color=color,
        )[1]

    def search(line):
        if not only_matching:
            if bool(pattern.search(line)) is not invert_match:
                return line
            return None
        else:
            matches = pattern.findall(line)
            if matches:
                lines = []
                for match in matches:
                    groups = (match,) if isinstance(match, str) else match
                    if color:
                        groups = [style(g, fg='red') for g in groups]
                    lines.append('\t'.join(groups))
                return '\n'.join(lines)
            return None

    return search


@cli.command(short_help="Shorten paths of existing files.")
@click.option(
    '--include',
    multiple=True,
    metavar='GLOB',
    help="""
    Replace the paths of existing files matching this pattern.
    Both recursive globs and brace expansion are supported, e.g.
    {src,tests}/**/*.py.
    """,
)
@click.option('--modules', is_flag=True, help="Also replaced dotted module names.")
@click.option(
    '--modules-skip',
    type=click.IntRange(0),
    metavar='INTEGER',
    help="Path levels to skip to obtain module names from paths. Implies --modules.",
)
@click.option(
    '--modules-recursive',
    is_flag=True,
    help="""
    Consider the parent directories of selected files to be modules too.
    Implies --modules.
    """,
)
@section_option
def sub_paths(include, modules, modules_skip, modules_recursive):
    """Replace paths of existing files with shorter versions.

    The replacement paths are still unique.

    For example, given these files are selected:

    \b
      src/one/mod1.py
      src/one/two/mod2.py
      tests/test.py

    Their paths will be replaced with:

    \b
      .../mod1.py
      .../mod2.py
      .../test.py

    Dotted module names derived from the selected files can also be shortened.
    For example, with --modules-skip 1 --modules-recursive, these modules:

    \b
      one.mod1
      one.two.mod2
      one.two

    Will be replaced with:

    \b
      ..mod1
      ..mod2
      ..two

    """
    from glob import glob
    from braceexpand import braceexpand
    from .paths import shorten_paths, paths_to_modules, make_file_paths_re

    paths = [
        path
        for unexpanded_pattern in include
        for pattern in braceexpand(unexpanded_pattern)
        for path in glob(pattern, recursive=True)
    ]

    replacements = shorten_paths(paths, os.sep, '...')

    if modules or modules_recursive or modules_skip is not None:
        modules = paths_to_modules(
            paths, skip=modules_skip or 0, recursive=modules_recursive
        )
        replacements.update(shorten_paths(modules, '.', '.'))

    if not replacements:
        return None

    for k, v in replacements.items():
        replacements[k] = style(v, fg='yellow')

    pattern_re = make_file_paths_re(paths, modules or ())

    def repl(match):
        return replacements[match.group(0)]

    def sub_paths(line):
        return pattern_re.sub(repl, line)

    return sub_paths


@cli.command(short_help="Make working directory paths relative.")
@section_option
def sub_cwd():
    """Make paths in the working directory relative.

    Roughly equivalent to: sub $( pwd ) ''

    """
    min_length = 2

    path = os.getcwd()
    if len(path.split(os.sep)) < min_length:
        return None

    from .paths import make_dir_path_re

    pattern_re = make_dir_path_re(path)

    def repl(match):
        return '' if match.group(1) is None else '.'

    def sub_cwd(line):
        return pattern_re.sub(repl, line)

    return sub_cwd


@cli.command(short_help="Replace symlink targets.")
@click.argument('link')
@section_option
def sub_link(link):
    """Replace the target of symlink LINK with LINK.

    Roughly equivalent to: sub $( realpath LINK ) LINK

    """
    min_length = 2

    try:
        path = os.path.abspath(os.readlink(link))
    except FileNotFoundError:
        # TODO: retry on the first sub_link call, maybe
        return None
    except OSError:
        return None

    if len(path.split(os.sep)) < min_length:
        return None

    from .paths import make_dir_path_re

    pattern_re = make_dir_path_re(path)

    def repl(match):
        return (link + os.sep) if match.group(1) is None else link

    def sub_link(line):
        return pattern_re.sub(repl, line)

    return sub_link


@cli.command(short_help="Output the first part of sections.")
@click.option(
    '-n',
    'count',
    metavar="COUNT",
    type=int,
    default=10,
    show_default=True,
    help="Print the first COUNT lines. "
    "With a leading '-', print all but the last COUNT lines.",
)
@section_option
def head(count):
    """Print the first COUNT lines.

    Roughly equivalent to: head -n COUNT

    """
    from itertools import islice

    def head(lines):
        if count >= 0:
            return islice(lines, count)
        else:
            # TODO: don't read in memory, use a temporary file
            return iter(list(lines)[0:count])

    head.is_iter = True
    return head


def tail_count_int(value):
    value = value.strip()
    if value.startswith('+'):
        rv = int(value) - 1
    elif value.startswith('-'):
        rv = int(value)
    else:
        rv = -int(value)
    return rv


@cli.command(short_help="Output the last part of sections.")
@click.option(
    '-n',
    'count',
    metavar="COUNT",
    type=tail_count_int,
    default=10,
    show_default=True,
    help="Print the last COUNT lines. "
    "With a leading '+', print lines starting with line COUNT.",
)
@section_option
def tail(count):
    """Print the last COUNT lines.

    Roughly equivalent to: tail -n COUNT

    """
    from itertools import islice
    from collections import deque

    def tail(lines):
        if count <= 0:
            # TODO: don't read in memory, use a temporary file
            return iter(deque(lines, maxlen=-count))
        else:
            return islice(lines, count, None)

    tail.is_iter = True
    return tail


def split_field_slices(value):
    rv = []
    for slice_str in value.split(','):
        parts = slice_str.split('-')

        if len(parts) == 1:
            start = int(parts[0])
            stop = start
        elif len(parts) == 2:
            try:
                start = int(parts[0])
            except ValueError:
                start = None
            try:
                stop = int(parts[1])
            except ValueError:
                stop = None
        else:
            raise ValueError

        if start is None and stop is None:
            raise ValueError
        if start is not None and stop is not None:
            if start > stop:
                raise ValueError
        if start is not None:
            if start < 1:
                raise ValueError
            start -= 1
        if stop is not None:
            if stop < 1:
                raise ValueError

        rv.append(slice(start, stop))

    return rv


@cli.command(short_help="Output selected parts of lines.")
@click.option(
    '-d',
    '--delimiter',
    metavar='PATTERN',
    help="Use as field delimiter (consecutive delimiters delimit empty strings). "
    "If not given, use runs of whitespace as a delimiter "
    "(with leading/trailing whitespace stripped first).",
)
@click.option(
    '-F',
    '--fixed-strings',
    is_flag=True,
    help="Interpret the delimiter as a fixed string.",
)
@click.option(
    '-i',
    '--ignore-case',
    is_flag=True,
    help="Interpret the delimiter as case-insensitive.",
)
@click.option(
    '-f',
    '--fields',
    type=split_field_slices,
    metavar='LIST',
    help="Select only these fields.",
)
@click.option(
    '--output-delimiter',
    show_default=True,
    help="Use as the output field delimiter. "
    "If not given, and --delimiter and --fixed-strings are given, "
    "use the input delimiter. Otherwise, use one tab character.",
)
@section_option
def split(delimiter, fixed_strings, ignore_case, fields, output_delimiter):
    """Print selected parts of lines.

    Roughly equivalent to:

    \b
      awk '{ print ... }'     (no --delimiter)
      cut -d delim            (--fixed-strings --delimiter delim)

    Python equivalents:

    \b
      line.split()            (no --delimiter)
      line.split(delim)       (--fixed-strings --delimiter delim)
      re.split(delim, line)   (--delimiter delim)

    --fields takes a comma-separated list of ranges, each range one of:

    \b
      N     Nth field, counted from 1
      N-    from Nth field to end of line
      N-M   from Nth to Mth (included) field
       -M   from first to Mth (included) field

    This is the same as the cut command. Unlike cut,
    selected fields are printed in the order from the list,
    and more than once, if repeated.

    """
    if delimiter is None or (fixed_strings and not ignore_case):

        def split(line):
            return line.split(delimiter)

    else:
        # TODO: optimization: if the pattern is a simple string ("aa"), use str.split()
        pattern = compile_pattern(delimiter, fixed_strings, ignore_case)
        split = pattern.split

    if not output_delimiter:
        if fixed_strings:
            output_delimiter = delimiter
        else:
            output_delimiter = '\t'

    if not fields:
        join = output_delimiter.join
    else:

        def join(parts):
            return output_delimiter.join(
                p for field_slice in fields for p in parts[field_slice]
            )

    def processor(line):
        return join(split(line))

    return processor

    # TODO:
    # tests
    # --max split
    # --output-format '{1}{2!r}'? zero-indexed? 1-indexed?
    # -s, --only-delimited
