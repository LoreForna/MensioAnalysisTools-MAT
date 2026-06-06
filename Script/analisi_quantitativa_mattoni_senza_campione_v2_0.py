"""
SCRIPT ANALISI QUANTITATIVA MATTONI SENZA AREA CAMPIONE - VERSIONE 2.0
Analisi senza layer campioni - Solo layer rilievo
"""

from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterBoolean,
    QgsProcessingException,
    QgsProcessingUtils
)
import processing
from typing import Dict, List


# ============ COSTANTI ============
class FieldNames:
    """Nomi dei campi richiesti nei layer"""
    # Campi layer rilievo
    FID = 'fid'
    TIPO = 'tipo'
    SUPERFICIE = 'superficie'
    AREA_COMPONENTE = 'area_componente'
    NUM_COMPONENTE = 'num_componente'
    USM = 'usm'
    
    # Campi bbox
    WIDTH_BBOX = 'width_bbox'
    HEIGHT_BBOX = 'height_bbox'
    ANGLE_BBOX = 'angle_bbox'
    PERIMETER_BBOX = 'perimeter_bbox'
    AREA_BBOX = 'area_bbox'


class SurfaceTypes:
    """Valori per il campo superficie"""
    INTERA = 'intera'
    PARZIALE = 'parziale'


class ProcessSteps:
    """Numero totale di step per il feedback"""
    TOTAL = 11


