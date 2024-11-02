import os
import re
import tempfile
import subprocess
from unittest.mock import patch
from arghelper import ArgsWrapper, TestingOptions, getArguments


class PrintableReport:
    def __init__(self, test_path: str) -> None:
        self.__test_path = test_path

    @property
    def suite_name(self) -> str:
        return f"./{os.path.relpath(self.__test_path)}"

    def print_report(self, report_lines: list[str]):
        print()
        print("-" * 40)
        print("\n".join(f"* {l}" for l in report_lines))


class TestResults(PrintableReport):
    def __init__(self, test_path: str) -> None:
        super().__init__(test_path)
        self.__entries = []

    def add_entry(self, passed: bool) -> None:
        self.__entries.append(passed)

    def count_success(self):
        return len([i for i in self.__entries if i])

    def give_score(self) -> tuple[int, int]:
        return (self.count_success(), len(self.__entries))

    def print_report(self):
        passed, total = self.give_score()
        COLSIZE = 8
        out_report = []
        out_report.append(f"{'suite:':<{COLSIZE}}{self.suite_name}")
        out_report.append(f"{'score:':<{COLSIZE}}{passed}/{total}\n")
        super().print_report(out_report)


class NullReport(PrintableReport):
    def print_report(self):
        pass


class TesterBase:
    PAYLOAD = "payload"
    RESULTS = "results"
    GENERATOR = "generator"
    TAB = "  "

    def __init__(self, test_path: str, callback, **kwargs):
        self.__callback = callback
        self.__kwargs = kwargs
        self.__ttree: dict[str, dict[str, dict[str, list[str]]]] = dict()
        self.__test_path = test_path
        self.__key_map = []

        state = None
        whitelist = re.compile(r"^$|\*[\w ]+\*|^>")

        with open(test_path) as file:
            for line in file:
                lnw = line.rstrip("\n")
                lsp = line.rstrip()

                if self.update_sections(state, lnw):
                    continue

                if whitelist.match(lsp):
                    continue  # ignore line

                state = self.advance_fsm(state, lnw)

    def callback(self, prog_arg: str, quantum_size: str):
        if len(self.__kwargs):
            return self.__callback(prog_arg, quantum_size, **self.__kwargs)
        else:
            return self.__callback(prog_arg, quantum_size)

    def validate_uniqueness(self, item: dict, key: str):
        if key in item:
            nice_path = os.path.relpath(self.__test_path)
            raise SystemExit(f"`{key}' is a duplicate entry in {nice_path}")

    def add_level(self, active_item: dict, key: str, payload):
        self.validate_uniqueness(active_item, key)
        active_item[key] = payload
        self.__key_map.append(active_item[key])

    def add_item(self, active_item: dict, key: str, payload):
        self.validate_uniqueness(active_item, key)
        active_item[key] = payload

    def run_section(self, unit: dict[str, list[str]]) -> tuple[bool, list[str]]:
        raise NotImplementedError("run_section must be derived")

    def is_filtered(self, key: str, filter: set[str]):
        if len(filter) == 0:
            return False
        remove_hash = re.compile(r"^#+ ")
        key = remove_hash.sub("", key).lower()
        return key not in filter

    def run_tests(self, section_filter: set[str], verbose: bool):
        print_buffer: list[str] = []
        section_filter = {i.lower() for i in section_filter}

        for name, title in self.__ttree.items():
            print_buffer.append(name)
            for name, section in title.items():
                if self.is_filtered(name, section_filter):
                    continue

                passed, msg = self.run_section(section)

                if passed and not verbose:
                    continue

                print_buffer.append(name)
                print_buffer.extend(msg)

        print("\n".join(print_buffer))

    def update_sections(self, state, line):
        if line == "```":
            return False

        if state == "payload" or state == "results" or state == "generator":
            self.__key_map[-1][state].append(line)
            return True

        else:
            return False

    def advance_fsm(self, state, line):
        FSM = {
            None: [(r"^# ", "title")],
            "title": [(r"^## ", "section")],
            "section": [(r"^```", "payload")],
            "payload": [(r"^```", "payload-end")],
            "payload-end": [(r"^```", "results")],
            "results": [(r"^```", "results-end")],
            "results-end": [(r"^```", "generator")],
            "generator": [(r"^```", "generator-end")],
            "generator-end": [(r"^## ", "section")],
        }

        entry_state = state
        for target, next in FSM[state]:
            if re.match(target, line):
                state = next

        if entry_state == state:
            raise SyntaxError(
                f"Incorrectly formatted test cases. It failed at:" + f"`{line}'"
            )

        if state == "title" and entry_state == None:
            self.__ttree[line] = dict()
            self.__key_map.append(self.__ttree[line])

        elif state == "section" and entry_state == "title":
            self.add_level(self.__key_map[-1], line, dict())

        elif state == "section" and entry_state == "generator-end":
            self.__key_map.pop()
            self.add_level(self.__key_map[-1], line, dict())

        elif state == "payload" or state == "results" or state == "generator":
            self.add_item(self.__key_map[-1], state, [])

        elif (
            state == "payload-end" or
            state == "results-end" or
            state == "generator-end"
        ):
            pass

        else:
            raise SyntaxError(
                f"Fatal error at:" + f"`{line}'.\nInvalid state transition."
            )

        return state


