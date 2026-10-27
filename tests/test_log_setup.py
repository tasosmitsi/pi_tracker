import logging
import os
import unittest
from unittest import mock

import log_setup


class SetupTest(unittest.TestCase):
    def tearDown(self):
        root = logging.getLogger()
        if log_setup._handler is not None:
            root.removeHandler(log_setup._handler)
            log_setup._handler = None
        root.setLevel(logging.WARNING)

    def test_sets_the_level_by_name(self):
        log_setup.setup('debug')
        self.assertEqual(logging.getLogger().level, logging.DEBUG)

    def test_unknown_level_falls_back_to_info(self):
        with self.assertLogs('log_setup', 'WARNING'):
            log_setup.setup('loud')
        self.assertEqual(logging.getLogger().level, logging.INFO)

    def test_calling_again_changes_the_level_without_a_second_handler(self):
        log_setup.setup('INFO')
        log_setup.setup('ERROR')
        ours = [h for h in logging.getLogger().handlers if h is log_setup._handler]
        self.assertEqual(len(ours), 1)
        self.assertEqual(logging.getLogger().level, logging.ERROR)

    def test_timestamps_by_hand_but_not_under_systemd(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            log_setup.setup()
        self.assertIn('asctime', log_setup._handler.formatter._fmt)

        self.tearDown()
        with mock.patch.dict(os.environ, {'JOURNAL_STREAM': '8:12345'}):
            log_setup.setup()
        self.assertNotIn('asctime', log_setup._handler.formatter._fmt)


if __name__ == '__main__':
    unittest.main()
