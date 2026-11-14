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
LEVELS = ["Serbia", "Macroregion", "Oblast", "Region", "Municipality"]
HIERARCHY_COLS = ["Serbia", "Macroregion", "Oblast", "Region", "Municipality"]
EXCLUDED_GROUPS = {"Остали", "Регионална припадност", "Нису се изјаснили", "Непознато"}

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


def _legacy_tuple_label(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).replace("\n", " ").replace("\r", " ")
    text = text.replace("\u00a0", " ")
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
    return text in {"укупно", "у к у п н о", "у градским", "у осталим"} or "у к у п н о" in text or "у градским" in text or "у осталим" in text


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


def parse_legacy_census_excel(file_bytes, file_name):
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
    groups = [group for group in header_values if group]
    if not groups:
        raise ValueError("No ethnicity groups found in the legacy census header.")

    current_region = None
    rows = []
    for idx in range(header_idx + 1, len(workbook)):
        row = workbook.iloc[idx].tolist()
        first_cell = _legacy_tuple_label(row[0]) if row else ""
        if not first_cell:
            continue

        if _legacy_summary_name(first_cell):
            if current_region:
                values = row[1:1 + len(groups)]
                values.extend([None] * (len(groups) - len(values)))
                if any(_legacy_numeric_value(value) for value in values):
                    records = {"Регион": current_region}
                    for group, value in zip(groups, values):
                        if _legacy_numeric_value(value):
                            records[group] = pd.to_numeric(value, errors="coerce")
                        else:
                            records[group] = pd.NA
                    rows.append(records)
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
def load_and_clean(file_bytes, file_name, header_row, footer_rows, extra_cols):
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
        if _legacy_census_file_name_looks_like_supported(file_name):
            return clean_dataframe(parse_legacy_census_excel(file_bytes, file_name), footer_rows, extra_cols)
        df = pd.read_excel(
            file_buffer, engine=excel_engines[extension], header=header_row
        )
    else:
        raise ValueError(f"Unsupported file type: .{extension}")

    return clean_dataframe(df, footer_rows, extra_cols)


@st.cache_data(show_spinner="Reading PDF table...")
def load_pdf_and_clean(file_bytes, start_page):
    return clean_dataframe(parse_ethnicity_pdf(file_bytes, start_page))


