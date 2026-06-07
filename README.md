# Mensio Analysis Tools

[![QGIS](https://img.shields.io/badge/QGIS-%3E%3D3.16-green)](https://qgis.org)
[![Python](https://img.shields.io/badge/Python-%3E%3D3.8-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-GPL--3.0-orange)]
[![Version](https://img.shields.io/badge/Version-2.0-brightgreen)](https://github.com/LoreForna/MensioAnalysisTools/releases)

**Suite di strumenti QGIS per l'analisi quantitativa di murature storiche**

Collezione di algoritmi di processing QGIS progettati per l'analisi dimensionale e statistica di componenti murari in contesti archeologici e architettonici, con particolare focus sulle tecniche edilizie antiche.

---

## ✨ Caratteristiche

- **Analisi automatizzata** di componenti murari con calcolo di statistiche dimensionali complete
- **Sistema modulare configurabile** per analisi metrologiche basate su diverse unità di misura storiche
- **Separazione intelligente** tra componenti interi e parziali (tagliati dall'area campione) per analisi accurate
- **Campo superficie opzionale**: adattamento automatico se presente o assente
- **Calcolo del poligono minimo orientato** (Minimum Oriented Bounding Box) per ogni elemento
- **Statistiche descrittive**: media, deviazione standard, range, distribuzioni
- **Statistiche avanzate**: individuazione di pattern di posa e di elementi di **reimpiego** tramite analisi multivariata e spaziale
- **Due modalità di analisi**: per campione o senza campione
- **Output multipli** organizzati: layer geometrici, tabelle statistiche, distribuzioni per range
- **Validazione robusta** dei dati in input con messaggi di errore dettagliati

---

## 🔄 Versioni Disponibili

La suite è disponibile in due versioni principali:

### Con Area Campione
**Modalità**: Analisi per campione  
**Requisiti**: Layer rilievo + Layer campioni  
**Ideale per**: Analisi comparative tra diverse aree campionate

**File**:
- `analisi_quantitativa_mattoni_v2_0.py`
- `analisi_quantitativa_componenti_a_secco_v2_0.py`
- `analisi_quantitativa_altri_componenti_v2_0.py`

### Senza Area Campione
**Modalità**: Analisi aggregate globali  
**Requisiti**: Solo layer rilievo  
**Ideale per**: Analisi rapide per murature non campionate

**File**:
- `analisi_quantitativa_mattoni_senza_campione_v2_0.py`
- `analisi_componenti_secco_altri_materiali_senza_campione_v2.0.py`

---

## 📋 Suite di Strumenti

### 1. Analisi Quantitativa Mattoni

Analisi specializzata per murature in laterizi di età romana.

#### Con Campione
**File**: `analisi_quantitativa_mattoni_v2_0.py`

**Caratteristiche**:
- Ottimizzato per opus latericium
- Intervalli di distribuzione configurabili (default, 4mm per larghezza e 2mm per altezza)
- Calcolo del rapporto di suoerficie mattoni/malta per campione
- Stima del numero di mattoni interi per campione
- Statistiche per ogni area campionata

#### Senza Campione
**File**: `analisi_quantitativa_mattoni_senza_campione_v2_0.py`

**Caratteristiche**:
- Nessun layer campioni richiesto
- Statistiche aggregate globali
- Campo `superficie` opzionale
- Output semplificati
- Tabella unica con statistiche: Componenti interi, Componenti parziali, Totale, Larghezza, Altezza, Area


---

### 2. Analisi Quantitativa Componenti a Secco / Altri Materiali

Analisi per componenti lapidei assemblati senza legante (blocchi, conci) e per
componenti eterogenei o materiali paericolari.

#### Con Campione
**File**:
- `analisi_quantitativa_componenti_a_secco_v2_0.py`
- `analisi_quantitativa_altri_componenti_v2_0.py`

**Caratteristiche**:
- Calcoli metrologici con modulo configurabile (default: piede romano 0.296m)
- Campi modulo solo per superficie='intera'
- Statistiche per campione
- Intervalli di distribuzione configurabili (default 1cm)
- Supporto per tipologie multiple di materiali e filtri avanzati

#### Senza Campione
**File**: `analisi_componenti_secco_altri_materiali_senza_campione_v2.0.py` 

**Caratteristiche**:
- Un **unico strumento** per componenti a secco e altri materiali
- Campi modulo per **TUTTI i componenti** (non solo per superficie='intera')
- Campo `superficie` opzionale
- Statistiche aggregate globali


---

## 🔬 Statistiche Avanzate: Pattern e Reimpiego

Strumento di **analisi statistica avanzata** dei componenti già quantificati finalizzato all'individuazione di **pattern** e di possibili elementi di **reimpiego**. Si 
concatena all'output `analisi_rilievo` (usa i campi `fid`, `area_componente`, `width_bbox`, `height_bbox`, `angle_bbox`).

**File**: `statistiche_avanzate_pattern_paramento_reimpiego.py`  

### Due modalità d'uso

- **Mattoni** (laterizi di ritaglio): sola analisi del paramento. L'analisi
  metrologica **non** va attivata (i ritagli non seguono un modulo di riferimento).
- **Componenti a secco / altri materiali** (blocchi, conci): analisi del
  paramento **più** analisi metrologica opzionale.

### Mapping dei campi in ingresso

| Parametro | Campo MensioAnalysisTools | Significato |
|---|---|---|
| Campo lunghezza | `width_bbox` | lato maggiore del bounding box |
| Campo spessore | `height_bbox` | lato minore del bounding box |
| Campo area | `area_componente` | area reale del poligono (non del bbox) |
| Campo angolo | `angle_bbox` | orientamento di posa, assiale 0–180° |
| Campo id | `fid` | identificativo univoco |

### Dipendenze aggiuntive

Richiede `numpy`, `scipy`, `scikit-learn` (di norma già presenti nel Python di QGIS).

---

## 🛠️ Installazione

### Metodo 1: Copia diretta (consigliato)

1. Scarica i file `.py` dalla repository
2. Apri QGIS e vai in:
   ```
   Settings → User Profiles → Open Active Profile Folder
   ```
3. Naviga nella cartella:
   ```
   processing/scripts/
   ```
4. Copia gli script scaricati nella cartella
5. Riavvia QGIS o ricarica gli script dal Processing Toolbox

### Metodo 2: Da Processing Toolbox

1. Apri il **Processing Toolbox** in QGIS
2. Clicca sull'icona Python in alto → "Add Script to Toolbox..."
3. Seleziona il file `.py` desiderato
4. Lo script apparirà nel gruppo "Analisi quantitative"

---

## 📧 Requisiti

### Software
- **QGIS**: versione ≥ 3.16 (LTR o superiore)
- **Python**: versione ≥ 3.8
- **Plugin**: DataPlotly (opzionale)
- **Librerie Python**: `numpy`, `scipy`, `scikit-learn` (solo per le statistiche avanzate; di norma già incluse nel Python di QGIS)

### Dati
- Sistema di riferimento **cartografico o locale** (NO geografico WGS84)
- Layer vettoriali poligonali con struttura dati specifica (vedi sotto)

### Sistema Operativo
- Windows, macOS, Linux (qualsiasi OS supportato da QGIS)

---

## 📊 Struttura Dati

### Versione 2.0 - Con Campione

Richiede due layer poligonali:

#### Layer "campioni"
Poligoni delle aree campionate (generalmente 1 m²)

| Campo | Tipo | Descrizione | Obbligatorio |
|-------|------|-------------|--------------|
| `fid` | Integer | ID univoco | ✗ |
| `campione` | String | Identificativo campione | ✓ |
| `sito` | String | Nome sito archeologico | ✗ |
| `ambiente` | String | Identificativo ambiente | ✗ |
| `usm` | String | Unità Stratigrafica Muraria | ✗ |
| `area_campione` | Double | Area del campione (m²) | ✗ |

#### Layer "rilievo"
Poligoni dei singoli componenti murari

| Campo | Tipo | Descrizione | Obbligatorio |
|-------|------|-------------|--------------|
| `fid` | Integer | ID univoco | ✗ |
| `tipo` | String | Tipologia materiale | ✗ |
| `superficie` | String | "intera" o "parziale" | ✗ |
| `area_componente` | Double | Area del componente (m²) | ✗ |
| `num_componente` | Integer | Numero progressivo | ✗ |
| `usm` | String | Unità Stratigrafica Muraria | ✗ |

---

### Versione 2.0 - Senza Campione

Richiede **solo** un layer:

#### Layer "rilievo"
Poligoni dei singoli componenti murari

| Campo | Tipo | Descrizione | Obbligatorio | Note v2.0 |
|-------|------|-------------|--------------|-----------|
| `fid` | Integer | ID univoco | ✗ | |
| `tipo` | String | Tipologia materiale | ✗ | |
| `superficie` | String | "intera" o "parziale" | ✗ | Se assente, tutti i componenti sono usati per statistiche |
| `area_componente` | Double | Area del componente (m²) | ✗ | |
| `num_componente` | Integer | Numero progressivo | ✗ | |
| `usm` | String | Unità Stratigrafica Muraria | ✗ | 

**⚠️ Comportamento campo `superficie` (v2.0)**:
- **Se PRESENTE**: Statistiche calcolate solo su componenti "interi"
- **Se ASSENTE o NULL**: Statistiche calcolate su **TUTTI** i componenti

---

## 🚀 Utilizzo

### Quale Versione Usare?

**Con Campione se:
- ✓ Hai definito aree campione specifiche
- ✓ Vuoi statistiche separate per ogni campione
- ✓ Devi confrontare diverse zone della muratura
- ✓ Segui metodologia con campionamento 1m²

**Senza Campione se:
- ✓ Vuoi analisi rapide senza campionamento
- ✓ Hai rilievo completo senza divisione in campioni
- ✓ Hai bisogno solo di statistiche globali
- ✓ Il campo "superficie" non è compilato o manca

---

### Workflow Con Campione

1. **Preparazione dati**
   - Crea layer "campioni" e "rilievo"
   - Verifica sistema di riferimento cartografico
   - Assicurati che tutti i campi obbligatori siano presenti

2. **Esecuzione analisi**
   - Apri Processing Toolbox
   - Cerca "Analisi quantitative"
   - Seleziona lo strumento v2.0 appropriato
   - Configura parametri

3. **Parametri**:
   - `Layer rilievo`: layer componenti
   - `Layer campioni`: layer aree campionate
   - `Tipo di materiale`: filtro opzionale
   - `Includi non classificati`: include elementi con tipo=NULL
   - `Step range larghezza/altezza`: intervalli per distribuzioni
   - `Valore del modulo`: (solo Componenti a secco/Altri)

---

### Workflow Senza Campione

1. **Preparazione dati**
   - Crea **solo** layer "rilievo"
   - Verifica sistema di riferimento cartografico
   - Campo `superficie` è **opzionale**

2. **Esecuzione analisi**
   - Apri Processing Toolbox
   - Cerca "Analisi quantitative"
   - Seleziona lo strumento "senza campione" appropriato
   - Configura parametri

3. **Parametri**:
   - `Layer rilievo`: layer componenti
   - `Tipo di materiale`: filtro opzionale
   - `Includi non classificati`: include elementi con tipo=NULL
   - `Step range larghezza/altezza`: intervalli per distribuzioni
   - `Valore del modulo`: (solo Componenti a secco/Altri)

---

## 📈 Output

### Output Con Campione (6 file)

1. **Min Oriented Bbox** - Rettangoli orientati minimi
2. **Analisi Rilievo** - Layer rilievo arricchito
3. **Analisi Campioni (Tabella)** - Statistiche per campione
4. **Analisi Campioni (Layer)** - Campioni con statistiche
5. **Conteggio Range Larghezza** - Distribuzioni per campione
6. **Conteggio Range Altezza** - Distribuzioni per campione

---

### Output Senza Campione (5 file)

1. **Min Oriented Bbox** - Rettangoli orientati minimi
2. **Analisi Rilievo** - Layer rilievo arricchito
3. **Statistiche Aggregate** - Tabella unica globale
   - **6 righe**:
     1. Componenti interi (count)
     2. Componenti parziali (count)
     3. Totale (count)
     4. Larghezza (count, min, max, range, mean, stddev)
     5. Altezza (count, min, max, range, mean, stddev)
     6. Area (count, min, max, range, mean, stddev)
4. **Conteggio Range Larghezza** - Distribuzione globale
5. **Conteggio Range Altezza** - Distribuzione globale

---

## 📬 Metodologia

### Pipeline di Elaborazione Con Campione

```
INPUT
  ├─ Layer campioni (poligoni aree)
  └─ Layer rilievo (poligoni componenti)
     │
     ▼
VALIDAZIONE
  ├─ Verifica campi obbligatori
  ├─ Controllo geometrie valide
  └─ Validazione sistema riferimento
     │
     ▼
SPATIAL JOIN
  └─ Associazione componenti → campioni
     │
     ▼
GEOMETRIC ANALYSIS
  ├─ Calcolo Minimum Oriented Bounding Box
  ├─ Estrazione dimensioni (width/height)
  └─ Calcolo metriche geometriche
     │
     ▼
FILTERING
  ├─ Separazione interi/parziali
  ├─ Filtro per tipologia materiale
  └─ Gestione valori NULL
     │
     ▼
STATISTICS PER CAMPIONE
  ├─ Aggregazione per campione
  ├─ Calcolo statistiche descrittive
  └─ Creazione distribuzioni per range
     │
     ▼
OUTPUT (6 file)
```

---

### Pipeline di Elaborazione Senza Campione 

```
INPUT
  └─ Layer rilievo (poligoni componenti)
     │
     ▼
VALIDAZIONE
  ├─ Verifica campi obbligatori
  ├─ Campo 'superficie' opzionale
  └─ Validazione sistema riferimento
     │
     ▼
GEOMETRIC ANALYSIS
  ├─ Calcolo Minimum Oriented Bounding Box
  ├─ Aggiunta campi usm e num_componente al bbox
  └─ Join bbox con rilievo
     │
     ▼
FILTERING (se campo superficie presente)
  ├─ Separazione interi/parziali
  └─ Scelta layer per statistiche
     │
     ▼
STATISTICS GLOBALI
  ├─ Calcolo statistiche aggregate
  ├─ Tabella unica (6 righe)
  └─ Distribuzioni globali
     │
     ▼
METROLOGICAL ANALYSIS (a secco/altri)
  └─ Campi modulo per TUTTI i componenti
     │
     ▼
OUTPUT (5 file)
```

---

## 💡 Esempio

**Nota**: I dati di esempio per testare gli script si trovano nella cartella **Data/** del repository:
- `TEST_Analisi_campioni.gpkg` - GeoPackage con layer di test (mattoni) già configurati

### Esempio - Analisi muratura con campione

```
1. Carica il geopackage "TEST_Analisi_campioni.gpkg"
2. Usa layer "campioni" e "rilievo"
3. Esegui "Analisi Quantitativa Mattoni" v2.0
   - Layer rilievo: "rilievo"
   - Layer campioni: "campioni"
   - Tipo materiale: "laterizio"
   - Step larghezza: 0.004 m
   - Step altezza: 0.002 m
4. Ottieni 6 output con statistiche per campione
```

### Esempio - Analisi rapida senza campioni 

```
1. Carica solo il layer "rilievo"
2. Esegui "Mattoni senza campione" v2.0
   - Layer rilievo: "rilievo"
   - Tipo materiale: "laterizio"
   - Step larghezza: 0.004 m
   - Step altezza: 0.002 m
3. Ottieni 5 output con statistiche globali
4. Verifica tabella "statistiche_aggregate" (6 righe)
```

---

## 📚 Riferimenti Metodologici

Gli script si basano sulla metodologia proposta da:

**Medri, M.** et al. - *"Metodi di analisi quantitativa delle murature romane in opera laterizia"*
[PDF](https://pdfs.semanticscholar.org/373e/c1a3bf317c3216612f4c63d9802da5d67ce0.pdf)

---

## 🎯 Best Practices

### Acquisizione dati
- ✓ Usa un sistema di riferimento metrico
- ✓ Digitalizza accuratamente i contorni dei componenti (scala 1:1)
- ✓ Mantieni la topologia pulita (no overlap, no gap, solo geometrie valide)
- ✓ Compila correttamente il campo `superficie` (intera/parziale) se necessario
- ✓ Per murature miste classifica i componenti nel campo `tipo`
- ✓ Compila il campo `usm` 

### Configurazione parametri
- ✓ Scegli step range appropriati al materiale
- ✓ Per analisi metrologiche, ricerca il valore del modulo di riferimento storicamente documentato
- ✓ Filtra i componenti per analisi separate su materiali diversi
- ✓ Documenta sempre i parametri utilizzati nei metadati

---

## 📖 Citazione

Fornaciari, L. (2026). MensioAnalysisTools: Suite di strumenti QGIS per l'analisi quantitativa delle murature storiche (Versione 2.0) [Software]. 
> GitHub. https://github.com/LoreForna/MensioAnalysisTools

---

## 📄 Licenza

Questo progetto è rilasciato sotto licenza **GNU GPLv3**.

---
