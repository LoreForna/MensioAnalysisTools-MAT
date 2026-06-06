# Statistiche avanzate pattern paramento e reimpiego

Algoritmo Processing per QGIS per l'analisi statistica di un paramento murario,
finalizzata all'individuazione di pattern di posa e di elementi di probabile
**reimpiego** (spolia). Si concatena all'output di **MensioAnalysisTools**
(`analisi_quantitativa_mattoni` o `analisi_quantitativa_altri_componenti`).

L'algoritmo opera in due modalità:

- **Mattoni** (laterizi di ritaglio): sola analisi del paramento.
- **Altri componenti / componenti a secco** (blocchi, conci): analisi del
  paramento **più** analisi metrologica modulare opzionale.

---

## Indice

1. [Mapping dei campi in ingresso](#1-mapping-dei-campi-in-ingresso)
2. [Le due modalità d'uso](#2-le-due-modalità-duso)
3. [I calcoli dell'analisi del paramento](#3-i-calcoli-dellanalisi-del-paramento)
   - 3.1 Fattore di riempimento
   - 3.2 Statistica circolare assiale dell'orientamento
   - 3.3 Distanza di Mahalanobis
   - 3.4 PCA
   - 3.5 Clustering gerarchico
   - 3.6 Coefficiente di variazione
   - 3.7 reuse_score
   - 3.8 LISA (Local Moran's I)
4. [I calcoli dell'analisi metrologica](#4-i-calcoli-dellanalisi-metrologica)
   - 4.1 Aderenza al modulo e test di Rayleigh
   - 4.2 Cosine quantogram di Kendall
   - 4.3 Validazione Monte Carlo
   - 4.4 Guardia di scala
5. [I parametri e il perché dei valori di default](#5-i-parametri-e-il-perché-dei-valori-di-default)
6. [Campi prodotti in output](#6-campi-prodotti-in-output)
7. [Come leggere i risultati](#7-come-leggere-i-risultati)
8. [Interpretazione dei risultati](#8-interpretazione-dei-risultati)
9. [Dipendenze e installazione](#9-dipendenze-e-installazione)

---

## 1. Mapping dei campi in ingresso

| Parametro dell'algoritmo | Campo MensioAnalysisTools | Significato |
|---|---|---|
| Campo lunghezza | `width_bbox` | lato maggiore del minimum oriented bounding box |
| Campo spessore | `height_bbox` | lato minore del bounding box |
| Campo area | `area_componente` | area **reale** del poligono (non del bbox) |
| Campo angolo | `angle_bbox` | orientamento di posa, **assiale 0–180°** |
| Campo id | `fid` | identificativo univoco |

> **Nota sull'angolo.** Il campo `angle_bbox` di MensioAnalysisTools deriva
> dall'algoritmo nativo QGIS `orientedMinimumBoundingBox`, che vincola l'angolo
> all'intervallo 0–180° (verificato sul codice sorgente di QGIS). È quindi una
> grandezza **assiale**, e lo script la tratta come tale (vedi §3.2). Nessuna
> conversione necessaria.

---

## 2. Le due modalità d'uso

### Mattoni
I mattoni romani da paramento sono **ritagli**: triangoli o frammenti ottenuti
spezzando bessali e sesquipedali in cantiere. La loro lunghezza dipende dal
taglio, non da un modulo teorico. Per questo **l'analisi metrologica NON va
attivata sui mattoni**: cercare un modulo su misure di ritaglio produrrebbe
picchi spuri. Si lascia il flag *"Esegui analisi metrologica modulare"*
disattivato (impostazione predefinita).

### Altri componenti / componenti a secco
Blocchi e conci lapidei seguono invece un modulo teorico reale, atteso **sia
sulla lunghezza sia sull'altezza**. Qui si attiva l'analisi metrologica, e lo
scarto dal modulo diventa un ulteriore indizio di reimpiego (un pezzo
fuori-modulo proviene verosimilmente da un altro edificio o da un'altra fase).

---

## 3. I calcoli dell'analisi del paramento

Per gli esempi che seguono si immagini un paramento in *opus testaceum* dove la
maggior parte dei mattoni misura circa 29,5 × 4,3 cm, posati orizzontalmente.

### 3.1 Fattore di riempimento (`R_fill`)

**Formula:** `R_fill = area_reale / (lunghezza × spessore)`

Misura quanto il componente "riempie" il proprio ingombro rettangolare teorico.

- **Esempio.** Mattone integro: area 0,0125 m², lunghezza 0,295 m, spessore
  0,043 m → ingombro = 0,295 × 0,043 = 0,012685 m² → R_fill = 0,0125 / 0,012685
  ≈ **0,986**. Pezzo quasi perfettamente rettangolare.
- **Esempio reimpiego.** Mattone scheggiato e irregolare: area 0,0090 m²,
  lunghezza 0,28 m, spessore 0,048 m → ingombro = 0,013440 → R_fill = 0,0090 /
  0,013440 ≈ **0,670**. Forma molto lontana dal rettangolo: candidato a riuso o
  taglio marcato.

R_fill ≈ 1 indica un pezzo squadrato; valori bassi indicano irregolarità,
scheggiature, profili obliqui.

### 3.2 Statistica circolare assiale dell'orientamento

L'orientamento di posa è una variabile **circolare e assiale**: 1° e 179° sono
quasi paralleli (distano 2°), non lontanissimi. Trattarli con media e
deviazione standard ordinarie sarebbe un errore: la media aritmetica di 1° e
179° darebbe 90°, ortogonale al vero orientamento (≈0°).

**Metodo.** Si raddoppia l'angolo (passando da [0,180) a [0,360)), si calcola
il vettore medio con seno e coseno, e si dimezza il risultato:

```
media_assiale = atan2( media(sin 2θ), media(cos 2θ) ) / 2
```

La **coerenza** è la lunghezza del vettore risultante R̄ ∈ [0,1]:
- R̄ → 1: orientamenti molto concordi (paramento ordinato)
- R̄ → 0: orientamenti sparsi (disordine, rappezzi)

- **Esempio coerente.** Angoli {2°, 1°, 179°, 3°, 178°}: nonostante la
  presenza di valori vicini a 180°, la media assiale risulta ≈ **0,5°** con
  **R̄ ≈ 0,999**. La statistica assiale riconosce che 178° e 179° sono
  praticamente orizzontali, non "ruotati di mezzo giro".
- **Esempio disordinato.** Angoli uniformemente sparsi tra 0° e 180°:
  **R̄ ≈ 0,03**, prossimo a zero.

**Scarto angolare locale.** Per ogni componente si calcola la differenza
assiale (in [0°, 90°]) tra il suo orientamento e l'orientamento medio dei suoi
vicini. Un pezzo che devia molto dai vicini è un'anomalia di posa.

Il vicinato è calcolato con **due criteri** (vedi §5), per confronto:
- **raggio fisso**: tutti i vicini entro un cerchio di raggio dato
- **k-nearest**: i k vicini più prossimi

### 3.3 Distanza di Mahalanobis (`mahal`)

Individua gli **outlier dimensionali** considerando lunghezza, spessore, area e
R_fill **simultaneamente** e tenendo conto della loro correlazione (a
differenza di una semplice soglia su una variabile alla volta).

Le variabili vengono prima standardizzate (z-score). La distanza di Mahalanobis
di un punto dal centroide della nuvola usa l'inversa della matrice di
covarianza: un valore alto significa che il componente è "lontano" dalla
popolazione tipica in modo statisticamente anomalo.

- **Esempio.** In un insieme di mattoni quasi tutti 29–30 cm × 4–4,5 cm, un
  pezzo da 25 cm × 5,5 cm con area anomala avrà un Mahalanobis molto più alto
  della media: la combinazione delle sue misure è insolita anche se nessuna
  singola dimensione è estrema.

### 3.4 PCA (Analisi delle Componenti Principali) — `PC1`, `PC2`

Riduce le quattro variabili lineari (lunghezza, spessore, area, R_fill) a due
componenti principali, decorrelate e ordinate per varianza spiegata.

- **PC1** cattura tipicamente la "taglia" generale (pezzi grandi vs piccoli):
  se i loadings sono tutti concordi, è un fattore di dimensione complessiva.
- **PC2** cattura di solito lo scarto di forma/proporzione indipendente dalla
  taglia.

- **Esempio.** Su un paramento omogeneo con pochi reimpieghi, una PCA potrebbe
  spiegare il 55% della varianza con PC1 e il 28% con PC2: i reimpieghi
  tenderanno a staccarsi lungo PC2 (forma diversa) più che lungo PC1 (taglia).

La PCA qui è esplorativa: serve a visualizzare la struttura e alimentare la
diagnostica, non è il fulcro dell'individuazione del riuso.

### 3.5 Clustering gerarchico (`cluster`)

Raggruppa i componenti con il metodo di **Ward** (minimizzazione della varianza
intra-cluster) sulle variabili lineari standardizzate **più lo scarto angolare
locale**. Se il numero di cluster è 0 (default), viene stimato automaticamente
tagliando il dendrogramma al 70% dell'altezza massima di fusione.

- **Esempio.** Un paramento con una tamponatura di reimpiego produce
  tipicamente **due cluster**: uno grande e omogeneo (la muratura coerente) e
  uno piccolo che raccoglie i pezzi anomali. Il cluster anomalo si riconosce
  dal coefficiente di variazione molto più alto (§3.6).

Il clustering è lo strumento più efficace per il **reimpiego diffuso** (pezzi
sparsi ma dimensionalmente diversi).

### 3.6 Coefficiente di variazione (CV)

**Formula:** `CV = deviazione standard / media`

Stampato nel log, globale e **per cluster**, su lunghezza, spessore, area e
R_fill. È adimensionale, quindi confrontabile tra dimensioni diverse.

- **CV basso** (es. 0,01–0,03): produzione/posa standardizzata.
- **CV alto** (es. > 0,10): eterogeneità, possibile approvvigionamento misto o
  reimpiego diffuso.

- **Esempio.** Cluster principale con CV lunghezza = 0,012 (mattoni molto
  uniformi) vs cluster anomalo con CV lunghezza = 0,128: un fattore 10 di
  differenza che identifica nettamente il gruppo di reimpiego.

### 3.7 Indicatore sintetico di reimpiego (`reuse_score`)

Combina gli indizi indipendenti in un punteggio ∈ [0,1], usando il **rango
percentile** di ciascuno (così ogni indizio pesa uguale, a prescindere dalla
scala):

- **Senza metrologia (mattoni), 3 indizi:**
  `reuse_score = ( basso_riempimento + alto_Mahalanobis + alto_scarto_angolare ) / 3`
- **Con metrologia (altri componenti), 4 indizi:** si aggiunge
  `alto_scarto_modulare`, e si divide per 4.

- **Esempio.** Un mattone con R_fill basso (rango 0,95 → contributo
  "basso riempimento" alto), Mahalanobis alto (rango 0,90) e forte scarto
  angolare (rango 0,88) ottiene reuse_score ≈ (0,95 + 0,90 + 0,88) / 3 ≈
  **0,91**: fortemente sospetto. Un mattone tipico avrà reuse_score intorno a
  0,4–0,5.

> Il reuse_score è una **euristica di segnalazione**, non una prova.
> L'interpretazione robusta nasce dalla **convergenza** degli indizi e dalla
> lettura spaziale (§3.8).

### 3.8 LISA — Local Moran's I (`lisa_I`, `lisa_p`, `lisa_clust`)

Analizza la **distribuzione spaziale** del reuse_score: distingue se i pezzi
sospetti sono concentrati in zone (rappezzi, tamponature, restauri) o sparsi.

Per ogni componente l'indice locale di Moran misura se un valore alto è
circondato da altri valori alti. Il risultato è classificato in:
- **HH** (high-high): pezzo ad alto reuse circondato da altri simili →
  **hotspot di reimpiego**
- **LL** (low-low): zona coerente, muratura "buona"
- **HL**: pezzo anomalo isolato (reimpiego sporadico)
- **LH**: pezzo coerente in zona disturbata
- **ns**: non significativo

**Significatività per permutazione.** Per stabilire se un hotspot è reale o
casuale, i valori vengono rimescolati a caso molte volte (default 999) e
l'indice osservato è confrontato con la distribuzione casuale. Il `lisa_p` è il
p-value risultante; la classificazione HH/LL/HL/LH è assegnata solo se
p < 0,05.

- **Esempio.** Una tamponatura di 9 pezzi di reimpiego in un angolo del
  paramento risulterà in un gruppo compatto di celle **HH significative**,
  mentre il resto del paramento sarà **LL**. I pezzi sani che confinano con la
  tamponatura possono risultare anch'essi HH (effetto-alone tipico del LISA):
  il LISA indica la **zona** dell'intervento, con un bordo sfumato, mentre il
  cluster anomalo (§3.5) indica il **singolo pezzo**.

**Complementarità.** Il clustering cattura il reimpiego **diffuso**; il LISA
cattura quello **concentrato**. Usare entrambi copre i due scenari.

---

## 4. I calcoli dell'analisi metrologica

Attiva solo per gli "altri componenti". Risponde a due domande: *(A)* le misure
sono compatibili con un modulo dato? *(B)* qual è il modulo che meglio le
spiega?

Il **resto modulare** è trattato come variabile **circolare**, come
l'orientamento: un resto di 0,99·modulo è "quasi un modulo intero", vicino alla
fase 0, non lontano.

### 4.1 Aderenza al modulo e test di Rayleigh

Per un modulo dato, si calcola la **fase** di ogni misura:
`fase = 2π · (misura mod modulo) / modulo`, e da questa il vettore risultante
**R̄** (aderenza ∈ [0,1]).

- R̄ → 1: tutte le misure sono prossime a multipli interi del modulo →
  forte conformità.
- R̄ → 0: resti sparsi → il modulo testato non spiega le misure.

Il **test di Rayleigh** fornisce un p-value per l'ipotesi nulla "i resti sono
distribuiti uniformemente" (= nessuna modularità).

- **Esempio.** 120 blocchi prodotti su modulo 0,296 m con dispersione di
  lavorazione ±8 mm: testando il modulo 0,296 si ottiene R̄ ≈ 0,99 e Rayleigh
  p ≈ 10⁻⁶⁰ (modularità nettissima). Testando un modulo errato di 0,34 m,
  R̄ scende e i resti appaiono disordinati.

### 4.2 Cosine quantogram di Kendall

Per **cercare** il modulo (non solo verificarlo), si scorre un intervallo di
moduli candidati e per ciascuno si calcola la statistica di Kendall:

```
Φ(q) = √(2/N) · Σ cos( 2π · εᵢ / q )
```

dove εᵢ è lo **scarto della misura dal multiplo di q più vicino**. Il modulo
che massimizza Φ è il candidato migliore.

> **Perché Kendall e non il semplice R̄?** Il R̄ tende a premiare anche i
> sottomultipli del modulo reale (se le misure sono multiple di 0,30 lo sono
> anche di 0,15, 0,10…). La formulazione di Kendall, usando lo scarto dal
> multiplo *più vicino*, attenua questo artefatto.

- **Esempio.** Su 150 conci a ~1 modulo di 0,297 m, il quantogram presenta un
  picco netto a **0,297 m**. Su un campione misto (parte a 0,297, parte a
  0,222) il picco cade in posizione intermedia: segnale che **non c'è un modulo
  unico** — indizio di due produzioni o di reimpiego.

### 4.3 Validazione Monte Carlo

Un picco del quantogram potrebbe emergere per caso (più candidati si provano,
più è probabile un falso allineamento). Per validarlo, si generano molti set di
misure **casuali** (default 300) e si registra il picco massimo di ciascuno,
costruendo una soglia di significatività.

- Picco osservato > 99° percentile dei casuali → **p < 0,01**
- Picco > 95° percentile → **p < 0,05**
- altrimenti → **non significativo**

- **Esempio.** Picco osservato Φ = 17,1; soglia Monte Carlo al 95% = 4,2, al
  99% = 4,7 → il picco è ampiamente significativo (p < 0,01). Misure casuali
  davano picchi massimi intorno a 3,9–4,2, ben sotto.

### 4.4 Guardia di scala

Se quasi tutte le misure di una dimensione sono **inferiori a 1 modulo**, quella
dimensione **non è informativa** per quel modulo (il resto coincide quasi sempre
con la misura stessa, gonfiando R̄ in modo spurio). In tal caso la dimensione
viene esclusa dal giudizio di modularità e segnalata con un avviso.

- **Esempio.** Testando il modulo 0,297 m su mattoni di ritaglio il cui
  spessore è ~0,043 m (molto < 0,297): la dimensione "spessore" viene
  riconosciuta come non informativa, evitando un falso positivo di modularità.
  Se **nessuna** dimensione informativa risulta modulare, lo script avvisa che
  il materiale potrebbe non essere modulare (tipico, appunto, dei laterizi).

---

## 5. I parametri e il perché dei valori di default

### Vicinato — Raggio fisso (default 0 = auto)
Definisce il cerchio entro cui cercare i vicini per la coerenza di
orientamento. **0 attiva il calcolo automatico = 3 × lunghezza media.**

*Perché 3× la lunghezza media:* un cerchio di raggio pari a tre volte la
lunghezza tipica di un componente racchiude il pezzo più la sua "cintura"
immediata — gli adiacenti sullo stesso corso e quelli dei corsi sopra e sotto —
senza allargarsi a una porzione troppo ampia di muratura. È la scala alla quale
la coerenza di posa è significativa dal punto di vista costruttivo.

### Vicinato — k-nearest (default 8)
Numero di vicini più prossimi. *Perché 8:* in una disposizione regolare a corsi,
gli 8 vicini più vicini corrispondono tipicamente al pezzo a sinistra e destra
sullo stesso corso e ai pezzi a contatto nei corsi superiore e inferiore — la
"corona" immediata di un mattone. Confrontare raggio fisso e k-nearest rivela
gli effetti di densità/pezzatura (dove i due criteri divergono, c'è una
variazione locale di densità, di per sé diagnostica).

### Numero di cluster (default 0 = automatico)
*Perché automatico:* in archeologia raramente si conosce a priori quanti gruppi
di paramento esistono. Il taglio del dendrogramma al 70% dell'altezza massima è
un'euristica robusta che separa il cluster principale dai gruppi minori senza
imporre un numero arbitrario. Se si conosce il numero atteso, lo si può fissare.

### Permutazioni LISA (default 999)
*Perché 999:* è il valore convenzionale standard in statistica spaziale. Con 999
permutazioni il p-value più piccolo ottenibile è 1/(999+1) = 0,001, risoluzione
più che sufficiente per la soglia di 0,05. Valori più alti (9999) servono solo
per p-value molto fini. 0 disattiva il test (passata esplorativa veloce).

### Modulo da verificare (default 0,297 m)
*Perché 0,297:* è il **piede romano** (pes monetalis, ≈ 0,2957–0,296 m), il
modulo di gran lunga più frequente nell'edilizia romana. È un punto di partenza
ragionevole, ma è una variabile libera: si può impostare qualunque altro modulo
(piede attico ≈ 0,308, cubito, ecc.).

### Ricerca del modulo: minimo 0,18 / massimo 0,60 / passo 0,002 m
Pensati per componenti con dimensioni nell'ordine di **10–60 cm**.

- *Minimo 0,18:* tiene fuori i sottomultipli più infidi (sotto i ~18 cm: mezzo
  piede, terzi di piede) che genererebbero picchi spuri, lasciando però dentro i
  piedi antichi "corti" e i moduli minori reali (palmi, spanne) intorno ai
  18–25 cm.
- *Massimo 0,60:* copre tutti i componenti fino a 60 cm anche se sono pezzi a un
  solo modulo. Va alzato se si sospettano moduli maggiori.
- *Passo 0,002:* localizza il picco con precisione di ±2 mm. È adeguato perché
  la dispersione di lavorazione del materiale antico (spesso ±5–8 mm) rende
  inutile una risoluzione più fine: si calcolerebbe sotto il livello del rumore
  dei dati. Per raffinare un picco interessante si può rifare una passata mirata
  a passo 0,001 su un intervallo stretto.

> **Importante:** l'intervallo di ricerca va scelto in modo da **contenere il
> modulo atteso con margine**, ma non troppo ampio: più candidati si provano,
> più cresce il rischio di picchi spuri (mitigato dal Monte Carlo).

### Permutazioni Monte Carlo (default 300)
*Perché 300:* sufficiente a stimare in modo affidabile i percentili 95° e 99°
della distribuzione dei picchi casuali, con un costo computazionale contenuto
(il Monte Carlo ripete l'intera scansione del quantogram). 0 disattiva la
validazione.

---

## 6. Campi prodotti in output

### Sempre presenti (analisi del paramento)

| Campo | Significato |
|---|---|
| `R_fill` | fattore di riempimento area/ingombro |
| `mahal` | distanza di Mahalanobis (outlier dimensionali) |
| `PC1`, `PC2` | punteggi delle prime due componenti principali |
| `dev_glob` | scarto angolare assiale vs media globale [0–90°] |
| `dev_loc_rad`, `disp_loc_rad`, `n_rad` | scarto, dispersione e n. vicini (raggio fisso) |
| `dev_loc_knn`, `disp_loc_knn` | scarto e dispersione locale (k-nearest) |
| `cluster` | etichetta di cluster |
| `reuse_score` | indicatore sintetico di reimpiego [0–1] |
| `lisa_I`, `lisa_p`, `lisa_clust` | indice locale di Moran, p-value e classe |

### Presenti solo con metrologia attiva

| Campo | Significato |
|---|---|
| `w_phase`, `w_resid` | fase modulare e scarto dal modulo della larghezza |
| `h_phase`, `h_resid` | fase modulare e scarto dal modulo dell'altezza |

Inoltre, con metrologia attiva, viene prodotto un **CSV del quantogram**
(modulo, Φ_lunghezza, Φ_altezza) per tracciare il grafico aderenza-vs-modulo.

---

## 7. Come leggere i risultati

1. **Simbolizza `reuse_score`** (gradiente) e `lisa_clust` (categorico:
   rosso = HH, blu = LL, grigio = ns) per una lettura immediata.
2. **Reimpiego concentrato** (rappezzo, tamponatura, restauro): cerca gruppi di
   celle HH significative compatte.
3. **Reimpiego diffuso:** guarda il `cluster` anomalo (CV alto) e gli `HL`
   isolati del LISA.
4. **Convergenza:** i candidati più solidi sono i pezzi che si accendono su più
   indicatori insieme — basso `R_fill`, alto `mahal`, alto scarto angolare, e
   (per gli altri componenti) alto scarto modulare — **e** concentrati
   spazialmente.
5. **Confronto dei vicinati:** dove `dev_loc_rad` e `dev_loc_knn` divergono, c'è
   un effetto di densità/pezzatura, esso stesso informativo.
6. **Metrologia:** controlla il log per R̄, Rayleigh, modulo ottimale e
   significatività Monte Carlo; usa il CSV per il grafico del quantogram.

---

## 8. Interpretazione dei risultati

Questa sezione spiega **cosa significano concretamente i valori** che lo script
scrive, con intervalli tipici ed esempi di lettura. Nessuna soglia è assoluta:
vanno calibrate sul singolo paramento, usando la *distribuzione* dei valori
come riferimento.

### `R_fill` — fattore di riempimento

| Intervallo tipico | Lettura |
|---|---|
| 0,95 – 1,00 | pezzo integro, ben squadrato, taglio netto |
| 0,85 – 0,95 | lievi irregolarità o usura dei bordi |
| < 0,85 | forma marcatamente irregolare: scheggiature, profilo obliquo, possibile reimpiego |

Più che il valore assoluto conta la **posizione nella distribuzione**: in un
paramento dove la maggior parte dei pezzi sta a 0,96–0,98, un valore di 0,88 è
già un'anomalia, anche se in assoluto non sembra basso. Guarda l'istogramma di
`R_fill`: una coda verso valori bassi segnala un sottogruppo di pezzi irregolari.

### `mahal` — distanza di Mahalanobis

Non ha un'unità intuitiva; si interpreta **relativamente**. In una popolazione
omogenea la maggioranza dei pezzi ha Mahalanobis basso e simile; i valori che
spiccano sopra la massa sono gli outlier dimensionali.

- **Esempio di lettura.** Se la maggior parte dei pezzi ha `mahal` tra 1 e 2,5
  e alcuni isolati arrivano a 4–5, questi ultimi hanno una **combinazione** di
  dimensioni insolita (non necessariamente una singola misura estrema). Ordina
  la tabella per `mahal` decrescente: i primi sono i candidati dimensionali al
  riuso.

### `PC1`, `PC2` — componenti principali

Sono coordinate in uno spazio ridotto, utili soprattutto per il **diagramma di
dispersione** (scatter PC1 vs PC2). Non si leggono come valori singoli ma come
mappa: la nuvola principale è la muratura coerente; punti che se ne staccano
sono anomalie. Tipicamente i reimpieghi migrano lungo **PC2** (forma) più che
lungo PC1 (taglia). Un grafico PC1–PC2 colorato per `reuse_score` o per
`cluster` è uno dei modi più efficaci di visualizzare la struttura.

### `dev_glob`, `dev_loc_rad`, `dev_loc_knn` — scarti angolari (in gradi, 0–90)

Misurano quanto l'orientamento di un pezzo devia, rispettivamente, dalla media
globale del paramento e dalla media dei vicini (raggio fisso / k-nearest).

| Valore | Lettura |
|---|---|
| 0° – 5° | posa allineata, regolare |
| 5° – 15° | lieve disallineamento, tollerabile in murature non rifinite |
| > 15° – 20° | pezzo nettamente fuori asse: anomalia di posa |

- **`dev_glob` alto ma `dev_loc` basso:** il pezzo è disallineato rispetto al
  paramento *nel suo complesso*, ma in accordo coi suoi vicini → probabilmente
  appartiene a una porzione di muratura con orientamento diverso (un corso
  inclinato, un settore ruotato), non a un'anomalia isolata.
- **`dev_loc` alto:** il pezzo è fuori asse rispetto a *chi gli sta intorno* →
  anomalia locale vera, indizio di reimpiego o rattoppo.

### `disp_loc_rad`, `disp_loc_knn` — dispersione circolare locale (0–1)

È `1 − R̄` calcolato sui vicini: misura quanto è *disordinato* l'intorno di
ogni pezzo. Vicino a 0 = intorno molto ordinato; vicino a 1 = intorno caotico.
Una **mappa** di questo campo evidenzia le zone di disordine costruttivo
(tamponature, rifacimenti) a prescindere dal singolo pezzo.

### `n_rad` — numero di vicini (raggio fisso)

Valore diagnostico di servizio. Dove `n_rad` è basso i componenti sono grandi e
radi; dove è alto sono piccoli e fitti. Un'area con `n_rad` anomalo rispetto
all'intorno può indicare un cambio di pezzatura (es. un rappezzo di mattoni
piccoli in una muratura di blocchi).

### `cluster` — etichetta di gruppo

Numero intero senza ordine intrinseco (0, 1, 2…): identifica i **gruppi di
paramento**. La lettura tipica:
- un cluster **grande e omogeneo** = la muratura coerente principale;
- cluster **piccoli o a CV alto** = potenziali gruppi di reimpiego o fasi
  diverse.

Incrocia sempre con i CV stampati nel log: il cluster con CV più alto su
lunghezza/`R_fill` è quasi sempre quello che raccoglie i pezzi eterogenei.

### `reuse_score` — indicatore sintetico (0–1)

Il campo di sintesi più immediato. Va letto **per ranghi**, non per soglia fissa:

| Fascia | Lettura |
|---|---|
| 0,0 – 0,5 | pezzi tipici della muratura coerente |
| 0,5 – 0,7 | leggermente atipici: da osservare |
| 0,7 – 1,0 | fortemente sospetti: convergenza di più indizi |

- **Esempio.** Un paramento sano avrà la maggior parte dei pezzi sotto 0,5 e
  una piccola coda sopra 0,8: quella coda è l'insieme dei candidati al riuso.
  Se invece i valori sono diffusamente alti, il paramento nel suo complesso è
  eterogeneo (riuso diffuso o approvvigionamento misto).

> Attenzione: `reuse_score` è **relativo al campione**. Anche in un paramento
> perfettamente omogeneo qualche pezzo avrà per forza il punteggio più alto
> (è un rango). Il valore va sempre accompagnato dalla lettura della
> distribuzione e dalla dimensione spaziale (LISA).

### `lisa_I`, `lisa_p`, `lisa_clust` — autocorrelazione spaziale

- **`lisa_I`**: indice locale di Moran. Positivo = il pezzo è circondato da
  valori simili al suo (cluster); negativo = circondato da valori opposti
  (outlier spaziale). Valori prossimi a 0 = nessuna struttura locale.
- **`lisa_p`**: p-value. Sotto 0,05 il raggruppamento locale è significativo.
- **`lisa_clust`**: la sintesi pratica. Lettura:

| Classe | Significato archeologico |
|---|---|
| **HH** | hotspot di reimpiego: pezzo sospetto tra pezzi sospetti → **zona di intervento** (tamponatura, restauro) |
| **HL** | pezzo sospetto isolato in muratura sana → **reimpiego sporadico** |
| **LL** | zona coerente, muratura "buona" |
| **LH** | pezzo regolare immerso in una zona disturbata (es. il bordo sano di una tamponatura) |
| **ns** | nessun pattern spaziale significativo |

- **Esempio di lettura combinata.** Un gruppo compatto di celle **HH** in un
  settore del paramento = quasi certamente una fase di rifacimento o una
  tamponatura. Pezzi **HL** sparsi qua e là = spolia reimpiegate
  occasionalmente nella muratura originale. La distinzione tra i due scenari è
  il cuore dell'interpretazione.

### Campi metrologici (`w_phase`, `w_resid`, `h_phase`, `h_resid`)

Presenti solo con metrologia attiva.

- **`w_phase` / `h_phase`** (0–1): posizione della misura entro il modulo.
  Valori prossimi a 0 (o a 1) = la misura è vicina a un multiplo intero del
  modulo (conforme); valori intorno a 0,5 = la misura cade "a metà" tra due
  multipli (non conforme a quel modulo).
- **`w_resid` / `h_resid`** (in metri): scarto con segno dal multiplo di modulo
  più vicino. Prossimo a 0 = pezzo modulare; grande in valore assoluto = pezzo
  fuori modulo → indizio di provenienza diversa.

- **Esempio.** Con modulo 0,297 m, un blocco lungo 0,59 m ha `w_resid` ≈
  0,59 − 2×0,297 = −0,004 m (a 4 mm da 2 moduli, conforme). Un blocco da 0,52 m
  ha `w_resid` ≈ 0,52 − 2×0,297 = −0,074 m: 7,4 cm fuori dal multiplo più
  vicino, fortemente sospetto di non appartenere alla produzione modulare.

### I risultati nel log dei Processing

Oltre ai campi, il log testuale riporta:
- la **varianza spiegata** da PC1/PC2;
- l'**orientamento medio globale** e la coerenza R̄ del paramento;
- i **coefficienti di variazione** globali e per cluster;
- il numero di **hotspot HH** significativi;
- per la metrologia: **R̄ e Rayleigh** per ciascuna dimensione, il **modulo
  ottimale** del quantogram e la sua **significatività Monte Carlo**, più
  eventuali **avvisi** della guardia di scala.

### Una regola pratica di sintesi

Nessun singolo campo "dimostra" un reimpiego. La lettura solida è **per
convergenza**: un pezzo è un candidato forte quando è anomalo su più fronti
indipendenti — forma (`R_fill` basso), dimensioni (`mahal` alto), posa
(`dev_loc` alto), e (per gli altri componenti) modulo (`*_resid` grande) — **e**
quando questa anomalia ha una **collocazione spaziale leggibile** (`lisa_clust`).
Lo script fornisce gli indizi; l'interpretazione resta archeologica.

---

## 9. Dipendenze e installazione

**Dipendenze Python** (di norma già presenti nel Python di QGIS):
`numpy`, `scipy`, `scikit-learn`.

**Installazione:** nella Toolbox dei Processing → icona Python →
*Aggiungi script alla raccolta* → seleziona il file `.py`. Lo script comparirà
nel gruppo **Analisi quantitative**.

**Avvertenza statistica:** su paramenti molto piccoli (poche decine di
componenti) i p-value (LISA e Rayleigh) vanno letti come indicativi, non come
soglie rigide: con pochi pezzi le distribuzioni di riferimento sono poco
popolate. Su campioni di qualche centinaio di componenti i test sono pienamente
affidabili.

---

*Documento di accompagnamento allo script `statistiche_avanzate_pattern_paramento_reimpiego.py`,
parte della suite MensioAnalysisTools.*
