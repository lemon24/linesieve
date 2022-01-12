import re
from functools import lru_cache
from itertools import chain
from itertools import groupby
from operator import itemgetter


def make_pipeline(
    file,
    section_pattern,
    success_pattern,
    failure_pattern,
    section_filters,
    line_filters,
):
    groups = group_by_section(
        annotate_lines(file, section_pattern, success_pattern, failure_pattern)
    )

    if not section_filters:

        def show_section(section):
            return True

    else:

        def show_section(section):
            return any(p.search(section) for p in section_filters)

    end_is_failure = None not in {success_pattern, failure_pattern}
    groups = filter_sections(groups, show_section, end_is_failure)

    @lru_cache
    def get_filters(section):
        rv = []
        for section_re, filter in line_filters:
            if not section_re or section_re.search(section):
                rv.append(filter)
        return rv

    groups = filter_lines(groups, get_filters)
    groups = dedupe_blank_lines(groups)

    return groups


MATCH_NOTHING = '$nothing'


def annotate_lines(
    lines,
    section_pattern=None,
    success_pattern=None,
    failure_pattern=None,
):
    """Annotate lines with their corresponding section.
    Stop when encountering a success/failure marker.

    The section and success/failure markers are considered to be one line.

    Yield (section, line) pairs, one for each content line.
    If a section is empty, yield exactly one (section, None) pair.
    The first section is always '', meaning "no section, yet".

    At the end, yield exactly one of:

    * (True, label), if the success pattern matched
    * (False, label), if the failure pattern matched
    * (None, None), if the lines ended before any of the above matched

    The section and label are:

    * the group named 'name', if any
    * the first captured group, if any
    * the entire match, otherwise

    >>> lines = ['0', 'one:', '1', 'two:', 'three:', '3', 'end']
    >>> list(annotate_lines(lines, '(.*):$', 'end'))
    [('', '0'), ('one', '1'), ('two', None), ('three', '3'), (True, 'end')]

    >>> list(annotate_lines([]))
    [('', None), (None, None)]

    """
    section_re, success_re, failure_re = [
        re.compile(pattern if pattern is not None else MATCH_NOTHING)
        for pattern in (section_pattern, success_pattern, failure_pattern)
    ]

    done = False
    ok = None
    section = ''
    yielded_lines = False
    for line in chain(lines, [None]):
        if line is not None:
            line = line.rstrip('\n')

        match = None
        label = None

        if line is None:
            done = True
        elif match := failure_re.search(line):
            done = True
            ok = False
        elif match := success_re.search(line):
            done = True
            ok = True
        elif match := section_re.search(line):
            pass

        if match:
            if not match.re.groups:
                label = match.group()
            elif 'name' in match.re.groupindex:
                label = match.group('name')
            elif match.re.groups == 1:
                label = match.group(1)

        if done:
            if not yielded_lines:
                yield section, None
            yield ok, label
            break

        if label:
            if not yielded_lines:
                yield section, None
            section = label
            yielded_lines = False
            continue

        yielded_lines = True
        yield section, line


def group_by_section(pairs):
    """Group annotate_lines() output into (section, lines) pairs.

    >>> pairs = [('', '0'), ('', '1'), ('section', None), (True, 'end')]
    >>> groups = group_by_section(pairs)
    >>> [(s, list(ls)) for s, ls in groups]
    [('', ['0', '1']), ('section', []), (True, ['end'])]

    """
    get_one = itemgetter(1)

    for section, group in groupby(pairs, itemgetter(0)):
        lines = map(get_one, group)
        first = next(lines, None)

        if first is None:
            yield section, ()
            continue

        yield section, chain([first], lines)


def filter_sections(groups, predicate, end_is_failure=True):
    """Filter (section, lines) pairs.

    If predicate(section) is true, yield the pair as-is.
    If predicate(section) is false, yield ('', ()) instead.

    If the last section is False or None,
    and the section before-last did not match the predicate,
    yield the before-last pair (again) as-is before the last one.

    >>> groups = [('1', 'i'), ('two', 'ii'), ('three', 'iii'), (None, '')]
    >>> groups = filter_sections(groups, str.isdigit)
    >>> list(groups)
    [('1', 'i'), ('', ()), ('', ()), ('three', ['i', 'i', 'i']), (None, '')]

    """
    last_before = {False}
    if end_is_failure:
        last_before.add(None)

    previous = None

    for section, lines in groups:
        if section in {True, False, None}:
            if section in last_before and previous is not None:
                yield previous
            yield section, lines
            break

        if predicate(section):
            yield section, lines
            previous = None
        else:
            yield '', ()
            previous = section, list(lines)


def filter_lines(groups, get_filters):
    """Filter the lines in (section, lines) pairs.

    >>> groups = [('one', 'a1B2')]
    >>> groups = filter_lines(groups, lambda _: [str.isalpha, str.upper])
    >>> [(s, list(ls)) for s, ls in groups]
    [('one', ['A', 'B'])]

    """

    def filter_lines(lines, filters):
        for line in lines:
            for filter in filters:
                rv = filter(line)
                if rv is True:
                    continue
                if rv is False:
                    line = None
                else:
                    line = rv
                if line is None:
                    break
            if line is not None:
                yield line

    for section, lines in groups:
        if section not in {True, False, None}:
            filters = get_filters(section)
            if filters:
                lines = filter_lines(lines, filters)
        yield section, lines


def dedupe_blank_lines(groups):
    """Deduplicate blank lines in (section, lines) pairs.

    >>> groups = [('one', ['', '1', '', '', '', '2', ''])]
    >>> groups = dedupe_blank_lines(groups)
    >>> [(s, list(ls)) for s, ls in groups]
    [('one', ['1', '', '2', ''])]

    """

    def dedupe(lines):
        prev_line = ''
        for line in lines:
            stripped = line.strip()
            if not (prev_line == line.strip() == ''):
                yield line
            prev_line = stripped

    for section, lines in groups:
        if section not in {True, False, None}:
            lines = dedupe(lines)
        yield section, lines
