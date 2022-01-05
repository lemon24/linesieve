import pytest
import os.path
import glob
import pathlib

from click.testing import CliRunner

from linesieve import cli

ROOT = pathlib.Path(__file__).parent


DATA = sorted(ROOT.glob('data/*.in'))

@pytest.fixture(params=DATA, ids=lambda p: p.name)
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
