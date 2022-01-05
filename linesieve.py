import re
from itertools import chain, groupby
from dataclasses import dataclass
from operator import itemgetter
import subprocess
from glob import glob
import os

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


def filter_sections(groups, predicate):
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
            if not section and previous is not None:
                yield previous
            yield section, lines
            break

        if predicate(section):
            yield section, lines
            previous = None
        else:
            yield '', ()
            previous = section, list(lines)


def filter_lines(groups, filters):
    """Filter the lines in (section, lines) pairs.

    >>> groups = [('one', 'a1B2')]
    >>> groups = filter_lines(groups, [str.isalpha, str.upper])
    >>> [(s, list(ls)) for s, ls in groups]
    [('one', ['A', 'B'])]

    """
    def filter_lines(lines):
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
            lines = filter_lines(lines)
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

        for line in lines:
            echo(line)

        prev_section = section


MATCH_NOTHING = '$nothing'

@click.group(chain=True, invoke_without_command=True)
@click.option('-s', '--section', metavar='PATTERN')
@click.option('-k', '--success', metavar='PATTERN')
@click.option('-f', '--failure', metavar='PATTERN')
@click.pass_context
def cli(ctx, **kwargs):
    ctx.obj = {}

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

    groups = filter_sections(groups, show_section)
    groups = filter_lines(groups, [p for p in processors if p])
    groups = dedupe_blank_lines(groups)
    status, label = output_sections(groups)

    if status is True:
        echo(style(label, fg='green'), err=True)
    if status is False:
        echo(style(label, fg='red'), err=True)
    if status is None:
        label = label or '<no-section>'
        # TODO: this is unexpected/red only if we have success and/or failure
        echo(style(f"unexpected end during {style(label, bold=True)}", fg='red'), err=True)

    if process:
        process.wait()
        ctx.exit(process.returncode)
    else:
        ctx.exit(0 if status else 1)

    # TODO:
    # cwd replace (doable via sub, easier to do here)
    # symlink replace (doable via sub, easier to do here)
    # per-section filters
    # cli (polish; short command aliases)


@cli.command()
@click.option('-F', '--fixed-strings', is_flag=True)
@click.option('-i', '--ignore-case', is_flag=True)
@click.argument('PATTERN')
@click.pass_obj
def show(obj, pattern, fixed_strings, ignore_case):
    if fixed_strings:
        pattern = re.escape(pattern)

    flags = 0
    if ignore_case:
        flags |= re.IGNORECASE

    pattern_re = re.compile(pattern, flags)

    obj.setdefault('show', []).append(pattern_re)


@cli.command()
@click.option('-o', '--only-matching', is_flag=True, help="Print only lines that match PATTERN.")
@click.option('-F', '--fixed-strings', is_flag=True)
@click.option('-i', '--ignore-case', is_flag=True)
@click.argument('pattern')
@click.argument('repl')
def sub(pattern, repl, only_matching, fixed_strings, ignore_case):
    if fixed_strings:
        pattern = re.escape(pattern)

    flags = 0
    if ignore_case:
        flags |= re.IGNORECASE

    pattern_re = re.compile(pattern, flags)

    if fixed_strings:
        repl = repl.replace('\\', r'\\')

    def sub(line):
        line, subn = pattern_re.subn(repl, line)
        if only_matching and not subn:
            return None
        return line

    return sub


@cli.command()
@click.option('-F', '--fixed-strings', is_flag=True)
@click.option('-i', '--ignore-case', is_flag=True)
@click.argument('pattern')
def match(pattern, fixed_strings, ignore_case):
    if fixed_strings:
        pattern = re.escape(pattern)

    flags = 0
    if ignore_case:
        flags |= re.IGNORECASE

    pattern_re = re.compile(pattern, flags)

    def search(line):
        if pattern_re.search(line):
            return line
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


@cli.command()
@click.option('-p', '--path', multiple=True)
@click.option('--module', multiple=True)
def sub_paths(path, module):
    paths = [p for g in path for p in glob(g, recursive=True)]
    replacements = shorten_paths(paths, os.sep, '...')

    modules = set()
    for ext in module:
        ext = '.' + ext.lstrip('.')
        for p in paths:
            # TODO: depth should be configurable, assuming 1 for now
            parts = p.removesuffix(ext).split(os.sep)[1:]
            if not parts:
                continue
            for i in range(len(parts)):
                modules.add('.'.join(parts[:i+1]))

    if modules:
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

    pattern_re = re.compile('|'.join(map(re.escape, replacements)))

    def repl(match):
        return replacements[match.group(0)]

    def sub(line):
        return pattern_re.sub(repl, line)


    return sub


if __name__ == '__main__':
    cli()







