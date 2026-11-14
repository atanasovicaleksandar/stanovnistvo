import io
import re
import unicodedata

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from matplotlib.colors import ListedColormap

from pdf_parser import parse_ethnicity_pdf

# Kako srediti Crnogorce...

# 1. Get the original 20 colors as RGB tuples
tab20_colors = list(plt.cm.tab20.colors)

# 2. Define your 21st color (Hex or RGB tuple)
new_color = '#B59C7B' 

# 3. Append it to the list
tab20_colors.append(new_color)

# 4. Create the new colormap
custom_tab21 = ListedColormap(tab20_colors)

ID_COLS = ["Регион"]
YEAR_COL = "Год пописа"
AREA_KEY_COL = "Geographic key"
CENSUS_YEARS = [2022, 2011, 2002, 1991, 1981]
OTHER_YEAR = "Other year"
LEVELS = ["Serbia", "Macroregion", "Oblast", "Region", "Municipality"]
HIERARCHY_COLS = ["Serbia", "Macroregion", "Oblast", "Region", "Municipality"]
EXCLUDED_GROUPS = {
    "Остали",
    "Остала",
    "Градска",
    "Регионална припадност",
    "Нису се изјаснили",
    "Непознато",
    "Ostali",
    "Ostala",
    "Gradska",
}
SUMMARY_GEOGRAPHIES = {
    "укупно", "свега", "укупно становништво", "градским", "у градским",
    "у осталим", "осталим", "сеоским",
}

LATIN_TO_CYRILLIC = str.maketrans({
    "a": "а", "b": "б", "v": "в", "g": "г", "d": "д", "đ": "ђ",
    "e": "е", "ž": "ж", "z": "з", "i": "и", "j": "ј", "k": "к",
    "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "r": "р",
    "s": "с", "t": "т", "ć": "ћ", "u": "у", "f": "ф", "h": "х",
    "c": "ц", "č": "ч", "š": "ш",
})

# Structural header -> short Serbian header
RENAME = {
    'Регион Област Град – општина': 'Регион',
}

LATIN_LOOKALIKES = str.maketrans({
    "A": "А", "a": "а", "O": "О", "o": "о",
})

LEGACY_ETHNICITY_TOKENS = (
    "срби", "црногорци", "хрвати", "македонци", "муслимани",
    "албанци", "бугари", "власи", "грци", "немци", "роми",
    "румуни", "руси", "словенци", "турци", "украјинци",
    "југословени", "шокци", "чеси", "словачки",
)


def normalize_header(value):
    value = str(value).replace("\u00a0", " ")
    value = re.sub(r"[–—−]", "-", value)
    return " ".join(value.split()).casefold()


def is_excluded_group(value):
    if value is None:
        return False
    normalized = normalize_header(value)
    if not normalized:
        return False
    if normalized in {normalize_header(group) for group in EXCLUDED_GROUPS}:
        return True
    return normalized in {
        "градским",
        "у градским",
        "осталим",
        "у осталим",
    } or normalized.startswith(
        ("у градским ", "у осталим ", "u gradskim ", "u ostalim ")
    )


def clean_column_name(value):
    value = str(value).replace("\u00a0", " ")
    value = re.sub(r"[–—−]", "-", value)
    parts = []
    for part in " ".join(value.split()).split(" "):
        has_cyrillic = any(
            "CYRILLIC" in unicodedata.name(character, "") for character in part
        )
        if has_cyrillic:
            part = part.translate(LATIN_LOOKALIKES)
            part = "".join(
                character for character in part
                if "LATIN" not in unicodedata.name(character, "")
            )
            parts.append(part)
        elif not any(
            "LATIN" in unicodedata.name(character, "") for character in part
        ):
            parts.append(part)
    return " ".join(part for part in parts if part)


def _legacy_census_file_name_looks_like_supported(name):
    lowered = (name or "").lower()
    return "popis" in lowered and ("1981" in lowered or "1991" in lowered)


def _infer_census_year(file_name):
    match = re.search(r"(?<!\d)(2022|2011|2002|1991|1981)(?!\d)", file_name or "")
    return int(match.group(1)) if match else None


