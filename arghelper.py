import textwrap
from argparse import (
    ArgumentParser,
    RawTextHelpFormatter,
)


# https://stackoverflow.com/a/29485128
class BlankLinesHelpFormatter(RawTextHelpFormatter):
    def _split_lines(self, text, width):
        return super()._split_lines(text, width) + [""]


class TestingOptions:
    UNIT_TEST = "testit"
    GEN_CASES = "makeit"
    OPTIONS = {UNIT_TEST, GEN_CASES}
    DEFAULT = UNIT_TEST

    def __init__(self, opt: str) -> None:
        if opt not in TestingOptions.OPTIONS:
            raise ValueError(f"'{opt}' is not a valid time type")
        self.__options = {o: o == opt for o in TestingOptions.OPTIONS}
        self.__selected = opt

    def __eq__(self, value: str) -> bool:
        return value == self.__selected

    def __repr__(self) -> str:
        return self.__selected

    def do_unit_test(self) -> bool:
        return self.__options[TestingOptions.UNIT_TEST]

    def do_run_test(self) -> bool:
        return self.__options[TestingOptions.GEN_CASES]


class ArgsWrapper:
    def __init__(self, args) -> None:
        self.__test_type = args.test_type
        self.__section = args.section
        self.__verbose = args.verbose

    @property
    def test_type(self) -> TestingOptions:
        return self.__test_type

    @property
    def filters(self) -> dict[str, set[str]]:
        return {"section_filter": self.__section}

    @property
    def verbose(self) -> str:
        return self.__verbose


def getArguments(*args: str) -> ArgsWrapper:
    arg_parser = ArgumentParser(
        prog="main",
        description="Tests round robin project and also generates test cases.",
        formatter_class=BlankLinesHelpFormatter,
    )
    arg_parser.add_argument(
        "-t",
        "--test-type",
        nargs=1,
        default=[TestingOptions.DEFAULT],
        choices=TestingOptions.OPTIONS,
        help=textwrap.dedent(
            f"""\
            Allows different modes of running your test programs. The options are:
                - {TestingOptions.UNIT_TEST}: runs each program against the expected output and shows a diff.
                - {TestingOptions.GEN_CASES}: runs each program as-is and prints the output in a markdown report.
            """
        ),
    )
    arg_parser.add_argument(
        "-s", "--section", nargs="+", help="Filter by a specific set of sections."
    )
    arg_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="If present testing mode will show the passed cases too.",
    )

    if len(args) > 0:
        p_args = arg_parser.parse_args(list(args))
    else:
        p_args = arg_parser.parse_args()

    p_args.test_type = TestingOptions(p_args.test_type[0])
    p_args.section = set(p_args.section) if p_args.section else set()

    return ArgsWrapper(p_args)
