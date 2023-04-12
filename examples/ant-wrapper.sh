#!/bin/sh

# make Apache Ant output more readable

linesieve \
    --section '^(\S+):$' \
    --success 'BUILD SUCCESSFUL' \
    --failure 'BUILD FAILED' \
show junit-batch \
show junit-single-test-only \
sub-cwd \
sub-paths --include 'src/main/**/*.java' --modules-skip 2 \
sub-paths --include 'src/tests/junit/**/*.java' --modules-skip 3 \
sub -s compile '^\s+\[javac?] ' '' \
push compile \
    match -v '^Compiling \d source file' \
    match -v '^Ignoring source, target' \
pop \
push junit \
    sub '^\s+\[junit] ?' '' \
    span -v \
        --start '^WARNING: multiple versions of ant' \
        --end '^Testsuite:' \
    match -v '^\s+at java\.\S+\.reflect\.' \
    match -v '^\s+at org.junit.Assert' \
    span -v \
        --start '^\s+at org.junit.(runners|rules|internal)' \
        --end '^(?!\s+at )' \
pop \
sub -X '^( \s+ at \s+ (?! .+ \.\. ) .*? ) \( .*' '\1' \
sub -X '
    (?P<pre> \s+ at \s .*)
    (?P<cls> \w+ )
    (?P<mid> .* \( )
    (?P=cls) \.java
    (?P<suf> : .* )
    ' \
    '\g<pre>\g<cls>\g<mid>\g<suf>' \
sub --color -X '^( \w+ (\.\w+)+ (?= :\s ))' '\1' \
sub --color -X '(FAILED)' '\1' \
read-cmd ant "$@"
