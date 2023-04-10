cat simple.txt \
| linesieve --section '(\S+):$' --failure fail \
  show --ignore-case ^O \
  match --section one --only-matching '\d+' \
  sub '([a-z])' '\1\1\1'
