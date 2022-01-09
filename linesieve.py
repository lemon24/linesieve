import re
from itertools import chain, groupby
from dataclasses import dataclass
from operator import itemgetter
import subprocess
from glob import glob
from functools import wraps
import os
import os.path

import click
from click import echo, style


def annotate_lines(lines, section_pattern, success_pattern, failure_pattern):
    """Annotate lines with their corresponding section.
    Stop when encountering a success/failure marker.

    The section and success/failure markers are considered to be one line.

    Yield (section, line) pairs, one for each content line.
    If a section is empty, yield exactly one (section, None) pair.
    The first section is always '', meaning "no section, yet".

    At the end, yield exactly one of:

    * (True, label), if the success pattern matched
    * (False, label), if the failure pattern matched
    * (None, None), if the lines ended before any of the above matched

    The section and label are:

    * the group named 'name', if any
    * the first captured group, if any
    * the entire match, otherwise

    >>> lines = ['0', 'one:', '1', 'two:', 'three:', '3', 'end']
    >>> list(annotate_lines(lines, '(.*):$', 'end', '$nothing'))
    [('', '0'), ('one', '1'), ('two', None), ('three', '3'), (True, 'end')]

    >>> list(annotate_lines([], '$nothing', '$nothing', '$nothing'))
    [('', None), (None, None)]

    """
    section_re = re.compile(section_pattern)
    success_re = re.compile(success_pattern)
    failure_re = re.compile(failure_pattern)

    done = False
    ok = None
    section = ''
    yielded_lines = False
    for line in chain(lines, [None]):
        if line is not None:
            line = line.rstrip()

        match = None
        label = None

        if line is None:
            done = True
        elif match := failure_re.search(line):
            done = True
            ok = False
        elif match := success_re.search(line):
            done = True
            ok = True
        elif match := section_re.search(line):
            pass

        if match:
            if not match.re.groups:
                label = match.group()
            elif 'name' in match.re.groupindex:
                label = match.group('name')
            elif match.re.groups == 1:
                label = match.group(1)

        if done:
            if not yielded_lines:
                yield section, None
            yield ok, label
            break

        if label:
            if not yielded_lines:
                yield section, None
            section = label
            yielded_lines = False
            continue

        yielded_lines = True
        yield section, line


def group_by_section(pairs):
    """Group annotate_lines() output into (section, lines) pairs.

    >>> pairs = [('', '0'), ('', '1'), ('section', None), (True, 'end')]
    >>> groups = group_by_section(pairs)
    >>> [(s, list(ls)) for s, ls in groups]
    [('', ['0', '1']), ('section', []), (True, ['end'])]

    """
    get_one = itemgetter(1)

    for section, group in groupby(pairs, itemgetter(0)):
        lines = map(get_one, group)
        first = next(lines, None)

        if first is None:
            yield section, ()
            continue

        yield section, chain([first], lines)


def filter_sections(groups, predicate, last_before={None, False}):
    """Filter (section, lines) pairs.

    If predicate(section) is true, yield the pair as-is.
    If predicate(section) is false, yield ('', ()) instead.

    If the last section is False or None,
    and the section before-last did not match the predicate,
    yield the before-last pair (again) as-is before the last one.

    >>> groups = [('1', 'i'), ('two', 'ii'), ('three', 'iii'), (None, '')]
    >>> groups = filter_sections(groups, str.isdigit)
    >>> list(groups)
    [('1', 'i'), ('', ()), ('', ()), ('three', ['i', 'i', 'i']), (None, '')]

    """
    previous = None

    for section, lines in groups:
        if section in {True, False, None}:
            if section in last_before and previous is not None:
                yield previous
            yield section, lines
            break

        if predicate(section):
            yield section, lines
            previous = None
        else:
            yield '', ()
            previous = section, list(lines)


def filter_lines(groups, get_filters):
    """Filter the lines in (section, lines) pairs.

    >>> groups = [('one', 'a1B2')]
    >>> groups = filter_lines(groups, lambda _: [str.isalpha, str.upper])
    >>> [(s, list(ls)) for s, ls in groups]
    [('one', ['A', 'B'])]

    """
    def filter_lines(lines, filters):
        for line in lines:
            for filter in filters:
                rv = filter(line)
                if rv is True:
                    continue
                if rv is False:
                    line = None
                else:
                    line = rv
                if line is None:
                    break
            if line is not None:
                yield line

    for section, lines in groups:
        if section not in {True, False, None}:
            filters = list(get_filters(section))
            if filters:
                lines = filter_lines(lines, filters)
        yield section, lines