def _normalized_geography_name(value):
    normalized = str(value).strip().casefold()
    normalized = re.sub(r"[–—−]", "-", normalized)
    normalized = re.sub(r"dž", "џ", normalized)
    normalized = re.sub(r"lj", "љ", normalized)
    normalized = re.sub(r"nj", "њ", normalized)
    normalized = normalized.translate(LATIN_TO_CYRILLIC)
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def _canonical_geography_label(value):
    if value is None or pd.isna(value):
        return value
    label = str(value).strip()
    normalized = _normalized_geography_name(label)
    canonical_names = {
        "г милановац": "Горњи Милановац",
        "горњи милановац": "Горњи Милановац",
        "срем карловци": "Сремски Карловци",
        "сремски карловци": "Сремски Карловци",
        "срем митровица": "Сремска Митровица",
        "сремска митровица": "Сремска Митровица",
        "кос каменица": "Косовска Каменица",
        "косовска каменица": "Косовска Каменица",
        "кос митровица": "Косовска Митровица",
        "косовска митровица": "Косовска Митровица",
    }
    if normalized in canonical_names:
        return canonical_names[normalized]
    if normalized in {"србија", "република србија"}:
        return "Република Србија"
    if not label.isupper():
        return label

    words = label.lower().title().split()
    lowercase_words = {"и", "у", "на", "из", "са", "за", "до", "област", "регион"}
    return " ".join(
        word.lower() if index > 0 and word.casefold() in lowercase_words else word
        for index, word in enumerate(words)
    )


SPECIAL_OBLAST_TO_REGION = {
    "београдска област": "Београдски регион",
}


def _geographic_level(value):
    raw_name = str(value).strip().casefold()
    if raw_name in {"serbia", "republic of serbia"}:
        return "Serbia"
    if raw_name in {"central serbia"}:
        return "Macroregion"

    normalized = _normalized_geography_name(value)
    words = normalized.split()
    if normalized in {"србија", "република србија"}:
        return "Serbia"
    if normalized in {
        "централна србија", "војводина", "србија север", "србија југ",
        "република србија север", "република србија југ",
        "србијасевер", "србијајуг",
    }:
        return "Macroregion"
    if "област" in words:
        return "Oblast"
    if "регион" in words:
        return "Region"
    if normalized == "град београд":
        return "Region"
    if normalized in SUMMARY_GEOGRAPHIES or normalized.startswith(
        ("укупно ", "свега ", "у градским ", "у осталим ", "у сеоским ")
    ):
        return None
    return "Municipality"


def _geographic_key(name, level):
    if level == "Serbia":
        return "serbia:република-србија"
    normalized = _normalized_geography_name(name)
    normalized = re.sub(r"^(општина|град|муниципалитет)\s+", "", normalized)
    return f"{level.casefold()}:{normalized.replace(' ', '-')}"


def filter_geographies(data, selected_regions=(), selected_levels=()):
    if selected_regions:
        filtered = data[data[AREA_KEY_COL].isin(selected_regions)]
        if selected_levels:
            filtered = filtered[filtered["Geographic level"].isin(selected_levels)]
        return filtered
    if selected_levels:
        return data[data["Geographic level"].isin(selected_levels)]
    return data[data["Geographic level"].eq("Municipality")]


def area_options_for_levels(area_labels, selected_levels=(), search_text=""):
    levels = selected_levels or ("Municipality",)
    options = area_labels.loc[area_labels["Geographic level"].isin(levels)]
    normalized_query = _normalized_geography_name(search_text) if search_text else ""
    if normalized_query:
        matches = options["Регион"].map(
            lambda name: normalized_query in _normalized_geography_name(name)
        )
        options = options.loc[matches]
    return options


def ambiguous_2022_hierarchy_keys(reference_rows):
    parent_columns = [column for column in HIERARCHY_COLS if column != "Municipality"]
    ambiguous_keys = set()
    for area_key, rows in reference_rows.groupby(AREA_KEY_COL):
        if any(rows[column].dropna().nunique() > 1 for column in parent_columns):
            ambiguous_keys.add(area_key)
    return ambiguous_keys


def municipality_match_report(data):
    municipalities = data[data["Geographic level"].eq("Municipality")]
    keys_by_year = {
        year: set(rows[AREA_KEY_COL])
        for year, rows in municipalities.groupby(YEAR_COL)
    }
    if not keys_by_year:
        return pd.DataFrame()
    common_keys = set.intersection(*keys_by_year.values())

    report_rows = []
    for year, keys in sorted(keys_by_year.items()):
        unmatched_keys = keys - common_keys
        unmatched_names = municipalities.loc[
            municipalities[YEAR_COL].eq(year)
            & municipalities[AREA_KEY_COL].isin(unmatched_keys),
            "Регион",
        ].drop_duplicates()
        report_rows.append(
            {
                YEAR_COL: year,
                "Municipalities": len(keys),
                "Matched across all years": len(keys & common_keys),
                "Without match": len(unmatched_keys),
                "Areas without match": ", ".join(sorted(unmatched_names.astype(str))),
            }
        )
    return pd.DataFrame(report_rows)


