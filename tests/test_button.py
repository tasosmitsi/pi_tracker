import unittest

from pi_tracker import alarm, button


class FakeStatus:
    def __init__(self, replies):
        self.replies = list(replies)
        self.accepted = []

    def GetButtonEvents(self):
        # Raises IndexError if the code reads more often than it should
        return self.replies.pop(0)

    def AcceptButtonEvent(self, name):
        self.accepted.append(name)


class FakePiJuice:
    def __init__(self, *replies):
        self.status = FakeStatus(replies)


def events(sw1):
    return {'data': {'SW1': sw1, 'SW2': 'NO_EVENT', 'SW3': 'NO_EVENT'}, 'error': 'NO_ERROR'}


BUS_ERROR = {'error': 'COMMUNICATION_ERROR'}


class CheckButtonTest(unittest.TestCase):
    def setUp(self):
        button._last_error = None
        self.saved = alarm.current
        alarm.current = alarm.AlarmState()

    def tearDown(self):
        alarm.current = self.saved

    def test_single_press_arms_and_is_accepted(self):
        pijuice = FakePiJuice(events('SINGLE_PRESS'))
        self.assertTrue(button.check_button(pijuice))
        self.assertEqual(alarm.current.state, alarm.ARMED)
        self.assertEqual(pijuice.status.accepted, ['SW1'])

    def test_single_press_while_armed_changes_nothing_but_is_accepted(self):
        alarm.current.arm()
        pijuice = FakePiJuice(events('SINGLE_PRESS'))
        button.check_button(pijuice)
        self.assertEqual(alarm.current.state, alarm.ARMED)
        self.assertEqual(pijuice.status.accepted, ['SW1'])

    def test_no_event_does_nothing(self):
        pijuice = FakePiJuice(events('NO_EVENT'))
        self.assertTrue(button.check_button(pijuice))
        self.assertEqual(alarm.current.state, alarm.DISARMED)
        self.assertEqual(pijuice.status.accepted, [])

    def test_long_press_is_left_for_the_pijuice_software(self):
        pijuice = FakePiJuice(events('LONG_PRESS1'))
        button.check_button(pijuice)
        self.assertEqual(alarm.current.state, alarm.DISARMED)
        self.assertEqual(pijuice.status.accepted, [])

    def test_an_error_is_read_once_per_call_and_logged_once(self):
        pijuice = FakePiJuice(BUS_ERROR, BUS_ERROR, BUS_ERROR)
        with self.assertLogs('pi_tracker.button', 'WARNING') as logs:
            for _ in range(3):
                self.assertTrue(button.check_button(pijuice))
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(pijuice.status.replies, [])

    def test_recovery_after_an_error_is_logged(self):
        pijuice = FakePiJuice(BUS_ERROR, events('NO_EVENT'))
        with self.assertLogs('pi_tracker.button', 'INFO') as logs:
            button.check_button(pijuice)
            button.check_button(pijuice)
        self.assertIn('read again', logs.output[-1])


if __name__ == '__main__':
    unittest.main()
