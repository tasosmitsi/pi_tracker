import logging
import os
import tempfile
import unittest
from unittest import mock

from pi_tracker import log_setup


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.log_file = os.path.join(self.dir.name, 'logs', 'pi_tracker.log')
        patcher = mock.patch.object(log_setup, 'LOG_FILE', self.log_file)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.env = mock.patch.dict(os.environ)  # the tests set or clear JOURNAL_STREAM
        self.env.start()
        os.environ.pop('JOURNAL_STREAM', None)

    def tearDown(self):
        root = logging.getLogger()
        for handler in (log_setup._console, log_setup._file):
            if handler is not None:
                root.removeHandler(handler)
                handler.close()
        log_setup._console = log_setup._file = None
        root.setLevel(logging.WARNING)
        self.env.stop()

    def written(self):
        log_setup._file.flush()
        with open(self.log_file) as f:
            return f.read()

    def test_sets_the_level_by_name(self):
        log_setup.setup('debug')
        self.assertEqual(logging.getLogger().level, logging.DEBUG)

    def test_unknown_level_falls_back_to_info(self):
        with self.assertLogs('pi_tracker.log_setup', 'WARNING'):
            log_setup.setup('loud')
        self.assertEqual(logging.getLogger().level, logging.INFO)

    def test_calling_again_changes_the_settings_without_more_handlers(self):
        log_setup.setup('INFO')
        log_setup.setup('ERROR', max_kb=2, backups=3)
        root = logging.getLogger()
        self.assertEqual([h for h in root.handlers if h in (log_setup._console, log_setup._file)],
                         [log_setup._file, log_setup._console])
        self.assertEqual(root.level, logging.ERROR)
        self.assertEqual((log_setup._file.maxBytes, log_setup._file.backupCount), (2048, 3))

    def test_by_hand_it_logs_to_the_file_and_the_terminal(self):
        log_setup.setup()
        logging.getLogger('pi_tracker.test').info('hello')
        self.assertRegex(self.written(), r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} INFO pi_tracker.test: hello\n$')
        self.assertIsNotNone(log_setup._console)
        self.assertIn('asctime', log_setup._console.formatter._fmt)

    def test_under_systemd_it_logs_to_the_file_only(self):
        os.environ['JOURNAL_STREAM'] = '8:12345'
        log_setup.setup()
        logging.getLogger('pi_tracker.test').info('hello')
        self.assertIn('INFO pi_tracker.test: hello', self.written())
        self.assertIsNone(log_setup._console)

    def test_the_level_applies_to_the_file(self):
        log_setup.setup('WARNING')
        logging.getLogger('pi_tracker.test').info('too chatty')
        logging.getLogger('pi_tracker.test').warning('worth keeping')
        self.assertNotIn('too chatty', self.written())
        self.assertIn('worth keeping', self.written())

    def test_the_file_rotates(self):
        log_setup.setup(max_kb=1, backups=2)
        for _ in range(100):  # about 8 KB
            logging.getLogger('pi_tracker.test').warning('x' * 40)
        files = sorted(os.listdir(os.path.dirname(self.log_file)))
        self.assertEqual(files, ['pi_tracker.log', 'pi_tracker.log.1', 'pi_tracker.log.2'])
        self.assertLessEqual(os.path.getsize(self.log_file), 1024)

    def test_an_unwritable_log_file_falls_back_to_the_journal(self):
        os.environ['JOURNAL_STREAM'] = '8:12345'
        open(os.path.join(self.dir.name, 'logs'), 'w').close()  # a file where the folder should be
        with self.assertLogs('pi_tracker.log_setup', 'WARNING') as logs:
            log_setup.setup()
        self.assertIsNone(log_setup._file)
        self.assertIsNotNone(log_setup._console)  # so nothing is lost
        self.assertIn("Can't write the log file", logs.output[0])


if __name__ == '__main__':
    unittest.main()
