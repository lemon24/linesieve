
# get all options used by any git command

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
