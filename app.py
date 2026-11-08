import io

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

st.set_page_config(page_title="Sredi mi podatke!!!", layout="wide")


# Kako srediti Crnogorce...

# 1. Get the original 20 colors as RGB tuples
tab20_colors = list(plt.cm.tab20.colors)

# 2. Define your 21st color (Hex or RGB tuple)
new_color = '#B59C7B' 

# 3. Append it to the list
tab20_colors.append(new_color)

# 4. Create the new colormap
custom_tab21 = ListedColormap(tab20_colors)

ID_COLS = ["Регион", "Пол"]
LEVELS = ["Serbia", "Macroregion", "Oblast", "Region", "Municipality"]
HIERARCHY_COLS = ["Serbia", "Macroregion", "Oblast", "Region", "Municipality"]
EXCLUDED_GROUPS = {"Остали", "Регионална припадност", "Нису се изјаснили", "Непознато"}

# Raw (cleaned) header -> short Serbian header
RENAME = {
    'Регион Област Град – општина': 'Регион',
    'Пол': 'Пол',
    'Укупно  Total': 'Укупно',
    'Срби  Serbs': 'Срби',
    'Aлбанци  Albanians': 'Aлбанци',
    'Бошњаци   Bosniaks': 'Бошњаци',
    'Бугари  Bulgarians': 'Бугари',
    'Буњевци   Bunjevci': 'Буњевци',
    'Власи  Vlachs': 'Власи',
    'Горанци  Goranci': 'Горанци',
    'Југословени   Yugoslavs': 'Југословени',
    'Мађари  Hungarians': 'Мађари',
    'Македонци  Macedonians': 'Македонци',
    'Муслимани  Muslims': 'Муслимани',
    'Немци   Germans': 'Немци',
    'Роми   Roma people': 'Роми',
    'Румуни   Romanians': 'Румуни',
    'Руси  Russians': 'Руси',
    'Русини  Ruthenians': 'Русини',
    'Словаци  Slovaks': 'Словаци',
    'Словенци  Slovenians': 'Словенци',
    'Украјинци  Ukrainians': 'Украјинци',
    'Хрвати  Croats': 'Хрвати',
    'Црногорци  Montenegrins': 'Црногорци',
    'Остали   Other': 'Остали',
    'Регионалнa припадност   Regional affiliation': 'Регионална припадност',
    'Нису се изјаснили   Did not declare': 'Нису се изјаснили',
    'Непознато  Unknown': 'Непознато',
}

# Possibly to filter out regions not in use...
#regions = []

@st.cache_data(show_spinner="Cleaning data...")
def load_and_clean(file_bytes, header_row, footer_rows, extra_cols):
    df = pd.read_excel(io.BytesIO(file_bytes), header=header_row)


# Maybe the best move would be to replace this with just index?

    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace("\n", "", regex=False)
        .str.replace("        ", " ", regex=False)
    )
    df = df.replace(" ", pd.NA).dropna(axis=0, how="all")

    if footer_rows:
        df = df.iloc[:-footer_rows, :]
    if extra_cols:
        df = df.iloc[:, :-extra_cols]

    df = df.replace("-", pd.NA).rename(columns=RENAME)

    missing = [c for c in ID_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Expected columns not found: {missing}. Check the file layout settings.")

    # Fill merged-cell gaps only in the label columns.
    # (Forward-filling the numbers would copy values into cells that were '-'.)
    df[ID_COLS] = df[ID_COLS].ffill()

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
            hierarchy["Region"] = name
            hierarchy["Municipality"] = pd.NA
        else:
            hierarchy["Municipality"] = name
        aligned_rows.append(hierarchy.copy())
    aligned = pd.DataFrame(aligned_rows, index=df.index)
    df[HIERARCHY_COLS] = aligned[HIERARCHY_COLS]
    df = df.drop(columns=[column for column in EXCLUDED_GROUPS if column in df.columns])

    value_cols = [c for c in df.columns if c not in ID_COLS]
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

# Add a hue by gender

    if kind == "Grouped bar (by group)":
        fig, ax = plt.subplots(figsize=(max(8, 0.9 * n), 5))
        sns.barplot(data=long, x="Група", y="Број становника", hue="Пол",
                    order=groups, estimator="sum", errorbar=None, ax=ax)
        if log_scale:
            ax.set_yscale("log")
        else:
            ax.ticklabel_format(useOffset=False, style="plain", axis="y")

    elif kind == "Boxplot (spread across regions)":
        fig, ax = plt.subplots(figsize=(max(8, 0.9 * n), 5))
        sns.boxplot(data=long, x="Група", y="Број становника", hue="Пол", order=groups, ax=ax)
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


# ------------------------------------------------------------------ UI
st.title("Sredi mi podatke!")

uploaded = st.file_uploader("Upload the Excel file", type=["xlsx"])

with st.sidebar:
    with st.expander("File layout (advanced)"):
        header_row = st.number_input("Header row (0-based)", min_value=0, value=1)
        footer_rows = st.number_input("Footer rows to drop", min_value=0, value=4)
        extra_cols = st.number_input("Trailing columns to drop", min_value=0, value=3)

if not uploaded:
    st.info("Upload the file to get started.")
    st.stop()

try:
    data, value_cols = load_and_clean(
        uploaded.getvalue(), int(header_row), int(footer_rows), int(extra_cols)
    )
except Exception as e:
    st.error(f"Could not read the file: {e}")
    st.stop()

with st.sidebar:
    st.header("Filters")
    regions = st.multiselect("Region (empty = all)", list(data["Регион"].dropna().unique()))
    levels = st.multiselect("Geographic levels (empty = all)", LEVELS)
    genders = st.multiselect("Gender (empty = all)", list(data["Пол"].dropna().unique()))
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

wide = view[ID_COLS + ["Geographic level"] + HIERARCHY_COLS + groups]

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

    long = wide.melt(id_vars=ID_COLS + ["Geographic level"] + HIERARCHY_COLS,
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
