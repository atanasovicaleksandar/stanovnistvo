Srpski:

# stanovnistvo – pregled problema i rešenja do sada

Skripta za sredjivanje podataka o stanovništvu. Prima Excel tabele i PDF publikaciju Popisa 2002. i radi posao koji je bio potreban: uzima RZS podatke koji su predviđeni za gledanje, pa ih sredjuje kako bi mogli da se koriste za filtriranje i pravljenje grafikona.

U osnovi, ovo je bila praksa da se podaci iz različitih popisnih tabela dovode u isti oblik, da se mogu porediti kroz godine i da se lakše radi analiza po opštinama, oblastima i etnicitetima. U tom procesu su se javile određene problematike, i neke od njih su već rešene, dok neke i dalje čekaju dodatno sređivanje.

### Problematike koje su bile

Prva i najvažnija stvar je bila da zbirne stavke Srbije, regiona, oblasti i opština imaju označen geografski nivo. To je bilo problematično zato što su se u prikazu mogle pojaviti i agregati i osnovne jedinice, pa bi se na kraju sabiranje dešavalo sa pogrešnim logikom. Zato je rešeno da se podrazumevano prikazuju samo opštine, a da se zbirne stavke ne dodaju automatski. Zbir Srbije se uključuje tek kada se izričito izabere u filteru oblasti.

Drugi problem je bio sa bojama u grafikonima. Koristili smo tab20, a u pitanju je bilo 21 etničko grupisanje, pa je trebalo dodati još jedan hex kod koji pokriva tu dodatnu kategoriju. To je rešeno dodatnim color entry-om, tako da grafikon više ne dobija “nedostajući” segment.

Još jedan problem je bio vezan za više fajlova odjednom. U aplikaciji može da se ucita više fajlova, a svaki fajl se bira sa godinom popisa pre učitavanja, i onda se ta godina upisuje u kolonu `Год пописа`. Godina se može prepoznati iz naziva fajla, ali može i ručno da se promeni. Ovo je bilo važno zato što se podaci iz više popisa moraju porediti u zajedničkom formatu, a ne samo “povuci i spoji”.

Problem je bio i sa polom. Ako tabela ima kolonu `Пол`, koriste se samo redovi označeni ćiriličnim `с` (zbirno), pa se pol ne nudi kao filter niti kao posebna dimenzija. Ovo je urađeno da se izbegne mešanje pojedinačnih kategorija i agregiranih vrednosti.

Takođe, grafikoni mogu da prikazuju više godina odvojeno, a 'lažna poređenja' su mogla da nastanu kada geografske granice ili definicije kategorija nisu uporedive. Zbog toga je napomenuto da trend grafikon ima smisla samo ako su granice i definicije stabilne kroz godine. Nazivi opština sami po sebi nisu dovoljna garancija da su granice iste.

Još jedan važan deo je bio matching kroz popise. Koristi se normalizovan ključ naziva, sa podrškom za ćirilične i latinice varijante. Tabela prikazuje opštine koje nisu uparene kroz sve učitane godine, i to služi kao kontrola mogućih nepoklapanja, a ne kao zvanična istorijska šifra. To znači da promena granica i promena imena treba proveriti i po potrebi eksplicitno rešiti kroz istorijsku tabelu preslikavanja.

Odstupanje u ovom momentu je delom i to, da za 2002 popisnu godinu postoji znatno obimniji broj rezultata. Razlog tome pretpostavljamo da se u tom popisu vodila evidencija i po naseljima zapravo.
Deo procesa bi bio i da se to uzme u obzir i da za 2002 popisnu godinu postoji ta hijerarhijska podela (opet, ne znamo da li je to situacija, ovo je pretpostavka).

### Reseni problemi

Najvažniji rešeni problemi su sledeći:

- Zbirne stavke Srbije, regiona, oblasti i opština imaju geografski nivo.
- Podrazumevano se prikazuju samo opštine, čime se izbegava njihovo sabiranje sa agregatima.
- Zbir Srbije se uključuje samo kada se izabere u filteru oblasti.
- Boje u grafikonima su korigovane tako da podržavaju 21 etničku kategoriju.
- Učitavanje više fajlova je rešeno kroz “godinu popisa” po fajlu.
- Pol se automatski filtrira ako postoji kolona `Пол`.
- Poređenje kroz godine je bolje definisano i zaštitno postavljeno.
- Uparivanje naziva je urađeno preko normalizovanog ključa sa ćirilicom i latinicom.
- Prikaz neuparenih opština služi kao kontrola podataka, a ne kao zvanična istorijska tabela.

### Sta treba da se sredi

Ipak, ovde još ima dosta toga što nije potpuno završeno. Svaki istorijski format mora da se proveri i po potrebi dobije poseban importer koji ga prevodi u isti oblik podataka. Godišnje označavanje i poređenje su pripremljeni, ali to ne garantuje da će svaka tabela iz 2011, 2002, 1991 ili 1981. biti pročitana bez prilagodjavanja parsera.

