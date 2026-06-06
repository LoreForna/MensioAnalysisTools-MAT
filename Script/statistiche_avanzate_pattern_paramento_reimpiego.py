# -*- coding: utf-8 -*-
"""
***************************************************************************
    Statistiche avanzate pattern paramento e reimpiego
    ---------------------------------------------------
    Analisi statistica di un paramento per l'individuazione di pattern di
    posa e di elementi di probabile reimpiego, con analisi metrologica
    modulare OPZIONALE.

    DUE MODALITA' D'USO:
      * MATTONI (laterizi): si usa la sola analisi del paramento. Lasciare
        DISATTIVATA l'analisi modulare (flag 'Esegui analisi metrologica').
      * COMPONENTI A SECCO / ALTRI COMPONENTI (es. blocchi, conci, elementi
        lapidei): attivare anche l'analisi metrologica modulare, che verifica
        un modulo dato (es. piede romano) e cerca il modulo ottimale (cosine
        quantogram di Kendall). Lo scarto modulare diventa anche un indicatore
        aggiuntivo, che confluisce nel reuse_score.

    PERCHE' LA METROLOGIA NON VA USATA SUI MATTONI:
    I mattoni romani da paramento sono RITAGLI (triangoli/frammenti ottenuti
    spezzando bessali o sesquipedali in cantiere): la loro lunghezza dipende
    dal taglio, NON da un modulo teorico. Applicare l'analisi modulare a un
    laterizio produrrebbe picchi spuri del quantogram e segnalerebbe come
    "fuori modulo" pezzi che un modulo di lunghezza non lo hanno mai avuto.
    Per i COMPONENTI A SECCO / ALTRI COMPONENTI, invece, il modulo teorico e'
    reale e atteso SIA sulla lunghezza SIA sull'altezza: per questo l'analisi
    e' applicata simmetricamente alle due dimensioni, e uno scarto dal modulo
    e' un indizio legittimo di provenienza diversa (reimpiego).

    INTEGRAZIONE CON MensioAnalysisTools:
    Si concatena all'output di 'analisi_quantitativa_mattoni' o di
    'analisi_quantitativa_altri_componenti'. Mapping verificato:
        lunghezza <- width_bbox
        spessore  <- height_bbox
        area      <- area_componente   (area reale del poligono)
        angolo    <- angle_bbox        (assiale 0-180, convenzione QGIS
                                        orientedMinimumBoundingBox, verificata
                                        sul sorgente: vincolata a 0-180 gradi)
        id        <- fid

    Variabili di input (campi del layer poligonale):
        - lunghezza   (lineare)
        - spessore    (lineare)
        - area        (reale, dal poligono)
        - angolo      (orientamento di posa, ASSIALE 0-180 gradi)
        - id          (identificativo univoco)

    Output: copia del layer con campi aggiunti:
        - R_fill        area / (lunghezza * spessore)   [fattore di riempimento]
        - mahal         distanza di Mahalanobis sulle variabili lineari std
        - PC1, PC2      punteggi delle prime due componenti principali
        - dev_glob      scarto angolare assiale vs media circolare globale [0-90]
        - dev_loc_rad   scarto angolare vs media circolare locale - RAGGIO FISSO
        - disp_loc_rad  dispersione circolare locale (1 - R_bar) - RAGGIO FISSO
        - n_rad         n. vicini usati nel criterio raggio fisso
        - dev_loc_knn   scarto angolare vs media circolare locale - K-NEAREST
        - disp_loc_knn  dispersione circolare locale (1 - R_bar) - K-NEAREST
        - cluster       etichetta di cluster (clustering gerarchico)
        - reuse_score   indicatore sintetico di reimpiego [0-1]
        - lisa_I        Local Moran's I del reuse_score
        - lisa_p        p-value per permutazione del LISA
        - lisa_clust    classe LISA: HH / LL / HL / LH / ns (non signif.)

    Campi aggiunti SOLO se l'analisi metrologica modulare e' attiva:
        - w_phase       fase modulare della larghezza [0-1)
        - w_resid       scarto della larghezza dal multiplo di modulo piu' vicino
        - h_phase       fase modulare dell'altezza/spessore [0-1)
        - h_resid       scarto dell'altezza dal multiplo di modulo piu' vicino
      In questo caso lo scarto modulare normalizzato confluisce come QUARTO
      indizio nel reuse_score (oltre a riempimento, Mahalanobis, orientamento).

    Inoltre nel log vengono stampati i COEFFICIENTI DI VARIAZIONE (CV = sigma/mu)
    globali e per cluster di lunghezza, spessore, area e fattore di riempimento:
    un CV elevato indica scarsa standardizzazione (approvvigionamento eterogeneo,
    possibile reimpiego diffuso).

    NOTE METODOLOGICHE:
      * L'orientamento e' ASSIALE: ogni operazione circolare usa il
        raddoppio dell'angolo (2*theta), media vettoriale, poi dimezzamento.
        Gli scarti angolari risultanti stanno quindi in [0, 90] gradi.
      * Le variabili lineari sono standardizzate (z-score) prima di PCA,
        Mahalanobis e clustering. L'angolo NON entra mai grezzo in queste
        analisi: vi rientra solo come scarto angolare locale (lineare).
      * Il vicinato e' calcolato sui centroidi dei poligoni.
***************************************************************************
"""

