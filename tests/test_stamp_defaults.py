from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aurora_jobserver.classic_settings import carriers, decode, ensure_supported, parse
from tests.test_classic_settings import payload
from tools.inspect_stamp_defaults import builder_dpi, f32, inspect, predict


REGISTRY = Path('analysis/extracted/laser-driver/NewWorld_Files/XGWRegistry.dll')


def first():
    return {'Scale': f32(.03), 'Base': f32(.012), 'Shoulder': f32(.004), 'Gradient': f32(.6)}


def second():
    return {'Scale': f32(.0625), 'Base': f32(.02), 'Shoulder': f32(.01), 'Gradient': f32(.3)}


class StampPredictionTests(unittest.TestCase):
    def test_dpi_adapter_uses_surface_mapping_and_explicit_binary32_store(self):
        self.assertEqual(builder_dpi(167),166.66700744628906)
        self.assertEqual(builder_dpi(333),333.3330078125)
        self.assertEqual(builder_dpi(250),250.00001525878906)
        self.assertNotEqual(builder_dpi(167),167)
        for invalid in (True,0,168,167.0):
            with self.assertRaises(ValueError): builder_dpi(invalid)

    def test_command_arguments_follow_serializer_order_not_getter_call_order(self):
        self.assertEqual(predict(first(),167)['arguments'],[3,1,60])
        self.assertEqual(predict(second(),167)['arguments'],[5,2,30])
        self.assertEqual(predict(first(),500)['arguments'],[8,2,60])
        # Binary32 adapter conversion moves the nominal 2.5 shoulder sample
        # just above the half-way boundary at 250 DPI; it becomes three.
        self.assertEqual(predict(second(),250)['arguments'],[8,3,30])
        self.assertEqual(predict(first(),50)['arguments'],[1,1,60])

    def test_scale_is_not_read_by_this_command_and_validation_stays_predictive(self):
        self.assertEqual(predict(first(),167),predict({**first(),'Scale':f32(.9)},167))
        result=predict(first(),167)
        self.assertIn('not_xp_capture',result['validation'])
        self.assertNotIn('!ZX',result['predicted_command'])
        for invalid in ({}, {**first(),'Base':float('nan')}, {**first(),'Gradient':1.1}):
            with self.assertRaises(ValueError): predict(invalid,167)

    def test_stamp_remains_held_without_any_encoding_or_network(self):
        encoded=payload(RubberStamp=True)
        with patch('socket.socket') as socket, patch('aurora_jobserver.print_pipeline._encode') as encoder:
            settings=decode(carriers(parse(encoded)),encoded)
            with self.assertRaisesRegex(ValueError,'RubberStamp'): ensure_supported(settings)
            encoder.assert_not_called();socket.assert_not_called()

    @unittest.skipUnless(REGISTRY.exists(),'Private archived registry and adapter binaries required')
    def test_archived_instructions_vtable_defaults_and_all_45_predictions(self):
        with patch('socket.socket') as socket:
            report=inspect(REGISTRY)
            self.assertEqual(len(report['profiles']),5)
            self.assertEqual(sum(len(p['predictions']) for p in report['profiles']),45)
            self.assertEqual(report['profiles'][0]['fallback_values'],first())
            self.assertEqual(report['profiles'][1]['fallback_values'],second())
            self.assertEqual([p['predictions'][2]['arguments'][-1] for p in report['profiles']],[60,30,50,70,90])
            self.assertFalse(report['vendor_module_loaded_or_executed'])
            self.assertFalse(report['registry_access_performed'])
            self.assertFalse(report['physical_device_io_performed'])
            socket.assert_not_called()
        with tempfile.TemporaryDirectory() as temp:
            bad=Path(temp)/'other.dll';bad.write_bytes(b'not the inspected archive')
            with self.assertRaisesRegex(ValueError,'address map'):inspect(bad)


if __name__=='__main__':unittest.main()
