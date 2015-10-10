import sys
from PySide.QtCore import *
from PySide.QtGui import *
from PySide.QtDeclarative import QDeclarativeView
__author__ = 'midvikus'


class QtUI(object):

    def __init__(self):
        # Create Qt application and the QDeclarative view
        self.app = QApplication(sys.argv)
        self.view = QDeclarativeView()

    def start(self):
        # Create an URL to the QML file
        url = QUrl('view.qml')
        # Set the QML file and show
        self.view.setSource(url)
        self.view.show()
        # Enter Qt main loop
        sys.exit(self.app.exec_())

if __name__ == '__main__':
    ui = QtUI()
    ui.start()