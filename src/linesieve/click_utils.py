import re
from contextlib import contextmanager

import click
from click import style


class InitialArgsMixin:
    @contextmanager
    def make_context(self, prog_name, args, **extra):
        initial_args = tuple(args)
        with super().make_context(prog_name, args, **extra) as ctx:
            ctx.initial_args = initial_args
            yield ctx


class EpilogSectionsMixin:
    def __init__(self, *args, epilog_sections=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.epilog_sections = dict(epilog_sections or ())

    def format_epilog(self, ctx, formatter):
        for name, text in self.epilog_sections.items():
            with formatter.section(name):
                formatter.write_text(text)
        super().format_epilog(ctx, formatter)


class OrderedCommandsMixin:
    def list_commands(self, ctx):
        return self.commands


class Group(InitialArgsMixin, EpilogSectionsMixin, OrderedCommandsMixin, click.Group):
    pass


def color_help(text):
    KWARGS = {
        'dim': dict(dim=True),
        'bold': dict(bold=True),
        'red': dict(fg='red'),
        'green': dict(fg='green'),
        'yellow': dict(fg='yellow'),
    }

    def repl(match):
        line, options = match.groups()
        kwargs = {}
        for option in options.split():
            kwargs.update(KWARGS[option])
        return style(line, **kwargs)

    options_re = '|'.join(map(re.escape, KWARGS))
    line_re = f"(.*)#((?: +(?:{options_re}))+ *)$"

    return re.sub(line_re, repl, text, flags=re.M)


class ManFormatter(click.HelpFormatter):
    def __init__(self):
        super().__init__(4, max_width=999999)
        # print(self.width)

    def write_dl(self, rows, col_max=30, col_spacing=2):
        """Write the options definition after the term, indented.

        col_max and col_spacing are ignored.

        """
        # for reasons (click bug?), the original write_dl() will spill over
        # if indenting more than once (worsened by indent_increment > 2);
        # this does not happen with our implementation

        for i, (first, second) in enumerate(rows, 1):
            self.write_text(first)
            with self.indentation():
                self.write_text(second)
            if i != len(rows):
                self.write_paragraph()

    def write_usage(self, prog, args='', prefix='Usage: '):
        if prefix is not None:
            prefix = style(prefix, bold=True)

        self.write(f"{'':>{self.current_indent}}")
        super().write_usage(prog, args, prefix)

    def write_heading(self, heading):
        heading = style(heading, bold=True)
        self.write(f"{'':>{self.current_indent}}{heading}\n")

    @contextmanager
    def supersection(self, name, short=None):
        title = style(name.upper(), bold=True)
        if short:
            title += style(' - ' + short, dim=True)

        self.write(title)
        self.write_paragraph()
        self.write_paragraph()

        with self.indentation():
            yield

        self.write_paragraph()


def format_help_all(ctx):
    formatter = ManFormatter()
    commands = list_commands_recursive(ctx.command, ctx)

    for path, command in commands:
        short = command.get_short_help_str(limit=55)
        if short:
            first = short.partition(' ')[0]
            if first.istitle():
                short = first.lower() + short[len(first) :]
            short = short.rstrip('.')

        if command is ctx.command:
            format_ctx = ctx
        else:
            format_ctx = type(ctx)(command, ctx, command.name)

        with formatter.supersection(' '.join(path), short):
            command.format_help(format_ctx, formatter)

    return formatter.getvalue()


def list_commands_recursive(self, ctx, path=()):
    path = path + (self.name,)
    yield path, self
    if not hasattr(self, 'list_commands'):
        return
    for subcommand in self.list_commands(ctx):
        cmd = self.get_command(ctx, subcommand)
        if cmd is None:
            continue
        if cmd.hidden:
            continue
        yield from list_commands_recursive(cmd, ctx, path)
