import os
import re
import time
import tempfile


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


class ProfilerStats(PrintableReport):
    def __init__(self, test_path: str) -> None:
        super().__init__(test_path)
        self.__start = None
        self.__records: list[float] = []

    def start(self):
        self.__start = time.time()

    def record(self):
        if self.__start is None:
            raise RuntimeError("Cannot call end before start")
        self.__records.append(time.time() - self.__start)
        self.__start = None

    def total_time(self):
        return sum(self.__records)

    def average_time(self):
        if len(self.__records):
            return self.total_time() / len(self.__records)
        else:
            return float("NaN")

    def print_report(self):
        COLSIZE = 14
        out_report = []
        out_report.append(f"{'suite:':<{COLSIZE}}{self.suite_name}")
        out_report.append(
            f"{'average time:':<{COLSIZE}}{1000 * self.average_time()} ms"
        )
        out_report.append(f"{'total time:':<{COLSIZE}}{1000 * self.total_time()} ms\n")
        super().print_report(out_report)


class NullReport(PrintableReport):
    def print_report(self):
        pass  # nothing to do here


class TesterBase:
    PAYLOAD = "payload"
    RESULTS = "results"
    GENERATOR = "generator"
    TAB = "  "

    def __init__(self, test_path: str, callback, *args):
        self.__callback = callback
        self.__args = args
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

    def callback(self, prog_arg: str, quantum_size: str, *args):
        return self.__callback(prog_arg, quantum_size, *self.__args)

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

    def make_md_table(self, entries: list[tuple], alignment: tuple[str], indentation=0):
        if not entries:
            return []

        table_out: list[str] = []
        TAB = TesterBase.TAB * indentation
        ALIGN_SEP = {
            "N": (" ", " "),
            "L": (":", " "),
            "R": (" ", ":"),
            "C": (":", ":"),
        }
        ALIGN_FMT = {
            "N": "<",
            "L": "<",
            "R": ">",
            "C": "^",
        }
        format_row = lambda st: TAB + "|" + st + "|"
        pipe_join = lambda it: "|".join(str(i) for i in it)
        get_divs = lambda sz, al: (align_divs(*a, "-" * s) for s, a in zip(sz, al))
        align_divs = lambda L, R, s: f"{L}{s}{R}"

        COLS = len(entries[0])
        ALSZ = len(alignment)
        col_size = [0] * COLS

        if COLS < len(alignment):
            alignment = alignment[:COLS]
        elif COLS > len(alignment):
            alignment = (alignment[i] if i < ALSZ else "N" for i in range(COLS))

        sep_aligners = [ALIGN_SEP[a.upper()] for a in alignment]
        fmt_aligners = [ALIGN_FMT[a.upper()] for a in alignment]

        for row in entries:
            if len(row) != COLS:
                return ["Error: row size must be uniform"]
            for i, cell in enumerate(row):
                col_size[i] = max(col_size[i], len(str(cell)))

        table_out.append(format_row(pipe_join(get_divs(col_size, sep_aligners))))

        for row in entries:
            row_str = []
            for cell, size, alg in zip(row, col_size, fmt_aligners):
                row_str.append(f" {cell:{alg}{size}} ")
            table_out.append(format_row(pipe_join(row_str)))

        table_out[0], table_out[1] = table_out[1], table_out[0]
        return table_out

    def run_tests(self, section_filter: set[str], verbose: bool):
        self._verbose = verbose
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

        if print_buffer[-1] == "":
            print_buffer.pop()

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
            state == "payload-end" or state == "results-end" or state == "generator-end"
        ):
            pass  # nothing to do here

        else:
            raise SyntaxError(
                f"Fatal error at:" + f"`{line}'.\nInvalid state transition."
            )

        return state


