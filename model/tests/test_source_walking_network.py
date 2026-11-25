"""Fictional source junctions: access, missing links and height boundaries."""
import copy
import unittest
import numpy as np
from shapely.geometry import LineString
from healthy_route.source_walking_network import build_graph, access_reason
from healthy_route.city_walk import selected_walk


class SourceWalkingNetworkTests(unittest.TestCase):
    def fixture(self, lines, classes=None, connectors=None):
        classes = classes or ['footway']*len(lines)
        display = [dict(line=p, cls=c, level=0, bridge=False) for p,c in zip(lines,classes)]
        refs = connectors or [[f'{i}a',f'{i}b'] for i in range(len(lines))]
        points = {}; source=[]
        for i,(p,c,ids) in enumerate(zip(lines,classes,refs)):
            source.append(dict(id=str(i), version=1, **{'class':c}, line=LineString(p),
                               connectors=[{'connector_id':ids[0]}, {'connector_id':ids[1]}]))
            points[ids[0]]=p[0];points[ids[1]]=p[-1]
        return dict(half_m=100,roads=display),source,points

    def build(self, fixture, height=None):
        return build_graph(*fixture,height or (lambda xy,row:np.zeros(len(xy))))[0]

    def test_crossing_coordinates_do_not_create_a_junction(self):
        fixture=self.fixture([[[-10,0],[10,0]],[[0,-10],[0,10]]])
        network=self.build(fixture)
        self.assertEqual(len(network['components']),2)
        with self.assertRaises(ValueError):
            selected_walk(network,'junction:0a:0','junction:1b:0',1,600)

    def test_shared_connector_recovers_rounded_endpoint_gap(self):
        f=self.fixture([[[-10,0],[0,0]],[[0,0],[10,0]]],connectors=[['a','join'],['join','b']])
        f[0]['roads'][0]['line'][-1]=[-.05,0]
        original=copy.deepcopy(f[0])
        n=self.build(f);route=selected_walk(n,'junction:a:0','junction:b:0',1,600)
        self.assertAlmostEqual(route['distance_m'],20)
        self.assertEqual(len(n['components']),1);self.assertEqual(f[0],original)
        for a,b in zip(route['timeline'],route['timeline'][1:]):
            self.assertEqual(a['points'][-1],b['points'][0])

    def test_coincident_distinct_connectors_stay_disconnected(self):
        n=self.build(self.fixture([[[-10,0],[0,0]],[[0,0],[10,0]]]))
        self.assertEqual(len(n['components']),2)

    def test_covered_segment_is_a_real_gap(self):
        f=self.fixture([[[-10,0],[-1,0],[1,0],[10,0]]])
        f[0]['roads'][0]['covered']=[1]
        n=self.build(f);self.assertEqual(len(n['components']),2)
        with self.assertRaises(ValueError):selected_walk(n,'junction:0a:0','junction:0b:0',1,600)

    def test_shared_cycle_path_requires_foot_permission(self):
        f=self.fixture([[[-10,0],[0,0]],[[0,0],[10,0]]],['footway','cycleway'],[['a','join'],['join','b']])
        n=self.build(f);self.assertNotIn('junction:b:0',n['nodes'])
        f[1][1]['access_restrictions']=[{'access_type':'allowed','when':{'mode':['foot']}}]
        n=self.build(f);self.assertEqual(selected_walk(n,'junction:a:0','junction:b:0',1,600)['distance_m'],20)

    def test_height_disagreement_never_makes_a_bridge(self):
        f=self.fixture([[[-10,0],[0,0]],[[0,0],[10,0]]],connectors=[['a','join'],['join','b']])
        f[0]['roads'][1]['name']='upper'
        n=self.build(f,lambda xy,row:np.ones(len(xy))*(5 if row.get('name') else 0))
        self.assertEqual(len(n['components']),2)
        self.assertEqual(n['summary']['vertically_separated_connectors'],1)

    def test_access_and_tunnel_rules_fail_closed(self):
        rows=[{'access_restrictions':[{'access_type':'denied'}]},
              {'access_restrictions':[{'access_type':'allowed','when':{'recognized':['as_private']}}]},
              {'access_restrictions':[{'access_type':'allowed','when':{'during':'Mo-Fr'}}]},
              {'road_flags':[{'values':['is_tunnel']}]},
              {'prohibited_transitions':[{'when':{'mode':['foot']}}]}]
        for extra in rows:
            with self.subTest(extra=extra):self.assertIsNotNone(access_reason({'class':'footway',**extra}))
        self.assertIsNone(access_reason({'class':'footway','access_restrictions':[{'access_type':'denied','when':{'mode':['motor_vehicle']}}]}))

    def test_input_mismatch_does_not_snap_to_nearby_road(self):
        f=self.fixture([[[-10,0],[10,0]]]);f[0]['roads'][0]['line']=[[-10,.2],[10,.2]]
        n=self.build(f);self.assertEqual(n['edges'],[])
        self.assertEqual(n['summary']['unmatched_source_geometry'],1)


if __name__=='__main__':unittest.main()
