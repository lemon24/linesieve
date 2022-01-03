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
            yield ok, label
            break

        if label:
            section = label
            continue
        
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
        yield section, map(get_one, lines)


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


def do_output(groups, section_dot='.', no_section='<no-section>'):
    prev_section = None
    last_was_dot = False

    for section, lines in groups:

        if section == '' and prev_section is not None:
            echo(style(section_dot, dim=True), err=True, nl=False)
            last_was_dot = True

        if last_was_dot:
            echo(err=True)
            last_was_dot = False

        if section in {True, False, None}:
            if section is True:
                echo(style(next(lines), fg='green'), err=True)
            elif section is False:
                echo(style(next(lines), fg='red'), err=True)
            else:
                echo(style(
                    f"unexpected end during {style(prev_section or no_section, bold=True)}", 
                    fg='red'
                ), err=True)
            return section

        if section:
            echo(style(section, dim=True), err=True)

        for line in lines:
            echo(line)

        prev_section = section


def pattern_option(*param_decls):
    return click.option(
        *param_decls, 
        default='$nothing',
        show_default=True, 
        metavar='PATTERN',
    )


@click.group(chain=True, invoke_without_command=True)
@pattern_option('--section')
@pattern_option('--success')
@pattern_option('--failure')
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

    tokens = tokenize(file, section, success, failure)
    
    if show is None:
        show_pred = lambda _: True
    else:
        show_pred = show.__contains__

    groups = group_by_section(tokens, show_pred)
    groups = apply_filters(groups, [p for p in processors if p])
    groups = dedupe_blanks(groups)
    status = do_output(groups)
    
    if process:
        process.wait()
        ctx.exit(process.returncode)
    else:
        ctx.exit(0 if status else 1)

    # TODO:
    # cwd replace (doable via sub, document)
    # symlink replace (doable via sub, document)
    # per-section filters
    # path replace / color
    # class replace / color
    # cli (polish)


@cli.command()
@click.argument('section')
@click.pass_obj
def show(obj, section):
    # TODO: show --fixed-strings section
    obj.setdefault('show', []).append(section)


@cli.command()
@click.option('-o', '--only', is_flag=True, help="Print only lines that match PATTERN.")
@click.option('-F', '--fixed-strings', is_flag=True)
@click.argument('pattern')
@click.argument('repl')
def sub(pattern, repl, only, fixed_strings):
    if fixed_strings:
            
        def sub(line):
            if only and pattern not in line:
                return None
            return line.replace(pattern, repl)
        
    else:
        pattern_re = re.compile(pattern)
            
        def sub(line):
            line, subn = pattern_re.subn(repl, line)
            if only and not subn:
                return None
            return line
        
    return sub


@cli.command()
@click.option('-F', '--fixed-strings', is_flag=True)
@click.argument('pattern')
def search(pattern, fixed_strings):
    if fixed_strings:
        
        def search(line):
            return pattern in line

    else:
        pattern_re = re.compile(pattern)

        def search(line):
            return bool(pattern_re.search(line))

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







