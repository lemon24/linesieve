import pathlib

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
