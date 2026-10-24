from copy import deepcopy
from datetime import datetime
import unittest

from aurora_jobserver.desktop_gui import completion_timing,duration_text,history_values,local_timestamp,palette_detail_lines


def completed_row():
    return {'name':'Mixed.cdr','state':'completed_with_warning','received_ns':1_700_000_000_000_000_000,
            'settings':{'process_settings':{'raster_power_percent':45,'raster_speed_native':30000,
                'vector_power_percent':15,'vector_speed_native':1000,'vector_ppi':1000}},
            'delivery':{'created':1_700_000_100,'updated':1_700_000_300,
                'result':{'state':'completed_with_warning','job_time':96.946,'end_code':'0'}}}


class HistoryTimingTests(unittest.TestCase):
    def test_per_color_cut_history_shows_palette_instead_of_ignored_global_power(self):
        row=completed_row()
        row['settings']['output_mode']='vector-only'
        row['settings']['classic_preferences']={'UseColors':True,'Colors':[
            {'Name':'Black','Enabled':True,'PowerPercent':'15','SpeedIps':'1','Ppi':1000},
            {'Name':'Red','Enabled':True,'PowerPercent':'10','SpeedIps':'1.5','Ppi':750},
            {'Name':'Blue','Enabled':False,'PowerPercent':'5','SpeedIps':'2','Ppi':500}]}
        self.assertEqual(history_values(row)[2:4],('Off','Per-color'))
        self.assertEqual(palette_detail_lines(row['settings']),[
            'Color palette (saved with this print):',
            '  Black: 15% at 1 ips; 1000 PPI',
            '  Red: 10% at 1.5 ips; 750 PPI'])

    def test_completed_time_uses_reply_receipt_and_duration_uses_controller_not_queue_wait(self):
        row=completed_row();original=deepcopy(row)
        self.assertEqual(completion_timing(row),(1_700_000_300,96.946))
        values=history_values(row)
        self.assertEqual(values[-2],datetime.fromtimestamp(1_700_000_300).strftime('%m/%d %H:%M:%S'))
        self.assertEqual(values[-1],'1:36.946')
        self.assertEqual(values[2:4],('45% / 30 ips','15% / 1 ips / 1000 PPI'))
        self.assertEqual(row,original)

    def test_operator_confirmation_does_not_invent_actual_completion_or_runtime(self):
        row=completed_row();row['delivery']['result']={'operator_outcome':'completed','note':'Observed complete'}
        self.assertEqual(completion_timing(row),(None,None))
        self.assertEqual(history_values(row)[-2:],('—','—'))

    def test_pending_failed_and_no_cut_rows_never_display_a_stale_completion(self):
        for state in ('captured_locally','awaiting_report','delivery_unknown','delivery_failed','nothing_to_cut'):
            with self.subTest(state=state):
                row=completed_row();row['state']=state
                self.assertEqual(history_values(row)[-2:],('—','—'))

    def test_unreported_duration_is_left_blank_even_when_completion_is_known(self):
        row=completed_row();del row['delivery']['result']['job_time']
        self.assertEqual(completion_timing(row),(1_700_000_300,None))
        self.assertEqual(history_values(row)[-1],'—')
        row['delivery']=None
        self.assertEqual(history_values(row)[-2:],('—','—'))

    def test_duration_carries_minutes_and_hours_without_losing_millisecond_precision(self):
        for seconds,display in ((0,'0:00.000'),(8.824,'0:08.824'),(59.9996,'1:00.000'),
                                (96.946,'1:36.946'),(3784.125,'1:03:04.125')):
            with self.subTest(seconds=seconds):self.assertEqual(duration_text(seconds),display)

    def test_invalid_or_unavailable_times_do_not_crash_history(self):
        for value in (None,True,False,'96.946',-1,float('nan'),float('inf'),1e308):
            with self.subTest(value=value):
                self.assertEqual(duration_text(value),'—')
                self.assertEqual(local_timestamp(value),'—')


if __name__=='__main__':unittest.main()
