"""Source schema facts with optional, explicitly attributed catalog enrichment."""
import copy
import re


def collect_atlas_enrichment(client, *, source, entity_guid, qualified_name, collected_at):
    """Read one explicitly mapped Atlas entity; no fuzzy matching or Atlas writes.

    The caller must authorize metadata access before invoking this adapter.
    An existing Helios AtlasClient supplies the read-only entity operation.
    """
    if not isinstance(entity_guid,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,128}',entity_guid):
        raise ValueError('Invalid mapped Atlas entity identifier')
    if not isinstance(qualified_name,str) or not qualified_name or len(qualified_name)>1000:
        raise ValueError('Invalid mapped Atlas qualified name')
    try:
        entity=client.entity(entity_guid)
    except Exception:
        raise ValueError('Atlas entity could not be read; enrichment unavailable') from None
    if not isinstance(entity,dict) or not isinstance(entity.get('attributes'),dict):
        raise ValueError('Atlas returned invalid entity metadata')
    attributes=entity['attributes']
    if (entity.get('guid')!=entity_guid or entity.get('status')!='ACTIVE'
            or attributes.get('qualifiedName')!=qualified_name):
        raise ValueError('Atlas entity identity, status or qualified name mismatch')
    def text(value):
        return value[:1000] if isinstance(value,str) else ''
    relationships=entity.get('relationshipAttributes',{})
    classifications=entity.get('classifications',[])
    if not isinstance(relationships,dict) or not isinstance(classifications,list):
        raise ValueError('Atlas returned invalid entity annotations')
    terms=relationships.get('meanings',[])
    if not isinstance(terms,list):
        raise ValueError('Atlas returned invalid glossary assignments')
    return {'source':source,'mode':'live','provider':'atlas','entity_guid':entity_guid,
            'qualified_name':qualified_name,'collected_at':collected_at,
            'description':text(attributes.get('description')),
            'classifications':[text(item.get('typeName')) for item in classifications[:100]
                               if isinstance(item,dict) and text(item.get('typeName'))],
            'terms':[text(item.get('displayText')) for item in terms[:100]
                     if isinstance(item,dict) and text(item.get('displayText'))]}


def inventory(catalog, schema, table, columns, *, mode, enrichment=None):
    """Normalize already discovered columns; never infer grants or query source rows."""
    if mode not in {'sample', 'live'}:
        raise ValueError('Explicit sample/live mode required')
    parts = (catalog, schema, table)
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_$-]{0,127}', part) for part in parts):
        raise ValueError('Invalid dataset identity')
    source = '.'.join(parts)
    fields = []
    for column in columns:
        name, datatype = column['name'], column['type']
        if not isinstance(name, str) or not isinstance(datatype, str):
            raise ValueError('Field name and type must be strings')
        fields.append({'name': name, 'type': datatype, 'origin': 'synthetic' if mode == 'sample' else 'trino'})
    if len({field['name'] for field in fields}) != len(fields):
        raise ValueError('Duplicate metadata fields')
    dataset = {'source': source, 'fields': fields, 'enrichment': None}
    if enrichment is not None:
        # Only an explicit exact source mapping can attach catalog annotations.
        # A table name alone is insufficient across catalogs and clusters.
        if enrichment.get('source') != source or enrichment.get('mode') != mode:
            raise ValueError('Catalog enrichment source or mode mismatch')
        allowed = {'source', 'mode', 'provider', 'entity_guid', 'qualified_name', 'collected_at',
                   'terms', 'classifications', 'lineage', 'description'}
        if set(enrichment) - allowed or enrichment.get('provider') not in {'atlas', 'synthetic'}:
            raise ValueError('Unsupported catalog enrichment fields')
        if mode == 'live' and enrichment['provider'] == 'synthetic':
            raise ValueError('Synthetic enrichment cannot describe a live source')
        dataset['enrichment'] = copy.deepcopy(enrichment)
    return {'schema': 'uob.metadata.inventory.v1', 'mode': mode, 'datasets': [dataset],
            'limitations': ['Schema metadata and catalog classifications do not grant data access.',
                            'Business meanings and relationships require review before Ossie publication.']}
