# Analisi dei corsi del paramento

Documento di accompagnamento allo script `analisi_corsi_paramento.py`, parte della
suite **MensioAnalysisTools**. Spiega cosa fa l'algoritmo, *perché* è costruito
così, il significato di ogni parametro e di ogni campo prodotto, con esempi
numerici concreti e una guida alla lettura dei risultati.

---

## Indice

1. [A cosa serve](#1-a-cosa-serve)
2. [Prerequisito: il rilievo raddrizzato](#2-prerequisito-fondamentale-il-rilievo-raddrizzato)
3. [Come riconosce i corsi](#3-come-riconosce-i-corsi)
4. [I parametri di aggancio e i loro default](#4-i-parametri-di-aggancio-e-i-loro-default)
5. [L'analisi dei giunti](#5-lanalisi-dei-giunti)
   - 5.1 Letto di malta orizzontale
   - 5.2 Giunto verticale di testa
   - 5.3 Sfalsamento dei giunti
6. [Il rilevamento delle discontinuità](#6-il-rilevamento-delle-discontinuità)
   - 6.1 Il segnale
   - 6.2 L'algoritmo
   - 6.3 La sensibilità
   - 6.4 Esempio
7. [Come leggere i risultati](#7-come-leggere-i-risultati)
8. [Interpretazione dei campi](#8-interpretazione-dei-campi)
9. [Campi prodotti in output](#9-campi-prodotti-in-output)
10. [Dipendenze e affidabilità](#10-dipendenze-e-affidabilità)

---

## 1. A cosa serve

Dato un paramento murario già segmentato in componenti poligonali (l'output
`analisi_rilievo` della suite), lo strumento ricostruisce automaticamente i
**corsi** — i filari orizzontali di posa — e ne misura la regolarità. Da questa
base ricava tre livelli di lettura, ciascuno attivabile in modo indipendente:

1. **i corsi**: a quale filare appartiene ogni componente, in che posizione, e
   con quale inclinazione corre il corso;
2. **i giunti**: lo spessore del letto di malta orizzontale, il giunto verticale
   di testa tra pezzi contigui, e il grado di ammorsatura (sfalsamento dei
   giunti verticali fra corsi consecutivi);
3. **le discontinuità**: i punti, lungo lo sviluppo verticale, in cui il regime
   costruttivo cambia — candidati a giornate di lavoro, riprese o lotti diversi
   di materiale.

L'obiettivo non è sostituire la lettura archeologica, ma fornirle una base
metrica oggettiva: lo strumento *propone* i corsi e le cesure; l'attribuzione
(giornata, ripresa, fase) resta all'interpretazione, da incrociare con buche
pontaie, stratigrafia e fonti.

---

## 2. Prerequisito fondamentale: il rilievo raddrizzato

L'algoritmo lavora in coordinate mappa assumendo che **il muro sia stato
raddrizzato** (ortofoto frontale, fotopiano o rilievo già ortorettificato) e che
la **Y cresca verso l'alto**. È la condizione naturale di un fotopiano di
prospetto. Se il rilievo non è raddrizzato — per esempio se è ancora in
coordinate oblique o prospettiche — i corsi non risulteranno orizzontali e
l'aggancio fallirà.

Lo strumento usa, per ogni componente:

| Dato | Origine | Significato |
|---|---|---|
| centroide | geometria del poligono | posizione del pezzo nel piano |
| `width_bbox` | campo MensioAnalysisTools | lato maggiore del bbox = lunghezza |
| `height_bbox` | campo MensioAnalysisTools | lato minore del bbox = altezza |
| `fid` | campo identificativo | id univoco |

Le dimensioni vengono prese dai campi del bounding box orientato già calcolati a
monte, non ricavate di nuovo dalla geometria: in questo modo "altezza" e
"lunghezza" sono quelle metrologicamente corrette (lati del rettangolo minimo
orientato), non l'estensione lungo gli assi cartografici.

---

## 3. Come riconosce i corsi

Il cuore dello strumento adatta a QGIS la logica incrementale di **TagLab**
(`QtCourseAnalysis.py`, funzione `detectCoursesIncremental`). Non è un
clustering: è una **costruzione "a catena"**, che ricalca il gesto dell'occhio
che segue un filare.

Il procedimento, ripetuto finché restano pezzi non assegnati:

1. si apre un nuovo corso partendo dal pezzo **più a sinistra** tra i non
   assegnati;
2. si cerca di **estendere il corso verso destra**, agganciando il *primo* pezzo
   alla destra dell'ultimo che superi tutti e quattro i test di compatibilità;
3. quando nessun pezzo a destra è più compatibile, il corso si chiude e se ne
   apre un altro.

I quattro test, valutati rispetto all'ultimo pezzo già inserito nel corso:

| # | Test | Condizione |
|---|---|---|
| 1 | gap orizzontale | `cx_nuovo − cx_ultimo ≤ larghezza_media_corso × x_gap_factor` |
| 2 | continuità del centroide Y | `|cy_nuovo − cy_ultimo| ≤ altezza × y_tolerance_factor` |
| 3 | continuità dei bordi alto/basso | `|top−top|` e `|bottom−bottom| ≤ altezza × ytb_tolerance_factor` |
| 4 | somiglianza di altezza | `altezza_nuovo / altezza_ultimo ∈ [1−h, 1+h]` |

dove `top = cy + h/2` e `bottom = cy − h/2` (coordinate mappa, Y in alto).

**Perché tre test su quattro sono relativi all'altezza del pezzo.** È la scelta
di fondo più importante. Un corso di mattoni alto 4 cm e uno di blocchi alto 40
cm hanno la stessa *regolarità relativa*, ma una tolleranza assoluta in metri
sarebbe assurda per entrambi (3 cm di slittamento è enorme per i laterizi,
trascurabile per i blocchi). Ancorando le tolleranze all'altezza locale, lo
stesso identico parametro lavora su laterizio sottile e su opera quadrata senza
ritocchi: l'algoritmo si auto-scala.

**Perché un test sul bordo *oltre* a quello sul centroide.** Due pezzi possono
avere lo stesso centroide Y ma altezze diverse disposte in modo che uno sporga
sopra e l'altro sotto: il solo test sul centroide li accetterebbe, ma non
appartengono allo stesso letto di posa. Verificando che *sia il bordo superiore
sia quello inferiore* siano allineati, l'algoritmo impone che i pezzi
condividano davvero la stessa fascia orizzontale.

Alla fine i pezzi di ogni corso sono ordinati per X, e i corsi sono numerati
**dal basso verso l'alto** (ordine di costruzione), con una quantizzazione della
quota che raggruppa allo stesso livello i corsi a quota simile.

### L'inclinazione del corso

Per ogni corso con almeno 2 pezzi si esegue un fit ai minimi quadrati `y = m·x + b`
sui centroidi e si ricava `inclinaz_deg = atan(m)` in gradi. Con Y verso l'alto,
**positivo = corso che sale verso destra**, negativo = scende. È un indicatore
diagnostico di cedimenti, pendenze di posa, riprese: un corso a +6° segnala una
deriva sistematica che spesso accompagna un giunto di ripresa.

---

## 4. I parametri di aggancio e i loro default

I default replicano quelli di TagLab, con un'unica modifica deliberata sul gap
orizzontale (1.5 invece di 3.0). Non sono valori magici: sono il punto in cui
"tollerante verso l'irregolarità costruttiva normale" incontra "rigoroso nel non
saltare di corso".

| Parametro | Default | Cosa controlla |
|---|---|---|
| `y_tolerance_factor` | 0.3 | scarto ammesso del centroide Y, in frazioni di altezza |
| `ytb_tolerance_factor` | 0.3 | scarto ammesso dei bordi alto/basso |
| `height_tolerance_factor` | 0.3 | somiglianza di altezza (rapporto in 0.7–1.3) |
| `x_gap_factor` | 1.5 | gap orizzontale massimo, in larghezze medie del corso |

**Le tre tolleranze a 0.3.** Tollerano lo scarto fino a circa un terzo
dell'altezza del pezzo: abbastanza per assorbire l'irregolarità costruttiva
reale (pezzi leggermente più alti o più bassi, malta non uniforme), ma sotto la
soglia di 0.5 oltre la quale si rischierebbe di agganciare un pezzo del corso
*sopra* o *sotto*. Su un paramento molto regolare puoi stringere a 0.2; su
muratura rustica allargare a 0.4.

**Il fattore gap a 1.5.** È l'unico parametro relativo alla *larghezza* (più
permissivo, perché due pezzi consecutivi distano normalmente circa una larghezza
di pezzo, separati solo dal giunto verticale). Il valore regola la tolleranza ai
*buchi*: a 1.5 il corso può scavalcare un pezzo mancante stretto ma si spezza su
una lacuna ampia; alzandolo (es. 3.0) il corso sopravvive a lacune più grandi ma
rischia di unire tronconi separati. Taralo sullo **stato di conservazione**:
paramento integro → 1.5; molto lacunoso → 2.5–3.0.

> *Esempio.* Mattoni di larghezza media 0.29 m, due pezzi consecutivi con
> centroidi a 0.30 m di distanza: gap effettivo ≈ 0.30 m, tolleranza
> `0.29 × 1.5 = 0.435 m` → agganciati. Se manca un pezzo, il successivo è a
> ≈ 0.60 m: `0.60 > 0.435` → il corso si spezza, e i due tronconi diventano due
> corsi separati (correggibili a mano sul campo `corso_id`).

---

## 5. L'analisi dei giunti

Attivabile con il flag **Analisi dei giunti** (attivo di default). Produce tre
misure, due per corso e una per pezzo.

### 5.1 Letto di malta orizzontale — `letto_malta_sup`

È lo spessore del giunto di allettamento tra un corso e quello immediatamente
sopra. Per ogni corso si calcolano due quote rappresentative (Y in alto):

```
bordo_sup = quota_media + altezza_corso / 2
bordo_inf = quota_media − altezza_corso / 2
```

dove `quota_media` è la media delle Y dei centroidi del corso e `altezza_corso`
è la **mediana** delle altezze dei suoi pezzi (mediana, non media, per non farsi
spostare la quota da un pezzo anomalo). Il letto tra il corso *k* e quello sopra
è poi:

```
letto_malta_sup(k) = bordo_inf(corso k+1) − bordo_sup(corso k)
```

cioè lo spazio libero tra la faccia alta del corso inferiore e la faccia bassa di
quello superiore.

> *Esempio.* Mattoni alti 0.043 m, corsi distanziati di 0.055 m da centro a
> centro. Bordo superiore del corso 1 a `0.0215 + 0.043/2 = 0.043`; bordo
> inferiore del corso 2 a `0.055 + 0.0215 − 0.043/2 = 0.055`. Letto di malta =
> `0.055 − 0.043 = 0.012 m`, cioè 12 mm.

È una misura **media e per-corso**, non puntuale: descrive il letto
rappresentativo dell'intero filare, non lo spessore sotto il singolo mattone (che
sarebbe rumore). Valori **negativi** non sono un errore: segnalano corsi che si
sovrappongono in verticale (corsi non perfettamente orizzontali, zeppe, rincocci,
o un pezzo assegnato al corso sbagliato), e lo script li conta nel log. L'ultimo
corso (il più alto) ha `letto_malta_sup` nullo, perché non c'è un corso sopra.

### 5.2 Giunto verticale di testa — `giunto_vert`

Calcolato per ogni pezzo (campo sul layer dei componenti): è lo spazio libero
verso il pezzo successivo a destra nello stesso corso.

```
giunto_vert(i) = (cx_{i+1} − w_{i+1}/2) − (cx_i + w_i/2)
```

L'ultimo pezzo di ogni corso ha valore nullo. Mappato sul paramento, una colonna
verticale di `giunto_vert` anomali che attraversa più corsi è un indizio di
cesura costruttiva.

### 5.3 Sfalsamento dei giunti — `sfalso_giunti_sup`

È l'indice di **ammorsatura**: misura quanto i giunti verticali di un corso sono
sfalsati rispetto a quelli del corso sopra. Per ogni giunto del corso inferiore
si misura la distanza orizzontale dal giunto più vicino del corso superiore, la
si normalizza sulla larghezza media dei pezzi e la si riporta alla fase entro un
passo, in `[0, 0.5]`:

- **≈ 0** → giunti allineati: ammorsatura assente, possibile **cesura** o giunto
  passante tra settori/fasi;
- **≈ 0.5** → sfalsamento di mezzo pezzo: ammorsatura regolare (il mattone copre
  il giunto sottostante, come nella buona pratica costruttiva).

> *Esempio.* In una muratura ben ammorsata i giunti del corso superiore cadono a
> metà tra quelli del corso sotto → `sfalso_giunti_sup ≈ 0.5`. Dove invece i
> giunti verticali si allineano per più corsi consecutivi (`≈ 0`), hai un giunto
> passante: segno tipico di due settori accostati o di un rifacimento.

Il valore per-corso, che aggrega su tutti i giunti del filare, è più robusto del
`giunto_vert` per-pezzo, che è più rumoroso ma spazialmente più ricco.

---

## 6. Il rilevamento delle discontinuità

Attivabile con il flag **Rilevamento discontinuità** (attivo di default).
Trasforma la suite di misure per-corso, lette **dal basso verso l'alto**
nell'ordine di costruzione, in **segmenti omogenei separati da cesure**. Ogni
cesura è un candidato giunto di giornata, ripresa o cambio di lotto di materiale.

### 6.1 Il segnale

Il parametro **Segnale per il rilevamento** sceglie su quale serie cercare le
discontinuità (default: *letto + sfalsamento*):

| Opzione | Serie | Cosa intercetta |
|---|---|---|
| letto di malta | `letto_malta_sup` | cambi di cadenza dell'allettamento |
| altezza corso | `altezza_corso` | cambi di pezzatura / lotto di materiale |
| sfalsamento giunti | `sfalso_giunti_sup` | cambi di tecnica di ammorsatura, cesure |
| **letto + sfalsamento** | multivariato (2 canali) | il "gesto di posa": cadenza *e* ammorsatura |
| letto + sfalsamento + altezza | multivariato (3 canali) | gesto di posa *più* approvvigionamento |

Il default a due canali combina i due indicatori che descrivono *come* è stato
costruito il muro (cadenza dell'allettamento e ammorsatura), entrambi proprietà
del gesto di posa: cambiano insieme quando cambia chi posa o quando si riprende.
L'altezza è tenuta fuori dal default perché descrive il *materiale*, non il
gesto, e un cambio di lotto può avvenire dentro la stessa giornata; resta
disponibile come serie a sé o nel multivariato completo.

### 6.2 L'algoritmo

Si usa la **change-point detection** (PELT della libreria `ruptures` se
installata; altrimenti un rilevatore interno equivalente in puro numpy). La serie
viene standardizzata (z-score per colonna) e segmentata col criterio dei minimi
quadrati: ogni cesura è accettata solo se la riduzione di varianza che produce
supera una **penalità** scalata come `penalty × log(N)` — formulazione tipo BIC
che rende il parametro indipendente dalla lunghezza della serie e robusto al
rumore.

I due percorsi (PELT e fallback) usano lo stesso criterio L2 e la stessa scala,
quindi producono **risultati identici a parità di penalità**: non sei vincolato
ad avere `ruptures`, che serve solo per la velocità su serie molto lunghe.

### 6.3 La sensibilità (penalità)

Il parametro **Sensibilità** (default 2.5) regola quanto netta deve essere una
discontinuità per essere dichiarata. Il default non è arbitrario: su serie corte
(qualche decina di corsi) è il valore che mantiene il tasso di falsi positivi su
puro rumore sotto il 4%, rilevando però il 100% dei salti reali di entità pari a
una deviazione standard. Sotto 1.5 i falsi positivi salgono oltre il 20%; sopra
3.0 si rischia di perdere le transizioni deboli.

- **alta** (es. 3–4) → poche cesure, solo quelle nette: lettura prudente;
- **bassa** (es. 1–1.5) → più cesure, anche transizioni deboli: lettura
  esplorativa, da filtrare a mano.

### 6.4 Esempio

Un paramento di 12 corsi in cui il letto di malta passa da ≈ 12 mm (corsi 1–6) a
≈ 22 mm (corsi 7–12). Con il segnale *letto di malta* e penalità 2.5, lo script
individua **una cesura al corso 7** e assegna `segmento = 1` ai corsi 1–6 e
`segmento = 2` ai corsi 7–12. Nel log compare la statistica per segmento (letto
medio e CV di ciascuno). La cesura è il candidato giunto di giornata: la ripresa
del giorno dopo ha lasciato un letto di allettamento sistematicamente più spesso.

---

## 7. Come leggere i risultati

Un percorso operativo, dal generale al particolare:

1. **Colora i componenti per `corso_id`**: verifica a colpo d'occhio che i corsi
   siano stati ricostruiti bene. Se trovi corsi spezzati (un filare diviso in
   due `corso_id`), alza `x_gap_factor` o correggi a mano; se trovi corsi fusi,
   abbassa le tolleranze.
2. **Guarda `inclinaz_deg`** nella sintesi: inclinazioni anomale o un cambio
   brusco di pendenza segnalano cedimenti o riprese.
3. **Leggi `letto_malta_sup` dal basso verso l'alto**: la sua *serie* è la firma
   della cadenza costruttiva; i salti sono i candidati alle giornate.
4. **Controlla `sfalso_giunti_sup`**: dove crolla verso 0 su uno o più corsi
   consecutivi, sospetta una cesura verticale (settori affiancati, ripresa).
5. **Incrocia con `segmento` e `cesura`**: i segmenti sono i tratti costruttivi
   omogenei proposti dallo strumento. Coloragli i componenti per `segmento` per
   leggere le presunte giornate sulla mappa.
6. **Convergenza**: le cesure più solide sono quelle che si accendono su più
   indicatori insieme — un salto di `letto_malta_sup` che coincide con un crollo
   di `sfalso_giunti_sup` e un cambio di `inclinaz_deg` è molto più affidabile di
   una cesura isolata su un solo segnale.

---

## 8. Interpretazione dei campi

Questa sezione spiega **cosa significano concretamente i valori** prodotti, con
intervalli tipici ed esempi di lettura. Nessuna soglia è assoluta: i valori
metrici dipendono dal materiale (laterizio sottile vs blocchi) e vanno calibrati
sul singolo paramento, usando la *distribuzione* come riferimento.

### `inclinaz_deg` — inclinazione del corso (gradi)

| Intervallo tipico | Lettura |
|---|---|
| −2° – +2° | corso orizzontale, posa regolare |
| ±2° – ±5° | lieve pendenza, normale in murature non rifinite |
| oltre ±5° | corso nettamente inclinato: cedimento, pendenza di posa o ripresa |

Più che il valore assoluto conta la *variazione* lungo la serie: un cambio
brusco di inclinazione tra corsi vicini segnala spesso un giunto di ripresa o un
assestamento strutturale. Il segno indica il verso (+ sale verso destra).

### `letto_malta_sup` — letto di malta orizzontale (metri)

Lo spessore del giunto di allettamento verso il corso superiore. L'intervallo
"normale" dipende dalla tecnica: in *opus testaceum* i letti sono tipicamente di
1–3 cm; in opera quadrata a secco tendono a zero.

| Lettura | Significato |
|---|---|
| valore stabile lungo la serie | cadenza costruttiva regolare |
| salto netto tra corsi vicini | candidato giunto di giornata / ripresa |
| valore **negativo** | sovrapposizione verticale dei corsi: zona irregolare, rincocci, o assegnazione di corso da verificare |

Leggi la *serie* dal basso verso l'alto, non il singolo valore: è la sua
**variazione** a portare l'informazione. L'ultimo corso ha valore nullo (non c'è
corso sopra).

### `sfalso_giunti_sup` — ammorsatura (0–0,5)

| Intervallo | Lettura |
|---|---|
| 0,35 – 0,50 | ammorsatura regolare: i giunti del corso sopra coprono quelli sotto |
| 0,15 – 0,35 | ammorsatura parziale o irregolare |
| 0,00 – 0,15 | giunti allineati: ammorsatura assente, possibile **cesura** o giunto passante |

Un crollo verso 0 su uno o più corsi consecutivi è il segnale più diretto di una
**cesura verticale** (settori affiancati, tamponatura, rifacimento) — qualcosa
che la sola analisi orizzontale dei letti non vedrebbe.

### `giunto_vert` — giunto verticale di testa (metri, per pezzo)

Spazio libero verso il pezzo a destra nello stesso corso. Valori tipici
dell'ordine del giunto di malta verticale (pochi mm – 1-2 cm). Valori
**negativi** indicano pezzi che si compenetrano (contatto diretto o
sovrapposizione dei bbox: posa a secco serrata o irregolarità). Mappato sul
paramento, una **colonna** verticale di valori anomali che attraversa più corsi
conferma una cesura a livello di singolo pezzo.

### `segmento` e `cesura` — discontinuità costruttive

- **`segmento`** (intero, dal basso): identifica i **tratti costruttivi
  omogenei** proposti dallo strumento. Non ha un ordine di merito: è solo
  un'etichetta di gruppo. Coloragli i componenti per leggere le presunte
  giornate/fasi sulla mappa.
- **`cesura`** (0/1): vale 1 sul **primo corso di ogni nuovo segmento**, cioè
  dove cade la discontinuità. È il candidato giunto di giornata, ripresa o
  cambio di lotto.

> I segmenti sono **candidati statistici**, non fasi accertate. Vanno letti per
> *convergenza*: una `cesura` è solida quando coincide con un salto di
> `letto_malta_sup`, un crollo di `sfalso_giunti_sup` o un cambio di
> `inclinaz_deg`. Una cesura isolata su un solo segnale è più debole.

### I risultati nel log dei Processing

Oltre ai campi, il log riporta: il numero di **corsi** riconosciuti (su quanti
componenti validi), gli eventuali corsi con **letto negativo**, e — per il
rilevamento delle discontinuità — il **segnale** usato, il **numero di cesure** e
di **segmenti**, con la statistica per segmento (numero di corsi, letto medio e
CV di ciascuno).

### Una regola pratica di sintesi

Nessun singolo campo "dimostra" un giunto di giornata. La lettura solida è **per
convergenza**: una cesura è un candidato forte quando più indicatori cambiano
insieme nello stesso punto della serie — letto di malta, ammorsatura,
inclinazione — e quando il cambio è coerente con la lettura archeologica
(buche pontaie, stratigrafia). Lo strumento fornisce i confini; l'interpretazione
resta archeologica.

---

## 9. Campi prodotti

### Layer "Componenti con corso"

Copia del layer in ingresso con i campi aggiunti:

| Campo | Tipo | Significato |
|---|---|---|
| `corso_id` | Int | filare di appartenenza (1 = il più basso) |
| `pos_in_corso` | Int | posizione nel filare, da sinistra |
| `corso_n_pezzi` | Int | numero di pezzi del corso |
| `giunto_vert` | Double | giunto verticale verso il pezzo a destra *(con analisi giunti)* |
| `segmento` | Int | tratto costruttivo omogeneo *(con rilevamento discontinuità)* |

I componenti privi di dimensioni valide restano con `corso_id` nullo e sono
esclusi dai corsi (segnalati nel log).

### Tabella "Sintesi per corso"

Una riga per corso:

| Campo | Tipo | Significato |
|---|---|---|
| `corso_id` | Int | id del corso (dal basso) |
| `n_pezzi` | Int | numero di pezzi |
| `quota_media` | Double | quota media dei centroidi |
| `altezza_corso` | Double | altezza rappresentativa (mediana) |
| `lunghezza_corso` | Double | estensione orizzontale del corso |
| `inclinaz_deg` | Double | inclinazione (gradi; + = sale verso destra) |
| `letto_malta_sup` | Double | letto di malta verso il corso superiore *(con giunti)* |
| `sfalso_giunti_sup` | Double | ammorsatura: 0 = allineati, 0.5 = mezzo pezzo *(con giunti)* |
| `segmento` | Int | tratto costruttivo omogeneo *(con discontinuità)* |
| `cesura` | Int | 1 sul primo corso di un nuovo segmento *(con discontinuità)* |

---

## 10. Dipendenze e affidabilità

**Dipendenze.** Obbligatoria: `numpy` (sempre presente nel Python di QGIS).
Opzionale: `ruptures` (algoritmo PELT), usata dal rilevamento delle
discontinuità solo se installata; in sua assenza lo strumento ricade
automaticamente sul rilevatore interno in puro numpy, che dà risultati
equivalenti. `ruptures` conviene solo per velocizzare l'analisi su serie molto
lunghe. Installazione, dalla *OSGeo4W Shell*:

```
python -m pip install ruptures
```

**Avvertenze.** L'algoritmo dà il meglio su paramenti **regolari a corsi
continui** (opera laterizia, opera quadrata regolare). Su *opus incertum* o
murature molto irregolari il concetto stesso di corso si indebolisce e il
risultato sarà frammentato — è un limite dell'approccio, non
dell'implementazione. Inoltre il `segmento` è un *candidato statistico*: dipende
dalla bontà dell'assegnazione dei corsi (un corso mal ricostruito crea un falso
salto), su paramenti corti va letto come indicativo, e non equivale
automaticamente a "giornata". La statistica propone i confini; l'archeologia li
interpreta.

---

*Documento di accompagnamento allo script `analisi_corsi_paramento.py`, parte
della suite MensioAnalysisTools. L'algoritmo di riconoscimento dei corsi adatta
`QtCourseAnalysis.py` di TagLab (CNR-ISTI Visual Computing Lab).*