def clean_dataframe(df, footer_rows=0, extra_cols=0):
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

    region_names = df["Регион"].astype(str)
    normalized_region_names = (
        region_names.str.casefold()
        .str.replace(r"[–—−]", "-", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    excluded = region_names.str.contains(
        r"gradska|ostala|градска|остала", case=False, regex=True, na=False
    )
    excluded |= normalized_region_names.isin({
        "србија - север", "србија - југ", "srbija - sever", "srbija - jug"
    })
    df = df.loc[~excluded].copy()

    def classify_region(name):
        normalized = (
            str(name).strip().casefold().replace("–", "-").replace("—", "-")
        )
        normalized = " ".join(normalized.split())
        if normalized in {
            "србија", "република србија", "serbia", "republic of serbia"
        }:
            return "Serbia"
        if normalized in {"централна србија", "војводина"}:
            return "Macroregion"
        if normalized == "град београд":
            return "Region"
        if "србија -" in normalized or "serbia -" in normalized:
            return "Macroregion"
        if "област" in normalized or "oblast" in normalized:
            return "Oblast"
        if "регион" in normalized or "region" in normalized:
            return "Region"
        return "Municipality"

    df["Geographic level"] = df["Регион"].map(classify_region)

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
            hierarchy["Region"] = pd.NA
            hierarchy["Municipality"] = pd.NA
        elif level == "Region":
            if str(name).strip().casefold() == "град београд":
                hierarchy["Macroregion"] = pd.NA
                hierarchy["Oblast"] = pd.NA
            hierarchy["Region"] = name
            hierarchy["Municipality"] = pd.NA
        else:
            hierarchy["Municipality"] = name
        aligned_rows.append(hierarchy.copy())
    aligned = pd.DataFrame(aligned_rows, index=df.index)
    df[HIERARCHY_COLS] = aligned[HIERARCHY_COLS]
    df = df.drop(columns=[column for column in EXCLUDED_GROUPS if column in df.columns])

    identity_cols = ID_COLS + (["Пол"] if "Пол" in df.columns else [])
    value_cols = [c for c in df.columns if c not in identity_cols]
    value_cols = [
        c for c in value_cols
        if c not in HIERARCHY_COLS + ["Geographic level"] + list(EXCLUDED_GROUPS)
    ]
    df[value_cols] = df[value_cols].apply(pd.to_numeric, errors="coerce")
    return df.reset_index(drop=True), value_cols


def to_excel_bytes(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    return buf.getvalue()


def region_pivot(long, groups, top_n, as_share):
    pv = long.pivot_table(index="Регион", columns="Група", values="Број становника", aggfunc="sum")
    pv = pv[[g for g in groups if g in pv.columns]]
    pv = pv.loc[pv.sum(axis=1).nlargest(top_n).index]
    if as_share:
        pv = pv.div(pv.sum(axis=1), axis=0) * 100
    return pv


def build_figure(kind, long, groups, top_n, as_share, log_scale, title):
    sns.set_theme(style="whitegrid")
    n = max(len(groups), 1)
    hue = "Пол" if "Пол" in long.columns else None

# Add a gender hue when the input includes a gender column.

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
        "Upload an Excel or PDF file",
        type=["xls", "xlsx", "xlsm", "xlsb", "ods", "csv", "pdf"],
    )

    if not uploaded:
        st.info("Upload an Excel or PDF file to get started.")
        st.stop()

    is_pdf = uploaded.name.lower().endswith(".pdf")
    if is_pdf:
        with st.sidebar:
            start_page = st.number_input("PDF table starts at page", min_value=1, value=14)
    else:
        with st.sidebar:
            with st.expander("File layout (advanced)"):
                header_row = st.number_input("Header row (0-based)", min_value=0, value=1)
                footer_rows = st.number_input("Footer rows to drop", min_value=0, value=4)
                extra_cols = st.number_input("Trailing columns to drop", min_value=0, value=3)

    try:
        if is_pdf:
            data, value_cols = load_pdf_and_clean(uploaded.getvalue(), int(start_page))
        else:
            data, value_cols = load_and_clean(
                uploaded.getvalue(), uploaded.name, int(header_row), int(footer_rows), int(extra_cols)
            )
    except Exception as e:
        st.error(f"Could not read the file: {e}")
        st.stop()

    with st.sidebar:
        st.header("Filters")
        regions = st.multiselect("Region (empty = all)", list(data["Регион"].dropna().unique()))
        levels = st.multiselect("Geographic levels (empty = all)", LEVELS)
        if "Пол" in data.columns:
            genders = st.multiselect("Gender (empty = all)", list(data["Пол"].dropna().unique()))
        else:
            genders = []
        default_groups = [c for c in value_cols if c != "Укупно"][:6]
        groups = st.multiselect("Columns / groups", value_cols, default=default_groups)

    view = data
    if regions:
        view = view[view["Регион"].isin(regions)]
    if levels:
        view = view[view["Geographic level"].isin(levels)]
    if genders:
        view = view[view["Пол"].isin(genders)]

    if not groups:
        st.warning("Pick at least one group in the sidebar.")
        st.stop()
    if view.empty:
        st.warning("No rows match these filters.")
        st.stop()

    identity_cols = ID_COLS + (["Пол"] if "Пол" in view.columns else [])
    wide = view[identity_cols + ["Geographic level"] + HIERARCHY_COLS + groups]

    tab_table, tab_chart = st.tabs(["Table", "Chart"])

    # Change population with first row in the original table (that's the name of the table!)

    with tab_table:
        st.caption(f"{len(wide)} rows")
        st.dataframe(wide)
        c1, c2 = st.columns(2)
        c1.download_button("Download CSV", wide.to_csv(index=False).encode("utf-8-sig"),
                           "populacija.csv", "text/csv")
        c2.download_button("Download Excel", to_excel_bytes(wide), "populacija.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab_chart:
        st.caption(
            "Tip: the Region column mixes levels (region, district, municipality). "
            "Select regions of the same level, or totals will be double counted."
        )

        long = wide.melt(id_vars=identity_cols + ["Geographic level"] + HIERARCHY_COLS,
                         var_name="Група", value_name="Број становника").dropna(subset=["Број становника"])

        c1, c2, c3 = st.columns(3)
        kind = c1.selectbox("Chart type", [
            "Grouped bar (by group)",
            "Stacked bar (by region)",
            "Heatmap (region x group)",
            "Boxplot (spread across regions)",
        ])
        title = c2.text_input("Title (optional)")
        top_n = c3.slider("Max regions shown", 3, 50, 15)

        o1, o2 = st.columns(2)
        as_share = o1.checkbox("Show shares (%) instead of counts (stacked bar, heatmap)")
        log_scale = o2.checkbox("Log scale (grouped bar, boxplot)")

        if long.empty:
            st.warning("No numeric data for this selection.")
        else:
            fig = build_figure(kind, long, groups, top_n, as_share, log_scale, title)
            st.pyplot(fig)

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
            plt.close(fig)
            st.download_button("Download chart (PNG)", buf.getvalue(), "chart.png", "image/png")
