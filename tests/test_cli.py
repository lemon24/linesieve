import pathlib
from textwrap import dedent

import pytest
from click.testing import CliRunner

from linesieve.cli import cli


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
