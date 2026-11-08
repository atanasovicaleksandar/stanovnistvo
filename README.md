# stanovnistvo
Skripta za sredjivanje podataka o stanovnistvu

## Svrha
Skripta uzima RZS podatke koji su predvidjeni za gledanje, i sredjuje ih kako bi mogli da se koriste za filtiranje i pravljenje grafikona.

### Sta tacno radi
Uzima eksel file za 2022 trenutno samo (nazalost) i sredi ih da mogu da se koriste za filtiranje i pravljenje grafikona.

#### Problematike koje su bile

##### Reseni problemi
Srbija u celosti, regioni, oblasti, opstine, tip naselja sve potpada pod istu kolonu.
Nezgodno za filtriranje, pravi pogresne zbirove u odredjenim grafikonima.

Boje kao takve u grafikonima su koristile tab20 a ima 21 etnicitet. Dodavali smo dodatan hex koji predstavlja taj dodatni etnicitet.

##### Sta treba da se sredi
Trenutno aplikacija radi samo na podacima iz 2022, da bi radila na podacima iz 2011 treba promeniti driver za citanje eksel podataka i prilagoditi dodatne elemente.
Podrzani su Excel formati `.xls`, `.xlsx`, `.xlsm`, `.xlsb` i `.ods`, kao i `.csv`.

Nazivi kolona (headeri) su hardcodovani zapravo, sto pravi problem ako se u drugoj nekoj tabeli promeni redosled ili bilo sta.
Headeri sami po sebi moraju bolje da se osmisle jer po ovoj postavci rade samo na ovom fajlu.

Sami filteri, pogotovo po regionima su clunky i ne postoji zapravo presek sto se tice hijerarhije na nacin na koji bi trebao.
Jer recimo, nije kategorizacija

Ovako bi trebalo da izgleda gde bi pod region uzimali zbir svih naselja (opstina ja mislim) u tom regionu.
Trenutno ta hijerarhijska kategorizacija ne postoji jer ti odnosi kao takvi ne postoje.
Moze da se koristi indentacija kroz openpyxl driver, ali ako se to koristi onda ne mogu da se otvaraju drugi formati.
Sto opet, potencijalno moze da se resi tako sto bi se u zavisnosti od tipa fajla koji se ubaci koristio drugi driver.
Sto onda stvara problem jer ovaj pristup sa indentacijom nece raditi u ranijim popisnim statistikama.
Tako da...

| Region | Naselje | Srbi |
| -------- | -------- | -------- |
| Region A   | Naselje A   | 5924   |
| Region A   | Naselje B   | 8658   |

#### Dalji koraci
Srediti kod tako da moze da cita bilo koji RZS file i da izbaci odgovarajuce filtere.
Ovo je malo nezgodno da se odradi, zahteva da se izdefinise dosta elemenata.
Bilo bi idealno da se isprati neki tok u tim podacima.
