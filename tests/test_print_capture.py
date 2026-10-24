"""Real loopback LPR sessions; no spooler or engraver access."""
import json
import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import socket
import tempfile
import threading
import unittest

from aurora_jobserver.print_capture import CaptureServer


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = CaptureServer(self.root, port=0, timeout=1)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def connect(self, queue=b'aurora-capture'):
        sock = socket.create_connection(self.server.server_address, timeout=2)
        sock.sendall(b'\2' + queue + b'\n')
        self.assertEqual(sock.recv(1), b'\0' if queue == b'aurora-capture' else b'\1')
        return sock

    def send_file(self, sock, kind, payload, name):
        sock.sendall(kind + str(len(payload)).encode() + b' ' + name + b'\n')
        self.assertEqual(sock.recv(1), b'\0')
        for start in range(0, len(payload), 7):
            sock.sendall(payload[start:start+7])
        sock.sendall(b'\0')
        self.assertEqual(sock.recv(1), b'\0')

    def finish(self, sock):
        sock.shutdown(socket.SHUT_WR)
        self.assertEqual(sock.recv(1), b'')
        sock.close()

    def receipt(self):
        return list(self.root.glob('*/capture.json'))

    def job(self, data_first=False):
        previous = len(self.receipt())
        sock = self.connect()
        control = b'Hlocal\nPxws\nJCorel test\nldfA001local\n'
        data = b'PK\3\4\0\xff\n' * 100
        files = [(b'\2', control, b'cfA001local'), (b'\3', data, b'dfA001local')]
        if data_first:
            files.reverse()
        for kind, payload, name in files:
            self.send_file(sock, kind, payload, name)
        self.assertEqual(len(self.receipt()), previous)
        self.finish(sock)
        return control, data

    def test_control_then_document_durable_and_exact(self):
        control, data = self.job()
        receipt = self.receipt()[0]
        report = json.loads(receipt.read_text())
        self.assertEqual((receipt.parent / 'source.bin').read_bytes(), data)
        self.assertEqual((receipt.parent / 'control.lpr').read_bytes(), control)
        self.assertEqual(report['lpr_metadata']['J'], ['Corel test'])
        self.assertEqual(report['state'], 'captured')

    def test_document_then_control(self):
        self.job(data_first=True)
        self.assertEqual(len(self.receipt()), 1)

    def test_repeat_prints_get_distinct_snapshots(self):
        self.job()
        self.job()
        self.assertEqual(len(self.receipt()), 2)

    def test_simultaneous_prints_with_identical_lpr_names_keep_documents_separate(self):
        clients=12
        accepted=threading.Barrier(clients,timeout=6)
        def submit(index):
            control=f'Hlocal\nJConcurrent {index}\n'.encode()
            document=bytes([index])*1021+b'\0\xff\r\n'+str(index).encode()
            with self.connect() as sock:
                accepted.wait()
                self.send_file(sock,b'\2',control,b'cfA001local')
                self.send_file(sock,b'\3',document,b'dfA001local')
                self.finish(sock)
            return (control,document)
        with ThreadPoolExecutor(max_workers=clients) as workers:
            expected=list(workers.map(submit,range(clients)))
        receipts=self.receipt()
        self.assertEqual(len(receipts),clients)
        self.assertEqual(len({p.parent.name for p in receipts}),clients)
        for receipt in receipts:
            report=json.loads(receipt.read_text())
            index=int(report['lpr_metadata']['J'][0].split()[-1])
            control,document=expected[index]
            self.assertEqual((receipt.parent/'control.lpr').read_bytes(),control)
            self.assertEqual((receipt.parent/'source.bin').read_bytes(),document)
            self.assertEqual(report['files']['document']['sha256'],hashlib.sha256(document).hexdigest())
        self.assertFalse(list(self.root.glob('.receiving-*')))

    def test_abort_after_both_file_acks_retains_pending_files_without_publication(self):
        with self.connect() as sock:
            self.send_file(sock,b'\2',b'Hlocal\nJAborted after ACK\n',b'control')
            self.send_file(sock,b'\3',b'complete document',b'document')
            self.assertFalse(self.receipt())
            sock.sendall(b'\1\n')
            self.assertEqual(sock.recv(1),b'\1')
        self.assertFalse(self.receipt())
        failures=list(self.root.glob('.receiving-*/failed.json'))
        self.assertEqual(len(failures),1)
        directory=failures[0].parent
        self.assertEqual((directory/'source.bin').read_bytes(),b'complete document')
        self.assertEqual(json.loads((directory/'received.json').read_text())['state'],'received_pending_close')
        self.assertIn('aborted',json.loads(failures[0].read_text())['error'])

    def test_wrong_queue_and_unbounded_length_rejected(self):
        with self.connect(b'other'):
            pass
        with self.connect() as sock:
            sock.sendall(b'\3' + str(65 * 1024 * 1024).encode() + b' file\n')
            self.assertEqual(sock.recv(1), b'\1')
        self.assertEqual(self.receipt(), [])

    def test_truncated_data_and_bad_terminator_do_not_publish(self):
        for payload in (b'12', b'12345X'):
            with self.connect() as sock:
                sock.sendall(b'\3' + b'5 file\n')
                self.assertEqual(sock.recv(1), b'\0')
                sock.sendall(payload)
                sock.shutdown(socket.SHUT_WR)
                self.assertEqual(sock.recv(1), b'\1')
        self.assertEqual(self.receipt(), [])

    def test_abort_preserves_evidence_without_publishing(self):
        with self.connect() as sock:
            self.send_file(sock, b'\3', b'artwork', b'../../ignored')
            sock.sendall(b'\1\n')
            self.assertEqual(sock.recv(1), b'\1')
        self.assertEqual(self.receipt(), [])
        self.assertEqual(len(list(self.root.glob('.receiving-*/failed.json'))), 1)

    def test_duplicate_file_and_zero_byte_count_rejected(self):
        with self.connect() as sock:
            self.send_file(sock, b'\3', b'data', b'data')
            sock.sendall(b'\3' + b'4 data\n')
            self.assertEqual(sock.recv(1), b'\1')
        with self.connect() as sock:
            sock.sendall(b'\3' + b'0 data\n')
            self.assertEqual(sock.recv(1), b'\1')
        self.assertEqual(self.receipt(), [])

    def test_only_binds_loopback_and_exclusive_port(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        with self.assertRaises(OSError):
            CaptureServer(self.root, port=self.server.server_address[1])

    def test_two_queues_on_one_lpr_port_keep_documents_separate(self):
        direct = self.root/'direct'
        preview = self.root/'preview'
        server = CaptureServer(preview,port=0,routes={'aurora-direct':direct})
        thread = threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True)
        thread.start()
        try:
            for queue,folder in ((b'aurora-capture',preview),(b'aurora-direct',direct)):
                sock = socket.create_connection(server.server_address,timeout=2)
                sock.sendall(b'\2'+queue+b'\n')
                self.assertEqual(sock.recv(1),b'\0')
                self.send_file(sock,b'\2',b'Hhost\nJprint\n',b'control')
                self.send_file(sock,b'\3',b'printed artwork',b'document')
                self.finish(sock)
                report = json.loads(next(folder.glob('*/capture.json')).read_text())
                self.assertEqual(report['queue'],queue.decode())
                self.assertIsInstance(report['received_ns'],int)
            self.assertEqual(len(list(preview.glob('*/capture.json'))),1)
            self.assertEqual(len(list(direct.glob('*/capture.json'))),1)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
