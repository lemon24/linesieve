import errno
import os.path
import re
from contextlib import contextmanager
from functools import partial
from functools import wraps

import click
from click import BadParameter
from click import echo
from click import secho
from click import style
from click import UsageError

import linesieve
from .click_utils import Group
from .click_utils import REGEX
from .click_utils import RegexType
from .parsing import group_records
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
    type=REGEX,
    help="""
    Consider matching lines the start of a new section.
    The section name is one of: the named group `name`,
    the first captured group, the entire match.
    """,
)
@click.option(
    '--success',
    type=REGEX,
    help="If matched, exit with a status code indicating success.",
)
@click.option(
    '--failure',
    type=REGEX,
    help="""
    If matched, exit with a status code indicating failure.
    Before exiting, output the last section if it wasn't already.
    """,
)
@click.option(
    '--record-start',
    '--rs',
    type=REGEX,
    help="""
    Operate on multi-line records instead of individual lines.
    Records begin with lines matching `--record-start`,
    and end with the line *before* the next record start,
    or with the line matching `--record-end`, if provided.
    Lines outside record markers are also grouped into records.
    `--section` always applies to individual lines,
    regardless of `--record-start`
    (input is first split into sections, then into records).
    In patterns that apply to records,
    `.` matches any character, including newlines.
    """,
)
@click.option(
    '--record-end',
    type=REGEX,
    help="""
    Consider matching lines the end of the current record.
    Requires `--record-start`.
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
    ctx,
    processors,
    section,
    success,
    failure,
    record_start,
    record_end,
    line_delay,
    section_delay,
):
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

        secho("linesieve: reading from terminal", dim=True, err=True)

    process = ctx.obj.get('process')
    show = ctx.obj.get('show')
    hide = ctx.obj.get('hide')

    processors = [p for p in processors if p]

    if record_start:
        group_records_processor = partial(
            group_records, record_start=record_start, record_end=record_end
        )
        group_records_processor.is_iter = True
        processors.insert(0, ([], group_records_processor))
    elif record_end:
        raise UsageError("Option --record-end requires --record-start.")

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
        make_pipeline(file, section, success, failure, show, hide, processors)
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
        returncode = process.wait()
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
            secho(section_dot, dim=True, err=True, nl=False)
            last_was_dot = True
        elif last_was_dot:
            echo(err=True)
            last_was_dot = False

        if section is True or section is False:
            return section, next(iter(lines))

        if section is None:
            return section, prev_section

        if section:
            secho(section, dim=True, bold=True)

        line = next(lines, None)
        if line:
            if last_was_dot:
                echo(err=True)
                last_was_dot = False
            echo(line)

        for line in lines:
            echo(line)

        prev_section = section


OPTIONS_REGEX = RegexType(re.DOTALL, with_options=True)


def pattern_argument(fn):
    @click.argument('pattern', type=OPTIONS_REGEX)
    @OPTIONS_REGEX.add_options
    @wraps(fn)
    def wrapper(*args, pattern, fixed_strings, ignore_case, verbose, **kwargs):
        return fn(*args, pattern=pattern, fixed_strings=fixed_strings, **kwargs)

    return wrapper


def section_option(fn):
    @click.option(
        '-s',
        '--section',
        type=REGEX,
        metavar='SECTION',
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
        if section:
            section_res.append(section)

        return section_res, rv

    return wrapper


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


# SECTION CONTROL


@cli.command(short_help="Show selected sections.")
@pattern_argument
@click.pass_obj
def show(obj, pattern, fixed_strings):
    """Output only sections matching PATTERN.

    `hide` patterns take priority over `show` patterns.

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


@cli.command(short_help="Hide selected sections.")
@pattern_argument
@click.pass_obj
def hide(obj, pattern, fixed_strings):
    """Do not output sections matching PATTERN.

    `hide` patterns take priority over `show` patterns.

    `^$` matches the lines before the first section.
    `$none` matches no section.

    \b
        $ ls -1 /* | linesieve -s '.*:' show bin hide /bin head -n2
        ............  # dim
        /sbin:  # dim bold
        apfs_hfs_convert
        disklabel
        ...  # dim


    """
    obj.setdefault('hide', []).append(pattern)


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


# GENERIC FILTERS


@cli.command(short_help="Pipe sections to command.")
@click.argument('command')
@section_option
def pipe(command):
    """Pipe lines to COMMAND and replace them with the output.

    COMMAND is executed once per section.

    Command output is not parsed back into multi-line records,
    even if `linesieve --record-start` was used.

    \b
        $ echo a-b | linesieve pipe 'tr -d -'
        ab

    """
    # alternate name: exec

    def pipe(lines):
        import subprocess
        import threading

        process = subprocess.Popen(
            command,
            shell=True,
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

        threading.Thread(
            target=stdin_write,
            args=(lines, process.stdin),
            daemon=True,
        ).start()

        keyboard_interrupt = False
        try:
            with process.stdout:
                for line in process.stdout:
                    yield line.rstrip('\n')
        except KeyboardInterrupt:
            keyboard_interrupt = True
            raise
        finally:
            returncode = process.wait()
            if keyboard_interrupt:
                pass
            elif returncode != 0:
                import shlex

                message = (
                    f"linesieve pipe: {shlex.split(command)[0]} "
                    f"exited with status code {returncode}"
                )
                secho(message, fg='red', err=True)

    pipe.is_iter = True
    return pipe


def stdin_write(lines, file):
    with handle_broken_pipe(), file, handle_broken_pipe():
        for line in lines:
            file.write(line)
            file.write('\n')


@contextmanager
def handle_broken_pipe():
    # https://github.com/python/cpython/blob/3.11/Lib/subprocess.py#L1138
    try:
        yield
    except BrokenPipeError:
        pass
    except OSError as exc:
        if exc.errno == errno.EINVAL:
            pass
        else:
            raise


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
    '--start', '--start-with', type=OPTIONS_REGEX, help="Span start (inclusive)."
)
@click.option('--end', '--end-before', type=OPTIONS_REGEX, help="Span end (exclusive).")
@OPTIONS_REGEX.add_options
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
    empty_match = re.search('.*', '')

    def match_span(lines):
        in_span = False
        in_span_changed = True

        for line in lines:
            start_match = start.search(line) if start else None

            if start and start_match:
                if not in_span:
                    in_span = True
                    in_span_changed = True
            elif end and end.search(line):
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

    For parsing structured data, see `linesieve parse`.

    """
    # we cannot have both `match PATTERN` and  `match -e PATTERN -e PATTERN`
    # because of click limitations on chained commands;
    # acceptable, `parse -e PATTERN ...` can offer similar functionality

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
@OPTIONS_REGEX.add_options
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
@click.pass_context
def split(
    ctx,
    delimiter,
    fixed_strings,
    ignore_case,
    verbose,
    max_split,
    fields,
    output_delimiter,
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
        param = next(p for p in ctx.command.params if p.name == 'delimiter')
        pattern = OPTIONS_REGEX.convert(delimiter, param, ctx)
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


@cli.command(short_help="Parse structured data.")
@click.option(
    '-e',
    '--regexp',
    'patterns',
    type=OPTIONS_REGEX,
    required=True,
    multiple=True,
    help="Use PATTERN as the pattern; multiple patterns are tried in order.",
)
@OPTIONS_REGEX.add_options
@click.option('-o', '--only-matching', is_flag=True, help="Output only matching lines.")
@click.option(
    '--json',
    is_flag=True,
    help="""
    Output groups as JSON instead of tab-separated values.
    Output one JSON value per line,
    either a JSON object (if named groups are used)
    or a JSON array (otherwise).
    """,
)
@section_option
def parse(patterns, fixed_strings, ignore_case, verbose, only_matching, json):
    """Parse lines into structured data.

    If the -e PATTERN uses named groups,
    output the groups as name-value pairs
    (unnamed groups are ignored):

    \b
        $ echo +1a+ | linesieve parse -e '(?P<one>\\d)(?P<two>\\w)'
        one	1	two	a

    If there are only groups without names, output all the groups:

    \b
        $ echo +1a+ | linesieve parse -e '(\\d)(\\w)'
        1	a

    If there are no groups, output the entire match.

    If mutiple patterns are specified, they are tried in order,
    and the first matching one is used.
    If no pattern matched, the line is output as-is.

    By default, both names and values are tab-separated.
    You can output JSON using the `--json` option:

    \b
        $ echo +1a+ | linesieve parse --json -e '(?P<one>\\d)(?P<two>\\w)'
        {"one": "1", "two": "a"}
        $ echo +1a+ | linesieve parse --json -e '(\\d)(\\w)'
        ["1", "a"]

    For matching groups with names of the form `<name>__<new_value>`,
    `name` is used as name and `new_value` as value,
    ignoring the actual group value.
    This can be used to tell which of multiple -e patterns matched,
    or to assign symbolic values to groups:

    \b
        $ linesieve parse \\
        > -e '(?P<event__get>)got (?P<count>\\d+) thing' \\
        > -e '(?x) (?P<event__send>) (
        >   (?P<status__ok>sent) |
        >   (?P<status__fail>could \\s+ not \\s+ send)
        > )' \\
        > --json << EOF
        got 10 things
        sent the things
        could not send the things
        EOF
        {"event": "get", "count": "10"}
        {"event": "send", "status": "ok"}
        {"event": "send", "status": "fail"}

    """
    # we cannot have both `parse PATTERN` and  `parse -e PATTERN -e PATTERN`
    # because of click limitations on chained commands;
    # we chose `-e` because we want to be able to try multiple patterns in a
    # single invocation (repeating the command doesn't make sense with -o)

    if not json:
        from itertools import chain

        def render_dict(data):
            return '\t'.join(v or '' for v in chain.from_iterable(data.items()))

        def render_list(data):
            return '\t'.join(v or '' for v in data)

    else:
        from json import dumps as json_dumps

        render_dict = render_list = json_dumps

    has_dunder = {p: any('__' in k for k in p.groupindex) for p in patterns}

    def processor(line):
        for pattern in patterns:
            match = pattern.search(line)
            if not match:
                continue
            if groupdict := match.groupdict():
                if has_dunder[pattern]:
                    groupdict = rewrite_dunders(groupdict)
                return render_dict(groupdict)
            return render_list(match.groups() or [match.group()])
        else:
            if not only_matching:
                return line
            return None

    return processor


def rewrite_dunders(groupdict):
    rv = {}
    for key, value in groupdict.items():
        if '__' in key:
            key, _, maybe_value = key.partition('__')
            # first key has priority
            if rv.get(key) is not None:
                continue
            if value is not None:
                value = maybe_value
        rv[key] = value
    return rv


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
