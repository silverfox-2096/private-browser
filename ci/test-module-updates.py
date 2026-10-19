#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('updates', Path(__file__).with_name('module-updates.py'))
updates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updates)


class ReportTests(unittest.TestCase):
    def test_concatenated_source_records(self):
        report = updates.render('{"Path":"example/main","Main":true}\n'
                                '{"Path":"example/dep","Version":"v1.0.0","Update":{"Version":"v1.1.0"}}')
        self.assertIn('2 module records; 1 available updates', report)
        self.assertIn('| example/dep | v1.0.0 | v1.1.0 |', report)

    def test_no_updates_is_observation(self):
        self.assertIn('0 available updates', updates.render('{"Path":"example/dep","Version":"v1.0.0"}'))

    def test_unavailable_or_malformed_is_not_success(self):
        for text in ['', ' ', '[]', '{"Path":42}', '{"Path":"x"} trailing',
                     '{"Path":"x","Version":"v1.0.0","Update":{}}']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                updates.render(text)


if __name__ == '__main__':
    unittest.main()
