import os

import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from fixtrack.frontend.range_slider import RangeSlider


class PlayerHeadWidget(QtWidgets.QWidget):
    """
    A widget for controlling video playback and frame navigation in FixTrack.

    This widget includes a frame slider, playback rate selector, and optional range slider
    for subsetting playback. It emits a signal when the current frame changes.

    Attributes:
        sig_frame_change (pyqtSignal): Emitted when the current frame changes (int index).

        dt (float): Time between frames in seconds (1 / fps).
        _playing (bool): Whether playback is currently active.
        video_reader (VideoReader): Provides frame metadata (e.g., FPS, num_frames).
        _ids (List[int]): List of frame IDs (0 to num_frames - 1).
        _id_2_idx (dict): Maps frame numbers to indices.
        _frame_num (int): The current frame number.
        _frame_idx (int): The index of the current frame in _ids.
        _idx_sel_a (int): Start of selected playback range.
        _idx_sel_b (int): End of selected playback range.

        play_button (QToolButton): Toggle play/pause.
        icon_play (QIcon): Play icon.
        icon_pause (QIcon): Pause icon.
        frame_text (QLineEdit): Displays frame status info (current frame and range).
        play_slider (QSlider): Slider for navigating frames.
        range_slider (RangeSlider): Optional slider for cropping playback range.
        rate_box (QComboBox): Dropdown to control playback speed.
        interval (float): Timer interval in ms, based on playback speed.
        timer (QTimer): Timer to trigger frame advancement during playback.
    """

    sig_frame_change = QtCore.pyqtSignal(int, bool)

    fname_play = os.path.join(os.path.dirname(__file__), "icons", "play.svg")
    fname_skip_ahead = os.path.join(os.path.dirname(__file__), "icons", "skip-forward.svg")
    fname_skip_back = os.path.join(os.path.dirname(__file__), "icons", "skip-back.svg")
    fname_pause = os.path.join(os.path.dirname(__file__), "icons", "pause.svg")

    
    def __init__(self, parent, video_reader, range_slider=True):
        """
        Initializes the playback and navigation controls.

        Args:
            parent (VideoWidget): Parent GUI container.
            video_reader (VideoReader): Provides video metadata (fps, num_frames).
            range_slider (bool): Whether to include the playback range slider.
        """

        QtWidgets.QWidget.__init__(self, parent)

        self.dt = 1.0 / video_reader.fps
        self._playing = False

        self.video_reader = video_reader

        self._ids = [i for i in range(self.video_reader.num_frames)]

        self._id_2_idx = {i: i for i in self._ids}
        self._frame_num = self._ids[0]
        self._frame_idx = self._id_2_idx[self._frame_num]
        self._idx_sel_a = self._ids[0]
        self._idx_sel_b = self._ids[-1]

        self.play_button = QtWidgets.QToolButton(self.parent())
        self.icon_play = QtGui.QIcon(QtGui.QPixmap(self.fname_play))
        self.icon_pause = QtGui.QIcon(QtGui.QPixmap(self.fname_pause))
        self.play_button.setIcon(self.icon_play)
        self.play_button.clicked.connect(self.cb_play)
        self.play_button.setToolTip("Start/stop playback")

        self.frame_text = QtWidgets.QLineEdit(str(self.frame_num))
        self.cb_slider_text(self.frame_idx, resize=True)
        self.frame_text.setReadOnly(True)
        self.frame_text.setSizePolicy(
            QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum
        )

        nextButton = QtWidgets.QToolButton(self.parent())
        nextButton.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_skip_ahead)))
        nextButton.clicked.connect(self.cb_last)
        nextButton.setToolTip("Skip to last frame")

        prevButton = QtWidgets.QToolButton(self.parent())
        prevButton.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_skip_back)))
        prevButton.clicked.connect(self.cb_first)
        prevButton.setToolTip("Skip to first frame")

        self.play_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.play_slider.setRange(0, self.num_frames - 1)
        self.play_slider.sliderMoved.connect(self.cb_play_slider)
        self.play_slider.sliderReleased.connect(self.cb_play_slider)
        self.play_slider.setFocusPolicy(QtCore.Qt.NoFocus)
        self.play_slider.setTickPosition(QtWidgets.QSlider.TicksBothSides)

        if range_slider:
            self.range_slider = RangeSlider(parent=self, other=self.play_slider)
            self.range_slider.setRangeLimit(0, self.num_frames - 1)
            self.range_slider.setRange(0, self.num_frames - 1)
            self.range_slider.setFocusPolicy(QtCore.Qt.NoFocus)
            self.range_slider.setTickPosition(QtWidgets.QSlider.NoTicks)
            self.range_slider.setTickInterval(0)
            self.range_slider.sliderMoved.connect(self.cb_range_slider)

        self.rate_box = QtWidgets.QComboBox()
        self.rate_box.addItem("1/8x  ", QtCore.QVariant(1.0 / 8.0))
        self.rate_box.addItem("1/4x  ", QtCore.QVariant(1.0 / 4.0))
        self.rate_box.addItem("1/2x  ", QtCore.QVariant(1.0 / 2.0))
        self.rate_box.addItem("1x  ", QtCore.QVariant(1.0))
        self.rate_box.addItem("2x  ", QtCore.QVariant(2.0))
        self.rate_box.setFocusPolicy(QtCore.Qt.NoFocus)
        self.rate_box.setCurrentIndex(3)
        self.rate_box.activated.connect(self.cb_update_rate)
        self.rate_box.setToolTip("Change playback speed")

        lh = QtWidgets.QHBoxLayout()
        lv = QtWidgets.QVBoxLayout()

        lh.addWidget(self.frame_text)
        lh.addWidget(prevButton)
        lh.addWidget(self.play_button)
        lh.addWidget(nextButton)
        lh.addWidget(self.rate_box)
        lh.addStretch()
        lv.addLayout(lh)
        lv.addWidget(self.play_slider)

        if range_slider:
            lv.addWidget(self.range_slider)

        self.setLayout(lv)

        self.interval = self.dt * 1000 / self.rate_box.currentData()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.cb_timeout)

    def cb_last(self):
        """Jump to the last frame and stop playback."""
        self.cb_stop()
        self.cb_play_slider(self._ids[-1])
        self.play_slider.blockSignals(True)
        self.play_slider.setValue(self.frame_num)
        self.play_slider.blockSignals(False)

    def cb_first(self):
        """Jump to the first frame and stop playback."""
        self.cb_stop()
        self.cb_play_slider(self._ids[0])
        self.play_slider.blockSignals(True)
        self.play_slider.setValue(self.frame_num)
        self.play_slider.blockSignals(False)

    def cb_slider_text(self, idx, resize=False):
        """
        Updates the frame_text to show current frame, total frames, and range selection.

        Args:
            idx (int): Current frame index.
            resize (bool): Whether to resize the text field to fit content.
        """

        def resize_frame_text_to_fit(self):
            text = self.frame_text.text()
            font = QtGui.QFont("", 0)
            fm = QtGui.QFontMetrics(font)
            pixelsWide = fm.width(text)
            pixelsHigh = fm.height()
            self.frame_text.setFixedSize(pixelsWide, pixelsHigh)

        msg = f"{idx:04d}/{self._ids[-1]:04d} [{self._idx_sel_a:04d}, {self._idx_sel_b:04d}]"
        self.frame_text.setText(msg)
        if resize:
            resize_frame_text_to_fit(self)

    def cb_play_slider(self, frame_num=None):
        """
        Sets the frame based on the slider value.

        Args:
            frame_num (int, optional): Frame number to set; uses slider value if None.
        """

        if frame_num is None:
            frame_num = self.play_slider.value()
        self.cb_stop()
        self.set_frame_num(frame_num)

    def cb_range_slider(self, idx_a, idx_b, handle):
        """
        Updates the playback range when the range slider is adjusted.

        Args:
            idx_a (int): Lower bound of selected range.
            idx_b (int): Upper bound of selected range.
            handle (int): Index of handle moved (0 = left, 1 = right).
        """

        self.cb_stop()
        self._idx_sel_a = idx_a
        self._idx_sel_b = idx_b
        if (self.frame_num < idx_a) or (handle == 0):
            self.set_frame_num(idx_a)
        elif (self.frame_num > idx_b) or (handle == 1):
            self.set_frame_num(idx_b)

    def toggle_play(self):
        """Toggles between play and pause states."""

        if self._playing:
            self.cb_stop()
        else:
            self.cb_play()

    def cb_play(self):
        """Starts playback using a timer and switches icon to pause."""

        if self._playing:
            self.cb_stop()
        else:
            self.timer.start(self.interval)
            self.play_button.setIcon(self.icon_pause)
            self._playing = True

    def cb_stop(self):
        """Stops playback and resets icon to play."""

        self.timer.stop()
        self.play_button.setIcon(self.icon_play)
        self._playing = False

    def cb_timeout(self):
        """
        Advances one frame during playback. Stops if the last frame is reached.
        """

        if self.frame_idx < self.num_frames - 1:
            self.incr()
            self.play_slider.setValue(self.frame_num)
        else:
            self.cb_stop()

    def cb_update_rate(self):
        """
        Updates the playback rate based on the rate_box selection.
        Restarts playback if it was active.
        """

        running = self.timer.isActive()
        self.timer.stop()
        self.interval = self.dt * 1000 / self.rate_box.currentData()
        if running:
            self._playing = False
            self.cb_play()

    @property
    def num_frames(self):
        """Returns total number of video frames."""
        return len(self._ids)

    @property
    def frame_num(self):
        """Returns the current frame number."""
        return self._frame_num

    @property
    def frame_idx(self):
        """Returns the current frame index."""
        return self._frame_idx

    def incr(self, emit=True):
        """Advance to the next frame. Emits signal by default."""
        self.jog(1, emit)

    def decr(self, emit=True):
        """Go to the previous frame. Emits signal by default."""
        self.jog(-1, emit)

    def jog(self, delta, emit=True):
        """
        Move forward/backward by a fixed number of frames.

        Args:
            delta (int): Number of frames to move (+/-).
            emit (bool): Whether to emit the frame change signal.
        """

        self._frame_idx = np.clip(self._frame_idx + delta, 0, self.num_frames - 1)
        self._frame_num = self._ids[self._frame_idx]
        self._set_frame(emit)

    def _set_frame(self, emit):
        """
        Internal method to update frame slider and emit change.

        Args:
            emit (bool): Whether to emit sig_frame_change.
        """

        self.cb_slider_text(self._frame_num)
        self.play_slider.blockSignals(True)
        self.play_slider.setValue(self.frame_num)
        self.play_slider.blockSignals(False)
        if emit:
            self.sig_frame_change.emit(self._frame_idx, False) #emits to canvas.on_frame_change

    def set_frame_idx(self, n, emit=True):
        """
        Sets frame using an index (0-based).

        Args:
            n (int): Frame index.
            emit (bool): Whether to emit sig_frame_change.
        """

        assert n >= 0 and n < self.num_frames
        if n == self._frame_idx:
            return
        self._frame_idx = n
        self._frame_num = self._ids[self._frame_idx]

        self._set_frame(emit)

    def set_frame_num(self, n, emit=True):
        """
        Sets frame using the frame number.

        Args:
            n (int): Frame number (in _ids).
            emit (bool): Whether to emit sig_frame_change.
        """

        assert n in self._ids
        if n == self._frame_num:
            # print("Already on frame num %d" % (n))
            return
        self._frame_num = n
        self._frame_idx = self._id_2_idx[self._frame_num]

        self._set_frame(emit)
