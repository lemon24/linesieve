import pathlib
from textwrap import dedent

import pytest
from click.testing import CliRunner

from linesieve.cli import cli


def pxfail(*args):
    return pytest.param(*args, marks=pytest.mark.xfail(strict=True))


ROOT = pathlib.Path(__file__).parent
DATA_PATHS = sorted(ROOT.glob('data/*.in'))


@pytest.fixture(params=DATA_PATHS, ids=lambda p: p.name)
def data(request):
    inp = request.param
    outp = inp.with_suffix('.out')
    with inp.open() as inf, outp.open() as outf:
        return next(inf).rstrip(), inf.read(), outf.read()


def test_data(data):
    args, input, output = data
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
    (
        '--modules-skip 1',
        'tst.test',
        None,
    ),
    ('--modules-skip 1 --modules-recursive', 'package.subpackage.module', '..module'),
    ('--modules-skip 1 --modules-recursive', 'package.subpackage', '..subpackage'),
    ('--modules-skip 1 --modules-recursive', 'tst.test', None),
    # boundaries
    ('', ' tst/test.py', ' .../test.py'),
    ('', 'atst/test.py', 'atst/test.py'),
    pxfail('', '-tst/test.py', '-tst/test.py'),
    pxfail('', 'tst/test.py.gz', 'tst/test.py.gz'),
    ('', 'tst/test.pyi', 'tst/test.pyi'),
    pxfail('', '"tst/test.py"', '"../test.py"'),
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
