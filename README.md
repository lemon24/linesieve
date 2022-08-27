*This is my text munging tool. There are many like it, but this one is mine.*

**linesieve** is an unholy blend of `grep`, `sed`, `awk`, and Python,
with *very* specific features, born out of spite.


[![build](https://github.com/lemon24/linesieve/actions/workflows/build.yaml/badge.svg)](https://github.com/lemon24/linesieve/actions/workflows/build.yaml) [![codecov](https://codecov.io/gh/lemon24/linesieve/branch/main/graph/badge.svg?token=MrpEP5cg24)](https://codecov.io/gh/lemon24/linesieve) [![PyPI](https://img.shields.io/pypi/v/linesieve)](https://pypi.org/project/linesieve/) [![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


## Features

* line-oriented
* section-oriented
  * show only matching sections
  * show the failing section
  * apply filters only to specific sections
* match/sub with the full power of [re](https://docs.python.org/3/library/re.html)
* chain filters into pipelines
* colors!
* TODO: specific filters


## Examples


### Get all options used by any git command

Note that some of the man pages contain multiple OPTIONS sections (e.g. ADVANCED OPTIONS).

```bash
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

```

Output:

```
-/ <path>
-, --stdin
-0
...
-a, --all
-A, --all, --ignore-removal
-a, --annotate
...
--autosquash, --autosquash
--autostash, --autostash
-b
-b, --branch
...
```


### Make Java tracebacks more readable

Assume you're writing some Java tests with JUnit, on a project that looks like this:

```
.
├── src
│   └── com
│       └── example
│           └── someproject
│               └── somepackage
│                   └── ThingDoer.java
└── tst
    └── com
        └── example
            └── someproject
                └── somepackage
                    └── ThingDoerTest.java
```

This command:

```bash
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
```

... shortens this traceback:

```
12:34:56.789 [main] ERROR com.example.someproject.somepackage.ThingDoer - exception while notifying done listener
java.lang.RuntimeException: listener failed
	at com.example.someproject.somepackage.ThingDoerTest$DummyListener.onThingDone(ThingDoerTest.java:420) ~[tests/:?]
	at com.example.someproject.somepackage.ThingDoer.doThing(ThingDoer.java:69) ~[library/:?]
    at com.example.otherproject.Framework.doAllTheThings(Framework.java:1066) ~[example-otherproject-2.0.jar:2.0]
	at com.example.someproject.somepackage.ThingDoerTest.listenerException(ThingDoerTest.java:666) ~[tests/:?]
	at jdk.internal.reflect.NativeMethodAccessorImpl.invoke0(Native Method) ~[?:?]
	at jdk.internal.reflect.NativeMethodAccessorImpl.invoke(NativeMethodAccessorImpl.java:62) ~[?:?]
	...
	... 60+ more lines of JUnit stuff we don't really care about ...
	...
12:34:56.999 [main] INFO done
```

... to just:

```
12:34:56.789 [main] ERROR ..ThingDoer - exception while notifying done listener
java.lang.RuntimeException: listener failed
	at ..ThingDoerTest$DummyListener.onThingDone(:420) ~[tests/:?]
	at ..ThingDoer.doThing(:69) ~[library/:?]
	at com.example.otherproject.Framework.doAllTheThings(:1066)
	at ..ThingDoerTest.listenerException(:666) ~[tests/:?]
	...
12:34:56.999 [main] INFO done
```

Let's break that linesieve command down a bit:

* The `match-span` gets rid of all the traceback lines coming from JUnit.
* The `sub-paths` shortens and highlights the names of classes in the current project;
  `com.example.someproject.somepackage.ThingDoer` becomes `..ThingDoer`
  (presumably that's enough info to open the file).
* The first `sub` gets rid of line numbers and JAR names for everything
  that is not either in the current project or in another `com.example.` package.
* The second `sub` gets rid of JAR names for things in other `com.example.` packages.
* The third `sub` gets rid of the source file name;
  `..ThingDoer.doThing(ThingDoer.java:69)` becomes `..ThingDoer.doThing(:69)`
  (the file name matches the class name).


### TODO: Ant output
