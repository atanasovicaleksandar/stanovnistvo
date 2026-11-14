import re

import pandas as pd
import pymupdf


PART_1_COLUMNS = [
    "Укупно",
    "Срби",
    "Црногорци",
    "Југословени",
    "Албанци",
    "Бошњаци",
    "Бугари",
    "Буњевци",
    "Власи",
    "Горанци",
    "Мађари",
    "Македонци",
    "Муслимани",
]

PART_2_COLUMNS = [
    "Немци",
    "Роми",
    "Румуни",
    "Руси",
    "Русини",
    "Словаци",
    "Словенци",
    "Украјинци",
    "Хрвати",
    "Чеси",
    "Остали",
    "Нису се изјаснили",
    "Регионална припадност",
    "Непознато",
]

DETAIL_TABLE_FIRST_PDF_PAGE = 17
SUMMARY_FIRST_PDF_PAGE = 15


def _table_panel(page, part):
    page_text = page.get_text()
    if f"Дeo {part}" not in page_text:
        return None

    expected_columns = 14 if part == 1 else 15
    expected_header = "Срби" if part == 1 else "Роми"
    for table in page.find_tables().tables:
        if table.row_count > 5 or table.col_count != expected_columns:
            continue
        header = " ".join(cell or "" for cell in table.extract()[0])
        if expected_header in header:
            bounds = table.rows[0].cells
            return bounds
    return None


def _clean_label(label):
    label = re.sub(r"\s+г$", "", label.strip())
    return re.sub(r"1\)$", "", label).strip()


def _parse_count(value):
    value = value.strip()
    if value == "-":
        return 0
    if value.isdigit():
        return int(value)
    raise ValueError(f"Unexpected table cell value: {value!r}")


def _overview_row(page, part, target_label):
    bounds = _table_panel(page, part)
    if bounds is None:
        raise ValueError(f"Could not locate overview table Part {part}.")
    rows = _extract_rows(page, bounds, {target_label})
    if not rows:
        raise ValueError(f"Could not read {target_label!r} from overview Part {part}.")
    return rows[0]


def _extract_rows(page, bounds, target_labels=None):
    rows_by_y = {}
    for x0, y0, x1, _y1, text, *_ in page.get_text("words"):
        if y0 < 130 or y0 > 780:
            continue
        rows_by_y.setdefault(round(y0, 1), []).append((x0, x1, text))

    rows = []
    label_right = bounds[0][2]
    for _y, words in sorted(rows_by_y.items()):
        words.sort(key=lambda word: word[0])
        label = " ".join(text for x0, _x1, text in words if x0 < label_right).strip()
        label = _clean_label(label)
        if not label or (target_labels is not None and label not in target_labels):
            continue

        values = [pd.NA] * (len(bounds) - 1)
        for x0, x1, text in words:
            if x0 < label_right:
                continue
            center = (x0 + x1) / 2
            column_index = next(
                (
                    index
                    for index, cell in enumerate(bounds[1:], start=1)
                    if cell[0] <= center <= cell[2]
                ),
                None,
            )
            if column_index is None:
                continue
            values[column_index - 1] = _parse_count(text)

        rows.append((label, values))
        if target_labels is not None:
            return rows
    return rows


def parse_ethnicity_pdf(file_bytes, start_page=14):
    if start_page < 1:
        raise ValueError("PDF start page must be at least 1.")

    document = pymupdf.open(stream=file_bytes, filetype="pdf")
    if len(document) < DETAIL_TABLE_FIRST_PDF_PAGE + 1:
        raise ValueError("The PDF is too short to contain the detailed ethnicity table.")

    panel_bounds = {
        1: _table_panel(document[DETAIL_TABLE_FIRST_PDF_PAGE - 1], 1),
        2: _table_panel(document[DETAIL_TABLE_FIRST_PDF_PAGE], 2),
    }
    if any(bounds is None for bounds in panel_bounds.values()):
        raise ValueError("Could not locate the detailed ethnicity table headers.")

    pending_part_1 = None
    parsed_rows = []

    first_page = max(start_page, DETAIL_TABLE_FIRST_PDF_PAGE)
    for page_index in range(first_page - 1, len(document)):
        page = document[page_index]
        part = 1 if "Дeo 1" in page.get_text() else 2 if "Дeo 2" in page.get_text() else None
        if part is None:
            continue
        page_rows = _extract_rows(page, panel_bounds[part])
        if not page_rows:
            continue

        if part == 1:
            pending_part_1 = page_rows
            continue
        if pending_part_1 is None:
            continue
        if [label for label, _ in pending_part_1] != [label for label, _ in page_rows]:
            raise ValueError(
                f"The Part 1 and Part 2 row labels do not match on PDF pages "
                f"{page_index} and {page_index + 1}."
            )

        for (label, values_1), (_, values_2) in zip(pending_part_1, page_rows):
            parsed_rows.append([label, *values_1, *values_2])
        pending_part_1 = None

    if not parsed_rows:
        raise ValueError(
            f"No detailed ethnicity table found from PDF page {start_page} onward."
        )

    if start_page <= SUMMARY_FIRST_PDF_PAGE:
        overview_1 = _overview_row(
            document[SUMMARY_FIRST_PDF_PAGE - 1], 1, "Београд-насеље"
        )
        overview_2 = _overview_row(document[SUMMARY_FIRST_PDF_PAGE], 2, "Београд-насеље")
        if overview_1[0] != overview_2[0]:
            raise ValueError("The opening overview page labels do not match.")

        belgrade_index = next(
            (
                index
                for index, row in enumerate(parsed_rows)
                if row[0] == "Град Београд"
            ),
            None,
        )
        if belgrade_index is not None:
            parsed_rows.insert(
                belgrade_index + 1,
                [overview_1[0], *overview_1[1], *overview_2[1]],
            )

    return pd.DataFrame(
        parsed_rows,
        columns=["Регион", *PART_1_COLUMNS, *PART_2_COLUMNS],
    )