def dedupe_blank_lines(groups):
    """Deduplicate blank lines in (section, lines) pairs.

    >>> groups = [('one', ['', '1', '', '', '', '2', ''])]
    >>> groups = dedupe_blank_lines(groups)
    >>> [(s, list(ls)) for s, ls in groups]
    [('one', ['1', '', '2', ''])]

    """
    def dedupe(lines):
        prev_line = ''
        for line in lines:
            stripped = line.strip()
            if not (prev_line == line.strip() == ''):
                yield line
            prev_line = stripped

    for section, lines in groups:
        if section not in {True, False, None}:
            lines = dedupe(lines)
        yield section, lines


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
            echo(style(section, dim=True), err=True)

        line = next(lines, None)
        if line:
            if last_was_dot:
                echo(err=True)
                last_was_dot = False
            echo(line)

        for line in lines:
            echo(line)

        prev_section = section


# -s --section --section-start
# -e --section-end
# -n --section-name # same as annotate_lines() marker

@click.group(chain=True, invoke_without_command=True)
@click.option('-s', '--section', metavar='PATTERN')
@click.option('--success', metavar='PATTERN')
@click.option('--failure', metavar='PATTERN')
@click.pass_context
def cli(ctx, **kwargs):
    ctx.obj = {}


MATCH_NOTHING = '$nothing'