class UnitTester(TesterBase):
    def __init__(self, test_path: str, callback, **kwargs):
        super().__init__(test_path, callback, **kwargs)
        self.result = TestResults(test_path)

    def trim_output(self, received: str):
        if received.endswith("\n"):
            received = received[:-1]
        return received

    def run_section(self, unit: dict[str, list[str]]):
        payload = unit[TesterBase.PAYLOAD]
        cases = (tuple(test.split(",")) for test in unit[TesterBase.RESULTS])
        generator = ','.join(unit[TesterBase.GENERATOR])
        generator = generator.split(",")
        
        passed = True
        prog_out: list[str] = []

        with tempfile.NamedTemporaryFile() as test_file:
            test_file.writelines(str.encode(s + "\n") for s in payload)
            test_file.flush()

            for qval, avgwait, avgresp in cases:
                try:
                    cl_result: str = self.callback(test_file.name, qval)
                except Exception as err:
                    passed = False
                    prog_out.append(f"Program exited with error for quantum of {qval}: {str(err)}")
                    continue

                lines = cl_result.split("\n")
                testAvgWaitTime = float(lines[0].split(":")[1])
                testAvgRespTime = float(lines[1].split(":")[1])
                if testAvgWaitTime != float(avgwait):
                    prog_out.append(f"❌ Average wait: recieved {testAvgWaitTime}, expected {float(avgwait)}, quantum {qval}")
                    passed = False
                if testAvgRespTime != float(avgresp):
                    prog_out.append(f"❌ Average response: recieved {testAvgRespTime}, expected {float(avgresp)}, quantum {qval}")
                    passed = False
                if passed:
                    prog_out.append("✔ both tests passed for quantum of {qval}")

        self.result.add_entry(passed)
        return (passed, prog_out)


class ResultGenerator(TesterBase):
    def __init__(self, test_path: str, callback, **kwargs):
        super().__init__(test_path, callback, **kwargs)
        self.result = NullReport(test_path)

    def trim_output(self, received: str):
        if received.endswith("\n"):
            received = received[:-1]
        return received

    def run_section(self, unit: dict[str, list[str]]):
        payload = unit[TesterBase.PAYLOAD]
        generator = ','.join(unit[TesterBase.GENERATOR])
        generator = generator.split(",")
        prog_out: list[str] = []

        prog_out.append("*payload*")
        prog_out.append("```")
        prog_out.extend(unit[TesterBase.PAYLOAD])
        prog_out.append("```")
        prog_out.append("")
        prog_out.append("*results*")
        prog_out.append("```")

        with tempfile.NamedTemporaryFile() as test_file:
            test_file.writelines(str.encode(s + "\n") for s in payload)
            test_file.flush()

            for qval in generator:
                try:
                    cl_result: str = self.callback(test_file.name, qval)
                except Exception as err:
                    prog_out.append(f"Program exited with error for quantum of {qval}: {str(err)}")
                    continue
                lines = cl_result.split("\n")
                testAvgWaitTime = lines[0].split(":")[1]
                testAvgRespTime = lines[1].split(":")[1]
                prog_out.append(f"{qval}, {testAvgWaitTime}, {testAvgRespTime}")

        prog_out.append("```")
        prog_out.append("")
        prog_out.append("*generator*")
        prog_out.append("```")
        prog_out.extend(unit[TesterBase.GENERATOR])
        prog_out.append("```")
        prog_out.append("")

        return (False, prog_out)


def project_callback(filename: str, q_size: str):
    PROG_NAME = os.path.abspath("./rr")
    retval= None

    try:
        retval = subprocess.check_output((PROG_NAME, filename, q_size)).decode()
    except Exception as err:
        raise err

    return retval


if __name__ == "__main__":
    args = getArguments()
    tester = None
    subprocess.check_output("make")

    if args.test_type == TestingOptions.UNIT_TEST:
        tester = UnitTester("./unit_tests.md", project_callback)
    elif args.test_type == TestingOptions.GEN_CASES:
        tester = ResultGenerator("./unit_tests.md", project_callback)

    if tester is None:
        subprocess.check_output(("make", "clean"))
        raise SystemError("tester did not generate correctly")

    tester.run_tests(**args.filters, verbose=args.verbose)
    tester.result.print_report()
    subprocess.check_output(("make", "clean"))
    pass