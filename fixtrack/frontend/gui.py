import os

from fixtrack.frontend.widget import VideoWidget
from PyQt5 import QtCore, QtWidgets


class FixtrackWindow(QtWidgets.QMainWindow):
    '''
    GUI for the fixtrack application, extends QtWidgets.QMainWindow class.

    Attributes:
        title (str): title of the GUI
        main_widget (VideoWidget): ...?
    ''' 
    title = "Track Fixer"

    def __init__(self, fname_video, fname_track, range_slider=True):
        QtWidgets.QMainWindow.__init__(self)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle(self.title)
        self.statusBar().showMessage(os.path.split(fname_video)[1])
        lag = None

        # if fname_video2:
        # lag = update_offset(fname_video, fname_video2)

        bgcolor = [0.09, 0.09, 0.11]
        self.main_widget = VideoWidget(
            self,
            fname_video=fname_video,
            fname_track=fname_track,
            range_slider=range_slider,
            lag=lag,
            bgcolor=bgcolor
        )
        self.main_widget.mutated.connect(self.mutated)
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)

        # self.main_widget.show_msg.connect(self.statusBar().showMessage)

    def fileQuit(self):
        self.close()

    def closeEvent(self, ce):
        self.fileQuit()

    def mutated(self, b):
        title = self.title
        if b:
            title += "*"
        self.setWindowTitle(title)