@cli.result_callback()
@click.pass_context
def process_pipeline(ctx, processors, section, success, failure):
    file = ctx.obj.get('file')
    if not file:
        file = click.get_text_stream('stdin')

    process = ctx.obj.get('process')

    show = ctx.obj.get('show')

    pairs = annotate_lines(
        file,
        section if section is not None else MATCH_NOTHING,
        success if success is not None else MATCH_NOTHING,
        failure if failure is not None else MATCH_NOTHING,
    )
    groups = group_by_section(pairs)

    if show is None:
        def show_section(section):
            return True
    else:
        def show_section(section):
            return any(p.search(section) for p in show)

    last_before = {False}
    if success is not None and failure is not None:
        last_before.add(None)

    groups = filter_sections(groups, show_section, last_before)

    processors = [p for p in processors if p]

    def get_filters(section):
        for section_re, filter in processors:
            if not section_re or section_re.search(section):
                yield filter

    groups = filter_lines(groups, get_filters)
    groups = dedupe_blank_lines(groups)
    status, label = output_sections(groups)

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
            message = style(f"unexpected end during {style(label, bold=True)}", fg='red')
            returncode = 1

    if message:
        echo(message, err=True)

    if process:
        process.wait()
        returncode = process.returncode
        if not message:
            message = style(
                f"command returned exit code {style(str(returncode), bold=True)}",
                fg=('green' if returncode == 0 else 'red')
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

    # TODO:
    # cwd replace (doable via sub, easier to do here)
    # symlink replace (doable via sub, easier to do here)
    # (maybe) runfilter "grep pattern"
    # cli (polish; short command aliases)


def pattern_argument(fn):

    @click.option('-F', '--fixed-strings', is_flag=True)
    @click.option('-i', '--ignore-case', is_flag=True)
    @click.argument('PATTERN')
    @wraps(fn)
    def wrapper(*args, pattern, fixed_strings, ignore_case, **kwargs):
        if fixed_strings:
            pattern = re.escape(pattern)

        flags = 0
        if ignore_case:
            flags |= re.IGNORECASE

        pattern_re = re.compile(pattern, flags)

        return fn(*args, pattern=pattern_re, fixed_strings=fixed_strings, **kwargs)

    return wrapper


def section_option(fn):

    @click.option('-s', '--section', metavar='PATTERN')
    @wraps(fn)
    def wrapper(*args, section, **kwargs):
        rv = fn(*args, **kwargs)
        if rv is None:
            return None
        section_re = re.compile(section) if section is not None else None
        return section_re, rv

    return wrapper


@cli.command()
@pattern_argument
@click.pass_obj
def show(obj, pattern, fixed_strings):
    obj.setdefault('show', []).append(pattern)


@cli.command()
@pattern_argument
@click.argument('repl')
@click.option('-o', '--only-matching', is_flag=True, help="Print only lines that match PATTERN.")
@section_option
def sub(pattern, repl, fixed_strings, only_matching):
    if fixed_strings:
        repl = repl.replace('\\', r'\\')

    def sub(line):
        line, subn = pattern.subn(repl, line)
        if only_matching and not subn:
            return None
        return line

    return sub


@cli.command()
@pattern_argument
@click.option('-o', '--only-matching', is_flag=True, help="Prints only the matching part of the lines.")
@click.option('-v', '--invert-match', is_flag=True)
@section_option
def match(pattern, fixed_strings, invert_match, only_matching):

    def search(line):
        if not only_matching:
            if bool(pattern.search(line)) is not invert_match:
                return line
            return None
        else:
            matches = pattern.findall(line)
            if matches:
                return '\n'.join(matches)
            return None

    return search


@cli.command()
@click.argument('file', type=click.File('r', lazy=True))
@click.pass_obj
def open(obj, file):
    assert not obj.get('file')
    obj['file'] = file


@cli.command()
@click.argument('command')
@click.argument('argument', nargs=-1)
@click.pass_obj
def run(obj, command, argument):
    assert not obj.get('file')
    process = subprocess.Popen(
        (command,) + argument,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    obj['process'] = process
    obj['file'] = process.stdout


def shorten_paths(paths, sep, ellipsis):
    shortened = {l: l.split(sep) for l in paths}

    _do_end(shortened.values(), 0, -1)

    for original, mask in shortened.items():

        path = []
        for ps, ms in zip(original.split(sep), mask):

            if ms is None:
                path.append(ps)
            else:
                if not path or path[-1] != ellipsis:
                    path.append(ellipsis)

        shortened[original] = sep.join(path)

    return shortened


def _do_end(paths, start, end):
    groups = {}
    for path in paths:
        groups.setdefault(path[end], []).append(path)

    for group in groups.values():
        for path in group:
            path[end] = None

        if len(group) == 1:
            continue

        _do_start(group, start, end-1)


def _do_start(paths, start, end):
    groups = {}
    for path in paths:
        groups.setdefault(path[start], []).append(path)

    for group in groups.values():
        if len(groups) > 1:
            for path in group:
                path[start] = None

        if len(group) == 1:
            continue

        _do_end(group, start+1, end)


def paths_to_modules(paths, newsep='.', skip=0, recursive=False):
    min_length = 2
    modules = set()

    for path in paths:
        parts = os.path.splitext(os.path.normpath(path))[0].split(os.sep)[skip:]
        if len(parts) < min_length:
            continue

        start = min_length if recursive else len(parts)
        for i in range(start, len(parts) + 1):
            candidate = parts[:i]
            if len(candidate) < 2:
                continue

            modules.add(newsep.join(candidate))

    return modules


@cli.command()
@click.option('--include', multiple=True, metavar='GLOB')
@click.option('--modules', is_flag=True)
@click.option('--modules-skip', type=click.IntRange(0), default=0, show_default=True)
@click.option('--modules-recursive', is_flag=True)
@section_option
def sub_paths(include, modules, modules_skip, modules_recursive):
    # TODO: use braceexpand for path

    paths = [p for g in include for p in glob(g, recursive=True)]
    replacements = shorten_paths(paths, os.sep, '...')

    if modules:
        modules = paths_to_modules(paths, skip=modules_skip, recursive=modules_recursive)
        replacements.update(shorten_paths(modules, '.', '.'))

    for k, v in replacements.items():
        replacements[k] = style(v, fg='yellow')

    replacements = dict(sorted(replacements.items(), key=lambda p: -len(p[0])))

    # dead code, likely slow

    def sub(line):
        for old, new in replacements.items():
            line = line.replace(old, new)
        return line

    # ...maybe this is faster? can still be improved
    # * collapse common prefixes (maybe re.compile() already does that)
    # * have a single pattern per run, not per sub-paths invocation

    pattern_re = re.compile('|'.join(r'\b' + re.escape(r) + r'\b' for r in replacements))

    def repl(match):
        return replacements[match.group(0)]

    def sub(line):
        return pattern_re.sub(repl, line)


    return sub


if __name__ == '__main__':
    cli()


