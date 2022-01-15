*This is my text munging tool. There are many like it, but this one is mine.*

**linesieve** is an unholy blend of `grep`, `sed`, and `awk`,
with *very* specific features, born out of spite.


[![build](https://github.com/lemon24/linesieve/actions/workflows/build.yaml/badge.svg)](https://github.com/lemon24/linesieve/actions/workflows/build.yaml) [![codecov](https://codecov.io/gh/lemon24/linesieve/branch/main/graph/badge.svg?token=MrpEP5cg24)](https://codecov.io/gh/lemon24/linesieve) [![PyPI](https://img.shields.io/pypi/v/linesieve)](https://pypi.org/project/linesieve/) [![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Features

* line-oriented
* section-oriented
  * show only matching sections
  * show the failing section
* match/sub with the full power of [re](https://docs.python.org/3/library/re.html)
* chain filters into pipelines
* colors!
* TODO: specific filters

## Examples

### Get all options used by any git command

Note that some of the man pages contain multiple OPTIONS sections (e.g. ADVANCED OPTIONS).

```bash
export MANWIDTH=9999

function man-section {
    col -b | linesieve -s '^[A-Z ()-]+$' show "$@"
}

man git \
| man-section COMMANDS match -o '^ +(git-\w+)' \
| cat - <( echo git ) \
| sort | uniq \
| xargs -n1 man \
| man-section OPTIONS match -o '^ +(-.*)' \
    sub -F -- '--[no-]' '--' \
    sub -F -- '--no-' '--' \
| sort -dfu

```

Output:

```
-/ <path>
-, --stdin
-0
...
-a, --all
-A, --all, --ignore-removal
-a, --annotate
...
--autosquash, --autosquash
--autostash, --autostash
-b
-b, --branch
...
```

### TODO: Ant output
