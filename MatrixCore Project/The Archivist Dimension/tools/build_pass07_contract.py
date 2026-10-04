from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
catalog=json.loads((ROOT/'assets/books/catalog.json').read_text(encoding='utf-8'))
links=json.loads((ROOT/'saves/simulation_links.json').read_text(encoding='utf-8')).get('links',{})
primary={
 'continuation_matrixcore':'matrixcore',
 'continuation_afterlife_of_io':'afterlife',
 'continuation_entropy':'entropy',
 'continuation_the_restoration_of_utopia':'utopia',
 'apocalypse_apocalypse_run':'apocalypse',
 'archive_what_the_archive_became':'archive',
}
continuation_map={
 'continuation_the_continuum':'matrixcore',
 'continuation_beyond_the_last_light':'entropy',
 'continuation_the_last_signal':'entropy',
 'continuation_sables_mission':'afterlife',
 'continuation_io_88_and_the_prototype_realities':'matrixcore',
 'continuation_the_victory_and_reunion':'utopia',
}

def sid(book):
    bid=str(book.get('id') or '')
    if bid in primary:return primary[bid]
    collection=str(book.get('collection') or '')
    section=str(book.get('archive_section') or '')
    if collection=='Mainland Apocalypse Cycle':return 'apocalypse'
    if bid in continuation_map:return continuation_map[bid]
    if collection=='MatrixCore Continuation':return 'matrixcore'
    if section in ('ARCHIVE ZERO','I — PUBLIC UTOPIA'):return 'utopia'
    if section=='II — ANOMALOUS MATERIAL':return 'archive'
    if section=='III — PERSONHOOD AND REVIEW':return 'matrixcore'
    if section=='IV — CONTINUITY CASES':return 'afterlife'
    if section=='V — REMNANTS AND CONTINUITY':return 'entropy'
    return 'archive'

systems={k:{'planet':None,'moons':[],'satellites':[],'linked_planet_gate':False} for k in ('matrixcore','afterlife','entropy','utopia','apocalypse','archive')}
for b in catalog:
    bid=str(b.get('id') or '')
    system=sid(b)
    if bid in primary:
        systems[system]['planet']=bid
        systems[system]['linked_planet_gate']=bid in links
    elif bid in links:
        systems[system]['satellites'].append(bid)
    else:
        systems[system]['moons'].append(bid)
roles={'planet':0,'moon':0,'satellite':0}
for data in systems.values():
    roles['planet'] += 1 if data['planet'] else 0
    roles['moon'] += len(data['moons'])
    roles['satellite'] += len(data['satellites'])
record_ids={str(x.get('id') or '') for x in catalog}
assigned={x for data in systems.values() for x in ([data['planet']] if data['planet'] else [])+data['moons']+data['satellites']}
out={
 'pass':7,
 'catalog_records':len(catalog),
 'assigned_records':len(assigned),
 'unassigned_records':sorted(record_ids-assigned),
 'duplicate_assignment_count':sum(1 for rid in assigned if sum(rid in (([d['planet']] if d['planet'] else [])+d['moons']+d['satellites']) for d in systems.values())>1),
 'role_counts':roles,
 'catalog_link_records':sorted(record_ids & set(links)),
 'noncatalog_link_records':sorted(set(links)-record_ids),
 'systems':systems,
}
(ROOT/'verification'/'planetary_story_systems.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