# ============ CLASSE PRINCIPALE ============
class AnalisiSenzaCampione(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        """Inizializza i parametri dell'algoritmo"""
        # Input layer
        self.addParameter(QgsProcessingParameterFeatureSource(
            'layer_rilievo',
            'Layer rilievo (poligoni componenti muratura)',
            types=[QgsProcessing.TypeVectorPolygon],
            defaultValue='rilievo'
        ))
        
        # Parametri filtro
        self.addParameter(QgsProcessingParameterString(
            'tipo_materiale',
            'Tipo di materiale (separati da virgola, vuoto=tutti)',
            defaultValue='',
            optional=True
        ))
        
        self.addParameter(QgsProcessingParameterBoolean(
            'includi_non_classificati',
            'Includi elementi non classificati (NULL)',
            defaultValue=False
        ))
        
        # Parametri range
        self.addParameter(QgsProcessingParameterNumber(
            'width_range_step',
            'Step range larghezza (m)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.004,
            minValue=0.001
        ))
        
        self.addParameter(QgsProcessingParameterNumber(
            'height_range_step',
            'Step range altezza (m)',
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.002,
            minValue=0.001
        ))
        
        # Output layers
        self.addParameter(QgsProcessingParameterFeatureSink(
            'output_bbox',
            'Min oriented bbox',
            type=QgsProcessing.TypeVectorPolygon
        ))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            'output_rilievo',
            'Analisi rilievo',
            type=QgsProcessing.TypeVectorPolygon
        ))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            'output_statistiche',
            'Statistiche aggregate',
            type=QgsProcessing.TypeVectorAnyGeometry
        ))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            'output_width_range',
            'Conteggio range larghezza',
            type=QgsProcessing.TypeVectorAnyGeometry
        ))
        
        self.addParameter(QgsProcessingParameterFeatureSink(
            'output_height_range',
            'Conteggio range altezza',
            type=QgsProcessing.TypeVectorAnyGeometry
        ))

    def validate_layer_fields(self, layer, required_fields: List[str], layer_name: str, feedback) -> bool:
        """Valida che un layer contenga tutti i campi richiesti"""
        if not layer:
            raise QgsProcessingException(f"Layer {layer_name} non valido!")
        
        existing_fields = [f.name() for f in layer.fields()]
        missing_fields = [f for f in required_fields if f not in existing_fields]
        
        if missing_fields:
            feedback.reportError(f"Campi mancanti in {layer_name}: {', '.join(missing_fields)}")
            feedback.reportError(f"Campi disponibili: {', '.join(existing_fields)}")
            raise QgsProcessingException(
                f"Il layer '{layer_name}' non contiene i campi obbligatori: {', '.join(missing_fields)}"
            )
        
        feedback.pushInfo(f"✓ Validazione campi {layer_name} completata")
        return True

    def create_field_mapping(self, fields: List[tuple]) -> List[Dict]:
        """Crea mapping per refactor fields"""
        return [
            {
                'expression': expr,
                'length': length,
                'name': name,
                'precision': precision,
                'sub_type': 0,
                'type': field_type,
                'type_name': ''
            }
            for expr, name, field_type, length, precision in fields
        ]

    def get_layer_from_source(self, source, context):
        """
        Ottiene un layer da varie sorgenti (stringa, QgsProcessingFeatureSourceDefinition, ecc.)
        """
        from qgis.core import QgsProcessingFeatureSourceDefinition, QgsVectorLayer
        
        # Se è già una stringa con ID layer
        if isinstance(source, str):
            return QgsProcessingUtils.mapLayerFromString(source, context)
        
        # Se è un QgsProcessingFeatureSourceDefinition
        if isinstance(source, QgsProcessingFeatureSourceDefinition):
            # Estrai la sorgente interna
            internal_source = source.source
            if hasattr(internal_source, 'staticValue'):
                # È un QgsProperty, prendi il valore statico
                layer_id = internal_source.staticValue()
            else:
                layer_id = str(internal_source)
            return QgsProcessingUtils.mapLayerFromString(layer_id, context)
        
        # Per altri tipi, prova a convertire in stringa
        try:
            return QgsProcessingUtils.mapLayerFromString(str(source), context)
        except Exception:
            return None
    
    def verifica_features(self, layer_source, context, feedback, layer_name: str):
        """Verifica il numero di features in un layer"""
        layer = self.get_layer_from_source(layer_source, context)
        
        if layer:
            count = layer.featureCount()
            feedback.pushInfo(f"✓ {layer_name}: {count} features")
            return count
        return 0

    def processAlgorithm(self, parameters, context, model_feedback):
        """Algoritmo principale"""
        feedback = QgsProcessingMultiStepFeedback(ProcessSteps.TOTAL, model_feedback)
        results = {}
        
        # ===== STEP 1: VALIDAZIONE INPUT =====
        feedback.setCurrentStep(0)
        feedback.pushInfo("\n" + "="*70)
        feedback.pushInfo("ANALISI QUANTITATIVA MATTONI SENZA AREA CAMPIONE - v2.0")
        feedback.pushInfo("="*70)
        
        # Validazione layer rilievo
        rilievo_source = self.parameterAsSource(parameters, 'layer_rilievo', context)
        required_fields = [
            FieldNames.FID, FieldNames.TIPO, FieldNames.AREA_COMPONENTE, 
            FieldNames.NUM_COMPONENTE
        ]
        self.validate_layer_fields(rilievo_source, required_fields, 'Layer rilievo', feedback)
        
        # Verifica se esiste il campo superficie
        existing_fields = [f.name() for f in rilievo_source.fields()]
        has_superficie_field = FieldNames.SUPERFICIE in existing_fields
        
        if has_superficie_field:
            feedback.pushInfo(f"✓ Campo '{FieldNames.SUPERFICIE}' trovato - Verrà applicata la separazione interi/parziali")
        else:
            feedback.pushInfo(f"⚠ Campo '{FieldNames.SUPERFICIE}' non trovato - Tutti i componenti saranno utilizzati per le statistiche")
        
        # Parametri filtro
        tipo_str = self.parameterAsString(parameters, 'tipo_materiale', context).strip()
        includi_null = self.parameterAsBool(parameters, 'includi_non_classificati', context)
        width_step = self.parameterAsDouble(parameters, 'width_range_step', context)
        height_step = self.parameterAsDouble(parameters, 'height_range_step', context)
        
        # Elabora filtro materiali
        applica_filtro = bool(tipo_str)
        tipi = [t.strip() for t in tipo_str.split(',')] if applica_filtro else []
        
        feedback.pushInfo("\n[PARAMETRI]")
        if applica_filtro:
            feedback.pushInfo(f"Filtro materiali: {', '.join(tipi)}")
            feedback.pushInfo(f"Includi NULL: {'SI' if includi_null else 'NO'}")
        else:
            feedback.pushInfo("Filtro materiali: NESSUNO (tutti i materiali)")
        feedback.pushInfo(f"Step larghezza: {width_step} m")
        feedback.pushInfo(f"Step altezza: {height_step} m")
        
        # ===== STEP 2: APPLICAZIONE FILTRO =====
        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo("\n--- APPLICAZIONE FILTRO ---")
        
        if applica_filtro:
            # Costruisci espressione filtro
            tipo_conditions = [f'"{FieldNames.TIPO}" = \'{tipo}\'' for tipo in tipi]
            filter_expr = ' OR '.join(tipo_conditions)
            
            if includi_null:
                filter_expr = f'({filter_expr}) OR "{FieldNames.TIPO}" IS NULL'
            
            feedback.pushInfo(f"Espressione filtro: {filter_expr}")
            
            rilievo_filtered = processing.run('native:extractbyexpression', {
                'INPUT': parameters['layer_rilievo'],
                'EXPRESSION': filter_expr,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            
            rilievo_input = rilievo_filtered['OUTPUT']
            feedback.pushInfo(f"✓ Filtro applicato")
        else:
            rilievo_input = parameters['layer_rilievo']
            feedback.pushInfo("✓ Nessun filtro applicato - elaborazione completa")
        
        self.verifica_features(rilievo_input, context, feedback, "Rilievo dopo filtro")
        
        # ===== STEP 3: CALCOLO BOUNDING BOX SU TUTTI I COMPONENTI =====
        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo("\n--- CALCOLO BOUNDING BOX ORIENTATI (TUTTI I COMPONENTI) ---")
        
        bbox = processing.run('native:orientedminimumboundingbox', {
            'INPUT': rilievo_input,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        self.verifica_features(bbox['OUTPUT'], context, feedback, "Bounding box")
        
        # ===== STEP 4: CONTEGGIO E PREPARAZIONE LAYER PER STATISTICHE =====
        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}
        
        # Conta componenti per tipo
        count_interi = 0
        count_parziali = 0
        count_totale = 0
        
        rilievo_layer = self.get_layer_from_source(rilievo_input, context)
        if rilievo_layer:
            count_totale = rilievo_layer.featureCount()
            
            if has_superficie_field:
                # Conta interi e parziali
                for feat in rilievo_layer.getFeatures():
                    superficie = feat[FieldNames.SUPERFICIE]
                    if superficie == SurfaceTypes.INTERA:
                        count_interi += 1
                    elif superficie == SurfaceTypes.PARZIALE:
                        count_parziali += 1
                
                feedback.pushInfo(f"\n[CONTEGGIO COMPONENTI - CON SEPARAZIONE]")
                feedback.pushInfo(f"Totale componenti: {count_totale}")
                feedback.pushInfo(f"  - Interi: {count_interi}")
                feedback.pushInfo(f"  - Parziali: {count_parziali}")
            else:
                # Tutti i componenti sono considerati come "interi" per le statistiche
                count_interi = count_totale
                count_parziali = 0
                
                feedback.pushInfo(f"\n[CONTEGGIO COMPONENTI - SENZA SEPARAZIONE]")
                feedback.pushInfo(f"Totale componenti: {count_totale}")
                feedback.pushInfo("Tutti i componenti saranno usati per le statistiche")
        
        # Crea layer per statistiche
        if has_superficie_field and count_interi > 0:
            feedback.pushInfo("\n--- ESTRAZIONE COMPONENTI INTERI PER STATISTICHE ---")
            interi_for_stats = processing.run('native:extractbyexpression', {
                'INPUT': rilievo_input,
                'EXPRESSION': f'"{FieldNames.SUPERFICIE}" = \'{SurfaceTypes.INTERA}\'',
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
            }, context=context, feedback=feedback, is_child_algorithm=True)
            layer_for_stats = interi_for_stats['OUTPUT']
            feedback.pushInfo(f"✓ Statistiche calcolate solo su componenti interi ({count_interi})")
        else:
            feedback.pushInfo("\n--- USO TUTTI I COMPONENTI PER STATISTICHE ---")
            layer_for_stats = rilievo_input
            feedback.pushInfo(f"✓ Statistiche calcolate su tutti i componenti ({count_totale})")
        
        # ===== STEP 5: AGGIUNTA CAMPO AREA BBOX =====
        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}
        
        bbox_with_area = processing.run('native:fieldcalculator', {
            'INPUT': bbox['OUTPUT'],
            'FIELD_NAME': FieldNames.AREA_BBOX,
            'FIELD_TYPE': 0,  # Double
            'FIELD_LENGTH': 10,
            'FIELD_PRECISION': 6,
            'FORMULA': '$area',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # ===== JOIN USM DAL RILIEVO AL BBOX =====
        feedback.pushInfo("\n--- AGGIUNTA CAMPI USM E NUM_COMPONENTE AL BBOX ---")
        
        bbox_with_usm = processing.run('native:joinattributestable', {
            'INPUT': bbox_with_area['OUTPUT'],
            'INPUT_2': rilievo_input,
            'FIELD': FieldNames.FID,
            'FIELD_2': FieldNames.FID,
            'FIELDS_TO_COPY': [FieldNames.USM, FieldNames.NUM_COMPONENTE],
            'METHOD': 1,
            'DISCARD_NONMATCHING': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # ===== STEP 6: REFACTOR CAMPI BBOX =====
        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}
        
        bbox_fields = self.create_field_mapping([
            ('"fid"', FieldNames.FID, 4, 0, 0),
            (f'"{FieldNames.USM}"', FieldNames.USM, 4, 0, 0),
            (f'"{FieldNames.NUM_COMPONENTE}"', FieldNames.NUM_COMPONENTE, 4, 0, 0),
            # width_bbox = lato MAGGIORE (lunghezza), height_bbox = lato MINORE
            # (spessore). Si usano max()/min() invece di affidarsi ai nomi nativi
            # "height"/"width": l'algoritmo QGIS orientedMinimumBoundingBox
            # garantisce gia' width<=height in output (vincolo nel sorgente,
            # qgsinternalgeometryengine.cpp), ma con max/min il mapping resta
            # corretto anche se quella convenzione cambiasse in futuro.
            ('max("width", "height")', FieldNames.WIDTH_BBOX, 6, 10, 6),
            ('min("width", "height")', FieldNames.HEIGHT_BBOX, 6, 10, 6),
            # L'angolo nativo e' riferito al lato corto ed e' assiale (0-180).
            # Una rotazione costante (lo stesso +90 per tutti gli elementi)
            # non altera coerenza R_bar ne' scarti relativi nella statistica
            # circolare assiale a valle: si conserva quindi l'angolo nativo.
            ('"angle"', FieldNames.ANGLE_BBOX, 6, 10, 6),
            ('"perimeter"', FieldNames.PERIMETER_BBOX, 6, 10, 6),
            (f'"{FieldNames.AREA_BBOX}"', FieldNames.AREA_BBOX, 6, 10, 6)
        ])
        
        bbox_refactored = processing.run('native:refactorfields', {
            'INPUT': bbox_with_usm['OUTPUT'],
            'FIELDS_MAPPING': bbox_fields,
            'OUTPUT': parameters['output_bbox']
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        results['output_bbox'] = bbox_refactored['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['output_bbox']).name = "min_oriented_bbox_mattoni_senza_campione"
        
        # ===== STEP 6: JOIN BBOX CON TUTTI I COMPONENTI =====
        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo("\n--- JOIN DATI BBOX CON TUTTI I COMPONENTI ---")
        
        rilievo_with_bbox = processing.run('native:joinattributestable', {
            'INPUT': rilievo_input,
            'INPUT_2': bbox_refactored['OUTPUT'],
            'FIELD': FieldNames.FID,
            'FIELD_2': FieldNames.FID,
            'FIELDS_TO_COPY': [
                FieldNames.WIDTH_BBOX, FieldNames.HEIGHT_BBOX, FieldNames.ANGLE_BBOX,
                FieldNames.PERIMETER_BBOX, FieldNames.AREA_BBOX
            ],
            'METHOD': 1,
            'DISCARD_NONMATCHING': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # ===== STEP 7: REFACTOR CAMPI FINALI =====
        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo("\n--- CREAZIONE LAYER RILIEVO COMPLETO ---")
        
        # Crea mapping campi base
        final_fields_list = [
            ('"fid"', FieldNames.FID, 4, 0, 0),
            (f'"{FieldNames.USM}"', FieldNames.USM, 4, 0, 0),
            (f'"{FieldNames.TIPO}"', FieldNames.TIPO, 10, 0, 0)
        ]
        
        # Aggiungi campo superficie solo se esiste
        if has_superficie_field:
            final_fields_list.append((f'"{FieldNames.SUPERFICIE}"', FieldNames.SUPERFICIE, 10, 0, 0))
        
        # Aggiungi altri campi
        final_fields_list.extend([
            (f'"{FieldNames.AREA_COMPONENTE}"', FieldNames.AREA_COMPONENTE, 6, 10, 6),
            (f'"{FieldNames.NUM_COMPONENTE}"', FieldNames.NUM_COMPONENTE, 2, 0, 0),
            (f'"{FieldNames.WIDTH_BBOX}"', FieldNames.WIDTH_BBOX, 6, 10, 6),
            (f'"{FieldNames.HEIGHT_BBOX}"', FieldNames.HEIGHT_BBOX, 6, 10, 6),
            (f'"{FieldNames.ANGLE_BBOX}"', FieldNames.ANGLE_BBOX, 6, 10, 6),
            (f'"{FieldNames.PERIMETER_BBOX}"', FieldNames.PERIMETER_BBOX, 6, 10, 6),
            (f'"{FieldNames.AREA_BBOX}"', FieldNames.AREA_BBOX, 6, 10, 6)
        ])
        
        final_fields = self.create_field_mapping(final_fields_list)
        
        rilievo_final = processing.run('native:refactorfields', {
            'INPUT': rilievo_with_bbox['OUTPUT'],
            'FIELDS_MAPPING': final_fields,
            'OUTPUT': parameters['output_rilievo']
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        results['output_rilievo'] = rilievo_final['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['output_rilievo']).name = "analisi_rilievo_mattoni_senza_campione"
        
        # ===== STEP 8: CALCOLO STATISTICHE AGGREGATE =====
        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo("\n--- CALCOLO STATISTICHE AGGREGATE ---")
        
        # Calcola statistiche manualmente dal layer
        from qgis.core import QgsFeature, QgsFields, QgsField
        from qgis.PyQt.QtCore import QVariant
        import math
        
        # Unisci bbox con layer_for_stats per avere i dati completi
        stats_with_bbox = processing.run('native:joinattributestable', {
            'INPUT': layer_for_stats,
            'INPUT_2': bbox_refactored['OUTPUT'],
            'FIELD': FieldNames.FID,
            'FIELD_2': FieldNames.FID,
            'FIELDS_TO_COPY': [
                FieldNames.WIDTH_BBOX, FieldNames.HEIGHT_BBOX, FieldNames.ANGLE_BBOX,
                FieldNames.PERIMETER_BBOX, FieldNames.AREA_BBOX
            ],
            'METHOD': 1,
            'DISCARD_NONMATCHING': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        stats_layer = self.get_layer_from_source(stats_with_bbox['OUTPUT'], context)
        
        # Funzione per calcolare statistiche
        def calcola_statistiche(layer, field_name):
            values = []
            for feat in layer.getFeatures():
                val = feat[field_name]
                if val is not None:
                    values.append(val)
            
            if not values:
                return None
            
            n = len(values)
            min_val = min(values)
            max_val = max(values)
            mean_val = sum(values) / n
            
            # Deviazione standard CAMPIONARIA (ddof=1, correzione di Bessel):
            # coerente con gli altri strumenti della suite. Indefinita per n<2.
            if n > 1:
                variance = sum((x - mean_val) ** 2 for x in values) / (n - 1)
                stddev_val = math.sqrt(variance)
            else:
                stddev_val = None
            
            range_val = max_val - min_val
            
            return {
                'count': n,
                'min': min_val,
                'max': max_val,
                'mean': mean_val,
                'stddev': stddev_val,
                'range': range_val
            }
        
        # Calcola statistiche per ogni campo
        stats_width = calcola_statistiche(stats_layer, FieldNames.WIDTH_BBOX)
        stats_height = calcola_statistiche(stats_layer, FieldNames.HEIGHT_BBOX)
        stats_area = calcola_statistiche(stats_layer, FieldNames.AREA_COMPONENTE)
        
        # Prepara dati per la tabella
        stats_data = []
        
        # Prima i conteggi
        stats_data.append({
            'parametro': 'Componenti interi',
            'count': count_interi,
            'min': None,
            'max': None,
            'range': None,
            'mean': None,
            'stddev': None
        })
        
        stats_data.append({
            'parametro': 'Componenti parziali',
            'count': count_parziali,
            'min': None,
            'max': None,
            'range': None,
            'mean': None,
            'stddev': None
        })
        
        stats_data.append({
            'parametro': 'Totale',
            'count': count_totale,
            'min': None,
            'max': None,
            'range': None,
            'mean': None,
            'stddev': None
        })
        
        # Poi le statistiche
        if stats_width:
            stats_data.append({
                'parametro': 'Larghezza',
                **stats_width
            })
        
        if stats_height:
            stats_data.append({
                'parametro': 'Altezza',
                **stats_height
            })
        
        if stats_area:
            stats_data.append({
                'parametro': 'Area',
                **stats_area
            })
        
        # Crea tabella statistiche
        from qgis.core import QgsWkbTypes
        
        fields = QgsFields()
        fields.append(QgsField('parametro', QVariant.String, len=50))
        fields.append(QgsField('count', QVariant.Int))
        fields.append(QgsField('min', QVariant.Double, len=10, prec=6))
        fields.append(QgsField('max', QVariant.Double, len=10, prec=6))
        fields.append(QgsField('range', QVariant.Double, len=10, prec=6))
        fields.append(QgsField('mean', QVariant.Double, len=10, prec=6))
        fields.append(QgsField('stddev', QVariant.Double, len=10, prec=6))
        
        (sink, dest_id) = self.parameterAsSink(
            parameters, 'output_statistiche', context, fields,
            QgsWkbTypes.NoGeometry
        )
        
        for data in stats_data:
            feat = QgsFeature(fields)
            feat['parametro'] = data['parametro']
            feat['count'] = data['count']
            feat['min'] = data.get('min')
            feat['max'] = data.get('max')
            feat['range'] = data.get('range')
            feat['mean'] = data.get('mean')
            feat['stddev'] = data.get('stddev')
            sink.addFeature(feat)
        
        results['output_statistiche'] = dest_id
        context.layerToLoadOnCompletionDetails(results['output_statistiche']).name = "statistiche_aggregate_mattoni_senza_campione"
        
        feedback.pushInfo("\n[STATISTICHE AGGREGATE]")
        for data in stats_data[:3]:  # Solo primi 3 (width, height, area)
            feedback.pushInfo(f"\n{data['parametro']}:")
            feedback.pushInfo(f"  Count: {data['count']}")
            if data.get('min') is not None:
                feedback.pushInfo(f"  Min: {data['min']:.6f}")
                feedback.pushInfo(f"  Max: {data['max']:.6f}")
                feedback.pushInfo(f"  Range: {data['range']:.6f}")
                feedback.pushInfo(f"  Mean: {data['mean']:.6f}")
                feedback.pushInfo(f"  StdDev: {data['stddev']:.6f}")
        
        # ===== STEP 9: CALCOLO CAMPI RANGE =====
        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo("\n--- CALCOLO CAMPI RANGE ---")
        
        # Formula per range larghezza
        width_formula = f'''CASE 
    WHEN "{FieldNames.WIDTH_BBOX}" IS NULL THEN 'N/A'
    ELSE concat(
        round(floor("{FieldNames.WIDTH_BBOX}"/{width_step})*{width_step}, 3),
        ' - ',
        round((floor("{FieldNames.WIDTH_BBOX}"/{width_step})+1)*{width_step}, 3)
    )
END'''
        
        with_width_range = processing.run('native:fieldcalculator', {
            'INPUT': stats_with_bbox['OUTPUT'],
            'FIELD_NAME': 'width_bbox_range',
            'FIELD_TYPE': 2,  # string
            'FORMULA': width_formula,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # Formula per range altezza
        height_formula = f'''CASE 
    WHEN "{FieldNames.HEIGHT_BBOX}" IS NULL THEN 'N/A'
    ELSE concat(
        round(floor("{FieldNames.HEIGHT_BBOX}"/{height_step})*{height_step}, 3),
        ' - ',
        round((floor("{FieldNames.HEIGHT_BBOX}"/{height_step})+1)*{height_step}, 3)
    )
END'''
        
        with_both_ranges = processing.run('native:fieldcalculator', {
            'INPUT': with_width_range['OUTPUT'],
            'FIELD_NAME': 'height_bbox_range',
            'FIELD_TYPE': 2,
            'FORMULA': height_formula,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        # ===== STEP 10: DISTRIBUZIONE RANGE LARGHEZZA =====
        feedback.setCurrentStep(9)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo("\n--- CALCOLO DISTRIBUZIONE RANGE LARGHEZZA ---")
        
        count_width = processing.run('qgis:statisticsbycategories', {
            'INPUT': with_both_ranges['OUTPUT'],
            'CATEGORIES_FIELD_NAME': ['width_bbox_range'],
            'VALUES_FIELD_NAME': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        sorted_width = processing.run('native:orderbyexpression', {
            'INPUT': count_width['OUTPUT'],
            'EXPRESSION': 'width_bbox_range',
            'ASCENDING': True,
            'OUTPUT': parameters['output_width_range']
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        results['output_width_range'] = sorted_width['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['output_width_range']).name = "conteggio_range_larghezza_mattoni_senza_campione"
        self.verifica_features(results['output_width_range'], context, feedback, "Range larghezza")
        
        # ===== STEP 11: DISTRIBUZIONE RANGE ALTEZZA =====
        feedback.setCurrentStep(10)
        if feedback.isCanceled():
            return {}
        
        feedback.pushInfo("\n--- CALCOLO DISTRIBUZIONE RANGE ALTEZZA ---")
        
        count_height = processing.run('qgis:statisticsbycategories', {
            'INPUT': with_both_ranges['OUTPUT'],
            'CATEGORIES_FIELD_NAME': ['height_bbox_range'],
            'VALUES_FIELD_NAME': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        sorted_height = processing.run('native:orderbyexpression', {
            'INPUT': count_height['OUTPUT'],
            'EXPRESSION': 'height_bbox_range',
            'ASCENDING': True,
            'OUTPUT': parameters['output_height_range']
        }, context=context, feedback=feedback, is_child_algorithm=True)
        
        results['output_height_range'] = sorted_height['OUTPUT']
        context.layerToLoadOnCompletionDetails(results['output_height_range']).name = "conteggio_range_altezza_mattoni_senza_campione"
        self.verifica_features(results['output_height_range'], context, feedback, "Range altezza")
        
        # ===== RIEPILOGO FINALE =====
        self._log_summary(count_interi, count_parziali, applica_filtro, tipi,
                         includi_null, width_step, height_step, results, context, feedback)
        
        return results

    def _log_summary(self, count_interi: int, count_parziali: int, applica_filtro: bool,
                    tipi: List[str], includi_null: bool, width_step: float, height_step: float,
                    results: Dict, context, feedback):
        """Stampa il riepilogo finale dell'elaborazione"""
        feedback.pushInfo("\n" + "="*70)
        feedback.pushInfo("ELABORAZIONE COMPLETATA CON SUCCESSO")
        feedback.pushInfo("="*70)
        
        feedback.pushInfo("\n[RIEPILOGO ELABORAZIONE]")
        feedback.pushInfo(f"Componenti totali analizzati: {count_interi + count_parziali}")
        feedback.pushInfo(f"  - Componenti interi: {count_interi}")
        feedback.pushInfo(f"  - Componenti parziali: {count_parziali}")
        
        if applica_filtro:
            feedback.pushInfo(f"\n[FILTRO APPLICATO]")
            feedback.pushInfo(f"Tipi materiale: {', '.join(tipi)}")
            if includi_null:
                feedback.pushInfo("Include non classificati: SI")
        else:
            feedback.pushInfo("\n[NESSUN FILTRO] - Tutti i materiali inclusi")
        
        feedback.pushInfo("\n[PARAMETRI RANGE]")
        feedback.pushInfo(f"Step larghezza: {width_step} m")
        feedback.pushInfo(f"Step altezza: {height_step} m")
        
        feedback.pushInfo("\n[OUTPUT GENERATI]")
        for name in results.keys():
            layer = self.get_layer_from_source(results[name], context)
            if layer:
                feedback.pushInfo(f"  * {layer.name()}: {layer.featureCount()} features")
        
        feedback.pushInfo("\n" + "="*70)

    def name(self) -> str:
        return 'analisi_mattoni_senza_campione'

    def displayName(self) -> str:
        return 'Mattoni senza campione'

    def group(self) -> str:
        return 'Analisi quantitative'

    def groupId(self) -> str:
        return 'analisi'

    def createInstance(self):
        return AnalisiSenzaCampione()

    def shortHelpString(self) -> str:
        return """
        <h3>Analisi Quantitativa Mattoni Senza Area Campione - Versione 2.0</h3>
        
        <p>Analizza le geometrie dei mattoni in una muratura senza necessità del layer campioni.
        Calcola statistiche aggregate su tutti i componenti, se il campo superficie è compilato con il valore intero o parziale i calcoli sono eseguiti sui soli componenti interi.</p>
        
        <h4>Parametri di Input:</h4>
        <ul>
            <li><b>Layer rilievo:</b> Poligoni dei componenti murari (richiede: fid, tipo, superficie, area_componente, num_componente)</li>
            <li><b>Tipo di materiale:</b> Lista separata da virgole o vuoto per tutti</li>
            <li><b>Includi non classificati:</b> Include elementi con tipo NULL</li>
            <li><b>Step range:</b> Incremento per calcolo dei range (metri)</li>
        </ul>
        
        <h4>Output Generati:</h4>
        <ul>
            <li><b>min_oriented_bbox:</b> Rettangoli orientati minimi</li>
            <li><b>analisi_rilievo:</b> Rilievo arricchito con metriche bbox</li>
            <li><b>statistiche_aggregate:</b> Statistiche globali (min, max, mean, stddev, range)</li>
            <li><b>distribuzione_range_larghezza/altezza:</b> Distribuzioni per range</li>
        </ul>
        
        <h4>Differenze dalla versione 1.0:</h4>
        <ul>
            <li>Non richiede il layer campioni</li>
            <li>Calcola statistiche aggregate su tutti i componenti interi</li>
            <li>Genera una tabella di statistiche globali invece che per campione</li>
            <li>Più semplice e veloce da utilizzare</li>
        </ul>
        
        <h4>Note Importanti:</h4>
        <ul>
            <li>Il layer rilievo deve contenere i campi: fid, tipo, superficie, area_componente, num_componente</li>
            <li>I componenti vengono separati in "interi" e "parziali" in base al campo "superficie" solo se compilato</li>
            <li>Le statistiche vengono calcolate solo sui componenti interi</li>
            <li>Il filtro materiali è case-sensitive</li>
        </ul>
        
        <p><b>Versione:</b> 2.0 - Senza Area Campione</p>
        """
