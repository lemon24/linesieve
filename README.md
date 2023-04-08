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
span -v -X \
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

* The `span` gets rid of all the traceback lines coming from JUnit.
* The `sub-paths` shortens and highlights the names of classes in the current project;
  `com.example.someproject.somepackage.ThingDoer` becomes `..ThingDoer`
  (presumably that's enough info to open the file).
* The first `sub` gets rid of line numbers and JAR names for everything
  that is not either in the current project or in another `com.example.` package.
* The second `sub` gets rid of JAR names for things in other `com.example.` packages.
* The third `sub` gets rid of the source file name;
  `..ThingDoer.doThing(ThingDoer.java:69)` becomes `..ThingDoer.doThing(:69)`
  (the file name matches the class name).


### Apache Ant output

Finally, let's look at why linesieve was born in the first place
– cleaning up Apache Ant output.

We'll use Ant's own test output as an example,
since it [builds itself](https://github.com/apache/ant/tree/ff62ff7151bbc84a7706f40988258fabbcc324f5).

Running a single test with `ant junit-single-test -Djunit.testcase=org.apache.tools.ant.ProjectTest`
produces 77 lines of output, which looks like this:

```
Buildfile: /Users/lemon/code/ant/build.xml

check-optional-packages:

prepare:

compile:

compile-jdk9+:

build:
   [delete] Deleting directory /Users/lemon/code/ant/build/classes/org/apache/tools/ant/taskdefs/optional/junitlauncher/confined
        ... more lines

... more targets, until we get to the one that we care about

junit-single-test-only:
    [junit] WARNING: multiple versions of ant detected in path for junit
    [junit]          file:/Users/lemon/code/ant/build/classes/org/apache/tools/ant/Project.class
    [junit]      and jar:file:/usr/local/Cellar/ant/1.10.12/libexec/lib/ant.jar!/org/apache/tools/ant/Project.class
    [junit] Testsuite: org.apache.tools.ant.ProjectTest
    [junit] Tests run: 12, Failures: 0, Errors: 0, Skipped: 1, Time elapsed: 5.635 sec
        ... more lines

junit-single-test:

BUILD SUCCESSFUL
Total time: 12 seconds
```

(If you don't think it's all that bad,
try to imagine how it would look for a serious Enterprise Project™️.)

This is indeed very helpful
– if you're waiting tens of minutes for the entire test suite to run,
you want all the details in the output,
so you can debug failures without having to run it another time.

However, it's not very helpful when you're developing,
and only care about the thing you're working on right now.

This is where a script consisting of a single linesieve command comes in:

```bash
#!/bin/sh

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
exec ant "$@"
```

You can then call it instead of `ant`: `ant-wrapper.sh junit-single-test ...`.

TODO: describe this output

```
............
junit-single-test-only
Testsuite: ..ProjectTest
Tests run: 12, Failures: 0, Errors: 0, Skipped: 1, Time elapsed: 5.635 sec
------------- Standard Output ---------------
bar
------------- ---------------- ---------------
------------- Standard Error -----------------
bar
------------- ---------------- ---------------

Testcase: testResolveFileWithDriveLetter took 0.034 sec
	SKIPPED: Not DOS or Netware
Testcase: testResolveFileWithDriveLetter took 0.036 sec
Testcase: testInputHandler took 0.007 sec
Testcase: testAddTaskDefinition took 0.179 sec
Testcase: testTaskDefinitionContainsKey took 0.002 sec
Testcase: testDuplicateTargets took 0.05 sec
Testcase: testResolveRelativeFile took 0.002 sec
Testcase: testOutputDuringMessageLoggedIsSwallowed took 0.002 sec
Testcase: testDataTypes took 0.154 sec
Testcase: testDuplicateTargetsImport took 0.086 sec
Testcase: testNullThrowableMessageLog took 0.002 sec
Testcase: testTaskDefinitionContainsValue took 0.002 sec
Testcase: testResolveFile took 0.001 sec

.
BUILD SUCCESSFUL
```

```
............
junit-single-test-only
Testsuite: ..ProjectTest
Tests run: 12, Failures: 1, Errors: 0, Skipped: 1, Time elapsed: 5.638 sec
------------- Standard Output ---------------
bar
------------- ---------------- ---------------
------------- Standard Error -----------------
bar
------------- ---------------- ---------------

Testcase: testResolveFileWithDriveLetter took 0.033 sec
	SKIPPED: Not DOS or Netware
Testcase: testResolveFileWithDriveLetter took 0.035 sec
Testcase: testInputHandler took 0.005 sec
	FAILED
expected null, but was:<..DefaultInputHandler@61dc03ce>
junit.framework.AssertionFailedError: expected null, but was:<..DefaultInputHandler@61dc03ce>
	at ..ProjectTest.testInputHandler(:254)

Testcase: testAddTaskDefinition took 0.182 sec
Testcase: testTaskDefinitionContainsKey took 0.003 sec
Testcase: testDuplicateTargets took 0.043 sec
Testcase: testResolveRelativeFile took 0.001 sec
Testcase: testOutputDuringMessageLoggedIsSwallowed took 0.003 sec
Testcase: testDataTypes took 0.161 sec
Testcase: testDuplicateTargetsImport took 0.088 sec
Testcase: testNullThrowableMessageLog took 0.001 sec
Testcase: testTaskDefinitionContainsValue took 0.001 sec
Testcase: testResolveFile took 0.001 sec
Test ..ProjectTest FAILED

.
BUILD SUCCESSFUL
```

```
...
compile
.../Project.java:65: error: cannot find symbol
public class Project implements xResourceFactory {
                                ^
  symbol: class xResourceFactory
.../Project.java:2483: error: method does not override or implement a method from a supertype
    @Override
    ^
2 errors

BUILD FAILED
```

TODO: linesieve command breakdown
