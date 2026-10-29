"""CSV export helpers. Spreadsheet programs run cells that start with = + - @ as formulas,
so a record reference like =HYPERLINK(...) must be neutralised before it is exported."""
import csv

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value):
    if isinstance(value, str) and value.startswith(_DANGEROUS):
        return "'" + value
    return value


class _SafeWriter:
    def __init__(self, handle):
        self._w = csv.writer(handle)

    def writerow(self, row):
        return self._w.writerow([safe_cell(v) for v in row])


def safe_csv_writer(handle):
    return _SafeWriter(handle)
