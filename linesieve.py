import re
from itertools import chain, groupby
from dataclasses import dataclass
from operator import itemgetter


def tokenize(it, section_pattern, success_pattern, failure_pattern):
    section_re = re.compile(section_pattern)
    success_re = re.compile(success_pattern)
    failure_re = re.compile(failure_pattern)
    
    done = False
    ok = None
    section = ''
    for line in chain(it, [None]):
        if line is not None:
            line = line.rstrip()
        
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
            elif 'l' in match.re.groupindex:
                label = match.group('l')
            elif match.re.groups == 1:
                label = match.group(1)

        if done:
            yield ok, label
            break

        if label:
            section = label
            continue
        
        yield section, line
            

def group_by_section(it, show):
    grouped = groupby(it, itemgetter(0))
    
    prev_lines = None
    for section, lines in grouped:

        if section in {True, False, None}:
            if not section and prev_lines is not None:
                yield prev_lines[0][0], prev_lines
            yield section, lines
            break

        if show(section):
            yield section, lines
            prev_lines = None
        else:
            yield '', ()
            prev_lines = list(lines)


def do_output(groups):
    prev_section = False

    for section, lines in groups:
        
        if section == '':
            dot = '.'
            print(dot, end='', flush=True)
            last_was_dot = True
            continue

        if last_was_dot:
            print()
            last_was_dot = False
            
        if section in {True, False, None}:
            print(*lines, prev_section)
            break
        
        print(section)
        for line in lines:
            print(' ', line)
            
        prev_section = section
            
    
    


if __name__ == '__main__':

    file = open('data/full.in')
    tokens = tokenize(file, '(\S+):$', 'good end', 'bad end')
    groups = group_by_section(tokens, {'two'}.__contains__)
    do_output(groups)
    # TODO: 
    # section/end colors
    # cwd replace
    # symlink replace
    # path replace / color
    # class replace / color
    # cli


    
    
    
    
    
