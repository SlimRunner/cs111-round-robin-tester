CS 111 Unit Tester - You Spin Me Round Robin
============================================

This tester is intended to make it easier to share test cases and results. **Some things you need to do first if you are going to use this tester**.

1. Do not fork this project.
2. If you clone, make sure to remove this repo as a remote.
3. Make sure to copy over to here your files:
   
   * ``rr.c``
   * ``README.md``

For (3) don't worry about overriding this readme. I made this in reStructuredText so it has a different extension.

Setup
-----

This was written inside the provided virtual machine, so it should run with the Python version installed there (v3.9.7).

To start using it, all you need to do is bring over your ``rr.c`` file and your ``README.md`` file. Yes, even the ``README.md``. I made the tester crash if it doesn't find it in this directory to avoid that you forget about it.

That is all you need. You can now start testing your code.

Usage
-----

The simplest way to call the tester is like this:

.. code-block:: shell

    python3 ./rrtester.py

It will read all the test cases in the file `unit_tests.md`_ and match it against the expected output specified there. When it is done, it will print a report in the terminal with all the info you need to debug your code. The report is markdown compatible so you can redirect it like this:

.. code-block:: shell

    python3 ./rrtester.py > mdout.md

.. warning::

   The "correct" answers in the test cases file are what my program generates, so I cannot guarantee that they are 100% correct. If you run it against my test cases and you get failed tests that you are sure are correct, feel free to bring it up in `the class discussion <https://piazza.com>`_.

Flags
-----

The tester allows you to pass flags to modify its behavior. The ``-h`` flag is pretty useful to get this info in the terminal. The flags are as follows:

* ``-h``, ``--help``

  * Shows the help message and exits.

* ``-t {makeit,timeit,testit}``, ``--test-type {makeit,timeit,testit}``

  * Allows different modes of running your test programs. The options are:
    
    * ``testit``: runs each program against the expected output and shows a diff.
    * ``makeit``: runs each program and prints the output in a markdown unit test report.
    * ``timeit``: runs each program as-is, prints the output, and times it.

* ``-s SECTION [SECTION ...]``, ``--section SECTION [SECTION ...]``

  * Filter by a specific set of sections.

* ``-v``, ``--verbose``

  * If present, testing mode will show the passed cases too.

* ``--args ARGS [ARGS ...]``

  * Pass extra arguments to your round robin program. The tester passes a file path and quantum number on its own. This is if you wish to pass extra ones for debugging purposes.

Example 1
~~~~~~~~~

You want to generate unit test cases of what your program outputs to share with others:

.. code-block:: shell

    python3 ./rrtester.py -t makeit > mdout.md

Example 2
~~~~~~~~~

You want to inspect what the actual output of your program is when you run a specific test case titled "Zero Burst Time Mixed":

.. code-block:: shell

    python3 ./rrtester.py -t timeit -s "Zero Burst Time Mixed"
