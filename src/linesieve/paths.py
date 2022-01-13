import os.path
import re


def shorten_paths(paths, sep, ellipsis):
    shortened = {path: path.split(sep) for path in paths}

    _do_end(shortened.values(), 0, -1)

    for original, mask in shortened.items():

        path = []
        for ps, ms in zip(original.split(sep), mask):

            if ms is None:
                path.append(ps)
            else:
                if not path or path[-1] != ellipsis:
                    path.append(ellipsis)

        shortened[original] = sep.join(path)

    return shortened


def _do_end(paths, start, end):
    groups = {}
    for path in paths:
        groups.setdefault(path[end], []).append(path)

    for group in groups.values():
        for path in group:
            path[end] = None

        if len(group) == 1:
            continue

        _do_start(group, start, end - 1)


def _do_start(paths, start, end):
    groups = {}
    for path in paths:
        groups.setdefault(path[start], []).append(path)

    for group in groups.values():
        if len(groups) > 1:
            for path in group:
                path[start] = None

        if len(group) == 1:
            continue

        _do_end(group, start + 1, end)


def paths_to_modules(paths, newsep='.', skip=0, recursive=False):
    min_length = 2
    modules = set()

    for path in paths:
        parts = os.path.splitext(os.path.normpath(path))[0].split(os.sep)[skip:]
        if len(parts) < min_length:
            continue

        start = min_length if recursive else len(parts)
        for i in range(start, len(parts) + 1):
            candidate = parts[:i]
            if len(candidate) < 2:
                continue

            modules.add(newsep.join(candidate))

    return modules


NON_PATH_CHARS = r'[\s"\':]'
NON_PATH_START = fr"(?:^|(?<={NON_PATH_CHARS}))"
NON_PATH_END = fr"(?:(?={NON_PATH_CHARS})|$)"


def make_dir_path_re(*paths):
    paths = sorted(paths, key=lambda p: -len(p))
    sep = re.escape(os.sep)
    return re.compile(
        fr"""
        {NON_PATH_START}
        { '|'.join(map(re.escape, paths)) }
        (?:
            ( {sep} ? {NON_PATH_END} )
            |
            ( {sep} (?! {NON_PATH_CHARS} ) )
        )
        """,
        re.VERBOSE,
    )


def make_file_paths_re(paths, modules=()):
    patterns = []

    paths = sorted(paths, key=lambda p: -len(p))
    if paths:
        patterns.append(
            fr"""
            {NON_PATH_START}
            (?: {'|'.join(map(re.escape, paths))} )
            {NON_PATH_END}
            """
        )

    modules = sorted(modules, key=lambda p: -len(p))
    if modules:
        patterns.append(
            fr"""
            (?:^|\b)
            (?: { '|'.join(map(re.escape, modules)) } )
            (?:\b|$)
            """
        )

    return re.compile('\n|\n'.join(patterns), re.VERBOSE)
