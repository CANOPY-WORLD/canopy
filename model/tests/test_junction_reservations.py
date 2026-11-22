import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from traffic.junction_reservations import junction_groups, junction_occupants

class JunctionReservationsTest(unittest.TestCase):
    def test_short_links_group_conflict_areas_but_keep_long_links_separate(self):
        root=ET.fromstring('<net><edge from="a" to="b"><lane length="19"/></edge><edge from="b" to="c"><lane length="20"/></edge></net>')
        groups=junction_groups(root)
        self.assertEqual(groups['a'],groups['b'])
        self.assertNotEqual(groups['a'],groups['c'])

    def test_rear_overhang_keeps_junction_occupied(self):
        keys=SimpleNamespace(VAR_LANE_ID='lane',VAR_ROAD_ID='edge',VAR_LANEPOSITION='position')
        states={'bus':{'lane':'exit_0','edge':'exit','position':15},'car':{'lane':':j_0','edge':':j','position':2}}
        result=junction_occupants(states,{'bus':10.5,'car':4.5},{'exit':'j'},{':j_0':'j'},keys)
        self.assertEqual(result,{'j':{'bus','car'}})
        states['bus']['position']=19
        self.assertEqual(junction_occupants(states,{'bus':10.5,'car':4.5},{'exit':'j'},{':j_0':'j'},keys),{'j':{'car'}})
