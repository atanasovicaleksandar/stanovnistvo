import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pdf_parser import (
    PART_1_COLUMNS,
    PART_2_COLUMNS,
    _overview_row,
    parse_ethnicity_pdf,
)


class FakeTable:
    def __init__(self, part):
        self.row_count = 2
        self.col_count = 14 if part == 1 else 15
        self.rows = [
            SimpleNamespace(
                cells=[
                    (index * 10, 0, (index + 1) * 10, 10)
                    for index in range(self.col_count)
                ]
            )
        ]
        self._header = ["Срби"] if part == 1 else ["Роми"]

    def extract(self):
        return [self._header]


class FakePage:
    def __init__(self, part, values):
        self.part = part
        self.values = values

    def get_text(self, mode=None):
        if mode == "words":
            return self.values
        return f"Дeo {self.part}"

    def find_tables(self):
        return SimpleNamespace(tables=[FakeTable(self.part)])


class PdfParserTests(unittest.TestCase):
    def test_combines_paired_parts_without_gender_column(self):
        part_1_words = [
            (1, 150, 8, 159, "Тест", 0, 0, 0),
            (11, 150, 19, 159, "100", 0, 0, 1),
            (21, 150, 29, 159, "80", 0, 0, 2),
        ]
        part_2_words = [
            (1, 150, 8, 159, "Тест", 0, 0, 0),
            (11, 150, 19, 159, "5", 0, 0, 1),
            (21, 150, 29, 159, "-", 0, 0, 2),
        ]
        document = [FakePage(None, []) for _ in range(18)]
        document[16] = FakePage(1, part_1_words)
        document[17] = FakePage(2, part_2_words)

        with patch("pdf_parser.pymupdf.open", return_value=document):
            result = parse_ethnicity_pdf(b"test", start_page=17)

        self.assertNotIn("Пол", result.columns)
        self.assertEqual(list(result.columns), ["Регион", *PART_1_COLUMNS, *PART_2_COLUMNS])
        self.assertEqual(result.loc[0, "Регион"], "Тест")
        self.assertEqual(result.loc[0, ["Укупно", "Срби", "Немци"]].tolist(), [100, 80, 5])
        self.assertEqual(result.loc[0, "Роми"], 0)

    def test_overview_row_uses_counts_not_later_percentages(self):
        words = [
            (1, 150, 8, 159, "Београд-насеље", 0, 0, 0),
            (11, 150, 19, 159, "110", 0, 0, 1),
            (21, 150, 29, 159, "90", 0, 0, 2),
            (1, 200, 8, 209, "Београд-насеље", 0, 1, 0),
            (11, 200, 19, 209, "100.00", 0, 1, 1),
        ]

        row = _overview_row(FakePage(1, words), 1, "Београд-насеље")

        self.assertEqual(row[0], "Београд-насеље")
        self.assertEqual(row[1][:2], [110, 90])

    def test_rejects_nonpositive_start_page(self):
        with self.assertRaisesRegex(ValueError, "at least 1"):
            parse_ethnicity_pdf(b"test", start_page=0)


if __name__ == "__main__":
    unittest.main()