class UnitTester(TesterBase):
    def __init__(self, test_path: str, callback, *args):
        super().__init__(test_path, callback, *args)
        self.result = TestResults(test_path)

    def trim_output(self, received: str):
        if received.endswith("\n"):
            received = received[:-1]
        return received

    def run_section(self, unit: dict[str, list[str]]):
        payload = unit[TesterBase.PAYLOAD]
        cases = (tuple(test.split(",")) for test in unit[TesterBase.RESULTS])
        generator = ",".join(unit[TesterBase.GENERATOR])
        generator = generator.split(",")

        INDENT_LEVEL = 0
        passed_all = True
        prog_out: list[str] = []

        with tempfile.NamedTemporaryFile() as test_file:
            test_file.writelines(str.encode(s + "\n") for s in payload)
            test_file.flush()

            md_table = [("qm", "average", "received", "expected", "status")]
            md_format = ("R", "L", "R", "R", "L")
            err_iter = 0

            for qval, avgwait, avgresp in cases:
                try:
                    cl_result: str = self.callback(test_file.name, qval)
                except Exception as err:
                    passed_all = False
                    err_iter += 1
                    md_table.append(
                        (qval, "none", "crashed", "n/a", f"see error {err_iter}")
                    )
                    prog_out.append(
                        TesterBase.TAB * INDENT_LEVEL
                        + f"{err_iter}. Crashed "
                        + f"(quantum={qval}): {str(err)}"
                    )
                    continue

                lines = cl_result.split("\n")
                testAvgWaitTime = float(lines[0].split(":")[1])
                testAvgRespTime = float(lines[1].split(":")[1])
                status_msg = ""

                passed = True
                if testAvgWaitTime != float(avgwait):
                    status_msg = "FAIL"
                    passed_all = passed = False
                else:
                    status_msg = "pass"

                if self._verbose or not passed:
                    md_table.append(
                        (qval, "wait", testAvgWaitTime, float(avgwait), status_msg)
                    )

                passed = True
                if testAvgRespTime != float(avgresp):
                    status_msg = "FAIL"
                    passed_all = passed = False
                else:
                    status_msg = "pass"

                if self._verbose or not passed:
                    md_table.append(
                        (qval, "response", testAvgRespTime, float(avgresp), status_msg)
                    )

        if err_iter:
            prog_out.append("")
        prog_out.extend(self.make_md_table(md_table, md_format, INDENT_LEVEL))
        prog_out.append("")
        self.result.add_entry(passed_all)
        return (passed_all, prog_out)


class ResultGenerator(TesterBase):
    def __init__(self, test_path: str, callback, *args):
        super().__init__(test_path, callback, *args)
        self.result = NullReport(test_path)

    def trim_output(self, received: str):
        if received.endswith("\n"):
            received = received[:-1]
        return received

    def run_section(self, unit: dict[str, list[str]]):
        payload = unit[TesterBase.PAYLOAD]
        generator = ",".join(unit[TesterBase.GENERATOR])
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
                    prog_out.append(f"Crashed (quantum={qval}): {str(err)}")
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


class BatchRun(TesterBase):
    def __init__(self, test_path: str, callback, *args):
        super().__init__(test_path, callback, *args)
        self.result = ProfilerStats(test_path)

    def trim_output(self, received: str):
        if received.endswith("\n"):
            received = received[:-1]
        return received

    def run_section(self, unit: dict[str, list[str]]):
        payload = unit[TesterBase.PAYLOAD]
        generator = ",".join(unit[TesterBase.GENERATOR])
        generator = generator.split(",")
        prog_out: list[str] = []

        with tempfile.NamedTemporaryFile() as test_file:
            test_file.writelines(str.encode(s + "\n") for s in payload)
            test_file.flush()

            md_table = [("pid", "arrival", "burst")]
            md_table.extend(p.split(",") for p in payload[1:])
            md_format = ("R", "R", "R")
            prog_out.extend(self.make_md_table(md_table, md_format))
            prog_out.append("")

            for qval in generator:
                try:
                    self.result.start()
                    cl_result: str = self.callback(test_file.name, qval, "1")
                except Exception as err:
                    prog_out.append(f"Crashed (quantum={qval}): {str(err)}")
                    continue
                finally:
                    self.result.record()
                lines = cl_result.split("\n")
                if lines[-1] == "":
                    lines.pop()
                prog_out.append(f"### Run with quantum {qval}")
                prog_out.append("```")
                prog_out.extend(lines)
                prog_out.append("```")
                prog_out.append("")

        return (False, prog_out)
