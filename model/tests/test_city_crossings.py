"""Fictional geometry verifies crossing mapping and explicitly replayed traffic."""
import copy
import unittest
import shapely
from shapely.geometry import LineString
from healthy_route.city_crossings import annotate_crossings,current_traffic_windows,apply_crossing_waits
from healthy_route.city_walk import selected_walk


class CityCrossingTests(unittest.TestCase):
    def traffic(self,frames=None):
        return dict(position_reference='front_bumper',coordinate_frame='ENU',center=[0,0],radius=100,
            vehicle_types={'car':dict(length=4,width=2)},
            lanes=[dict(shape=[[-50,0],[50,0,0]])],
            frames=frames or [dict(time=t,vehicles=[]) for t in [10,11,13]],
            signals=dict(recorded_interval=[10,14]))

    def crossing(self):
        return dict(id='cross',segments=[[[0,-5,0],[0,5,0]]],length_m=10)

    def test_crosswalk_ranges_split_only_existing_path_and_preserve_original(self):
        from healthy_route.source_walking_network import project
        origin=dict(longitude=0,latitude=0);coords=[[0,0],[.0002,0]];xy=project(coords,origin)
        points=[[float(x),float(y),0] for x,y in xy]
        network=dict(nodes={'a':points[0],'b':points[1]},edges=[dict(u='a',v='b',points=points,source_segment='s',level=[0,False])],components=[['a','b']])
        source=dict(id='s',geometry=shapely.to_wkb(LineString(coords)),subclass=None,subclass_rules=[dict(value='crosswalk',between=[.25,.75])])
        before=copy.deepcopy(network);out=annotate_crossings(network,{'s':source},origin)
        self.assertEqual(network,before);self.assertEqual(out['crossing_mapping']['new_connections'],0)
        self.assertEqual(len(out['edges']),3);self.assertEqual(sum(e['crossing_id'] is not None for e in out['edges']),1)
        self.assertAlmostEqual(sum(e['distance'][-1] for e in out['edges']),points[1][0])
        for a,b in zip(out['edges'],out['edges'][1:]):self.assertEqual(a['points'][-1],b['points'][0]);self.assertEqual(a['v'],b['u'])
        network['edges'][0]['level']=[1,True]
        self.assertEqual(annotate_crossings(network,{'s':source},origin)['crossings'],[])

    def test_front_bumper_reference_and_unknown_coverage(self):
        t=self.traffic();t['vehicle_types']['car']['length']=16
        for f in t['frames']:f['vehicles']=[['a','car',16,0,0,0,0,0]]
        windows,_=current_traffic_windows(t,[self.crossing()]);self.assertFalse(windows['cross'].clear(0,.1))
        t['lanes']=[]
        windows,clock=current_traffic_windows(t,[self.crossing()]);self.assertEqual(windows,{})
        self.assertEqual(clock['covered_crossings'],0)

    def test_sparse_membership_and_replay_seam_never_sweep_a_teleport(self):
        frames=[dict(time=10,vehicles=[['a','car',-50,0,0,0,0,0]]),dict(time=11,vehicles=[['b','car',50,0,0,0,0,0]]),dict(time=13,vehicles=[['b','car',50,0,0,0,0,0]])]
        w,c=current_traffic_windows(self.traffic(frames),[self.crossing()]);self.assertEqual(w['cross'].blocked,())
        self.assertEqual(c['period_s'],4)
        frames[1]['vehicles'][0][0]='a'
        w,_=current_traffic_windows(self.traffic(frames),[self.crossing()]);self.assertTrue(w['cross'].blocked)

    def test_one_wait_for_consecutive_crossing_edges_and_failure_on_no_gap(self):
        nodes={'a':[0,-5,0],'b':[0,0,0],'c':[0,5,0]}
        n=dict(nodes=nodes,edges=[dict(u=u,v=v,points=[nodes[u],nodes[v]],crossing_id='cross') for u,v in [('a','b'),('b','c')]],components=[list(nodes)],crossings=[self.crossing()])
        p=dict(speed_m_s=1,crossing_red_s=45,crossing_green_s=15,crossing_clearance_s=10)
        r=selected_walk(n,'a','c',1,300)
        # No lane coverage: explicit modelled gate, not invented clear traffic.
        t=self.traffic();t['lanes']=[]
        result=apply_crossing_waits(r,n,t,0,300,p)
        self.assertEqual(result['walking_duration_s'],10)
        self.assertEqual(result['duration_s'],10+result['wait_s'])
        self.assertLessEqual(len(result['waits']),1)
        self.assertEqual(len(result['crossing_signals']),1)
        self.assertFalse(result['crossing_signals'][0]['traffic_covered'])
        self.assertEqual([e['kind'] for e in result['timeline'] if e['kind']!='Waiting'],['Crossing','Crossing'])
        t=self.traffic()
        for f in t['frames']:f['vehicles']=[['car','car',0,0,0,0,0,0]]
        with self.assertRaisesRegex(ValueError,'No crossing release'):apply_crossing_waits(r,n,t,0,300,p)
