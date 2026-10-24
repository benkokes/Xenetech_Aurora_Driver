import copy
from dataclasses import replace
from decimal import Decimal
import tempfile
from pathlib import Path
import unittest

from aurora_jobserver.artwork import ProcessSettings, Scene
from aurora_jobserver.corel_layout import COREL_GRID
from aurora_jobserver.jbs import prepare
from aurora_jobserver.sender import send_job
from aurora_jobserver.store import JobStore
from aurora_jobserver.vector_only import HAIRLINE_MAX_MM, encode_candidate
from aurora_jobserver.wire import raster_plan
from aurora_jobserver.worker import process_one
from tools.compare_preference_jobs import decode
from tools.controller_simulator import ControllerSimulator
from aurora_jobserver.transport import Timing


class VectorOnlyCandidateTests(unittest.TestCase):
    def scene(self):
        return Scene({'dpi':167,'raster_grid':COREL_GRID,'text_rendering':'outline-aliased',
                      'cut_paths_only':True,'cut_color':'any','max_cut_width_mm':HAIRLINE_MAX_MM},
                     {'exposure':None},b'',(((1002,1002),(2004,1002),(2004,2004),(1002,1002)),))

    def process(self):
        return ProcessSettings(30000,Decimal('88.73'),1000,Decimal('25.35'),1000)

    def test_only_blank_zero_power_carrier_and_requested_vectors_are_encoded(self):
        scene=self.scene();original=copy.deepcopy(scene)
        raw,cg=encode_candidate(scene,self.process())
        job=decode(cg)
        self.assertEqual(job['vector_paths'][0]['points'],[[1002.0,1002.0],[2004.0,1002.0],[2004.0,2004.0],[1002.0,1002.0]])
        self.assertEqual(len(job['rasters']),1)
        raster=job['rasters'][0]
        self.assertEqual((raster['width'],raster['height'],raster['pixels']),(1,1,b'\0'))
        self.assertEqual(raster['settings']['power'],0)
        self.assertNotIn(b'88.73 power',raw)
        self.assertIn(b'25.35 power',raw)
        self.assertFalse(prepare(cg,allow_draft=True).auto_start)
        self.assertEqual(scene,original)
        with self.assertRaisesRegex(ValueError,'uncalibrated draft'):
            raster_plan(cg,r'c:\xfiles\jbs\Convert\Default.jbs')

    def test_empty_or_ambiguous_candidates_are_rejected_before_encoding(self):
        scene=self.scene()
        for invalid in (replace(scene,paths=()),
                        replace(scene,manifest=dict(scene.manifest,cut_color='#FF0000')),
                        replace(scene,manifest=dict(scene.manifest,max_cut_width_mm=0.2))):
            with self.assertRaises(ValueError):encode_candidate(invalid,self.process())

    def test_candidate_uses_existing_wire_profile_once_on_loopback(self):
        _,data=encode_candidate(self.scene(),self.process(),draft=False)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'candidate.jbs';source.write_bytes(data)
            store=JobStore(root/'queue');job=store.submit(source);process_one(store)
            with ControllerSimulator(data,echo=False,fragment=True) as sim:
                result=send_job(store,job,sim.endpoint,r'c:\xfiles\jbs\Convert\Default.jbs',
                                timing=Timing(connect=1,handshake=1,job=3,sync_delay=.005,
                                              feature_delay=.005,sync_quiet=.005),locks=root/'locks')
                self.assertEqual(result['state'],'completed')
                self.assertTrue(sim.upload_received.is_set())
                self.assertEqual(bytes(sim.main_tx),b''.join(s.request for s in raster_plan(data,r'c:\xfiles\jbs\Convert\Default.jbs')))
            self.assertEqual(sum(e['kind']=='uploaded' for e in store.history(job)),1)
            self.assertFalse(list((root/'locks').glob('*.pending.json')))


if __name__=='__main__':unittest.main()
