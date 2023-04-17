
.. default-role:: literal


.. begin-intro

*This is my text munging tool. There are many like it, but this one is mine.*

**linesieve** is an unholy blend of grep, sed, awk, and Python,
born out of spite.

.. end-intro


|build-status-github| |code-coverage| |documentation-status| |pypi-status| |code-style|

.. |build-status-github| image:: https://github.com/lemon24/linesieve/workflows/build/badge.svg
  :target: https://github.com/lemon24/linesieve/actions?query=workflow%3Abuild
  :alt: build status (GitHub Actions)

.. |code-coverage| image:: https://codecov.io/gh/lemon24/linesieve/branch/main/graph/badge.svg?token=MrpEP5cg24
  :target: https://codecov.io/gh/lemon24/linesieve
  :alt: code coverage

.. |documentation-status| image:: https://readthedocs.org/projects/linesieve/badge/?version=latest&style=flat
  :target: https://linesieve.readthedocs.io/en/latest/?badge=latest
  :alt: documentation status

.. |pypi-status| image:: https://img.shields.io/pypi/v/linesieve.svg
  :target: https://pypi.python.org/pypi/linesieve
  :alt: PyPI status

.. |type-checking| image:: http://www.mypy-lang.org/static/mypy_badge.svg
  :target: http://mypy-lang.org/
  :alt: checked with mypy

.. |code-style| image:: https://img.shields.io/badge/code%20style-black-000000.svg
  :target: https://github.com/psf/black
  :alt: code style: black



.. begin-main


Features
--------

`linesieve` allows you to:

* split text input into sections
* apply filters to specific sections
* search and highlight success/failure markers
* match/sub/split with the full power of Python's `re`_
* shorten paths, links and module names
* chain filters into pipelines
* color output!

.. _re: https://docs.python.org/3/library/re.html


Installing
----------

Install and update using `pip`_:

.. code-block:: console

    $ pip install --upgrade linesieve

.. _pip: https://pip.pypa.io/en/stable/getting-started/


A simple example
----------------

.. code-block:: console

    $ ls -1 /* | linesieve -s '.*:' show bin match ^d head -n2
    .....
    /bin:
    dash
    date
    ......
    /sbin:
    disklabel
    dmesg
    ...

This example uses `linesieve`
to print the first two files starting with `d`
from each directory whose name contains `bin`
(skipped sections are marked with a dot on stderr).


Links
-----

* PyPI Releases: https://pypi.org/project/linesieve/
* Documentation: https://linesieve.readthedocs.io/
* Issue Tracker: https://github.com/lemon24/linesieve/issues
* Source Code: https://github.com/lemon24/linesieve


.. end-main



Examples
--------

.. begin-examples


Make Java tracebacks more readable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Assume you're writing some Java tests with JUnit,
on a project that looks like this:

.. code-block:: text

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

This command:

.. code-block:: bash

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

... shortens this 76 line traceback:

.. code-block:: text

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

... to just:

.. code-block:: text

    12:34:56.789 [main] ERROR ..ThingDoer - exception while notifying done listener
    java.lang.RuntimeException: listener failed
    	at ..ThingDoerTest$DummyListener.onThingDone(:420) ~[tests/:?]
    	at ..ThingDoer.doThing(:69) ~[library/:?]
    	at com.example.otherproject.Framework.doAllTheThings(:1066)
    	at ..ThingDoerTest.listenerException(:666) ~[tests/:?]
    	...
    12:34:56.999 [main] INFO done

Let's break that `linesieve` command down a bit:

* The `span` gets rid of all the traceback lines coming from JUnit.
* The `match -v` skips some usually useless lines from stack traces.
* The `sub-paths` shortens and highlights the names of classes in the current project;
  `com.example.someproject.somepackage.ThingDoer` becomes `..ThingDoer`
  (presumably that's enough info to open the file).
* The first `sub` gets rid of line numbers and JAR names for everything
  that is not either in the current project or in another `com.example.` package.
* The second `sub` gets rid of JAR names for things in other `com.example.` packages.
* The third `sub` gets rid of the source file name;
  `..ThingDoer.doThing(ThingDoer.java:69)` becomes `..ThingDoer.doThing(:69)`
  (the file name matches the class name).


Apache Ant output
~~~~~~~~~~~~~~~~~

Let's look at why `linesieve` was born in the first place
– cleaning up Apache Ant output.

We'll use Ant's own test output as an example,
since it `builds itself`_.

.. _builds itself: https://github.com/apache/ant/tree/ff62ff7151bbc84a7706f40988258fabbcc324f5


Running a single test with:

.. code-block:: bash

    ant junit-single-test -Djunit.testcase=org.apache.tools.ant.ProjectTest

... produces 77 lines of output:

.. code-block:: text

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

If this doesn't look all that bad,
try imagining what it looks like
for a Serious Enterprise Project™.


Lots of output is indeed very helpful
– if you're waiting tens of minutes for the entire test suite to run,
and/or it runs on some remote server,
you want all the details in there,
so you can debug failures without having to run it another time.

However, it's not very helpful during development,
whey you only care about the thing you're working on *right now*.
And it's doubly not helpful if you want to re-run the test suite
on each file update with something like `entr`_.

.. _entr: http://eradman.com/entrproject/


This is where a `linesieve` wrapper script can help:

.. code-block:: bash

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
    read-cmd ant "$@"

You can then call this instead of `ant`: `ant-wrapper.sh junit-single-test ...`.


Successful output looks like this (28 lines):

.. code-block:: text

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

... "failure" output looks like this (34 lines):

.. code-block:: text

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

... and true failure due to a compile error looks like this (12 lines):

.. code-block:: text

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


Breaking down the `linesieve` command
(skipping the parts discussed in the previous example):

* `--section '^(\S+):$'` tells `linesieve`
  sections start with a word followed by a colon.
* The `show`\s hide all sections except specific ones.
* `--success` and `--failure` tell `linesieve`
  to exit when encountering one of these patterns.
  Note that the failing section above is shown
  despite not being selected with `show`.
* `sub-cwd` makes absolute paths in the working directory relative.
* The `-s compile` option passed to `sub` applies that filter
  only to sections matching `compile`.
* `push compile` applies all the following filters, until `pop`,
  only to sections matching `compile`.
* The last two `sub --color ... '\1'` color
  dotted words followed by a colon at the beginning of the line
  (e.g. `junit.framework.AssertionFailedError:`),
  and `FAILED` anywhere in the input.
* Finally, `read-cmd` executes a command and uses its output as input.

.. end-examples
