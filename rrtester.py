import os
import subprocess
from arghelper import ArgsWrapper, TestingOptions, getArguments
from unittester import UnitTester, ResultGenerator, BatchRun


def main(args: ArgsWrapper):
    tester = None

    if args.test_type == TestingOptions.UNIT_TEST:
        tester = UnitTester("./unit_tests.md", project_callback, *args.arguments)
    elif args.test_type == TestingOptions.GEN_CASES:
        tester = ResultGenerator("./unit_tests.md", project_callback, *args.arguments)
    elif args.test_type == TestingOptions.TIME_PROG:
        tester = BatchRun("./unit_tests.md", project_callback, *args.arguments)
    else:
        raise SystemExit(f"Unexpected test type: {args.test_type}")

    if tester is None:
        raise SystemError("tester did not generate correctly")

    tester.run_tests(**args.filters, verbose=args.verbose)
    tester.result.print_report()


def project_callback(filename: str, q_size: str, *args):
    PROG_NAME = os.path.abspath("./rr")
    retval = None

    try:
        if args:
            retval = subprocess.check_output(
                (PROG_NAME, filename, q_size, *args)
            ).decode()
        else:
            retval = subprocess.check_output((PROG_NAME, filename, q_size)).decode()
    except Exception as err:
        raise err

    return retval


def validate_required_files():
    INVALID_DIR = any(
        not os.path.exists(os.path.abspath(p))
        for p in ["./rr.c", "./Makefile", "./README.md"]
    )
    if INVALID_DIR:
        raise SystemError("rr.c, Makefile, or README.md is missing in your directory")


if __name__ == "__main__":
    validate_required_files()
    args = getArguments()
    subprocess.check_output("make")
    try:
        main(args)
    except Exception as err:
        raise err
    finally:
        subprocess.check_output(("make", "clean"))
