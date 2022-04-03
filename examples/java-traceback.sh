
# make Java tracebacks more readable

linesieve \
match-span -v -X \
    --start '^ (\s+) at \s ( org\.junit\. | \S+ \. reflect\.\S+\.invoke )' \
    --end '^ (?! \s+ at \s )' \
    --repl '\1...' \
match -v '^\s+at \S+\.(rethrowAs|translateTo)IOException' \
sub-paths --include '{src,tst}/**/*.java' --modules-skip 1 \
sub -X '^( \s+ at \s+ (?! .+ \.\. | com\.example\. ) .*? ) \( .*' '\1' \
sub -X '^( \s+ at \s+ com\.example\. .*? ) \ ~\[ .*' '\1' \
sub -X '
    (?P<pre> \s+ at \s .*)
    (?P<cls> \w+ )
    (?P<mid> .* \( )
    (?P=cls) \.java
    (?P<suf> : .* )
    ' \
    '\g<pre>\g<cls>\g<mid>\g<suf>'
