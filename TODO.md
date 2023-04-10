
Before 1.0:

* [ ] help should mention "use subcommands to filter output"
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
* exec time
* collapse any repeated lines
* runfilter "grep pattern"
* short command aliases (four-letter ones)
* make dedupe_blank_lines optional
* match replace spans of skipped lines with ... (match span already does this)
* section -s pattern section --include pattern (tried it, not necessarily better)
* a way to reuse pre-configured commands
