import unittest

import pandas as pd

from app import (
    AREA_KEY_COL,
    YEAR_COL,
    _geographic_key,
    _geographic_level,
    _legacy_1991_geography_label,
    add_geographic_hierarchy_aggregates,
    area_options_for_levels,
    build_figure,
    clean_dataframe,
    filter_geographies,
    municipality_match_report,
    region_pivot,
)


class CensusDataTests(unittest.TestCase):
    def test_clean_dataframe_keeps_only_combined_sex_rows(self):
        source = pd.DataFrame(
            {
                "Регион": ["Општина А"] * 3,
                "Пол": ["м", "ж", "с"],
                "Срби": [50, 60, 110],
            }
        )

        cleaned, value_columns = clean_dataframe(source)

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned.loc[0, "Срби"], 110)
        self.assertNotIn("Пол", cleaned.columns)
        self.assertIn("Срби", value_columns)

    def test_clean_dataframe_reports_missing_combined_sex_rows(self):
        source = pd.DataFrame(
            {
                "Регион": ["Општина А", "Општина А"],
                "Пол": ["м", "ж"],
                "Срби": [50, 60],
            }
        )

        with self.assertRaisesRegex(ValueError, "marked 'с'"):
            clean_dataframe(source)

    def test_region_pivot_omits_single_area_label_across_census_years(self):
        source = pd.DataFrame(
            {
                YEAR_COL: [2011, 2022],
                "Регион": ["Општина А", "Општина А"],
                "Група": ["Срби", "Срби"],
                "Број становника": [100, 120],
            }
        )

        pivot = region_pivot(source, ["Срби"], top_n=10, as_share=False)

        self.assertEqual(list(pivot.index), [2011, 2022])
        self.assertEqual(pivot["Срби"].tolist(), [100, 120])

    def test_region_pivot_omits_area_label_when_comparing_one_area_across_years(self):
        source = pd.DataFrame(
            {
                YEAR_COL: [2011, 2022],
                "Регион": ["Општина Врање", "Град Врање"],
                AREA_KEY_COL: ["municipality:врање", "municipality:врање"],
                "Група": ["Срби", "Срби"],
                "Број становника": [100, 120],
            }
        )

        pivot = region_pivot(source, ["Срби"], top_n=10, as_share=False)

        self.assertEqual(list(pivot.index), [2011, 2022])
        self.assertEqual(pivot["Срби"].tolist(), [100, 120])

    def test_region_pivot_shows_only_area_name_for_one_census_year(self):
        source = pd.DataFrame(
            {
                YEAR_COL: [2022, 2022],
                "Регион": ["Општина А", "Општина Б"],
                "Група": ["Срби", "Срби"],
                "Број становника": [100, 120],
            }
        )

        pivot = region_pivot(source, ["Срби"], top_n=10, as_share=False)

        self.assertEqual(list(pivot.index), ["Општина Б", "Општина А"])
        self.assertEqual(pivot["Срби"].tolist(), [120, 100])

    def test_geographic_levels_recognize_aggregates_and_municipalities(self):
        self.assertEqual(_geographic_level("Република Србија"), "Serbia")
        self.assertEqual(_geographic_level("Srbija - sever"), "Macroregion")
        self.assertEqual(_geographic_level("Србијасевер"), "Macroregion")
        self.assertEqual(_geographic_level("Србијајуг"), "Macroregion")
        self.assertEqual(_geographic_level("Јужнобачка област"), "Oblast")
        self.assertEqual(_geographic_level("Београдски регион"), "Region")
        self.assertEqual(_geographic_level("Општина Суботица"), "Municipality")
        self.assertIsNone(_geographic_level("Укупно"))

    def test_geographic_key_matches_cyrillic_and_latin_name_variants(self):
        cyrillic_key = _geographic_key("Општина Суботица", "Municipality")
        latin_key = _geographic_key("Opština Subotica", "Municipality")

        self.assertEqual(cyrillic_key, latin_key)
        self.assertEqual(
            _geographic_key("Serbia", "Serbia"),
            _geographic_key("Република Србија", "Serbia"),
        )

    def test_geographic_names_use_canonical_capitalization(self):
        source = pd.DataFrame(
            {
                "Регион": ["РЕПУБЛИКА СРБИЈА", "Republika Srbija", "РЕГИОН ВОЈВОДИНЕ"],
                "Срби": [100, 100, 100],
            }
        )

        cleaned, _ = clean_dataframe(source)

        self.assertEqual(
            cleaned["Регион"].tolist(),
            ["Република Србија", "Република Србија", "Регион Војводине"],
        )
        self.assertEqual(cleaned[AREA_KEY_COL].nunique(), 2)

    def test_known_municipality_abbreviations_are_canonicalized(self):
        source = pd.DataFrame(
            {
                "Регион": [
                    "Г. Милановац",
                    "Срем. Карловци",
                    "Срем. Митровица",
                    "Кос. Каменица",
                    "Кос. Митровица",
                ],
                "Срби": [1, 2, 3, 4, 5],
            }
        )

        cleaned, _ = clean_dataframe(source)

        self.assertEqual(
            cleaned["Регион"].tolist(),
            [
                "Горњи Милановац",
                "Сремски Карловци",
                "Сремска Митровица",
                "Косовска Каменица",
                "Косовска Митровица",
            ],
        )

    def test_1991_beograd_prefix_is_removed_from_municipality_labels(self):
        labels = [
            "Београдбарајево",
            "Београдвождовац",
            "Београднови Београд",
            "Београдсавски Венац",
            "Београддео Г",
            "Београдски регион",
            "Београдг. Милановац",
            "Г",
            "Део Г",
            "Г. Милановац",
            "Београд - Барајево",
            "Београд - ",
            "Ниш - Барајево",
            "Ниш - ",
            "Јагодина - град",
            "Бујановац1)",
        ]

        normalized = [_legacy_1991_geography_label(label) for label in labels]

        self.assertEqual(
            normalized,
            [
                "Барајево",
                "Вождовац",
                "Нови Београд",
                "Савски Венац",
                "",
                "Београдски регион",
                "Милановац",
                "",
                "",
                "Милановац",
                "Барајево",
                "",
                "Барајево",
                "",
                "Јагодина",
                "Бујановац",
            ],
        )

    def test_clean_dataframe_recleans_beograd_dash_labels_for_2011(self):
        labels = [
            "Београд - Барајево",
            "Београд - Вождовац",
            "Београд - Врачар",
            "Београд - Гроцка",
            "Београд - Звездара",
            "Београд - Земун",
            "Београд - Лазаревац",
            "Београд - Младеновац",
            "Београд - Нови Београд",
            "Београд - Обреновац",
            "Београд - Палилула",
            "Београд - Раковица",
            "Београд - Савски Венац",
            "Београд - Сопот",
            "Београд - Стари Град",
            "Београд - Сурчин",
            "Београд - Чукарица",
            "Београд - ",
        ]
        source = pd.DataFrame({"Регион": labels, "Срби": range(1, len(labels) + 1)})

        cleaned, _ = clean_dataframe(source, census_year=2011)

        self.assertEqual(
            cleaned["Регион"].tolist(),
            [
                "Барајево",
                "Вождовац",
                "Врачар",
                "Гроцка",
                "Звездара",
                "Земун",
                "Лазаревац",
                "Младеновац",
                "Нови Београд",
                "Обреновац",
                "Палилула",
                "Раковица",
                "Савски Венац",
                "Сопот",
                "Стари Град",
                "Сурчин",
                "Чукарица",
            ],
        )

    def test_clean_dataframe_labels_geographic_rows_and_omits_summary_rows(self):
        source = pd.DataFrame(
            {
                "Регион": [
                    "Република Србија",
                    "Јужнобачка област",
                    "Општина Суботица",
                    "Укупно",
                ],
                "Срби": [1000, 500, 300, 1000],
            }
        )

        cleaned, _ = clean_dataframe(source)

        self.assertEqual(
            cleaned["Geographic level"].tolist(),
            ["Serbia", "Oblast", "Municipality"],
        )
        self.assertEqual(
            cleaned[AREA_KEY_COL].tolist(),
            [
                "serbia:република-србија",
                "oblast:јужнобачка-област",
                "municipality:суботица",
            ],
        )

    def test_2022_regions_and_oblasts_are_aggregated_from_municipalities(self):
        source = pd.DataFrame(
            {
                "Регион": [
                    "Република Србија",
                    "Регион Војводине",
                    "Јужнобачка област",
                    "Општина Нови Сад",
                    "Регион Шумадије и Западне Србије",
                    "Београдски регион",
                    "Београдска област",
                    "Општина Земун",
                    "Општина Нови Београд",
                    "Регион Јужне и Источне Србије",
                ],
                "Срби": [9999, 5000, 1000, 120, 4000, 3000, 2000, 20, 10, 3000],
            }
        )

        cleaned, _ = clean_dataframe(source)
        cleaned[YEAR_COL] = 2022
        result = add_geographic_hierarchy_aggregates(cleaned)

        belgrade_oblast = result.loc[
            result["Регион"].eq("Београдска област")
        ].iloc[0]
        self.assertEqual(belgrade_oblast["Region"], "Београдски регион")

        def aggregate(name, level):
            return result.loc[
                result["Регион"].eq(name)
                & result["Geographic level"].eq(level)
                & result[YEAR_COL].eq(2022)
            ].iloc[0]

        self.assertEqual(aggregate("Регион Војводине", "Region")["Срби"], 120)
        self.assertEqual(aggregate("Јужнобачка област", "Oblast")["Срби"], 120)
        self.assertEqual(aggregate("Београдски регион", "Region")["Срби"], 30)
        self.assertEqual(aggregate("Београдска област", "Oblast")["Срби"], 30)
        self.assertEqual(aggregate("Република Србија", "Serbia")["Срби"], 150)
        self.assertEqual(aggregate("Београдска област", "Oblast")["Region"], "Београдски регион")
        self.assertEqual(aggregate("Београдска област", "Oblast")["Serbia"], "Република Србија")
        self.assertEqual(
            result.loc[result["Geographic level"].eq("Serbia"), "Срби"].tolist(),
            [150],
        )

    def test_2022_municipality_hierarchy_maps_to_other_years_before_aggregation(self):
        reference_source = pd.DataFrame(
            {
                "Регион": [
                    "Република Србија",
                    "Србија север",
                    "Регион Војводине",
                    "Јужнобачка област",
                    "Општина Нови Сад",
                ],
                "Срби": [9000, 8000, 7000, 6000, 100],
            }
        )
        historical_source = pd.DataFrame(
            {
                "Регион": ["Општина Нови Сад", "Општина Суботица"],
                "Срби": [80, 20],
            }
        )

        reference, _ = clean_dataframe(reference_source)
        reference[YEAR_COL] = 2022
        historical, _ = clean_dataframe(historical_source)
        historical[YEAR_COL] = 2011
        result = add_geographic_hierarchy_aggregates(
            pd.concat([reference, historical], ignore_index=True, sort=False)
        )

        historical_municipality = result.loc[
            result[YEAR_COL].eq(2011)
            & result["Регион"].eq("Општина Нови Сад")
        ].iloc[0]
        self.assertEqual(historical_municipality["Macroregion"], "Србија север")
        self.assertEqual(historical_municipality["Region"], "Регион Војводине")
        self.assertEqual(historical_municipality["Oblast"], "Јужнобачка област")

        historical_aggregate = result.loc[
            result[YEAR_COL].eq(2011)
            & result["Geographic level"].eq("Region")
            & result["Регион"].eq("Регион Војводине")
        ].iloc[0]
        self.assertEqual(historical_aggregate["Срби"], 80)
        historical_macroregion = result.loc[
            result[YEAR_COL].eq(2011)
            & result["Geographic level"].eq("Macroregion")
            & result["Регион"].eq("Србија север")
        ].iloc[0]
        self.assertEqual(historical_macroregion["Срби"], 80)

    def test_2022_name_variants_do_not_conflict_on_municipality_display_name(self):
        source = pd.DataFrame(
            {
                "Регион": [
                    "Република Србија",
                    "Србија југ",
                    "Регион Јужне и Источне Србије",
                    "Пчињска област",
                    "Град Врање",
                    "Општина Врање",
                ],
                "Срби": [1000, 900, 800, 700, 40, 60],
            }
        )
        reference, _ = clean_dataframe(source)
        reference[YEAR_COL] = 2022

        result = add_geographic_hierarchy_aggregates(reference)
        vranje_rows = result.loc[
            result["Geographic level"].eq("Municipality")
            & result["Регион"].isin(["Град Врање", "Општина Врање"])
        ]

        self.assertEqual(len(vranje_rows), 2)
        self.assertEqual(vranje_rows["Region"].tolist(), [
            "Регион Јужне и Источне Србије",
            "Регион Јужне и Источне Србије",
        ])

    def test_ambiguous_municipality_names_are_not_mapped_between_regions(self):
        source = pd.DataFrame(
            {
                "Регион": [
                    "Република Србија",
                    "Србија север",
                    "Регион Војводине",
                    "Општина Палилула",
                    "Србија југ",
                    "Регион Јужне и Источне Србије",
                    "Општина Палилула",
                ],
                "Срби": [1000, 900, 800, 70, 600, 500, 60],
            }
        )
        reference, _ = clean_dataframe(source)
        reference[YEAR_COL] = 2022
        historical, _ = clean_dataframe(
            pd.DataFrame({"Регион": ["Општина Палилула"], "Срби": [50]})
        )
        historical[YEAR_COL] = 2011

        result = add_geographic_hierarchy_aggregates(
            pd.concat([reference, historical], ignore_index=True, sort=False)
        )
        historical_municipality = result.loc[
            result[YEAR_COL].eq(2011)
            & result["Geographic level"].eq("Municipality")
        ].iloc[0]

        self.assertTrue(pd.isna(historical_municipality["Region"]))

    def test_geography_filter_defaults_to_municipalities_and_selects_serbia_explicitly(self):
        source = pd.DataFrame(
            {
                AREA_KEY_COL: [
                    "municipality:subotica",
                    "oblast:subotica",
                    "serbia:република-србија",
                ],
                "Geographic level": ["Municipality", "Oblast", "Serbia"],
            }
        )

        self.assertEqual(
            filter_geographies(source)[AREA_KEY_COL].tolist(),
            ["municipality:subotica"],
        )
        self.assertEqual(
            filter_geographies(
                source, selected_regions=["serbia:република-србија"]
            )[AREA_KEY_COL].tolist(),
            ["serbia:република-србија"],
        )
        self.assertEqual(
            filter_geographies(source, selected_levels=["Oblast"])[AREA_KEY_COL].tolist(),
            ["oblast:subotica"],
        )

    def test_area_options_follow_selected_geographic_levels(self):
        areas = pd.DataFrame(
            {
                AREA_KEY_COL: ["municipality:subotica", "region:vojvodine"],
                "Geographic level": ["Municipality", "Region"],
            }
        ).set_index(AREA_KEY_COL)

        self.assertEqual(
            area_options_for_levels(areas)["Geographic level"].tolist(),
            ["Municipality"],
        )
        self.assertEqual(
            area_options_for_levels(areas, ["Region"]).index.tolist(),
            ["region:vojvodine"],
        )

    def test_area_search_matches_latin_and_cyrillic_but_keeps_cyrillic_labels(self):
        areas = pd.DataFrame(
            {
                AREA_KEY_COL: ["municipality:novi-sad", "municipality:subotica"],
                "Регион": ["Нови Сад", "Суботица"],
                "Geographic level": ["Municipality", "Municipality"],
            }
        ).set_index(AREA_KEY_COL)

        latin_matches = area_options_for_levels(areas, search_text="Novi Sad")
        cyrillic_matches = area_options_for_levels(areas, search_text="Суботица")

        self.assertEqual(latin_matches["Регион"].tolist(), ["Нови Сад"])
        self.assertEqual(cyrillic_matches["Регион"].tolist(), ["Суботица"])

    def test_municipality_match_report_identifies_year_specific_areas(self):
        source = pd.DataFrame(
            {
                YEAR_COL: [2011, 2011, 2022, 2022],
                AREA_KEY_COL: [
                    "municipality:subotica",
                    "municipality:backa-palanka",
                    "municipality:subotica",
                    "municipality:novi-sad",
                ],
                "Регион": ["Суботица", "Бачка Паланка", "Суботица", "Нови Сад"],
                "Geographic level": ["Municipality"] * 4,
            }
        )

        report = municipality_match_report(source).set_index(YEAR_COL)

        self.assertEqual(report.loc[2011, "Matched across all years"], 1)
        self.assertEqual(report.loc[2011, "Areas without match"], "Бачка Паланка")
        self.assertEqual(report.loc[2022, "Areas without match"], "Нови Сад")

    def test_trend_chart_uses_census_years(self):
        source = pd.DataFrame(
            {
                YEAR_COL: [2011, 2022],
                "Регион": ["Општина А", "Општина А"],
                "Група": ["Срби", "Срби"],
                "Број становника": [100, 120],
            }
        )

        figure = build_figure(
            "Trend (by census year)",
            source,
            groups=["Срби"],
            top_n=10,
            as_share=False,
            log_scale=False,
            title="",
        )

        self.assertEqual(list(figure.axes[0].get_xticks()), [2011, 2022])


if __name__ == "__main__":
    unittest.main()
