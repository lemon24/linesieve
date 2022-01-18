import pathlib
import shlex
from textwrap import dedent

import pytest
from click.testing import CliRunner

from linesieve.cli import cli


ROOT = pathlib.Path(__file__).parent


def load_data(root):
    for path in sorted(root.glob('data/*.in')):
        with path.open() as f:
            args = shlex.split(next(f).rstrip())
            input = f.read()
        with path.with_suffix('.out').open() as f:
            output = f.read()

        yield path.name, (args, input, output)

        args_with_color = []
        for arg in args:
            args_with_color.append(arg)
            if arg in {'sub', 'match'}:
                args_with_color.append('--color')

        if args_with_color != args:
            yield path.name + '--color', (args_with_color, input, output)


DATA = dict(load_data(ROOT))


@pytest.mark.parametrize('args, input, output', list(DATA.values()), ids=list(DATA))
def test_data(args, input, output):
    runner = CliRunner()
    result = runner.invoke(cli, args, input, catch_exceptions=False)
    assert result.output == output


def test_sub_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    input = dedent(
        f"""\
        {tmp_path}
        {tmp_path}/
        {tmp_path}/one
        "{tmp_path}"
        '{tmp_path}/'
        a {tmp_path} z
        \t{tmp_path}/\t
        abc{tmp_path}
        ab-{tmp_path}
        {tmp_path}xyz
        {tmp_path}-yz
        """
    )

    runner = CliRunner()
    result = runner.invoke(cli, 'sub-cwd', input, catch_exceptions=False)

    assert result.output == dedent(
        f"""\
        .
        .
        one
        "."
        '.'
        a . z
        \t.\t
        abc{tmp_path}
        ab-{tmp_path}
        {tmp_path}xyz
        {tmp_path}-yz
        """
    )


def test_sub_link(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    dirs = "one/two/three/four"
    dirs_path = tmp_path.joinpath(dirs)
    dirs_path.mkdir(parents=True)
    tmp_path.joinpath('link').symlink_to(dirs_path)

    # not testing path boundaries, it's already covered in test_sub_cwd()

    input = dedent(
        f"""\
        {tmp_path}/{dirs}
        {tmp_path}/{dirs}/
        {tmp_path}/{dirs}/five
        """
    )

    runner = CliRunner()
    result = runner.invoke(cli, 'sub-link link', input, catch_exceptions=False)

    assert result.output == dedent(
        """\
        link
        link
        link/five
        """
    )


SUB_PATHS = """
src/package/subpackage/__init__.py
src/package/subpackage/module.py
src/package/subpackage/py.typed
tst/test.py
""".split()


SUB_PATHS_DATA = [
    ('', path, None)
    for path in """
        src/package
        src/package/none.py
        src/package/subpackage
        src/package/subpackage/py.typed
        package.subpackage.module
        src.package.subpackage.module
        tst.test
    """.split()
] + [
    ('', 'src/package/subpackage/module.py', '.../module.py'),
    ('', 'tst/test.py', '.../test.py'),
    ('--modules', 'package.subpackage.module', None),
    ('--modules', 'src.package.subpackage', None),
    ('--modules', 'src.package.subpackage.module', '..module'),
    ('--modules', 'tst.test', '..test'),
    ('--modules-skip 1', 'package.subpackage.module', '..module'),
    ('--modules-skip 1', 'package.subpackage', None),
    ('--modules-skip 1', 'test', None),
    ('--modules-skip 1', 'tst.test', None),
    ('--modules-skip 1 --modules-recursive', 'package.subpackage.module', '..module'),
    ('--modules-skip 1 --modules-recursive', 'package.subpackage', '..subpackage'),
    ('--modules-skip 1 --modules-recursive', 'tst.test', None),
    # boundaries
    ('', ' tst/test.py', ' .../test.py'),
    ('', 'atst/test.py', 'atst/test.py'),
    ('', '-tst/test.py', '-tst/test.py'),
    ('', 'tst/test.py.gz', 'tst/test.py.gz'),
    ('', 'tst/test.pyi', 'tst/test.pyi'),
    ('', '"tst/test.py"', '".../test.py"'),
    ('--modules', ' tst.test', ' ..test'),
    ('--modules', 'atst.test', 'atst.test'),
    ('--modules', 'tst.testz', 'tst.testz'),
    ('--modules', '-tst.test', '-..test'),
    ('--modules', 'tst.test-', '..test-'),
    ('--modules', '_tst.test', '_tst.test'),
    ('--modules', 'tst.test_', 'tst.test_'),
    ('--modules', '"tst.test"', '"..test"'),
    ('--modules', 'nope.tst.test', 'nope...test'),
    ('--modules', 'tst.test.nope', '..test.nope'),
]


@pytest.mark.parametrize('options, input, output', SUB_PATHS_DATA)
def test_sub_paths(tmp_path, monkeypatch, options, input, output):
    monkeypatch.chdir(tmp_path)

    for path in SUB_PATHS:
        path = tmp_path.joinpath(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        "sub-paths --include '{src,tst}/**/*.py' " + options,
        input,
        catch_exceptions=False,
    )

    if output is None:
        output = input

    assert result.output.rstrip('\n') == output