import os
import math
import numpy as np

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterFeatureSink,
    QgsField,
    QgsFields,
    QgsFeature,
    QgsFeatureSink,
    QgsWkbTypes,
)


class MasonryPatternAnalysis(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    FIELD_ID = 'FIELD_ID'
    FIELD_LEN = 'FIELD_LEN'
    FIELD_THK = 'FIELD_THK'
    FIELD_AREA = 'FIELD_AREA'
    FIELD_ANG = 'FIELD_ANG'
    RADIUS = 'RADIUS'
    KNN = 'KNN'
    NCLUSTERS = 'NCLUSTERS'
    PERMUTATIONS = 'PERMUTATIONS'
    DO_METRO = 'DO_METRO'
    MODULE = 'MODULE'
    Q_MIN = 'Q_MIN'
    Q_MAX = 'Q_MAX'
    Q_STEP = 'Q_STEP'
    MC_RUNS = 'MC_RUNS'
    CSV_OUT = 'CSV_OUT'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return MasonryPatternAnalysis()

    def name(self):
        return 'statistiche_avanzate_pattern_paramento_reimpiego'

    def displayName(self):
        return 'Statistiche avanzate pattern paramento e reimpiego'

    def group(self):
        return 'Analisi quantitative'

    def groupId(self):
        return 'analisi'

    def shortHelpString(self):
        return self.tr(
            "Analisi statistica di un paramento.\n\n"
            "PER I MATTONI: lascia disattivata l'analisi metrologica. Calcola "
            "fattore di riempimento, statistica circolare assiale dell'orientamento "
            "(raggio fisso + k-nearest), Mahalanobis, PCA, clustering, CV, e LISA "
            "(Local Moran's I) per individuare hotspot di reimpiego.\n\n"
            "PER I COMPONENTI A SECCO / ALTRI COMPONENTI (es. blocchi, conci, "
            "elementi lapidei): attiva anche l'analisi metrologica modulare. Verifica "
            "un modulo dato (R_bar + Rayleigh) e cerca il modulo ottimale (cosine "
            "quantogram di Kendall, validato Monte Carlo) su lunghezza e altezza, "
            "trattate simmetricamente: per questi componenti il modulo e' atteso su "
            "entrambe. Lo scarto modulare confluisce nel reuse_score. NON usare sui "
            "mattoni: sono ritagli senza modulo di lunghezza.\n\n"
            "L'orientamento e il resto modulare sono trattati come variabili circolari."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr('Layer poligonale dei componenti'),
            [QgsProcessing.TypeVectorPolygon]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD_ID, self.tr('Campo identificativo univoco'),
            parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD_LEN, self.tr('Campo lunghezza'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD_THK, self.tr('Campo spessore'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD_AREA, self.tr('Campo area (reale, dal poligono)'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterField(
            self.FIELD_ANG, self.tr('Campo angolo di posa (assiale, 0-180)'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))
        self.addParameter(QgsProcessingParameterNumber(
            self.RADIUS, self.tr('Raggio per vicinato a raggio fisso (unita\' mappa; 0 = auto = 3 x lunghezza media)'),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.KNN, self.tr('Numero di vicini k (k-nearest)'),
            type=QgsProcessingParameterNumber.Integer, defaultValue=8, minValue=1))
        self.addParameter(QgsProcessingParameterNumber(
            self.NCLUSTERS, self.tr('Numero di cluster (0 = stima automatica)'),
            type=QgsProcessingParameterNumber.Integer, defaultValue=0, minValue=0))
        self.addParameter(QgsProcessingParameterNumber(
            self.PERMUTATIONS, self.tr('Permutazioni per significativita\' LISA (0 = nessun test)'),
            type=QgsProcessingParameterNumber.Integer, defaultValue=999, minValue=0))
        # --- analisi metrologica modulare (opzionale: per componenti a secco, non mattoni) ---
        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_METRO,
            self.tr('Esegui analisi metrologica modulare (per componenti a secco/altri componenti, es. blocchi)'),
            defaultValue=False))
        self.addParameter(QgsProcessingParameterNumber(
            self.MODULE, self.tr('Modulo da verificare (m) - default piede romano'),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.297, minValue=0.0001))
        self.addParameter(QgsProcessingParameterNumber(
            self.Q_MIN, self.tr('Ricerca modulo: minimo (m)'),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.18, minValue=0.0001))
        self.addParameter(QgsProcessingParameterNumber(
            self.Q_MAX, self.tr('Ricerca modulo: massimo (m)'),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.60, minValue=0.0002))
        self.addParameter(QgsProcessingParameterNumber(
            self.Q_STEP, self.tr('Ricerca modulo: passo (m)'),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.002, minValue=0.0001))
        self.addParameter(QgsProcessingParameterNumber(
            self.MC_RUNS, self.tr('Permutazioni Monte Carlo per la soglia del quantogram (0 = nessuna)'),
            type=QgsProcessingParameterNumber.Integer, defaultValue=300, minValue=0))
        self.addParameter(QgsProcessingParameterFileDestination(
            self.CSV_OUT, self.tr('Quantogram in CSV (prodotto se la metrologia e\' attiva)'),
            'CSV files (*.csv)'))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, self.tr('Paramento analizzato')))

    # ---------- statistica circolare assiale ----------
    @staticmethod
    def _axial_mean(angles_deg):
        """Media circolare di angoli ASSIALI (0-180). Ritorna (media_deg, R_bar)."""
        a = np.deg2rad(np.asarray(angles_deg, dtype=float)) * 2.0  # raddoppio
        C = np.cos(a).mean()
        S = np.sin(a).mean()
        R_bar = math.hypot(C, S)
        mean2 = math.atan2(S, C)            # in [-pi, pi] sul cerchio raddoppiato
        mean_deg = (math.degrees(mean2) / 2.0) % 180.0  # dimezzamento
        # blindatura caso-limite: un risultato di 180.0 e' equivalente a 0.0
        # come orientamento assiale; lo normalizziamo per coerenza del campo.
        if abs(mean_deg - 180.0) < 1e-9:
            mean_deg = 0.0
        return mean_deg, R_bar

    @staticmethod
    def _axial_diff(a_deg, b_deg):
        """Differenza angolare assiale tra due orientamenti, risultato in [0, 90]."""
        d = abs((a_deg - b_deg) % 180.0)
        return min(d, 180.0 - d)

    @staticmethod
    def _cv(x):
        """Coefficiente di variazione campionario (sigma/mu, ddof=1).
        Ritorna NaN se mu~0 o se i dati validi sono meno di 2 (la deviazione
        standard campionaria non e' definita per n<2)."""
        x = np.asarray(x, dtype=float)
        x = x[~np.isnan(x)]
        if x.size < 2:
            return float('nan')
        mu = x.mean()
        if abs(mu) < 1e-12:
            return float('nan')
        return float(x.std(ddof=1) / mu)

    # ---------- metrologia modulare (statistica circolare sul resto) ----------
    @staticmethod
    def _phase_stats(values, modulus):
        """R_bar e media circolare della fase (resto/modulo). Fase in [0,1)."""
        if modulus <= 0:
            return float('nan'), float('nan')
        v = np.asarray(values, dtype=float)
        v = v[~np.isnan(v)]
        if v.size == 0:
            return float('nan'), float('nan')
        phase = 2.0 * np.pi * ((v % modulus) / modulus)
        C = np.cos(phase).mean()
        S = np.sin(phase).mean()
        R = math.hypot(C, S)
        mean_phase = (math.atan2(S, C) / (2.0 * np.pi)) % 1.0
        return R, mean_phase

    @staticmethod
    def _rayleigh_p(R, n):
        """p-value del test di Rayleigh (non-uniformita' circolare), Zar 1999."""
        if n <= 1 or np.isnan(R):
            return float('nan')
        Z = n * R * R
        p = math.exp(-Z) * (
            1.0 + (2.0 * Z - Z * Z) / (4.0 * n)
            - (24.0 * Z - 132.0 * Z ** 2 + 76.0 * Z ** 3 - 9.0 * Z ** 4)
            / (288.0 * n * n))
        return max(0.0, min(1.0, p))

    @staticmethod
    def _cosine_quantogram(values, q):
        """Phi(q) di Kendall: scarto dal multiplo PIU' VICINO (non premia i sottomultipli)."""
        v = np.asarray(values, dtype=float)
        v = v[~np.isnan(v)]
        if v.size == 0 or q <= 0:
            return float('nan')
        eps = v - q * np.round(v / q)
        return math.sqrt(2.0 / v.size) * np.sum(np.cos(2.0 * np.pi * eps / q))

    def _quantogram(self, values, q_min, q_max, step):
        qs = np.arange(q_min, q_max + step / 2.0, step)
        phi = np.array([self._cosine_quantogram(values, q) for q in qs])
        return qs, phi

    def _run_metrology(self, name, vals, module, q_min, q_max, q_step,
                       mc_runs, feedback):
        """Verifica modulo + ricerca quantogram per una dimensione. Log + dict."""
        n = len(vals)
        feedback.pushInfo("\n===== METROLOGIA - %s (n=%d) =====" % (name, n))
        # Guardia di scala: se quasi tutte le misure sono < 1 modulo, la
        # dimensione NON e' informativa per questo modulo (il resto e' quasi
        # sempre la misura stessa, producendo un R_bar alto ma spurio).
        vv = np.asarray(vals, dtype=float)
        vv = vv[~np.isnan(vv)]
        frac_small = float(np.mean(vv < 1.0 * module)) if vv.size else 1.0
        informative = frac_small < 0.5
        if not informative:
            feedback.pushWarning(
                "    %s: il %.0f%% delle misure e' inferiore a 1 modulo (%.3f m): "
                "dimensione poco informativa per il modulo %.4f m, l'aderenza R_bar "
                "qui e' inaffidabile e viene esclusa dal giudizio di modularita'." % (
                    name, frac_small * 100.0, 1.0 * module, module))
        R, mean_phase = self._phase_stats(vals, module)
        p_ray = self._rayleigh_p(R, n)
        feedback.pushInfo("(A) Verifica modulo %.4f m: R_bar=%.3f  fase_media=%.3f  "
                          "Rayleigh p=%.3e %s" % (
                              module, R, mean_phase, p_ray,
                              "(modularita' significativa)" if p_ray < 0.05
                              else "(non significativa)"))
        qs, phi = self._quantogram(vals, q_min, q_max, q_step)
        i_peak = int(np.nanargmax(phi))
        q_best, phi_best = qs[i_peak], phi[i_peak]
        feedback.pushInfo("(B) Modulo ottimale = %.4f m (Phi=%.2f) nell'intervallo "
                          "[%.3f-%.3f]" % (q_best, phi_best, q_min, q_max))
        signif = "n/d"
        if mc_runs and mc_runs > 0 and n > 1:
            rng = np.random.default_rng(42)
            lo, hi = float(np.nanmin(vals)), float(np.nanmax(vals))
            # La distribuzione nulla DEVE essere costruita sulla stessa griglia
            # di candidati (q_step) usata per il picco osservato: una griglia piu'
            # rada darebbe massimi sistematicamente piu' bassi (meno candidati =
            # meno occasioni di allineamento spurio), rendendo il test
            # ANTICONSERVATIVO (sovrastima della significativita'). Si usa quindi
            # q_step pieno anche nel Monte Carlo.
            peaks = np.empty(mc_runs)
            for r in range(mc_runs):
                rv = rng.uniform(lo, hi, n)
                _, pn = self._quantogram(rv, q_min, q_max, q_step)
                peaks[r] = np.nanmax(pn)
            s95 = float(np.percentile(peaks, 95))
            s99 = float(np.percentile(peaks, 99))
            if phi_best > s99:
                signif = "p < 0.01"
            elif phi_best > s95:
                signif = "p < 0.05"
            else:
                signif = "non significativo (entro il rumore)"
            feedback.pushInfo("    Monte Carlo: 95%%=%.2f 99%%=%.2f -> picco %s" % (
                s95, s99, signif))
        rel = abs(q_best - module) / module * 100.0
        feedback.pushInfo("    Scostamento modulo ottimale vs verificato: %.1f%%" % rel)
        return {'name': name, 'R': R, 'p_ray': p_ray, 'q_best': q_best,
                'phi': phi, 'qs': qs, 'informative': informative}

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        f_id = self.parameterAsString(parameters, self.FIELD_ID, context)
        f_len = self.parameterAsString(parameters, self.FIELD_LEN, context)
        f_thk = self.parameterAsString(parameters, self.FIELD_THK, context)
        f_area = self.parameterAsString(parameters, self.FIELD_AREA, context)
        f_ang = self.parameterAsString(parameters, self.FIELD_ANG, context)
        radius = self.parameterAsDouble(parameters, self.RADIUS, context)
        knn = self.parameterAsInt(parameters, self.KNN, context)
        nclusters = self.parameterAsInt(parameters, self.NCLUSTERS, context)
        permutations = self.parameterAsInt(parameters, self.PERMUTATIONS, context)
        do_metro = self.parameterAsBool(parameters, self.DO_METRO, context)
        module = self.parameterAsDouble(parameters, self.MODULE, context)
        q_min = self.parameterAsDouble(parameters, self.Q_MIN, context)
        q_max = self.parameterAsDouble(parameters, self.Q_MAX, context)
        q_step = self.parameterAsDouble(parameters, self.Q_STEP, context)
        mc_runs = self.parameterAsInt(parameters, self.MC_RUNS, context)

        # --- dipendenze scientifiche ---
        try:
            from sklearn.preprocessing import StandardScaler
            from sklearn.decomposition import PCA
            from sklearn.cluster import AgglomerativeClustering
            from scipy.spatial import cKDTree
            from scipy.cluster.hierarchy import linkage, fcluster
        except ImportError as e:
            raise Exception(
                "Librerie mancanti nell'ambiente QGIS (%s). "
                "Installa scikit-learn e scipy nel Python di QGIS." % str(e))

        # --- lettura dati ---
        feats = list(source.getFeatures())
        n = len(feats)
        if n < 3:
            raise Exception("Servono almeno 3 mattoni per l'analisi.")

        ids, L, T, A, ANG, XY = [], [], [], [], [], []
        for ft in feats:
            ids.append(ft[f_id])
            L.append(float(ft[f_len]))
            T.append(float(ft[f_thk]))
            A.append(float(ft[f_area]))
            ANG.append(float(ft[f_ang]) % 180.0)
            c = ft.geometry().centroid().asPoint()
            XY.append((c.x(), c.y()))

        L = np.array(L); T = np.array(T); A = np.array(A)
        ANG = np.array(ANG); XY = np.array(XY)

        # --- fattore di riempimento ---
        denom = L * T
        R_fill = np.where(denom > 0, A / denom, np.nan)

        # --- variabili lineari standardizzate (len, thk, area, R_fill) ---
        lin = np.column_stack([L, T, A, R_fill])
        # sostituisci eventuali NaN di R_fill con la mediana per non rompere PCA/scaler
        med = np.nanmedian(lin, axis=0)
        inds = np.where(np.isnan(lin))
        lin[inds] = np.take(med, inds[1])
        Z = StandardScaler().fit_transform(lin)

        # --- PCA ---
        pca = PCA(n_components=min(2, Z.shape[1]))
        pcs = pca.fit_transform(Z)
        PC1 = pcs[:, 0]
        PC2 = pcs[:, 1] if pcs.shape[1] > 1 else np.zeros(n)
        feedback.pushInfo("Varianza spiegata PC1/PC2: %s" %
                          np.round(pca.explained_variance_ratio_, 3))

        # --- distanza di Mahalanobis sulle variabili lineari std ---
        cov = np.cov(Z, rowvar=False)
        try:
            inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            inv = np.linalg.pinv(cov)
        mu = Z.mean(axis=0)
        diff = Z - mu
        mahal = np.sqrt(np.einsum('ij,jk,ik->i', diff, inv, diff))

        # --- orientamento: media globale + scarto globale ---
        glob_mean, glob_R = self._axial_mean(ANG)
        feedback.pushInfo("Orientamento medio globale: %.2f deg | coerenza R_bar=%.3f"
                          % (glob_mean, glob_R))
        dev_glob = np.array([self._axial_diff(a, glob_mean) for a in ANG])

        # --- vicinato spaziale sui centroidi ---
        tree = cKDTree(XY)

        if radius <= 0:
            radius = 3.0 * float(np.mean(L))
            feedback.pushInfo("Raggio automatico: %.4f (3xlunghezza media)" % radius)

        dev_loc_rad = np.full(n, np.nan)
        disp_loc_rad = np.full(n, np.nan)
        n_rad = np.zeros(n, dtype=int)
        dev_loc_knn = np.full(n, np.nan)
        disp_loc_knn = np.full(n, np.nan)
        # liste di vicini k-nearest: calcolate UNA sola volta qui e riusate dal
        # LISA, per evitare di ricalcolare la query (e il rischio che le due
        # liste divergano).
        neigh = [[] for _ in range(n)]

        k_query = min(knn + 1, n)  # +1 perche' il primo vicino e' il punto stesso

        for i in range(n):
            if feedback.isCanceled():
                break
            # --- raggio fisso ---
            idx_r = tree.query_ball_point(XY[i], radius)
            idx_r = [j for j in idx_r if j != i]
            n_rad[i] = len(idx_r)
            if idx_r:
                lm, lR = self._axial_mean(ANG[idx_r])
                dev_loc_rad[i] = self._axial_diff(ANG[i], lm)
                disp_loc_rad[i] = 1.0 - lR
            # --- k-nearest ---
            dists, idx_k = tree.query(XY[i], k=k_query)
            idx_k = np.atleast_1d(idx_k)
            idx_k = [j for j in idx_k if j != i][:knn]
            neigh[i] = idx_k  # salvato per il LISA
            if idx_k:
                lm, lR = self._axial_mean(ANG[idx_k])
                dev_loc_knn[i] = self._axial_diff(ANG[i], lm)
                disp_loc_knn[i] = 1.0 - lR
            feedback.setProgress(int(70.0 * i / n))

        # --- clustering: variabili lineari std + scarto angolare locale (knn) ---
        dev_for_clust = np.nan_to_num(dev_loc_knn, nan=np.nanmean(dev_loc_knn))
        dev_z = StandardScaler().fit_transform(dev_for_clust.reshape(-1, 1))
        feat_clust = np.column_stack([Z, dev_z])

        if nclusters and nclusters >= 2:
            model = AgglomerativeClustering(n_clusters=nclusters)
            labels = model.fit_predict(feat_clust)
        else:
            # stima automatica: taglio del dendrogramma su distanza di Ward
            Zlink = linkage(feat_clust, method='ward')
            # soglia euristica: 0.7 * altezza massima di fusione
            thr = 0.7 * Zlink[:, 2].max()
            labels = fcluster(Zlink, t=thr, criterion='distance') - 1
            feedback.pushInfo("Cluster stimati automaticamente: %d" %
                              len(np.unique(labels)))

        # --- indicatore sintetico di reimpiego ---
        # convergenza di indizi: bassa R_fill, alto Mahalanobis, alto scarto
        # angolare locale. Ogni componente normalizzata a percentile [0-1].
        def _rank01(x):
            x = np.asarray(x, dtype=float)
            order = np.argsort(np.argsort(x))
            return order / (len(x) - 1) if len(x) > 1 else np.zeros_like(x)

        low_fill = 1.0 - _rank01(np.nan_to_num(R_fill, nan=np.nanmedian(R_fill)))
        hi_mahal = _rank01(mahal)
        hi_dev = _rank01(np.nan_to_num(dev_loc_knn, nan=0.0))

        # --- METROLOGIA MODULARE (opzionale): scarto dal modulo come 4o indizio ---
        w_phase = np.full(n, np.nan)
        w_resid = np.full(n, np.nan)
        h_phase = np.full(n, np.nan)
        h_resid = np.full(n, np.nan)
        metro_results = []
        if do_metro:
            if q_max <= q_min:
                raise Exception("Metrologia: il massimo della ricerca deve superare il minimo.")
            # L = lunghezza (width_bbox), T = spessore/altezza (height_bbox)
            metro_results.append(
                self._run_metrology('LUNGHEZZA', L[~np.isnan(L)], module,
                                    q_min, q_max, q_step, mc_runs, feedback))
            metro_results.append(
                self._run_metrology('SPESSORE/ALTEZZA', T[~np.isnan(T)], module,
                                    q_min, q_max, q_step, mc_runs, feedback))
            # controllo difensivo: se NESSUNA dimensione INFORMATIVA e' modulare,
            # avvisa. (tipico dei laterizi/ritagli, su cui la metrologia non va
            # applicata.) Si basa sull'ADERENZA R_bar, misura della FORZA della
            # modularita': il solo p-value di Rayleigh non basta, perche' su molti
            # campioni in un range stretto risulta significativo anche per dati non
            # modulari. Le dimensioni non informative (misure << modulo) sono escluse.
            informative_R = [r['R'] for r in metro_results
                             if r.get('informative') and not np.isnan(r['R'])]
            if not informative_R:
                feedback.pushWarning(
                    "ATTENZIONE: nessuna dimensione e' informativa per il modulo "
                    "%.4f m (misure troppo piccole rispetto al modulo). L'analisi "
                    "modulare non e' applicabile a questo materiale con questo modulo." % module)
                best_R = 0.0
            else:
                best_R = max(informative_R)
                if best_R < 0.5:
                    feedback.pushWarning(
                        "ATTENZIONE: nessuna dimensione informativa mostra aderenza "
                        "modulare apprezzabile (R_bar max = %.3f < 0.5). Il materiale "
                        "potrebbe NON essere modulare (es. mattoni di ritaglio): in tal "
                        "caso il modulo ottimale del quantogram va considerato spurio e "
                        "lo scarto modulare non e' un indizio affidabile di reimpiego." % best_R)
            # per-feature: fase e scarto dal multiplo piu' vicino
            w_phase = (L % module) / module
            w_resid = L - module * np.round(L / module)
            h_phase = (T % module) / module
            h_resid = T - module * np.round(T / module)
            # indizio metrologico: |scarto| normalizzato (alto = lontano dal modulo)
            metro_anom = (np.abs(np.nan_to_num(w_resid)) + np.abs(np.nan_to_num(h_resid)))
            hi_metro = _rank01(metro_anom)
            reuse_score = (low_fill + hi_mahal + hi_dev + hi_metro) / 4.0
            feedback.pushInfo("\nMetrologia attiva: reuse_score calcolato su 4 indizi "
                              "(riempimento, Mahalanobis, orientamento, scarto modulare).")
        else:
            reuse_score = (low_fill + hi_mahal + hi_dev) / 3.0

        # --- coefficiente di variazione (globale e per cluster) ---
        feedback.pushInfo("--- Coefficiente di variazione (CV = sigma/mu) ---")
        feedback.pushInfo("GLOBALE  len=%.3f  thk=%.3f  area=%.3f  R_fill=%.3f" % (
            self._cv(L), self._cv(T), self._cv(A), self._cv(R_fill)))
        for cl in sorted(np.unique(labels)):
            m = labels == cl
            nm = int(m.sum())
            if nm < 2:
                feedback.pushInfo(
                    "cluster %d (n=%d)  CV non definito (servono almeno 2 elementi)"
                    % (cl, nm))
                continue
            feedback.pushInfo(
                "cluster %d (n=%d)  len=%.3f  thk=%.3f  area=%.3f  R_fill=%.3f" % (
                    cl, nm, self._cv(L[m]), self._cv(T[m]),
                    self._cv(A[m]), self._cv(R_fill[m])))
        feedback.pushInfo("Nota: CV basso = produzione/posa standardizzata; "
                          "CV alto = eterogeneita' (possibile reimpiego).")

        # --- LISA: Local Moran's I sul reuse_score (vicinato k-nearest) ---
        feedback.pushInfo("--- LISA (Local Moran's I) sul reuse_score ---")
        zr = reuse_score - reuse_score.mean()
        s2 = (zr ** 2).mean()
        # I vicini k-nearest sono gia' stati calcolati nel loop principale e
        # salvati in 'neigh' (row-standardized): si riusano qui, evitando una
        # seconda query e ogni rischio di divergenza tra le due liste.

        lisa_I = np.zeros(n)
        spatial_lag = np.zeros(n)
        for i in range(n):
            idx = neigh[i]
            if not idx:
                continue
            w = 1.0 / len(idx)
            lag = sum(w * zr[j] for j in idx)
            spatial_lag[i] = lag
            lisa_I[i] = (zr[i] / s2) * lag if s2 > 0 else 0.0

        # test di significativita' per permutazione condizionale
        lisa_p = np.full(n, np.nan)
        if permutations and permutations > 0 and s2 > 0:
            rng = np.random.default_rng(42)
            others = zr  # pool di valori per la randomizzazione
            for i in range(n):
                ki = len(neigh[i])
                if ki == 0:
                    continue
                pool = np.delete(others, i)
                # Permutazione condizionale "da manuale": si estraggono k_i valori
                # SENZA rimpiazzo dai rimanenti (come PySAL), per non distorcere la
                # distribuzione nulla. Con il rimpiazzo, su vicinati piccoli o
                # paramenti poco popolati i p-value risulterebbero leggermente
                # falsati. Se ki supera il pool disponibile (caso limite con n
                # molto piccolo) si ripiega sul campionamento con rimpiazzo.
                replace = ki > pool.size
                sim = np.empty((permutations, ki))
                for r in range(permutations):
                    sim[r] = rng.choice(pool, size=ki, replace=replace)
                sim_lag = sim.mean(axis=1)
                sim_I = (zr[i] / s2) * sim_lag
                # p pseudo a due code basata sul conteggio di |sim| >= |oss|
                ge = np.sum(np.abs(sim_I) >= abs(lisa_I[i]))
                lisa_p[i] = (ge + 1.0) / (permutations + 1.0)
                feedback.setProgress(int(70 + 15.0 * i / n))

        # classificazione LISA (HH/LL/HL/LH/ns) con soglia p<0.05
        lisa_clust = []
        for i in range(n):
            sig = (not np.isnan(lisa_p[i])) and lisa_p[i] < 0.05
            if not sig:
                lisa_clust.append('ns')
                continue
            zi, lg = zr[i], spatial_lag[i]
            if zi > 0 and lg > 0:
                lisa_clust.append('HH')   # alto reuse circondato da alto = hotspot riuso
            elif zi < 0 and lg < 0:
                lisa_clust.append('LL')   # zona coerente, basso riuso
            elif zi > 0 and lg < 0:
                lisa_clust.append('HL')   # pezzo anomalo isolato
            else:
                lisa_clust.append('LH')   # pezzo coerente in zona disturbata
        nHH = lisa_clust.count('HH')
        feedback.pushInfo("Hotspot di reimpiego (HH significativi): %d" % nHH)

        # --- preparazione output ---
        out_fields = QgsFields()
        for fld in source.fields():
            out_fields.append(fld)
        new_defs = [
            ('R_fill', QVariant.Double), ('mahal', QVariant.Double),
            ('PC1', QVariant.Double), ('PC2', QVariant.Double),
            ('dev_glob', QVariant.Double),
            ('dev_loc_rad', QVariant.Double), ('disp_loc_rad', QVariant.Double),
            ('n_rad', QVariant.Int),
            ('dev_loc_knn', QVariant.Double), ('disp_loc_knn', QVariant.Double),
            ('cluster', QVariant.Int), ('reuse_score', QVariant.Double),
            ('lisa_I', QVariant.Double), ('lisa_p', QVariant.Double),
            ('lisa_clust', QVariant.String),
        ]
        if do_metro:
            new_defs += [
                ('w_phase', QVariant.Double), ('w_resid', QVariant.Double),
                ('h_phase', QVariant.Double), ('h_resid', QVariant.Double),
            ]
        existing = [f.name() for f in out_fields]
        for nm, tp in new_defs:
            if nm in existing:
                feedback.pushWarning("Campo '%s' gia' presente: verra' duplicato." % nm)
            out_fields.append(QgsField(nm, tp))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, out_fields,
            source.wkbType(), source.sourceCrs())

        for i, ft in enumerate(feats):
            g = QgsFeature(out_fields)
            g.setGeometry(ft.geometry())
            attrs = ft.attributes() + [
                float(R_fill[i]) if not np.isnan(R_fill[i]) else None,
                float(mahal[i]),
                float(PC1[i]), float(PC2[i]),
                float(dev_glob[i]),
                float(dev_loc_rad[i]) if not np.isnan(dev_loc_rad[i]) else None,
                float(disp_loc_rad[i]) if not np.isnan(disp_loc_rad[i]) else None,
                int(n_rad[i]),
                float(dev_loc_knn[i]) if not np.isnan(dev_loc_knn[i]) else None,
                float(disp_loc_knn[i]) if not np.isnan(disp_loc_knn[i]) else None,
                int(labels[i]),
                float(reuse_score[i]),
                float(lisa_I[i]),
                float(lisa_p[i]) if not np.isnan(lisa_p[i]) else None,
                lisa_clust[i],
            ]
            if do_metro:
                attrs += [
                    float(w_phase[i]) if not np.isnan(w_phase[i]) else None,
                    float(w_resid[i]) if not np.isnan(w_resid[i]) else None,
                    float(h_phase[i]) if not np.isnan(h_phase[i]) else None,
                    float(h_resid[i]) if not np.isnan(h_resid[i]) else None,
                ]
            g.setAttributes(attrs)
            sink.addFeature(g, QgsFeatureSink.FastInsert)
            feedback.setProgress(85 + int(15.0 * i / n))

        # --- CSV del quantogram (prodotto solo se metrologia attiva) ---
        if do_metro and metro_results:
            csv_path = self.parameterAsFileOutput(parameters, self.CSV_OUT, context)
            if csv_path:
                try:
                    rw, rh = metro_results[0], metro_results[1]
                    with open(csv_path, 'w', encoding='utf-8') as fh:
                        fh.write("modulo,phi_lunghezza,phi_spessore\n")
                        qs = rw['qs']
                        for i, q in enumerate(qs):
                            ph = rh['phi'][i] if i < len(rh['phi']) else ''
                            fh.write("%.4f,%.4f,%s\n" % (q, rw['phi'][i], ph))
                    feedback.pushInfo("Quantogram salvato in: %s" % csv_path)
                except OSError as e:
                    feedback.pushWarning("Impossibile scrivere il CSV: %s" % str(e))

        feedback.pushInfo("Analisi completata su %d componenti." % n)
        return {self.OUTPUT: dest_id}
