
After 1.0:

* bugbear?
* match-span -s ... -s ..s (update: does this mean multiple starts?)
* print last section without --failure if read-cmd exits with non-zero (how?)
* option to turn off stderr dots for hidden sections
* read-cmd time (and maybe for each section?)
* collapse any repeated lines
* make dedupe_blank_lines optional
* short command aliases (four-letter ones)
* match/head/tail --repl spans of skipped lines with ... (match span already does this)
* a way to reuse pre-configured commands
* split --only-delimited
* split --output-format '{1}{2!r}'? requires a custom string.Formatter that coerces string arguments
* parse -D/--output-delimiter (account for both : and ,)
* parse --all/--findall to match multiple times? (like match -o); we need re.findall() for multiple patterns, though
* parse --prefix-non-matching UNKNOWN -> `["UNKNOWN", line]` / `{"UNKNOWN": line}`