def _legacy_tuple_label(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s*1\)\s*$", "", text)
    text = re.sub(r"[–—−]", "-", text)
    text = re.sub(r"\s*-\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _legacy_group_name(value):
    text = _legacy_tuple_label(value)
    if not text:
        return ""
    lowered = text.casefold()
    lowered = re.sub(r"\s*[-–—−]\s*", "", lowered)
    if lowered in {"укупно", "свега"}:
        return "Укупно"
    if lowered.startswith("национална") or lowered.startswith("национално"):
        return ""
    return text.strip()


def _legacy_summary_name(value):
    text = _legacy_tuple_label(value).casefold()
    if not text:
        return True
    return (
        text in {
            "укупно",
            "у к у п н о",
            "у градским",
            "у осталим",
            "градска",
            "остала",
        }
        or "у к у п н о" in text
        or text.startswith(("у градским ", "у осталим "))
    )


def _legacy_1991_geography_label(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    raw_label = str(value).replace("\n", " ").replace("\r", " ")
    raw_label = raw_label.replace("\u00a0", " ").strip()
    raw_label = re.sub(r"\s*1\)\s*$", "", raw_label)

    raw_label = re.sub(
        r"\s*[-–—−]\s*град\s*$",
        "",
        raw_label,
        flags=re.IGNORECASE,
    )
    city_prefix = re.match(
        r"^(?:београд|ниш)\s*[-–—−]\s*(.*)$",
        raw_label,
        flags=re.IGNORECASE,
    )
    if city_prefix:
        raw_label = city_prefix.group(1).strip()
    label = _legacy_tuple_label(raw_label)
    prefix = "београд"
    normalized_label = _normalized_geography_name(label)
    if label.casefold().startswith(prefix) and not normalized_label.startswith(
        ("београдски ", "београдска ")
    ):
        municipality = label[len(prefix):].strip()
        if municipality:
            label = municipality[0].upper() + municipality[1:]

    label = re.sub(r"^г\.\s*", "", label, flags=re.IGNORECASE).strip()
    if _normalized_geography_name(label) in {"г", "део г"}:
        return ""
    return label


def _legacy_numeric_value(value):
    if value in (None, "", "-", "—"):
        return False
    if isinstance(value, (int, float)) and not pd.isna(value):
        return True
    text = str(value).strip()
    if not text or text in {"Укупно", "Национална припадност", "Национално се изјаснили"}:
        return False
    try:
        float(text.replace(",", "."))
        return True
    except ValueError:
        return False


def parse_legacy_census_excel(file_bytes, file_name, census_year=None):
    extension = file_name.rsplit(".", 1)[-1].lower()
    excel_engines = {
        "xls": "xlrd",
        "xlsx": "openpyxl",
        "xlsm": "openpyxl",
        "xlsb": "pyxlsb",
        "ods": "odf",
    }
    if extension not in excel_engines:
        raise ValueError(f"Unsupported legacy Excel type: .{extension}")
    census_year = census_year if census_year is not None else _infer_census_year(file_name)

    workbook = pd.read_excel(
        io.BytesIO(file_bytes),
        engine=excel_engines[extension],
        header=None,
    )

    header_idx = None
    for idx, row in workbook.iterrows():
        values = [
            _legacy_tuple_label(value)
            for value in row.tolist()
        ]
        nonempty = [value for value in values if value]
        if len(nonempty) < 4:
            continue
        if any(
            any(token in value.casefold() for token in LEGACY_ETHNICITY_TOKENS)
            for value in values[1:]
            if value
        ):
            header_idx = idx
            break
    if header_idx is None:
        raise ValueError("Could not detect an ethnicity header in the legacy census workbook.")

    header_values = [
        _legacy_group_name(value)
        for value in workbook.iloc[header_idx].tolist()[1:]
    ]
    groups = [group for group in header_values if group and not is_excluded_group(group)]
    if not groups:
        raise ValueError("No ethnicity groups found in the legacy census header.")

    current_region = None
    rows = []
    for idx in range(header_idx + 1, len(workbook)):
        row = workbook.iloc[idx].tolist()
        first_cell = row[0] if row else ""
        if census_year in {1991, 2011}:
            first_cell = _legacy_1991_geography_label(first_cell)
        else:
            first_cell = _legacy_tuple_label(first_cell)
        if not first_cell or _legacy_summary_name(first_cell):
            continue

        data_values = row[1:1 + len(groups)]
        data_values.extend([None] * (len(groups) - len(data_values)))
        has_data = any(_legacy_numeric_value(value) for value in data_values)

        if has_data:
            records = {"Регион": first_cell}
            for group, value in zip(groups, data_values):
                if _legacy_numeric_value(value):
                    records[group] = pd.to_numeric(value, errors="coerce")
                else:
                    records[group] = pd.NA
            rows.append(records)
            current_region = None
            continue

        if first_cell not in {"У К У П Н О", "У ГРАДСКИМ", "У ОСТАЛИМ"}:
            current_region = first_cell

    if not rows:
        raise ValueError("Legacy census workbook had no parsable rows.")

    df = pd.DataFrame(rows)
    if not df.empty and groups:
        df = df.dropna(axis=0, how="all", subset=groups)
    return df.reset_index(drop=True)


# Possibly to filter out regions not in use...
#regions = []

@st.cache_data(show_spinner="Cleaning data...")
def load_and_clean(file_bytes, file_name, header_row, footer_rows, extra_cols, census_year=None):
    extension = file_name.rsplit(".", 1)[-1].lower()
    excel_engines = {
        "xls": "xlrd",
        "xlsx": "openpyxl",
        "xlsm": "openpyxl",
        "xlsb": "pyxlsb",
        "ods": "odf",
    }
    file_buffer = io.BytesIO(file_bytes)
    if extension == "csv":
        df = pd.read_csv(
            file_buffer, sep=None, engine="python", encoding="utf-8-sig", header=header_row
        )
    elif extension in excel_engines:
        if _legacy_census_file_name_looks_like_supported(file_name) or census_year in {1981, 1991}:
            return clean_dataframe(
                parse_legacy_census_excel(file_bytes, file_name, census_year),
                footer_rows,
                extra_cols,
                census_year,
            )
        df = pd.read_excel(
            file_buffer, engine=excel_engines[extension], header=header_row
        )
    else:
        raise ValueError(f"Unsupported file type: .{extension}")

    return clean_dataframe(df, footer_rows, extra_cols, census_year)


@st.cache_data(show_spinner="Reading PDF table...")
def load_pdf_and_clean(file_bytes, start_page):
    return clean_dataframe(parse_ethnicity_pdf(file_bytes, start_page))


def clean_dataframe(df, footer_rows=0, extra_cols=0, census_year=None):
    cleaned_columns = [clean_column_name(column) for column in df.columns]
    rename_by_normalized_header = {
        normalize_header(source): target for source, target in RENAME.items()
    }
    df.columns = [
        rename_by_normalized_header.get(normalize_header(column), column)
        for column in cleaned_columns
    ]
    df = df.replace(" ", pd.NA).dropna(axis=0, how="all")

    if footer_rows:
        df = df.iloc[:-footer_rows, :]
    if extra_cols:
        df = df.iloc[:, :-extra_cols]

    df = df.replace("-", pd.NA).rename(columns=RENAME)

    missing = [c for c in ID_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Expected columns not found: {missing}. Detected columns: "
            f"{list(df.columns)}. Check the header row setting."
        )

    # Fill merged-cell gaps only in the label columns.
    # (Forward-filling the numbers would copy values into cells that were '-'.)
    identity_cols = ID_COLS + (["Пол"] if "Пол" in df.columns else [])
    df[identity_cols] = df[identity_cols].ffill()
    if census_year in {1991, 2011}:
        df["Регион"] = df["Регион"].map(_legacy_1991_geography_label)
        df = df.loc[df["Регион"].ne("")].copy()
    df["Регион"] = df["Регион"].map(_canonical_geography_label)
    if "Пол" in df.columns:
        combined_sex = df["Пол"].astype("string").str.strip().str.casefold().eq("с")
        if not combined_sex.any():
            detected = sorted(
                str(value) for value in df["Пол"].dropna().unique()
            )
            raise ValueError(
                "Expected combined-sex rows marked 'с' in the Пол column. "
                f"Detected values: {detected}"
            )
        df = df.loc[combined_sex].drop(columns=["Пол"]).copy()

    df["Geographic level"] = df["Регион"].map(_geographic_level)
    df = df.loc[~df["Регион"].map(is_excluded_group)].copy()
    df = df.loc[df["Geographic level"].notna()].copy()
    df[AREA_KEY_COL] = [
        _geographic_key(name, level)
        for name, level in zip(df["Регион"], df["Geographic level"])
    ]

    hierarchy = {column: pd.NA for column in HIERARCHY_COLS}
    aligned_rows = []
    for name, level in zip(df["Регион"], df["Geographic level"]):
        if level == "Serbia":
            hierarchy = {column: pd.NA for column in HIERARCHY_COLS}
            hierarchy["Serbia"] = name
        elif level == "Macroregion":
            hierarchy["Macroregion"] = name
            hierarchy["Oblast"] = pd.NA
            hierarchy["Region"] = pd.NA
            hierarchy["Municipality"] = pd.NA
        elif level == "Oblast":
            hierarchy["Oblast"] = name
            parent_region = SPECIAL_OBLAST_TO_REGION.get(
                _normalized_geography_name(name)
            )
            if parent_region:
                hierarchy["Region"] = parent_region
            hierarchy["Municipality"] = pd.NA
        elif level == "Region":
            if str(name).strip().casefold() == "град београд":
                hierarchy["Macroregion"] = pd.NA
                hierarchy["Oblast"] = pd.NA
            hierarchy["Oblast"] = pd.NA
            hierarchy["Region"] = name
            hierarchy["Municipality"] = pd.NA
        else:
            hierarchy["Municipality"] = name
        aligned_rows.append(hierarchy.copy())
    aligned = pd.DataFrame(aligned_rows, index=df.index)
    df[HIERARCHY_COLS] = aligned[HIERARCHY_COLS]
    df = df.drop(columns=[column for column in df.columns if is_excluded_group(column)])

    identity_cols = ID_COLS + [AREA_KEY_COL] + (["Пол"] if "Пол" in df.columns else [])
    value_cols = [c for c in df.columns if c not in identity_cols]
    value_cols = [
        c for c in value_cols
        if c not in HIERARCHY_COLS + ["Geographic level"] and not is_excluded_group(c)
    ]
    df[value_cols] = df[value_cols].apply(pd.to_numeric, errors="coerce")
    return df.reset_index(drop=True), value_cols


def add_geographic_hierarchy_aggregates(data):
    required = {YEAR_COL, AREA_KEY_COL, "Geographic level", *HIERARCHY_COLS}
    if not required.issubset(data.columns):
        return data

    municipality_rows = data[data["Geographic level"].eq("Municipality")].copy()
    if municipality_rows.empty:
        return data

    reference_rows = municipality_rows[municipality_rows[YEAR_COL].eq(2022)]
    if not reference_rows.empty:
        parent_hierarchy_columns = [
            column for column in HIERARCHY_COLS if column != "Municipality"
        ]
        ambiguous_keys = ambiguous_2022_hierarchy_keys(reference_rows)
        hierarchy_by_area = {}
        for area_key, rows in reference_rows.groupby(AREA_KEY_COL):
            if area_key in ambiguous_keys:
                continue
            hierarchy = {}
            for column in parent_hierarchy_columns:
                values = rows[column].dropna().drop_duplicates()
                hierarchy[column] = values.iloc[0] if not values.empty else pd.NA
            hierarchy_by_area[area_key] = hierarchy

        for column in parent_hierarchy_columns:
            mapped_values = municipality_rows[AREA_KEY_COL].map(
                {
                    area_key: hierarchy[column]
                    for area_key, hierarchy in hierarchy_by_area.items()
                    if pd.notna(hierarchy[column])
                }
            )
            has_reference = mapped_values.notna()
            municipality_rows.loc[has_reference, column] = mapped_values.loc[has_reference]

    value_cols = [
        column
        for column in municipality_rows.columns
        if column not in {YEAR_COL, *ID_COLS, AREA_KEY_COL, "Geographic level", *HIERARCHY_COLS}
        and not is_excluded_group(column)
    ]
    if not value_cols:
        return data

    aggregated_rows = []

    def append_grouped_rows(frame, level_name, label_column, group_columns):
        frame = frame.loc[frame[label_column].notna()]
        if frame.empty:
            return
        grouped = frame.groupby(group_columns, dropna=False, as_index=False)[value_cols].sum()
        for _, grouped_row in grouped.iterrows():
            label = grouped_row[label_column]
            record = {
                YEAR_COL: grouped_row[YEAR_COL],
                "Регион": label,
                AREA_KEY_COL: _geographic_key(str(label), level_name),
                "Geographic level": level_name,
            }
            for column in HIERARCHY_COLS:
                record[column] = grouped_row[column] if column in group_columns else pd.NA
            for column in value_cols:
                record[column] = grouped_row[column]
            aggregated_rows.append(record)

    for year, frame in municipality_rows.groupby(YEAR_COL, dropna=False):
        total = frame[value_cols].sum()
        serbia_name = frame["Serbia"].dropna().iloc[0] if frame["Serbia"].notna().any() else "Република Србија"
        serbia_record = {
            YEAR_COL: year,
            "Регион": serbia_name,
            AREA_KEY_COL: _geographic_key(str(serbia_name), "Serbia"),
            "Geographic level": "Serbia",
        }
        for column in HIERARCHY_COLS:
            serbia_record[column] = serbia_name if column == "Serbia" else pd.NA
        serbia_record.update(total.to_dict())
        aggregated_rows.append(serbia_record)

        append_grouped_rows(
            frame,
            "Macroregion",
            "Macroregion",
            [YEAR_COL, "Serbia", "Macroregion"],
        )
        append_grouped_rows(
            frame,
            "Region",
            "Region",
            [YEAR_COL, "Serbia", "Macroregion", "Region"],
        )
        append_grouped_rows(
            frame,
            "Oblast",
            "Oblast",
            [YEAR_COL, "Serbia", "Macroregion", "Region", "Oblast"],
        )

    return pd.concat(
        [municipality_rows, pd.DataFrame(aggregated_rows)],
        ignore_index=True,
        sort=False,
    )


def to_excel_bytes(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    return buf.getvalue()


def region_pivot(long, groups, top_n, as_share):
    has_year = YEAR_COL in long.columns
    year_count = long[YEAR_COL].nunique(dropna=True) if has_year else 0
    has_multiple_years = year_count > 1
    area_count = (
        long[AREA_KEY_COL].nunique(dropna=True)
        if AREA_KEY_COL in long.columns
        else long["Регион"].nunique(dropna=True)
    )
    one_area_across_years = has_multiple_years and area_count == 1
    index = (
        [YEAR_COL]
        if one_area_across_years
        else [YEAR_COL, "Регион"] if has_multiple_years
        else ["Регион"]
    )
    pv = long.pivot_table(index=index, columns="Група", values="Број становника", aggfunc="sum")
    pv = pv[[g for g in groups if g in pv.columns]]
    if has_multiple_years:
        pv = pv.sort_index()
        if not one_area_across_years:
            top_regions = (
                pv.groupby(level="Регион")
                .sum()
                .sum(axis=1)
                .nlargest(top_n)
                .index
            )
            pv = pv.loc[pv.index.get_level_values("Регион").isin(top_regions)]
    else:
        if has_year:
            pv = pv.sort_index()
        pv = pv.loc[pv.sum(axis=1).nlargest(top_n).index]
    if as_share:
        pv = pv.div(pv.sum(axis=1), axis=0) * 100
    return pv


def build_figure(kind, long, groups, top_n, as_share, log_scale, title):
    sns.set_theme(style="whitegrid")
    n = max(len(groups), 1)
    has_multiple_years = (
        YEAR_COL in long.columns and long[YEAR_COL].nunique(dropna=True) > 1
    )
    hue = YEAR_COL if has_multiple_years else None

    if kind == "Grouped bar (by group)":
        fig, ax = plt.subplots(figsize=(max(8, 0.9 * n), 5))
        sns.barplot(data=long, x="Група", y="Број становника", hue=hue,
                    order=groups, estimator="sum", errorbar=None, ax=ax)
        if log_scale:
            ax.set_yscale("log")
        else:
            ax.ticklabel_format(useOffset=False, style="plain", axis="y")

    elif kind == "Boxplot (spread across regions)":
        fig, ax = plt.subplots(figsize=(max(8, 0.9 * n), 5))
        sns.boxplot(data=long, x="Група", y="Број становника", hue=hue, order=groups, ax=ax)
        if log_scale:
            ax.set_yscale("log")

    elif kind == "Trend (by census year)":
        fig, ax = plt.subplots(figsize=(max(8, 0.9 * n), 5))
        sns.lineplot(
            data=long,
            x=YEAR_COL,
            y="Број становника",
            hue="Група",
            estimator="sum",
            errorbar=None,
            marker="o",
            ax=ax,
        )
        ax.set_xticks(sorted(long[YEAR_COL].dropna().unique()))
        if log_scale:
            ax.set_yscale("log")
        else:
            ax.ticklabel_format(useOffset=False, style="plain", axis="y")

    elif kind == "Stacked bar (by region)":
        pv = region_pivot(long, groups, top_n, as_share)
        fig, ax = plt.subplots(figsize=(max(8, 0.6 * len(pv)), 6))
        pv.plot(kind="bar", stacked=True, ax=ax,
            color=sns.color_palette(custom_tab21.colors, n_colors=len(pv.columns)))
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left")
        ax.set_ylabel("%" if as_share else "Број становника")

        ax.ticklabel_format(useOffset=False, style="plain", axis="y")


    else:  # Heatmap
        pv = region_pivot(long, groups, top_n, as_share)
        fig, ax = plt.subplots(figsize=(max(7, 0.9 * n), max(4, 0.4 * len(pv))))
        annotate = pv.size <= 200
        sns.heatmap(pv, annot=annotate, fmt=".1f" if as_share else ",.0f",
                    cmap="YlGnBu", ax=ax)

    ax.set_xlabel("")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    if title:
        ax.set_title(title)
    fig.tight_layout()
    return fig


if __name__ == "__main__":
    st.set_page_config(page_title="Sredi mi podatke!!!", layout="wide")

    # ------------------------------------------------------------------ UI
    st.title("Sredi mi podatke!")

    uploaded = st.file_uploader(
        "Upload one or more Excel, CSV, or PDF files",
        type=["xls", "xlsx", "xlsm", "xlsb", "ods", "csv", "pdf"],
        accept_multiple_files=True,
    )

    if not uploaded:
        st.info("Upload an Excel or PDF file to get started.")
        st.stop()

    file_settings = []
    with st.sidebar:
        st.header("Census files")
        for index, file in enumerate(uploaded):
            with st.expander(file.name, expanded=True):
                inferred_year = _infer_census_year(file.name)
                year_options = [None, *CENSUS_YEARS, OTHER_YEAR]
                default_index = (
                    year_options.index(inferred_year)
                    if inferred_year in CENSUS_YEARS
                    else 0
                )
                year_choice = st.selectbox(
                    "Census year",
                    year_options,
                    index=default_index,
                    format_func=lambda year: (
                        "Select a year" if year is None
                        else "Other year" if year == OTHER_YEAR
                        else str(year)
                    ),
                    key=f"census_year_{index}_{file.name}",
                )
                if year_choice == OTHER_YEAR:
                    census_year = st.number_input(
                        "Enter census year",
                        min_value=1800,
                        max_value=2200,
                        value=2000,
                        step=1,
                        key=f"custom_census_year_{index}_{file.name}",
                    )
                else:
                    census_year = year_choice

                settings = {"year": census_year}
                if file.name.lower().endswith(".pdf"):
                    settings["start_page"] = st.number_input(
                        "PDF table starts at page",
                        min_value=1,
                        value=14,
                        key=f"pdf_start_page_{index}_{file.name}",
                    )
                else:
                    settings["header_row"] = st.number_input(
                        "Header row (0-based)",
                        min_value=0,
                        value=1,
                        key=f"header_row_{index}_{file.name}",
                    )
                    settings["footer_rows"] = st.number_input(
                        "Footer rows to drop",
                        min_value=0,
                        value=4,
                        key=f"footer_rows_{index}_{file.name}",
                    )
                    settings["extra_cols"] = st.number_input(
                        "Trailing columns to drop",
                        min_value=0,
                        value=3,
                        key=f"extra_cols_{index}_{file.name}",
                    )
                file_settings.append(settings)

    if any(settings["year"] is None for settings in file_settings):
        st.warning("Choose a census year for every file before loading the data.")
        st.stop()

    census_frames = []
    value_cols = []
    for file, settings in zip(uploaded, file_settings):
        try:
            if file.name.lower().endswith(".pdf"):
                frame, file_value_cols = load_pdf_and_clean(
                    file.getvalue(), int(settings["start_page"])
                )
            else:
                frame, file_value_cols = load_and_clean(
                    file.getvalue(),
                    file.name,
                    int(settings["header_row"]),
                    int(settings["footer_rows"]),
                    int(settings["extra_cols"]),
                    int(settings["year"]),
                )
        except Exception as e:
            st.error(f"Could not read {file.name}: {e}")
            st.stop()
        if YEAR_COL in frame.columns:
            frame = frame.drop(columns=[YEAR_COL])
        frame.insert(0, YEAR_COL, int(settings["year"]))
        census_frames.append(frame)
        value_cols.extend(column for column in file_value_cols if column not in value_cols)

    combined_data = pd.concat(census_frames, ignore_index=True, sort=False)
    reference_municipalities = combined_data.loc[
        combined_data[YEAR_COL].eq(2022)
        & combined_data["Geographic level"].eq("Municipality")
    ]
    ambiguous_keys = ambiguous_2022_hierarchy_keys(reference_municipalities)
    if ambiguous_keys:
        ambiguous_names = (
            reference_municipalities.loc[
                reference_municipalities[AREA_KEY_COL].isin(ambiguous_keys),
                "Регион",
            ]
            .drop_duplicates()
            .astype(str)
            .tolist()
        )
        shown_names = ", ".join(ambiguous_names[:10])
        omitted_count = len(ambiguous_names) - 10
        if omitted_count > 0:
            shown_names += f", and {omitted_count} more"
        st.warning(
            "2022 hierarchy mapping was skipped for ambiguous municipality names: "
            f"{shown_names}. Those municipalities keep their source hierarchy."
        )
    data = add_geographic_hierarchy_aggregates(combined_data)

    area_labels = (
        data[["Регион", AREA_KEY_COL, "Geographic level"]]
        .drop_duplicates(subset=[AREA_KEY_COL])
        .set_index(AREA_KEY_COL)
    )
    with st.sidebar:
        st.header("Filters")
        levels = st.multiselect("Geographic levels (empty = municipalities)", LEVELS)
        area_search = st.text_input("Search areas (Cyrillic or Latin)")
        available_areas = area_options_for_levels(area_labels, levels, area_search)
        area_widget_key = "selected_area_keys"
        valid_area_keys = set(area_options_for_levels(area_labels, levels).index)
        selected_area_keys = [
            key
            for key in st.session_state.get(area_widget_key, [])
            if key in valid_area_keys
        ]
        st.session_state[area_widget_key] = selected_area_keys
        option_keys = list(dict.fromkeys([*selected_area_keys, *available_areas.index]))
        regions = st.multiselect(
            "Area (empty = all areas at selected levels)",
            option_keys,
            format_func=lambda key: area_labels.loc[key, "Регион"],
            key=area_widget_key,
        )
        default_groups = [c for c in value_cols if c != "Укупно"][:6]
        groups = st.multiselect("Columns / groups", value_cols, default=default_groups)

    view = filter_geographies(data, regions, levels)
    if not groups:
        st.warning("Pick at least one group in the sidebar.")
        st.stop()
    if view.empty:
        st.warning("No rows match these filters.")
        st.stop()

    identity_cols = [YEAR_COL] + ID_COLS + [AREA_KEY_COL]
    wide = view[identity_cols + ["Geographic level"] + HIERARCHY_COLS + groups]

    tab_table, tab_chart = st.tabs(["Table", "Chart"])

    # Change population with first row in the original table (that's the name of the table!)

    with tab_table:
        with st.expander("Municipality matching across uploaded years"):
            st.caption(
                "Matches use normalized names, not official geographic codes. "
                "Unmatched areas need review; boundary changes may require a "
                "historical crosswalk."
            )
            st.dataframe(municipality_match_report(data), hide_index=True)
        st.caption(f"{len(wide)} rows")
        st.dataframe(wide)
        c1, c2 = st.columns(2)
        c1.download_button("Download CSV", wide.to_csv(index=False).encode("utf-8-sig"),
                           "populacija.csv", "text/csv")
        c2.download_button("Download Excel", to_excel_bytes(wide), "populacija.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab_chart:
        st.caption(
            "The Region column mixes geographic levels. Select one area for a trend "
            "chart, and compare only years with compatible boundaries and definitions."
        )

        long = wide.melt(id_vars=identity_cols + ["Geographic level"] + HIERARCHY_COLS,
                         var_name="Група", value_name="Број становника").dropna(subset=["Број становника"])

        c1, c2, c3 = st.columns(3)
        chart_types = [
            "Grouped bar (by group)",
            "Stacked bar (by region)",
            "Heatmap (region x group)",
            "Boxplot (spread across regions)",
        ]
        if data[YEAR_COL].nunique() > 1:
            chart_types.append("Trend (by census year)")
        kind = c1.selectbox("Chart type", chart_types)
        title = c2.text_input("Title (optional)")
        top_n = c3.slider("Max regions shown", 3, 50, 15)

        o1, o2 = st.columns(2)
        as_share = o1.checkbox("Show shares (%) instead of counts (stacked bar, heatmap)")
        log_scale = o2.checkbox("Log scale (grouped bar, boxplot, trend)")

        if long.empty:
            st.warning("No numeric data for this selection.")
        elif kind == "Trend (by census year)" and len(regions) != 1:
            st.warning("Select exactly one region in the sidebar for a trend chart.")
        elif kind == "Trend (by census year)" and long[YEAR_COL].nunique() < 2:
            st.warning("The selected area has data for fewer than two census years.")
        else:
            fig = build_figure(kind, long, groups, top_n, as_share, log_scale, title)
            st.pyplot(fig)

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
            plt.close(fig)
            st.download_button("Download chart (PNG)", buf.getvalue(), "chart.png", "image/png")
