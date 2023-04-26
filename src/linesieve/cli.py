import os.path
import re
from contextlib import contextmanager
from functools import wraps

import click
from click import BadParameter
from click import echo
from click import style
from click import UsageError

import linesieve
from .click_utils import Group
from .parsing import make_pipeline


# references for common command-line option names:
# https://www.gnu.org/prep/standards/html_node/Option-Table.html
# http://www.catb.org/~esr/writings/taoup/html/ch10s05.html
# all the git options, generated with the script in the README


FURTHER_HELP = """\
\b
linesieve help --all
linesieve [COMMAND] --help
https://linesieve.readthedocs.io/
"""


@click.group(
    name='linesieve',
    chain=True,
    cls=Group,
    invoke_without_command=True,
    context_settings=dict(auto_envvar_prefix='LINESIEVE'),
    subcommand_metavar='[COMMAND [ARGS]...]... ',
    epilog_sections={'Further help': FURTHER_HELP},
    help=linesieve.__doc__,
    short_help="An unholy blend of grep, sed, awk, and Python.",
)
@click.option(
    '-s',
    '--section',
    metavar='PATTERN',
    help="""
    Consider matching lines the start of a new section.
    The section name is one of: the named group `name`,
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
@click.option('--line-delay', type=click.FloatRange(0), hidden=True)
@click.option('--section-delay', type=click.FloatRange(0), hidden=True)
@click.version_option(linesieve.__version__, message='%(prog)s %(version)s')
@click.pass_context
def cli(ctx, **kwargs):
    # options reserved for future expansion:
    # -s --section --section-start
    # -e --section-end
    # -n --section-name # same as annotate_lines() marker
    ctx.obj = {}


@cli.result_callback()
@click.pass_context
def process_pipeline(
    ctx, processors, section, success, failure, line_delay, section_delay
):
    if section is not None:
        with handle_re_error('--section'):
            section = re.compile(section)
    if success is not None:
        with handle_re_error('--success'):
            success = re.compile(success)
    if failure is not None:
        with handle_re_error('--failure'):
            failure = re.compile(failure)

    file = ctx.obj.get('file')
    if not file:
        file = click.get_text_stream('stdin')

    if file.isatty():
        # we are not using no_args_is_help=True, because as of click 8.1.3,
        # "linesieve show p --not-an-option" shows help instead of
        # "Error: No such command '--not-an-option'." (click bug?)
        if not ctx.initial_args:
            echo(ctx.command.get_abridged_help(ctx), color=ctx.color)
            ctx.exit()

        echo(style("linesieve: reading from terminal", dim=True), err=True)

    process = ctx.obj.get('process')
    show = ctx.obj.get('show')

    processors = [p for p in processors if p]

    if line_delay:

        def _line_delay(file):
            from time import sleep

            for line in file:
                sleep(line_delay)
                yield line

        file = _line_delay(file)

    if section_delay:

        def _section_delay(lines):
            from time import sleep

            sleep(section_delay)
            return lines

        _section_delay.is_iter = True
        processors.insert(0, ([], _section_delay))

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
                f"linesieve: unexpected end during {style(label, bold=True)}", fg='red'
            )
            returncode = 1

    if message:
        echo(message, err=status not in {True, False})

    if process:
        process.wait()
        returncode = process.returncode
        if not message:
            message = style(
                f"linesieve: {process.args[0]} exited with status code "
                f"{style(str(returncode), bold=True)}",
                fg=('green' if returncode == 0 else 'red'),
            )
        else:
            message = None

    else:
        if not message:
            assert success is None or failure is None, (success, failure)
            if success is not None:
                message = style("linesieve: success marker not found", fg='red')
                returncode = 1
            if failure is not None:
                message = style("linesieve: failure marker not found", fg='green')
                returncode = 0
        else:
            message = None

    if message:
        echo(message, err=True)

    ctx.exit(returncode)


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


@contextmanager
def handle_re_error(param_hint):
    if isinstance(param_hint, str):
        param_hint = [param_hint]
    try:
        yield
    except re.error as e:
        raise BadParameter(f"{e}: {e.pattern!r}", param_hint=param_hint)


# INPUT


@cli.command(short_help="Read input from file.")
@click.argument('file', type=click.File('r', lazy=True))
@click.pass_obj
def read(obj, file):
    """Read input from FILE instead of standard input.

    Roughly equivalent to: `linesieve < FILE`

    \b
        $ linesieve read file.txt
        hello

    """
    assert not obj.get('file'), "should not be possible for read to follow read-cmd"
    obj['file'] = file


@cli.command(short_help="Read input from command.")
@click.argument('command')
@click.argument('argument', nargs=-1)
@click.pass_obj
def read_cmd(obj, command, argument):
    """Execute COMMAND and use its output as input.

    Roughly equivalent to: `COMMAND | linesieve`

    If the command finishes, exit with its status code.

    \b
        $ linesieve read-cmd echo bonjour
        bonjour
        linesieve: echo exited with status code 0  # green

    """
    if obj.get('file'):
        raise UsageError("read-cmd and read are mutually exclusive")

    import subprocess

    try:
        process = subprocess.Popen(
            (command,) + argument,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as e:
        raise BadParameter(e, param_hint='COMMAND')

    obj['process'] = process
    obj['file'] = process.stdout


PATTERN_OPTIONS = [
    click.option(
        '-F',
        '--fixed-strings',
        is_flag=True,
        help="Interpret the pattern as a fixed string.",
    ),
    click.option(
        '-i', '--ignore-case', is_flag=True, help="Perform case-insensitive matching."
    ),
    click.option(
        '-X',
        '--verbose',
        is_flag=True,
        help="Ignore whitespace and comments in the pattern.",
    ),
]


def pattern_options(fn):
    for decorator in PATTERN_OPTIONS:
        fn = decorator(fn)
    return fn


def pattern_argument(fn):
    @click.argument('pattern')
    @pattern_options
    @wraps(fn)
    def wrapper(*args, pattern, fixed_strings, ignore_case, verbose, **kwargs):
        with handle_re_error('PATTERN'):
            pattern_re = compile_pattern(pattern, fixed_strings, ignore_case, verbose)
        return fn(*args, pattern=pattern_re, fixed_strings=fixed_strings, **kwargs)

    return wrapper


def compile_pattern(pattern, fixed_strings, ignore_case, verbose):
    if fixed_strings:
        pattern = re.escape(pattern)

    flags = 0
    if ignore_case:
        flags |= re.IGNORECASE
    if verbose:
        flags |= re.VERBOSE

    return re.compile(pattern, flags)


# SECTION CONTROL


@cli.command(short_help="Show selected sections.")
@pattern_argument
@click.pass_obj
def show(obj, pattern, fixed_strings):
    """Output only sections matching PATTERN.

    `^$` matches the lines before the first section.
    `$none` matches no section.

    \b
        $ ls -1 /* | linesieve -s '.*:' show /bin match ash
        .....  # dim
        /bin:  # dim bold
        bash
        dash
        ..........  # dim

    """
    obj.setdefault('show', []).append(pattern)


@cli.command(short_help="Push patterns onto the section stack.")
@pattern_argument
@click.pass_obj
def push(obj, pattern, fixed_strings):
    """Push a pattern onto the section stack.

    When there are patterns on the section stack,
    filters apply only to the sections that match
    any of the patterns in the stack.

    `filter --section PATTERN` is equivalent to
    `push PATTERN filter pop`.

    \b
        $ ls -1 /* | linesieve -s '.*:' \\
        > show bin \\
        > push /bin \\
        >   head -n1 \\
        > pop \\
        > head -n2
        .....  # dim
        /bin:  # dim bold
        [
        ......  # dim
        /sbin:  # dim bold
        apfs_hfs_convert
        disklabel
        ...  # dim

    """
    stack = obj.setdefault('section_stack', [])
    stack.append(pattern)


@cli.command(short_help="Pop patterns off the section stack.")
@click.option(
    '-a', '--all', is_flag=True, help="Remove all the patterns from the stack."
)
@click.pass_obj
def pop(obj, all):
    """Pop patterns off the section stack. See 'push' for details.

    With no arguments, removes the top pattern from the stack.

    """
    stack = obj.setdefault('section_stack', [])
    if not all:
        if not stack:
            raise UsageError('nothing to pop')
        stack.pop()
    else:
        stack.clear()


def section_option(fn):
    @click.option(
        '-s',
        '--section',
        metavar='PATTERN',
        help="""
        Apply only to matching sections.
        If there are patterns on the section stack,
        push the pattern (that is, apply *also* to matching sections).
        """,
    )
    @wraps(fn)
    def wrapper(*args, section, **kwargs):
        rv = fn(*args, **kwargs)
        if rv is None:
            return None

        ctx = click.get_current_context()
        section_res = list(ctx.obj.setdefault('section_stack', []))
        if section is not None:
            with handle_re_error('--section'):
                section_res.append(re.compile(section))

        return section_res, rv

    return wrapper


# LINE RANGES


@cli.command(short_help="Output the first part of sections.")
@click.option(
    '-n',
    'count',
    metavar="COUNT",
    type=int,
    default=10,
    show_default=True,
    help="Print the first COUNT lines. "
    "With a leading `-`, print all but the last COUNT lines.",
)
@section_option
def head(count):
    """Print the first COUNT lines.

    Roughly equivalent to: `head -n COUNT`

    \b
        $ echo -e 'a\\nb\\nc' | linesieve head -n2
        a
        b

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
    "With a leading `+`, print lines starting with line COUNT.",
)
@section_option
def tail(count):
    """Print the last COUNT lines.

    Roughly equivalent to: `tail -n COUNT`

    \b
        $ echo -e 'a\\nb\\nc' | linesieve tail -n2
        b
        c

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


@cli.command(short_help="Output matching line spans.")
@click.option(
    '--start', '--start-with', metavar='PATTERN', help="Span start (inclusive)."
)
@click.option('--end', '--end-before', metavar='PATTERN', help="Span end (exclusive).")
@pattern_options
@click.option(
    '-v',
    '--invert-match',
    is_flag=True,
    help="Output only lines *not* between those matching `--start` and `--end`.",
)
@click.option(
    '--repl',
    '--replacement',
    help="""
    Replace non-matching line spans with TEXT.
    With `--invert-match`, backreferences to captures in `--start` are expanded;
    without `--invert-match`, only escapes are expanded.
    """,
)
@section_option
def span(start, end, fixed_strings, ignore_case, verbose, invert_match, repl):
    """Output only lines between those matching `--start` and `--end`.

    Roughly equivalent to: `grep START -A9999 | grep END -B9999 | head -n-1`

    \b
        $ seq 20 | linesieve span --start ^2$ --end ^5$ --repl ...
        ...
        2
        3
        4
        ...

    """

    # options reserved for future expansion:
    # --start-after (mutually exclusive with --start-with)
    # --end-with (mutually exclusive with --end-before)

    # TODO: should start/end be arguments? hard to do if we want them to be optional

    start_re = end_re = None
    if start:
        with handle_re_error('--start'):
            start_re = compile_pattern(start, fixed_strings, ignore_case, verbose)
    if end:
        with handle_re_error('--end'):
            end_re = compile_pattern(end, fixed_strings, ignore_case, verbose)

    empty_match = re.search('.*', '')

    def match_span(lines):
        in_span = False
        in_span_changed = True

        for line in lines:
            start_match = start_re.search(line) if start_re else None

            if start_re and start_match:
                if not in_span:
                    in_span = True
                    in_span_changed = True
            elif end_re and end_re.search(line):
                if in_span:
                    in_span = False
                    in_span_changed = True

            if invert_match != in_span:
                yield line
            elif repl is not None and in_span_changed:
                if invert_match and start_match:
                    repl_match = start_match
                else:
                    repl_match = empty_match

                yield repl_match.expand(repl)
                in_span_changed = False

    match_span.is_iter = True
    return match_span


# LINE FILTERS


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

    Roughly equivalent to: `grep PATTERN`

    Works like re.search() in Python.

    \b
        $ seq 10 | linesieve match 1
        1
        10
    \b
        $ echo a1b2c3 | linesieve match -o '\\d+'
        1
        2
        3

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


def split_field_slices(value):
    rv = []
    for slice_str in value.split(','):
        parts = slice_str.split('-')

        if len(parts) == 1:
            start = stop = int(parts[0])
        elif len(parts) == 2:
            start = int(parts[0]) if parts[0] else None
            stop = int(parts[1]) if parts[1] else None
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
@pattern_options
@click.option(
    '-n',
    '--max-split',
    metavar="INTEGER",
    type=click.IntRange(1),
    help="Maximum number of splits to do. The default is no limit.",
)
@click.option(
    '-f',
    '--fields',
    type=split_field_slices,
    metavar='LIST',
    help="Select only these fields.",
)
@click.option(
    '-D',
    '--output-delimiter',
    show_default=True,
    help="Use as the output field delimiter. "
    "If not given, and `--delimiter` and `--fixed-strings` are given, "
    "use the input delimiter. Otherwise, use one tab character.",
)
@section_option
def split(
    delimiter, fixed_strings, ignore_case, verbose, max_split, fields, output_delimiter
):
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

    `--fields` takes a comma-separated list of ranges, each range one of:

    \b
        N     Nth field, counted from 1
        N-    from Nth field to end of line
        N-M   from Nth to Mth (included) field
         -M   from first to Mth (included) field

    This is the same as the cut command. Unlike cut,
    selected fields are printed in the order from the list,
    and more than once, if repeated.

    \b
        $ echo -e 'a-b\\nc-d' | linesieve split -d- -f2
        b
        d

    """
    if delimiter is None or (fixed_strings and not ignore_case):
        max_split = max_split or -1

        def split(line):
            return line.split(delimiter, max_split)

    else:
        # TODO: optimization: if the pattern is a simple string ("aa"), use str.split()
        with handle_re_error('--delimiter'):
            pattern = compile_pattern(delimiter, fixed_strings, ignore_case, verbose)
        max_split = max_split or 0

        def split(line):
            return pattern.split(line, max_split)

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
    # -s, --only-delimited
    # --output-format '{1}{2!r}'? zero-indexed? 1-indexed?
    #   ...this requires a custom string.Formatter that coerces string arguments


@cli.command(short_help="Replace pattern.")
@pattern_argument
@click.argument('repl')
@click.option('-o', '--only-matching', is_flag=True, help="Output only matching lines.")
@click.option('--color', is_flag=True, help="Color replacements.")
@section_option
def sub(pattern, repl, fixed_strings, only_matching, color):
    """Replace PATTERN matches with REPL.

    Roughly equivalent to: `sed 's/PATTERN/REPL/g'`

    Works like re.sub() in Python.

    \b
        $ echo a1b2c3 | linesieve sub '\\d+' x
        axbxcx

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


# SPECIALIZED FILTERS


@cli.command(short_help="Shorten paths of existing files.")
@click.option(
    '--include',
    multiple=True,
    metavar='GLOB',
    help="""
    Replace the paths of existing files matching this pattern.
    Both recursive globs and brace expansion are supported, e.g.
    `{src,tests}/**/*.py`.
    """,
)
@click.option('--modules', is_flag=True, help="Also replace dotted module names.")
@click.option(
    '--modules-skip',
    type=click.IntRange(0),
    metavar='INTEGER',
    help="Path levels to skip to obtain module names from paths. Implies `--modules`.",
)
@click.option(
    '--modules-recursive',
    is_flag=True,
    help="""
    Consider the parent directories of selected files to be modules too.
    Implies `--modules`.
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
    For example, with `--modules-skip 1 --modules-recursive`, these modules:

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

    paths = []
    try:
        for unexpanded_pattern in include:
            for pattern in braceexpand(unexpanded_pattern):
                paths.extend(glob(pattern, recursive=True))
    except ValueError as e:
        raise BadParameter(e, param_hint=['--include'])

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
    """Make absolute paths in the working directory relative.

    Roughly equivalent to: `sub $( pwd ) ''`

    \b
        $ echo "hello from $( pwd )/src" | linesieve sub-cwd
        hello from src

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

    Roughly equivalent to: `sub $( realpath LINK ) LINK`

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


# HELP


@cli.command()
@click.option('--all', is_flag=True, help="Show help for all commands, man-style.")
@click.pass_context
def help(ctx, all):
    """Show detailed help."""

    from .click_utils import format_help_all

    ctx = ctx.find_root()

    if not all:
        click.echo(ctx.get_help(), color=ctx.color)
    else:
        click.echo_via_pager(format_help_all(ctx))

    ctx.exit()
