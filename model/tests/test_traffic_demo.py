import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET


def load(name, relative):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/relative)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

resampler=load('resample_demo','tools/resample_traffic_demo.py')
preparation=load('demo_network','src/traffic/demo_network.py')


class TrafficDemoTests(unittest.TestCase):
    def test_resampling_reproducible_and_source_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.xml'
            source.write_text('<routes><vType id="car"/><vehicle id="source" type="car" depart="0"><route edges="a b c"/></vehicle></routes>')
            before=source.read_bytes()
            for name in ('a','b'):resampler.resample(source,root/name,12,60,42)
            self.assertEqual((root/'a/routes.rou.xml').read_bytes(),(root/'b/routes.rou.xml').read_bytes())
            vehicles=ET.parse(root/'a/routes.rou.xml').getroot().findall('vehicle')
            self.assertEqual(len({v.get('id') for v in vehicles}),12)
            self.assertTrue(all(0<=float(v.get('depart'))<60 for v in vehicles))
            self.assertEqual([float(v.get('depart')) for v in vehicles],sorted(float(v.get('depart')) for v in vehicles))
            self.assertTrue(all(v.find('route').get('edges')=='a b c' for v in vehicles))
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual(json.loads((root/'a/provenance.json').read_text())['requested_departures'],12)

    def test_bad_rate_rejected_before_sumo_or_output(self):
        for rate in (0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):preparation.build_demand('missing','unused',rate,60,42)

    def test_partial_osm_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);osm=root/'in.xml';osm.write_text('<osm><remark>timeout</remark><way id="1"/></osm>')
            with self.assertRaises(ValueError):preparation.build_network(osm,root/'scenario.json',root/'out')
            self.assertFalse((root/'out').exists())

    def test_invalid_interval_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'out'
            with self.assertRaises(ValueError):resampler.resample(Path('missing'),output,1,float('nan'),42)
            self.assertFalse(output.exists())

    def test_vehicle_mix_is_complete(self):
        self.assertAlmostEqual(sum(v[1] for v in preparation.VEHICLES.values()),1)
        self.assertEqual(len(preparation.VEHICLES),6)

    def test_conflicting_protected_greens_rejected_by_audit(self):
        with tempfile.TemporaryDirectory() as folder:
            network=Path(folder)/'network.xml'
            network.write_text('<net><tlLogic id="t"><phase state="GG"/></tlLogic>'
                '<junction id="j" intLanes="a b"><request index="0" foes="10"/>'
                '<request index="1" foes="01"/></junction>'
                '<connection via="a" tl="t" linkIndex="0"/>'
                '<connection via="b" tl="t" linkIndex="1"/></net>')
            self.assertEqual(len(preparation.audit_signals(network)['conflicting_protected_greens']),1)
            network.write_text(network.read_text().replace('state="GG"','state="Gr"'))
            self.assertEqual(preparation.audit_signals(network)['conflicting_protected_greens'],[])
