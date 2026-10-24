from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from aurora_jobserver.jbs import prepare
from aurora_jobserver.store import JobStore
from aurora_jobserver.wire import raster_plan
from aurora_jobserver.worker import process_one


def raw(pixels=b'\x80\xff'):
    return (b'!ZX\rJOB Import\rPU\r2 RA\r0.0 0.0 V\rPICT-UL\r'
            +struct.pack('<HIIIIH',0x58c3,len(pixels),1,167,167,0x41)
            +pixels+b'\0\xffPU\r0. 0. V\rEND_PLOT\r')


class HostPreprocessingTests(unittest.TestCase):
    def test_known_stamp_directives_are_held_in_raw_and_compressed_jobs(self):
        for source in (raw(),prepare(raw()).data):
            for directive in (b'3 1 60 set_stamp_mode\r',b'0 0 0 set_stamp_mode\r',
                              b'1 set_stamp_action\r',b'3 1 60 set_stamp_mode\nPU\r',
                              b'3 1 60set_stamp_mode\r',b'1set_stamp_action\r'):
                with self.subTest(directive=directive,compressed=b'cG' in source):
                    job=source.replace(b'JOB Import\r',b'JOB Import\r'+directive)
                    with self.assertRaisesRegex(ValueError,'preprocessing is not implemented'):prepare(job)
                    with self.assertRaisesRegex(ValueError,'preprocessing is not implemented'):
                        raster_plan(job,r'c:\xfiles\jbs\Convert\Default.jbs')

    def test_directive_words_inside_valid_raster_pixels_are_not_commands(self):
        source=raw(b'3 1 60set_stamp_mode\r1set_stamp_action\r')
        result=prepare(source)
        self.assertEqual(result.rasters,1)
        self.assertEqual(prepare(result.data).data,result.data)
        self.assertEqual(len(raster_plan(result.data,r'c:\xfiles\jbs\Convert\Default.jbs')),8)

    def test_import_queue_fails_before_prepared_artifact_or_network_access(self):
        with tempfile.TemporaryDirectory() as temp, patch('socket.socket') as socket:
            root=Path(temp);source=root/'stamp.jbs'
            source.write_bytes(raw().replace(b'JOB Import\r',b'JOB Import\r3 1 60 set_stamp_mode\r'))
            store=JobStore(root/'queue');job=store.submit(source)
            process_one(store)
            self.assertEqual(store.get(job)['state'],'failed')
            self.assertIn('Rubber-stamp job preprocessing',store.get(job)['error'])
            self.assertFalse((store.directory(job)/'prepared.jbs').exists())
            socket.assert_not_called()


if __name__=='__main__':unittest.main()
