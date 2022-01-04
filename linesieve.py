import re
from itertools import chain, groupby
from dataclasses import dataclass
from operator import itemgetter
import subprocess

import click
from click import echo, style


def tokenize(it, section_pattern, success_pattern, failure_pattern):
    section_re = re.compile(section_pattern)
    success_re = re.compile(success_pattern)
    failure_re = re.compile(failure_pattern)

    done = False
    ok = None
    section = ''
    yielded_lines = False
    for line in chain(it, [None]):
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
            elif 'l' in match.re.groupindex:
                label = match.group('l')
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


def group_by_section(it, show):

    def groups():
        grouped = groupby(it, itemgetter(0))

        prev_lines = None
        for section, lines in grouped:
            if section in {True, False, None}:
                if not section and prev_lines is not None:
                    yield prev_lines[0][0], prev_lines
                yield section, lines
                break

            if show(section):
                yield section, lines
                prev_lines = None
            else:
                yield '', ()
                prev_lines = list(lines)

    get_one = itemgetter(1)

    for section, lines in groups():
        lines =  map(get_one, lines)

        first = next(lines, None)

        if first is None:
            yield section, ()
            continue

        yield section, chain([first], lines)


def dedupe_blanks(groups):

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


def apply_filters(groups, filters):

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


def output_lines(groups, section_dot='.'):
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
            return section, next(lines)

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

    tokens = tokenize(
        file,
        section if section is not None else MATCH_NOTHING,
        success if success is not None else MATCH_NOTHING,
        failure if failure is not None else MATCH_NOTHING,
    )

    if show is None:
        def show_section(section):
            return True
    else:
        def show_section(section):
            return any(p.search(section) for p in show)

    groups = group_by_section(tokens, show_section)

    groups = apply_filters(groups, [p for p in processors if p])
    groups = dedupe_blanks(groups)
    status, label = output_lines(groups)

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
    # path replace / color
    # class replace / color
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



if __name__ == '__main__':
    cli()







