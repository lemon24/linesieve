
Before 1.0:

* [ ] help should mention "use subcommands to filter output"
* [ ] use `ls -1 /* | linesieve -s '(.*:)' show -i 'app*|bin' head -n2` as example
* [ ] short help should not show options or commands
* [ ] readme
  * [x] no backticks for "grep, sed, awk"?
  * [ ] TODO: specific filters
  * [ ] basic example
  * [ ] git example – explain what's happening
  * [ ] traceback example – reread/edit
  * [ ] ant example – finish


After 1.0:

* bugbear?
* hide section command
* match -e pattern -e pattern (hard to do with click while keeping arg)
* match-span -s ... -s ..s
* print last section without --failure if exec exits with non-zero (how?)
* option to turn off stderr dots for hidden sections
* read-cmd time (and maybe for each section?)
* collapse any repeated lines
* make dedupe_blank_lines optional
* runfilter "grep pattern" (exec sounds like a good name)
* short command aliases (four-letter ones)
* match/head/tail --repl spans of skipped lines with ... (match span already does this)
* section -s pattern section --include pattern (tried it, not necessarily better)
* a way to reuse pre-configured commands
