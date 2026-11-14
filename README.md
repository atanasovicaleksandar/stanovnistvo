# stanovnistvo
Skripta za sredjivanje podataka o stanovnistvu. Prima Excel tabele i PDF publikaciju Popisa 2002.

Za PDF Popisa 2002. izaberi početnu stranu (podrazumevano 14). Skripta preskače početne grafikone i zbirne procentualne tabele, a čita detaljnu tabelu sa susednih strana „Deo 1“ i „Deo 2“.

## Svrha
Skripta uzima RZS podatke koji su predvidjeni za gledanje, i sredjuje ih kako bi mogli da se koriste za filtiranje i pravljenje grafikona.

### Sta tacno radi
Ucitava popisne tabele i sredjuje ih za filtriranje i pravljenje grafikona.

Moze se dodati vise fajlova odjednom. Za svaki fajl se bira godina popisa pre
ucitavanja, a aplikacija je upisuje u kolonu `Год пописа`. Godina moze da se
prepozna iz naziva fajla, ali moze i rucno da se promeni. Ako tabela ima kolonu
`Пол`, koriste se samo redovi oznaceni cirilicnim `с` (zbirno), pa se pol ne
nudi kao filter niti kao posebna dimenzija.

Grafikoni mogu da prikazuju vise godina odvojeno; grafikon trenda prikazuje
izabranu oblast kroz godine. Poredjenje ima smisla samo kada su geografske
granice i definicije kategorija uporedive. Nazivi opstina sami po sebi nisu
dovoljna garancija da su granice iste.

Podrazumevani prikaz sadrzi samo opstine; zbirne stavke kao Republika Srbija,
regioni i oblasti nisu ukljucene dok se izricito ne izaberu u filteru oblasti.
Za uparivanje kroz popise koristi se normalizovan kljuc naziva, ukljucujuci
podrsku za cirilicne i latinicne varijante. Tabela prikazuje opstine koje nisu
uparene kroz sve ucitane godine. Ovo je kontrola mogucih nepoklapanja, a ne
zvanicna istorijska sifra: promene granica i promenjena imena zahtevaju proveru
i po potrebi eksplicitnu istorijsku tabelu preslikavanja.

#### Problematike koje su bile

##### Reseni problemi
Zbirne stavke Srbije, regiona, oblasti i opstina imaju oznacen geografski nivo.
Podrazumevano se prikazuju samo opstine, cime se izbegava njihovo sabiranje sa
agregatima. Zbir Srbije se ukljucuje samo kada se izabere u filteru oblasti.

Boje kao takve u grafikonima su koristile tab20 a ima 21 etnicitet. Dodavali smo dodatan hex koji predstavlja taj dodatni etnicitet.

##### Sta treba da se sredi
Svaki istorijski format mora da se proveri i po potrebi dobije poseban importer
koji ga prevodi u isti oblik podataka. Godisnje oznacavanje i poredjenje su
pripremljeni, ali time se ne garantuje da ce svaka tabela iz 2011, 2002, 1991
ili 1981. biti procitana bez prilagodjavanja parsera.
Podrzani su Excel formati `.xls`, `.xlsx`, `.xlsm`, `.xlsb` i `.ods`, kao i `.csv`.

Filteri i prepoznavanje geografskog nivoa zavise od naziva u izvoru. Neprepoznati
istorijski nazivi i promenjene granice moraju se proveriti prema izvornim
tabelama; za potpuno pouzdano spajanje kroz popise potreban je zvanicni
crosswalk geografskih sifara.

#### Dalji koraci
Srediti kod tako da moze da cita bilo koji RZS file i da izbaci odgovarajuce filtere.
Ovo je malo nezgodno da se odradi, zahteva da se izdefinise dosta elemenata.
Bilo bi idealno da se isprati neki tok u tim podacima.
