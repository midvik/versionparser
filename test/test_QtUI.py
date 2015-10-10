from UserInterface.QtUI import QtUI
import unittest
__author__ = 'midvikus'


class QtUITestCase(unittest.TestCase):
    def setUp(self):
        self.ui = QtUI()

    def test_ui_show(self):
        self.assertTrue(self.ui.start())

if __name__ == '__main__':
    unittest.main()
