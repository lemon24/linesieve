import pytest
import os.path
import glob
import pathlib

from linesieve import tokenize, group_by_section, do_output

ROOT = pathlib.Path(__file__).parent

DATA_FILES = [
    (path, os.path.splitext(path)[0] + '.out')
    for path in sorted(glob.glob(os.path.join(ROOT, 'data/*.in')))
]

@pytest.fixture(scope="module", params=DATA_FILES, ids=lambda t: os.path.basename(t[0]))
def input_output(request):
    inp, outp = request.param
    with open(inp) as inf, open(outp) as outf:
        yield inf, outf

def test_data(input_output, capsys):
    input, output = input_output
    expected_output = output.read()
    
    tokens = tokenize(input, '(\S+):$', 'good end', 'bad end')
    groups = group_by_section(tokens, {'two'}.__contains__)
    do_output(groups)
    
    captured = capsys.readouterr()
    assert captured.out == expected_output