Podržani su Excel formati `.xls`, `.xlsx`, `.xlsm`, `.xlsb` i `.ods`, kao i `.csv`. To je dobra osnova, ali je jasno da to nije dovoljno da se garantuje da će svaki RZS fajl bez problema proći kroz skriptu.
Pored toga '.pdf' kao format je isto upotrebljiv. Potencijalni problem je da to ne radi na svakom tipu PDF tabele kao takve, nego samo za 2002 popisnu godinu.

Filteri i prepoznavanje geografskog nivoa zavise od naziva u izvoru. Neprepoznati istorijski nazivi i promenjene granice moraju se proveriti prema izvornih tabelama. Za potpuno pouzdano spajanje kroz popise potreban je zvanični crosswalk geografskih šifara. Ovo je možda najveći tehnički i metodološki problem koji ostaje.

### Dalji koraci

Dalji koraci su relativno jasni:

- srediti kod tako da može da čita bilo koji RZS fajl i da izbaci odgovarajuće filtere,
- definisati više elemenata za standardizaciju podataka,
- pratiti tok u tim podacima kako bi se smanjile nejasnoće i razlike između istorijskih formata,
- proveriti i unaprediti geografsku mapiranje po godinu,
- napraviti pouzdanije parsiranje za sve popise i sve moguće varijante naziva.

Ukratko: rešeno je ono što je bilo najhitnije i najčešće, a ostalo je još “sredi i proveri” deo projekta, gde se pravi sve što treba da bi skripta bila stabilna i univerzalno upotrebljiva.

English:

# stanovnistvo – overview of the issues and solutions so far

This script is for cleaning and organizing population data. It takes Excel tables and the PDF publication of the 2002 Census. The basic purpose is simple: It takes RZS data that is meant to be viewed, cleans it, and prepares it for filtering and chart creation.

In practice, this was about bringing data from different census tables into one consistent format, so it can be compared across years and analyzed by municipality, region, or ethnicity. Along the way, a number of issues appeared, some of which were already resolved, while others still need further cleanup.

### Problems that came up

The first big issue was that aggregate rows for Serbia, regions, areas, and municipalities all had a geographic level assigned. That was problematic because the display could include both aggregates and base units, which led to incorrect summing logic. The solution was to show only municipalities by default, and to avoid automatically adding aggregate rows. The aggregate for Serbia is included only when explicitly selected in the area filter.

Another issue was with chart colors. We were using tab20, but the data included 21 ethnic categories, so one extra hex color was needed to cover the additional category. That was fixed by adding one extra color value so the chart no longer misses a segment.

There was also a problem with loading multiple files at once. The app allows several files to be uploaded, and each file is assigned a census year before loading, which is then written into the `Год пописа` column. The year can be recognized from the file name, but it can also be changed manually. This was necessary because data from multiple census years must be compared in a common format and not just merged blindly.

Another issue involved gender. If the table has a `Пол` column, only rows marked with the Cyrillic `с` (aggregate) are used, and gender is not offered as a filter or a separate dimension. This was done to avoid mixing individual rows with aggregate values.

The charts can also display multiple years separately, but false comparisons can happen when geographic boundaries or category definitions are not comparable. Because of that, the trend chart only makes sense when the geographic boundaries and definitions are stable across years. Municipality names alone are not enough to guarantee that the borders are the same.

There was also a key matching issue across censuses. The script uses a normalized name key, with support for both Cyrillic and Latin variants. The table shows municipalities that were not matched across all loaded years, and this serves as a check for possible mismatches rather than as an official historical identifier. That means boundary changes and renamed municipalities must be checked and, if needed, handled through an explicit historical mapping table.

### Resolved issues

The main resolved issues are:

- Aggregate rows for Serbia, regions, areas, and municipalities have a geographic level.
- Only municipalities are shown by default, which avoids summing them together with aggregates.
- The aggregate for Serbia is included only when selected in the area filter.
- Chart colors were corrected to support 21 ethnic categories.
- Loading multiple files works through per-file census-year assignment.
- Gender is automatically filtered when the `Пол` column exists.
- Comparing across years is better defined and guarded.
- Name matching is done via a normalized key with Cyrillic and Latin support.
- Unmatched municipalities are displayed as a data-quality check, not as an official historical table.

### What still needs to be fixed

There is still a lot to clean up. Every historical format must be checked, and, if necessary, each one needs a custom importer that converts it into the same data structure. The annual labeling and year-to-year comparison are prepared, but that does not guarantee that every table from 2011, 2002, 1991, or 1981 will be read correctly without parser adjustments.

The supported formats include `.xls`, `.xlsx`, `.xlsm`, `.xlsb`, `.ods`, and `.csv`. That is a good starting point, but it is not enough to ensure that every RZS file will work without issue.

Filters and geographic-level recognition depend on the source names. Unrecognized historical names and changed borders must be checked against the original tables. For fully reliable cross-census matching, an official geographic crosswalk is needed. This is probably the biggest remaining technical and methodological problem.

### Next steps

The next steps are fairly clear:

- clean up the code so it can read any RZS file and produce appropriate filters,
- define more of the standard elements needed for consistent data handling,
- follow the data flow more carefully so the historical differences are reduced,
- improve geographic mapping across years,
- build more reliable parsing for all census formats and name variants.

In short: the most urgent and common issues have been solved, but the remaining work is the “clean, verify, and standardize” part of the project, which is what makes the script stable and truly reusable across all datasets.
