"""Extract highway ways and their turn restrictions from a retained OSM PBF."""
import argparse
import hashlib
import json
from pathlib import Path
import osmium


def extract(source, output, bbox):
    if output.exists(): raise FileExistsError(output)
    west, south, east, north = bbox
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError('Invalid WGS84 bounding box')
    ways, nodes, relations = set(), set(), set()
    class Select(osmium.SimpleHandler):
        def way(self, way):
            if 'highway' not in way.tags: return
            if any(n.location.valid() and west <= n.lon <= east and south <= n.lat <= north for n in way.nodes):
                ways.add(way.id)
        def relation(self, relation):
            if relation.tags.get('type') == 'restriction' and any(m.type == 'w' and m.ref in ways for m in relation.members):
                relations.add(relation.id)
                ways.update(m.ref for m in relation.members if m.type == 'w')
                nodes.update(m.ref for m in relation.members if m.type == 'n')
    Select().apply_file(str(source), locations=True)
    class References(osmium.SimpleHandler):
        def way(self, way):
            if way.id in ways: nodes.update(n.ref for n in way.nodes)
    References().apply_file(str(source))
    with osmium.SimpleWriter(str(output)) as writer:
        class Write(osmium.SimpleHandler):
            def node(self, n):
                if n.id in nodes: writer.add_node(n)
            def way(self, w):
                if w.id in ways: writer.add_way(w)
            def relation(self, r):
                if r.id in relations: writer.add_relation(r)
        Write().apply_file(str(source))
    def sha(path):
        h=hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        return h.hexdigest()
    report={'source_sha256':sha(source),'output_sha256':sha(output),'bbox_wgs84':bbox,
            'ways':len(ways),'nodes':len(nodes),'turn_restrictions':len(relations),
            'license':'OpenStreetMap contributors, ODbL 1.0',
            'selection':'Highways with a node inside bbox, expanded to complete restriction member ways; full way nodes retained'}
    output.with_suffix('.provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--bbox',nargs=4,type=float,required=True,metavar=('WEST','SOUTH','EAST','NORTH'))
    a=p.parse_args();extract(a.source,a.output,a.bbox)
