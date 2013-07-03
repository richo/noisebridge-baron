import StringIO
import json
import os
import tempfile
import unittest
import urllib2

import baron

class BaronTestCase(unittest.TestCase):

    def setUp(self):
        urllib2.urlopen = self.urlopen
        baron.keypad = DummySerial()
        baron.codes = ['42']
        baron.last_mtime = 0
        self.api_open_success = True
        self.urlopen_data = None
        baron.promiscuous = False
        baron.codes_path = os.path.join(os.path.dirname(__file__), 'codes.txt.example')

    def urlopen(self, url, data):
        self.urlopen_data = data
        return DummyResult(json.dumps({"open": self.api_open_success}))

    def door_loop(self):
        loop = baron.DoorLoop()
        [loop.step() for x in range(10)]

    def test_check_code_should_open_door_and_show_blue_led_and_play_happy_sound_for_valid_code(self):
        baron.check_code('42', reload_codes=False)
        self.assertEquals('open=1', self.urlopen_data)
        self.assertEquals(['BH'], baron.keypad.output)

    def test_check_code_should_not_open_door_and_show_red_led_and_play_sad_sound_for_invalid_code(self):
        baron.check_code('666', reload_codes=False)
        self.assertEquals(None, self.urlopen_data)
        self.assertEquals(['SR'], baron.keypad.output)

    def test_check_code_should_play_fail_sequence_if_api_returns_error(self):
        self.api_open_success = False
        baron.check_code('42', reload_codes=False)
        self.assertEquals(['SR', 'QSR', 'QSR'], baron.keypad.output)

    def test_load_codes(self):
        baron.load_codes()
        self.assertEquals(['12345', '2169', '42'], baron.codes)

    def test_door_loop_should_open_door_for_valid_code(self):
        baron.keypad.add_input('42#')
        self.door_loop()
        self.assertEquals('open=1', self.urlopen_data)

    def test_door_loop_should_not_open_door_for_invalid_code(self):
        baron.keypad.add_input('666#')
        self.door_loop()
        self.assertEquals(None, self.urlopen_data)

    def test_door_loop_should_not_open_door_for_valid_code_without_pound_key(self):
        baron.keypad.add_input('42')
        self.door_loop()
        self.assertEquals(None, self.urlopen_data)

    def test_door_loop_should_reset_buffer_on_star_key(self):
        baron.keypad.add_input('666*42#')
        self.door_loop()
        self.assertEquals('open=1', self.urlopen_data)

    def test_door_loop_should_ignore_nondigits(self):
        baron.keypad.add_input('as4df2jk#')
        self.door_loop()
        self.assertEquals('open=1', self.urlopen_data)

    def test_door_loop_should_ignore_empty_code(self):
        baron.keypad.add_input('#')
        self.door_loop()
        self.assertEquals(None, self.urlopen_data)

    def test_door_loop_should_open_door_for_any_keypress_in_promiscuous_mode(self):
        baron.promiscuous = True
        baron.keypad.add_input('4')
        self.door_loop()
        self.assertEquals('open=1', self.urlopen_data)

    def test_door_loop_should_not_open_door_without_keypress_in_promiscuous_mode(self):
        baron.promiscuous = True
        baron.keypad.add_input('')
        self.door_loop()
        self.assertEquals(None, self.urlopen_data)

class DummySerial(object):

    def __init__(self):
        self.input = ''
        self.output = []
    
    def write(self, data):
        self.output.append(data)

    def read(self, length):
        result = self.input[:length]
        self.input = self.input[length:]
        return result

    def add_input(self, data):
        self.input += data


class DummyResult(object):

    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

if __name__ == '__main__':
    unittest.main()
