import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
from traffic.review_facilities import signal_facilities, crossing_facilities

NET='<net><edge id="a"><lane id="a_0" shape="0,0,2 10,0,3" width="3"/></edge><connection from="a" fromLane="0" tl="s" linkIndex="1" dir="s"/></net>'
class FacilitiesTests(unittest.TestCase):
    def test_native_link_and_recorded_initial_state(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'signals.xml'
            p.write_text('<tlsStates>'+''.join(f'<tlsState id="s" time="{t}" state="{s}" phase="0" programID="p"/>' for t,s in [(0,'Gr'),(5,'ry'),(7,'rG'),(10,'rr')])+'</tlsStates>')
            result=signal_facilities(ET.fromstring(NET),p,6,10,lambda x,y:True)
            self.assertEqual(result['heads'][0]['position'],[10,0,3])
            self.assertEqual(result['heads'][0]['link_index'],1)
            self.assertEqual([v['time'] for v in result['timeline']['s']],[5,7])
            self.assertEqual(result['recorded_interval'],[6,10])
            with self.assertRaises(ValueError):signal_facilities(ET.fromstring(NET.replace('linkIndex="1"','linkIndex="2"')),p,6,10,lambda x,y:True)
            with self.assertRaises(ValueError):signal_facilities(ET.fromstring(NET),p,-1,10,lambda x,y:True)
            p.unlink()
            self.assertIsNone(signal_facilities(ET.fromstring(NET),p,6,10,lambda x,y:True)['recorded_interval'])

    def test_only_explicit_markings_are_painted_and_clipped(self):
        try:import pyproj, shapely
        except ImportError:self.skipTest('Optional projection/geometry dependencies; run with SUMO review environment')
        net=ET.fromstring('<net><location projParameter="+proj=aeqd +lat_0=0 +lon_0=0 +datum=WGS84 +units=m" netOffset="0,0"/></net>')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source.xml'
            p.write_text('<osm><node id="1" lon="0" lat="-0.001"/><node id="2" lon="0" lat="0.001"/>'+''.join(f'<way id="{i}"><nd ref="1"/><nd ref="2"/><tag k="footway" v="crossing"/><tag k="crossing:markings" v="{mark}"/></way>' for i,mark in enumerate(['zebra','dots','no','']))+'</osm>')
            result=crossing_facilities(p,net,[{'shape':[[-10,0,2],[10,0,2]],'internal':False,'width':4}],[],lambda x,y:True)
            self.assertEqual([f['kind'] for f in result],['zebra','dots'])
            self.assertEqual(result[0]['osm_way_id'],'0')
            for feature in result:
                for x,y,z in feature['line']:
                    self.assertLessEqual(abs(y),2.00001);self.assertAlmostEqual(z,2)
