#!/bin/bash
#
# usage: ./run.sh command [argument ...]
#
# See https://death.andgravity.com/run-sh for how this works.

set -o nounset
set -o pipefail
set -o errexit

PROJECT_ROOT=${0%/*}
if [[ $0 != $PROJECT_ROOT && $PROJECT_ROOT != "" ]]; then
    cd "$PROJECT_ROOT"
fi
readonly PROJECT_ROOT=$( pwd )


function install-dev {
    pip install -e '.[tests,dev]'
    pre-commit install
}


function test {
    pytest "$@"
}

function coverage {
    pytest --cov
    coverage html
}

"$@"
