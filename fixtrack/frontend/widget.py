from PyQt5 import QtCore, QtWidgets

from fixtrack.frontend.canvas import VideoCanvas
from fixtrack.frontend.player_head import PlayerHeadWidget
from fixtrack.frontend.track_controls import TrackEditLayoutBar
from fixtrack.frontend.track_controls import TopLevelControls


class VideoWidget(QtWidgets.QWidget):
    """
    Main GUI component for the FixTrack application.

    This widget organizes and manages the main elements of the interface,
    including the video canvas, track editing controls, player controls,
    and top-level control buttons.

    Attributes:
        _parent (FixtrackWindow): Reference to the parent window.
        top_level_ctrls (TopLevelControls): Button controls for track management (save, link, etc.).
        canvas (VideoCanvas): Widget for rendering the video and overlays.
        scroll_area (QtWidgets.QScrollArea): Scrollable area containing track editing controls.
        track_edit_bar (TrackEditLayoutBar): Interface for editing tracks (adding/selecting).
        player_controls (PlayerHeadWidget): Timeline controls and playback buttons.
    """
    mutated = QtCore.pyqtSignal(bool)

    def __init__(
        self, parent, fname_video=None, fname_track=None, range_slider=True, bgcolor="white"
    ):
        """
        Initializes the VideoWidget and lays out all subcomponents.

        Args:
            parent (FixtrackWindow): Parent window of this widget.
            fname_video (str, optional): Path to the video file to be displayed.
            fname_track (str, optional): Path to the tracking file to load overlays.
            range_slider (bool, optional): Whether to include the range slider in the player controls.
            bgcolor (str, optional): Background color for the video canvas.
        """
        super().__init__(parent)
        self._parent = parent

        self.top_level_ctrls = TopLevelControls(self)

        self.canvas = VideoCanvas(
            self, fname_video=fname_video, fname_track=fname_track, bgcolor=bgcolor
        )

        self.canvas.native.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        self.canvas.create_native()
        self.canvas.native.setParent(self)

        self.scroll_area = QtWidgets.QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        sp = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.scroll_area.setSizePolicy(sp)
        self.scroll_area.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setup_track_edit_bar()

        vl2 = QtWidgets.QVBoxLayout()
        vl1 = QtWidgets.QVBoxLayout()

        vl2.addWidget(self.canvas.native)
        self.player_controls = PlayerHeadWidget(
            self, self.canvas.video, range_slider=range_slider
        )
        vl2.addWidget(self.player_controls)

        hl1 = QtWidgets.QHBoxLayout()

        vl1.addWidget(self.top_level_ctrls)
        vl1.addWidget(self.scroll_area)

        hl1.addLayout(vl1)
        hl1.addLayout(vl2)
        self.setLayout(hl1)

        self.player_controls.sig_frame_change.connect(self.canvas.on_frame_change)
        self.player_controls.sig_frame_change.emit(0)

    def setup_track_edit_bar(self, select_last=False):
        """
        Initializes the track editing bar with track selectors.

        Args:
            select_last (bool, optional): If True, selects the last track by default.
            Otherwise, the first track is selected.
        """
        self.track_edit_bar = TrackEditLayoutBar(self)
        for i in range(self.canvas.tracks.num_tracks):
            last = i == (self.canvas.tracks.num_tracks - 1)
            select = (i == 0)
            if select_last:
                select = last
            self.track_edit_bar.add_track(index=i, select=select, last=last)

        self.scroll_area.setWidget(self.track_edit_bar)

    def idx_selected(self):
        """
        Returns the index of the currently selected track.

        Returns:
            int: Index of the selected track.
        """
        return self.track_edit_bar.idx_selected()

    def keyPressEvent(self, event):
        """
        Handles keyboard shortcuts for quick GUI operations.

        Supported keys:
            Ctrl + Q       → Quit
            Ctrl + S       → Save tracks
            Ctrl + Shift + S → Save tracks with shift behavior
            Ctrl + B       → Break track
            Ctrl + L       → Link track
            Ctrl + N       → Add new track
            Ctrl + Z       → Undo
            Ctrl + Shift + Z → Redo
            Space          → Toggle play/pause
            Left Arrow     → Go to previous frame
            Right Arrow    → Go to next frame
            C              → Toggle camera overlay
            V              → Toggle visibility of main image layer
            [              → Set start of frame range
            ]              → Set end of frame range
        """
        key = event.key()
        if key == QtCore.Qt.Key_Escape:
            self.parent().fileQuit()

        c0 = event.modifiers() == QtCore.Qt.ControlModifier
        c1 = event.modifiers() == (QtCore.Qt.ShiftModifier | QtCore.Qt.ControlModifier)
        if key == QtCore.Qt.Key_Q and c0:
            self.parent().fileQuit()
        elif key == QtCore.Qt.Key_S and c0:
            self.top_level_ctrls.btn_save_tracks.animateClick()
        elif key == QtCore.Qt.Key_S and c1:
            self.top_level_ctrls.btn_save_tracks.animateShiftClick()
        elif key == QtCore.Qt.Key_B and c0:
            self.top_level_ctrls.btn_break.animateClick()
        elif key == QtCore.Qt.Key_L and c0:
            self.top_level_ctrls.btn_link.animateClick()
        elif key == QtCore.Qt.Key_N and c0:
            self.top_level_ctrls.btn_add_track.animateClick()
        elif key == QtCore.Qt.Key_Z and c0:
            self.top_level_ctrls.btn_undo.animateClick()
        elif key == QtCore.Qt.Key_Z and c1:
            self.top_level_ctrls.btn_redo.animateClick()
        elif key == QtCore.Qt.Key_Space:
            self.player_controls.toggle_play()
        elif key == QtCore.Qt.Key_Left:
            self.player_controls.decr()
        elif key == QtCore.Qt.Key_Right:
            self.player_controls.incr()
        elif key == QtCore.Qt.Key_C:
            self.canvas.toggle_cam()
        elif key == QtCore.Qt.Key_V:
            self.canvas.visuals["img"].visible ^= True
        elif key == QtCore.Qt.Key_BracketLeft:
            self.player_controls.range_slider.setFirstPosition(self.player_controls.frame_num)
            self.canvas.on_frame_change()
        elif key == QtCore.Qt.Key_BracketRight:
            self.player_controls.range_slider.setSecondPosition(self.player_controls.frame_num)
            self.canvas.on_frame_change()
