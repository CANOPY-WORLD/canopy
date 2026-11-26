"""Small fictional networks test endpoint routing, not participant predictions."""
import copy
import unittest
from healthy_route.city_walk import selected_walk


class CityWalkTests(unittest.TestCase):
    def fixture(self):
        nodes = {'a': [0,0,10], 'b': [10,0,10], 'c': [10,10,11], 'd': [0,10,11], 'island': [1,1,10]}
        edges = [dict(u=u,v=v,points=[nodes[u],nodes[v]]) for u,v in [('a','b'),('b','c'),('a','d'),('d','c')]]
        edges[2]['points'] = [nodes['a'], [-10,5,11], nodes['d']]  # Longer detour.
        return dict(nodes=nodes,edges=edges,components=[['a','b','c','d'],['island']])

    def test_endpoint_change_changes_actual_walk_and_preserves_geometry(self):
        network = self.fixture(); original = copy.deepcopy(network)
        r = selected_walk(network, 'a', 'c', 1, 30)
        self.assertEqual(r['edge_keys'], [['a','b'],['b','c']])
        self.assertEqual(r['distance_m'],20); self.assertEqual(r['duration_s'],20)
        self.assertEqual(r['timeline'][1]['start'],r['timeline'][0]['end'])
        reverse = selected_walk(network, 'c','a',2,30)
        self.assertEqual(reverse['timeline'][0]['points'],[network['nodes']['c'],network['nodes']['b']])
        self.assertEqual(reverse['duration_s'],10)
        shorter = selected_walk(network,'a','b',1,30)
        self.assertEqual(shorter['distance_m'],10)
        self.assertEqual(network,original)

    def test_no_disconnected_bridge_or_extrapolation(self):
        network = self.fixture()
        for origin,goal,speed,duration in [('a','island',1,600),('a','a',1,600),('a','absent',1,600),('a','c',1,19.9),('a','b',0,600)]:
            with self.subTest(origin=origin,goal=goal,speed=speed,duration=duration),self.assertRaises(ValueError):
                selected_walk(network,origin,goal,speed,duration)
        self.assertEqual(selected_walk(network,'a','c',1,20)['duration_s'],20)

    def test_cancellation_checkpoint(self):
        def cancel(): raise InterruptedError('cancelled')
        with self.assertRaises(InterruptedError):selected_walk(self.fixture(),'a','c',1,30,cancel)
