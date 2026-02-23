import os

import numpy as np
from fixtrack.backend.track_io import TrackIO
from fixtrack.common.utils import color_from_index
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QRadioButton,
    QVBoxLayout, QWidget
)


class ShiftPushbutton(QPushButton):
    """
    A QPushButton subclass that emits a custom signal when clicked with the Shift key held.

    This is useful for distinguishing between normal clicks and Shift-clicks,
    allowing for dual-purpose buttons (e.g., "Save" vs. "Save As").

    Signals:
        shiftClicked (bool, bool): Emitted when clicked with Shift.
                                   First argument: button's checked state.
                                   Second argument: always True (indicating Shift was held).
    """

    shiftClicked = QtCore.pyqtSignal(bool, bool)

    def mousePressEvent(self, event):
        """
        Overrides the default mouse press event to detect Shift-modified clicks.

        If the Shift key is held, emits the `shiftClicked` signal and skips the default behavior.
        Otherwise, proceeds with the normal QPushButton behavior.

        Args:
            event (QMouseEvent): The mouse press event.
        """
        
        if (event.modifiers() == QtCore.Qt.ShiftModifier):
            self.shiftClicked.emit(self.isChecked(), True)
            return
        super().mousePressEvent(event)

    def animateShiftClick(self):
        """
        Simulates a Shift-click animation and emits the `shiftClicked` signal.

        This method is used to visually and functionally trigger a Shift-click programmatically,
        typically to implement Shift-click behavior from a keyboard shortcut (e.g., Ctrl+Shift+S).
        """

        self.setCheckable(True)
        self.setChecked(True)
        QtCore.QTimer.singleShot(100, self._doAnimateShiftClick)

    def _doAnimateShiftClick(self):
        """
        Internal method called after a short delay to reset the button state
        and emit the `shiftClicked` signal.

        This is used by `animateShiftClick` to create a visual click effect.
        """

        self.setChecked(False)
        self.setCheckable(False)
        self.shiftClicked.emit(self.isChecked(), True)


class FilterDialog(QDialog):
    """
    A modal dialog for configuring low-pass filtering options on a single track.

    Allows the user to:
      - Choose whether to filter position and/or heading data
      - Specify cutoff frequencies for each
      - Select the filter order (1 to 5)

    The dialog validates inputs via PyQt's built-in double validators, and
    provides OK/Cancel buttons for confirmation.

    Attributes:
        filter_pos (QCheckBox): Checkbox to enable position filtering.
        filter_heading (QCheckBox): Checkbox to enable heading filtering.
        freq_pos (QLineEdit): Input field for position cutoff frequency.
        freq_heading (QLineEdit): Input field for heading cutoff frequency.
        filter_order (QComboBox): Dropdown for selecting filter order (1–5).
        buttonBox (QDialogButtonBox): OK and Cancel buttons.
    """

    def __init__(self, index, *args, **kwargs):
        """
        Initializes the FilterDialog UI.

        Args:
            index (int): The track index to be filtered (used in window title).
            *args: Additional positional arguments passed to QDialog.
            **kwargs: Additional keyword arguments passed to QDialog.
        """

        super().__init__(*args, **kwargs)

        self.setWindowTitle(f"Filter Track {index}")

        QBtn = QDialogButtonBox.Ok | QDialogButtonBox.Cancel

        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()

        gl = QGridLayout()
        self.filter_pos = QCheckBox("Filter Position")
        gl.addWidget(self.filter_pos, 0, 0, 1, 1, QtCore.Qt.AlignRight)
        self.filter_heading = QCheckBox("Filter Heading")
        gl.addWidget(self.filter_heading, 1, 0, 1, 1, QtCore.Qt.AlignRight)

        self.freq_pos = QLineEdit()
        self.freq_pos.setValidator(QtGui.QDoubleValidator(0.1, 30.0, 2, self))
        self.freq_pos.setPlaceholderText("Cutoff Frequency")
        gl.addWidget(self.freq_pos, 0, 1, 1, 1)
        gl.addWidget(QLabel("Hz"), 0, 2, 1, 1, QtCore.Qt.AlignRight)

        self.freq_heading = QLineEdit()
        self.freq_heading.setValidator(QtGui.QDoubleValidator(0.1, 30.0, 2, self))
        self.freq_heading.setPlaceholderText("Cutoff Frequency")
        gl.addWidget(self.freq_heading, 1, 1, 1, 1)
        gl.addWidget(QLabel("Hz"), 1, 2, 1, 1, QtCore.Qt.AlignRight)

        self.filter_order = QComboBox()
        gl.addWidget(QLabel("Filter Order"), 2, 0, 1, 1, QtCore.Qt.AlignLeft)
        for i in range(1, 6):
            self.filter_order.addItem(f"{i}")
        self.filter_order.setCurrentIndex(1)
        gl.addWidget(self.filter_order, 2, 1, 1, 1, QtCore.Qt.AlignLeft)

        self.layout.addLayout(gl)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)


class TopLevelControls(QWidget):
    """
    Top-level toolbar widget for track editing operations in the FixTrack UI.

    This widget provides global control buttons for manipulating tracks,
    including actions like saving, linking, breaking, undo/redo, toggling
    visibility, heading estimation, and interpolation direction.
    """
    fname_add = os.path.join(os.path.dirname(__file__), "icons", "plus.svg")
    fname_eye = os.path.join(os.path.dirname(__file__), "icons", "eye.svg")
    fname_save = os.path.join(os.path.dirname(__file__), "icons", "save.svg")
    fname_undo = os.path.join(os.path.dirname(__file__), "icons", "rotate-ccw.svg")
    fname_redo = os.path.join(os.path.dirname(__file__), "icons", "rotate-cw.svg")
    fname_interp_l = os.path.join(os.path.dirname(__file__), "icons", "arrow-left-circle.svg")
    fname_interp_r = os.path.join(os.path.dirname(__file__), "icons", "arrow-right-circle.svg")
    fname_heading = os.path.join(os.path.dirname(__file__), "icons", "compass.svg")
    fname_link = os.path.join(os.path.dirname(__file__), "icons", "link.svg")
    fname_break = os.path.join(os.path.dirname(__file__), "icons", "scissors.svg")

    
    def __init__(self, parent):
        """
        Initializes the TopLevelControls layout with all control buttons.

        Args:
            parent (VideoWidget): The parent widget, typically the main window container.
        """

        QWidget.__init__(self, parent)
        self._parent = parent
        self.buttons = []
        self.last_addr = None
        hl1 = QHBoxLayout()
        hl2 = QHBoxLayout()
        hl3 = QHBoxLayout()
        hl4 = QHBoxLayout()
        hl5 = QHBoxLayout()

        vl = QVBoxLayout()
        self.vis_toggle_state = True
        self.bbox_vis_toggle_state = True
        self._fname_save = None

        self.btn_add_track = QPushButton(self)
        self.btn_add_track.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_add)))
        self.btn_add_track.setToolTip("Add new track")
        self.btn_add_track.clicked.connect(self.cb_add_new_track)
        self.btn_add_track.setFocusPolicy(QtCore.Qt.NoFocus)
        hl1.addWidget(self.btn_add_track)
        self.buttons.append(self.btn_add_track)

        self.btn_toggle_vis = QPushButton(self)
        self.btn_toggle_vis.setToolTip("Show/hide all tracks")
        self.btn_toggle_vis.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_eye)))
        self.btn_toggle_vis.clicked.connect(self.cb_toggle_vis)
        self.btn_toggle_vis.setFocusPolicy(QtCore.Qt.NoFocus)
        hl1.addWidget(self.btn_toggle_vis)
        self.buttons.append(self.btn_toggle_vis)

        self.btn_toggle_bbox_vis = QPushButton(self)
        self.btn_toggle_bbox_vis.setToolTip("Show/hide bbox for all tracks")
        self.btn_toggle_bbox_vis.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_eye)))
        self.btn_toggle_bbox_vis.clicked.connect(self.cb_toggle_box_vis)
        self.btn_toggle_bbox_vis.setFocusPolicy(QtCore.Qt.NoFocus)
        hl1.addWidget(self.btn_toggle_bbox_vis)
        self.buttons.append(self.btn_toggle_bbox_vis)

        self.btn_save_tracks = ShiftPushbutton(self)
        self.btn_save_tracks.setToolTip("Save tracks to H5 file Ctrl+S")
        self.btn_save_tracks.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_save)))
        self.btn_save_tracks.clicked.connect(self.cb_btn_save_tracks)
        self.btn_save_tracks.shiftClicked.connect(self.cb_btn_save_tracks)
        self.btn_save_tracks.setFocusPolicy(QtCore.Qt.NoFocus)
        hl1.addWidget(self.btn_save_tracks)
        self.buttons.append(self.btn_save_tracks)

        self.btn_undo = QPushButton(self)
        self.btn_undo.setToolTip("Undo last action Ctrl+Z")
        self.btn_undo.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_undo)))
        self.btn_undo.clicked.connect(self.cb_btn_undo)
        self.btn_undo.setFocusPolicy(QtCore.Qt.NoFocus)
        hl4.addWidget(self.btn_undo)
        self.buttons.append(self.btn_undo)

        self.btn_redo = QPushButton(self)
        self.btn_redo.setToolTip("Redo last action Ctrl+Shift+Z")
        self.btn_redo.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_redo)))
        self.btn_redo.clicked.connect(self.cb_btn_redo)
        self.btn_redo.setFocusPolicy(QtCore.Qt.NoFocus)
        hl4.addWidget(self.btn_redo)
        self.buttons.append(self.btn_redo)

        self.btn_heading = QPushButton(self)
        self.btn_heading.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_heading)))
        self.btn_heading.setToolTip("Show/hide heading vectors")
        self.btn_heading.clicked.connect(self.cb_btn_heading)
        self.btn_heading.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_heading.setCheckable(True)
        self.btn_heading.setChecked(True)
        hl3.addWidget(self.btn_heading)
        self.buttons.append(self.btn_heading)

        self.btn_interp_l = QPushButton(self)
        self.btn_interp_l.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_interp_l)))
        self.btn_interp_l.setToolTip("Interpolate backward in time")
        self.btn_interp_l.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_interp_l.setCheckable(True)
        self.btn_interp_l.setChecked(True)
        hl3.addWidget(self.btn_interp_l)
        self.buttons.append(self.btn_interp_l)

        self.btn_interp_r = QPushButton(self)
        self.btn_interp_r.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_interp_r)))
        self.btn_interp_r.setToolTip("Interpolate forward in time")
        self.btn_interp_r.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_interp_r.setCheckable(True)
        self.btn_interp_r.setChecked(True)
        hl3.addWidget(self.btn_interp_r)
        self.buttons.append(self.btn_interp_r)

        self.btn_link = QPushButton(self)
        self.btn_link.setToolTip("Link two tracks Ctrl+L")
        self.btn_link.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_link)))
        self.btn_link.setCheckable(True)
        self.btn_link.clicked.connect(self.cb_btn_link)
        self.btn_link.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_link.setEnabled(False)
        hl5.addWidget(self.btn_link)

        self.btn_break = QPushButton(self)
        self.btn_break.setToolTip("Break selected track into two at the current frame Ctrl+B")
        self.btn_break.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_break)))
        self.btn_break.setCheckable(False)
        self.btn_break.clicked.connect(self.cb_btn_break)
        self.btn_break.setFocusPolicy(QtCore.Qt.NoFocus)
        hl5.addWidget(self.btn_break)
        self.buttons.append(self.btn_break)

        vl.addLayout(hl1)
        vl.addLayout(hl2)
        vl.addLayout(hl3)
        vl.addLayout(hl4)
        vl.addLayout(hl5)

        self.setLayout(vl)

    
    def cb_marker_clicked(self, idx_track, idx_frame, modifiers):
        """
        Handles click events on track markers when in linking mode.

        If no marker was previously selected, stores the current one.
        If a previous marker exists, links the two selected markers.

        Args:
            idx_track (int): Index of the clicked track.
            idx_frame (int): Frame index of the clicked point.
            modifiers: Keyboard modifiers from the event (currently unused).
        """

        if not self.btn_link.isChecked():
            self.last_addr = (idx_track, idx_frame)
            self.btn_link.setEnabled(True)
            return

        assert self.last_addr is not None, "No previously selected track point"

        print("Linking", self.last_addr[0], idx_track, "=>", self.last_addr[1], idx_frame)
        linked = self._parent.canvas.tracks.link_tracks(
            self.last_addr[0], idx_track, self.last_addr[1], idx_frame
        )
        self.btn_link.click()

        #remove bbox
        if linked and self._parent.canvas.tracks.contains_bboxes:
            print('removed bbox')
            self._parent.canvas.visuals["tracks"].remove_bbox()


        self._parent.canvas.on_frame_change()
        self._parent.setup_track_edit_bar(select_last=False)
        self._parent.canvas.on_frame_change()

        self.last_addr = None
        self.btn_link.setEnabled(False)

    
    def cb_btn_link(self, checked):
        """
        Enables or disables linking mode.

        Disables most UI buttons and shows instructions when linking is active.
        Re-enables everything when linking is canceled or completed.

        Args:
            checked (bool): Whether the link button is active.
        """
        
        for btn in self.buttons:
            btn.setEnabled(not checked)

        idx_track = self._parent.idx_selected()
        idx_frame = self._parent.canvas.frame_num

        track_widgets = self._parent.track_edit_bar.track_widgets
        track_widgets[idx_track].btn_selected.setEnabled(not checked)

        for idx, widget in track_widgets.items():
            if not checked:
                widget.btn_selected.setEnabled(not checked)
            for btn in widget.buttons:
                btn.setEnabled(not checked)

        if checked:
            self._parent.track_edit_bar.show_msg.emit(
                f"Linking track {idx_track} frame {idx_frame}: Select track point to link"
            )
        else:
            self._parent.track_edit_bar.show_msg.emit("")


    def cb_btn_break(self, checked):
        """
        Breaks the currently selected track at the current frame.

        Args:
            checked (bool): Unused; signal parameter from button.
        """

        idx_track = self._parent.idx_selected()
        idx_frame = self._parent.canvas.frame_num


        broken = self._parent.canvas.tracks.break_track(idx_track, idx_frame)
        #add new bbox object
        if self._parent.canvas.tracks.contains_bboxes and broken:
            self._parent.canvas.visuals["tracks"].add_bbox()
        self._parent.canvas.on_frame_change()
        self._parent.setup_track_edit_bar(select_last=False)
        self._parent.canvas.on_frame_change()

    def cb_btn_redo(self, clicked):
        """
        Redoes the last undone action on the selected track.

        Args:
            clicked (bool): Unused; signal parameter from button.
        """

        idx_sel_track = self._parent.idx_selected()
        self._parent.canvas.tracks.redo(idx_sel_track)
        self._parent.canvas.on_frame_change()

    def cb_btn_undo(self, clicked):
        """
        Undoes the last action on the selected track.

        Args:
            clicked (bool): Unused; signal parameter from button.
        """

        idx_sel_track = self._parent.idx_selected()
        self._parent.canvas.tracks.undo(idx_sel_track)
        self._parent.canvas.on_frame_change()

    def cb_btn_save_tracks(self, checked, save_as=False):
        """
        Saves track data to an HDF5 file. Prompts for a filename if none is set.

        Args:
            checked (bool): Whether the save button is clicked (or Shift-clicked).
            save_as (bool): If True, always prompt for a new save location.
        """

        # Get filename if necessary
        if (self._fname_save is None) or save_as:
            ext = ".h5"
            if self._parent.canvas.fname_tracks is not None:
                savedir = os.path.dirname(self._parent.canvas.fname_tracks)
            else:
                savedir = os.path.dirname(self._parent.canvas.fname_video)

            fname, _ = QFileDialog.getSaveFileName(
                self, "Save File", savedir, f"H5 File (*{ext});;All Files (*)"
            )

            if fname == "":
                return

            if not fname.lower().endswith(ext):
                fname += ext
            self._fname_save = fname

        # Save the tracks
        TrackIO.save(self._fname_save, self._parent.canvas.tracks)
        print(f"Saved tracks as {self._fname_save}")
        self._parent.mutated.emit(False)

    def cb_btn_heading(self, checked):
        """
        Toggles visibility of heading vectors on all tracks.

        Args:
            checked (bool): Whether the heading button is checked.
        """

        self._parent.canvas.visuals["tracks"].visuals["headings"].visible = checked

    def cb_toggle_vis(self, clicked):
        """
        Toggles visibility of all tracks
        """

        vis = []
        for idx, track_widget in self._parent.track_edit_bar.track_widgets.items():
            if self._parent.canvas.tracks[idx].visible == self.vis_toggle_state:
                track_widget.toggle_vis_btn(self.vis_toggle_state)
                vis.append(idx)
        self.vis_toggle_state = not self.vis_toggle_state
        self.bbox_vis_toggle_state = self.vis_toggle_state
        self._parent.canvas.visuals["tracks"].set_all_track_vis(vis, self.vis_toggle_state)


    def cb_toggle_box_vis(self, clicked):
        '''
        Toggles bbox visibility for all tracks
        '''
        if not self._parent.canvas.tracks.contains_bboxes:
            return

        vis = []
        for idx, track_widget in self._parent.track_edit_bar.track_widgets.items():
            if self._parent.canvas.visuals["tracks"].current_boxes[idx].visible == self.bbox_vis_toggle_state:
                vis.append(idx)
        self.bbox_vis_toggle_state = not self.bbox_vis_toggle_state
        self._parent.canvas.visuals["tracks"].set_all_bbox_vis(vis, self.bbox_vis_toggle_state)

    def cb_add_new_track(self, clicked):
        """
        Adds a new empty track to the canvas and refreshes the track layout.

        Args:
            clicked (bool): Unused; signal parameter from button.
        """

        self._parent.canvas.tracks.add_track()

        #call add_bbox in TrackCollectionVisual
        if self._parent.canvas.tracks.contains_bboxes:
            self._parent.canvas.visuals["tracks"].add_bbox()

        self._parent.canvas.on_frame_change()
        self._parent.setup_track_edit_bar(select_last=True)
        self._parent.mutated.emit(True)


class TrackEditLayoutBar(QWidget):
    """
    Scrollable layout bar containing interactive widgets for editing individual tracks.

    Each track is represented by a `TrackEditItem`, and this layout manages their
    creation, selection, visibility toggles, and user-triggered messages.

    Attributes:
        _parent (VideoWidget): Reference to the parent widget (typically `VideoWidget`).
        track_widgets (dict[int, TrackEditItem]): Dictionary mapping track indices to their corresponding widgets.
        radio_button_group (QButtonGroup): Ensures only one track is selected at a time.
        vbox (QVBoxLayout): Vertical layout container for all track widgets.
    
    Signals:
        show_msg (str): Used to display a message on the parent window's status bar.
    """

    show_msg = QtCore.pyqtSignal(str)

    def __init__(self, parent):
        """
        Initializes the TrackEditLayoutBar and sets up message routing to the status bar.

        Args:
            parent (VideoWidget): The parent widget that owns this layout bar.
        """

        QWidget.__init__(self, parent)
        self._parent = parent
        self.reset()

        self.show_msg.connect(self._parent._parent.statusBar().showMessage)

    def idx_selected(self):
        """
        Returns the index of the currently selected track.

        Returns:
            int or None: Track index if one is selected, otherwise None.
        """

        for idx, wid in self.track_widgets.items():
            if wid.btn_selected.isChecked():
                return idx
        return None

    def mutated(self, b=True):
        """
        Emits a mutation signal to indicate the project state has changed (e.g., for save prompting).

        Args:
            b (bool): Whether a mutation occurred (default is True).
        """

        self._parent.mutated.emit(b)

    def reset(self):
        """
        Clears all existing track widgets and resets the layout.

        This is typically used when reinitializing the editor (e.g., loading a new file).
        """

        self.track_widgets = {}
        self.vbox = QVBoxLayout()
        self.radio_button_group = QButtonGroup(self)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

    def add_track(self, index, select=False, last=False):
        """
        Adds a new TrackEditItem to the layout for a given track index.

        Args:
            index (int): Track index to add.
            select (bool): Whether this track should be initially selected.
            last (bool): If True, finalizes the layout after adding this track.
    
        Raises:
            AssertionError: If a track with the given index already exists.
        """

        assert index not in self.track_widgets, "Attempting to add duplicate track %s" % (
            index
        )

        self.track_widgets[index] = TrackEditItem(
            index=index,
            parent=self,
            radio_bg=self.radio_button_group,
            select=select,
        )

        self.vbox.addWidget(self.track_widgets[index])

        self.track_widgets[index].sig_set_track_vis.connect(
            self._parent.canvas.visuals["tracks"].slot_set_track_vis
        )

        if last:
            self.finalize_layout()

    def finalize_layout(self):
        """
        Finalizes the layout by adding vertical stretch and enabling exclusive selection.

        Should be called after all tracks are added (typically when `last=True` in `add_track`).
        """

        self.vbox.addStretch()
        self.setLayout(self.vbox)
        self.radio_button_group.setExclusive(True)


class TrackEditItem(QGroupBox):
    """
    A control widget for a single track, used within the TrackEditLayoutBar.

    Displays buttons to manage an individual track, including visibility,
    deletion, heading estimation, filtering, and selection.

    Attributes:
        _parent (TrackEditLayoutBar): Parent widget that manages all track items.
        index (int): The index of this track.
        buttons (list): All child buttons in this widget for unified access.

        btn_visible (QPushButton): Toggles the visibility of the track.
        icon_eye (QIcon): Icon for "visible" state.
        icon_eye_off (QIcon): Icon for "hidden" state.

        btn_del (QPushButton): Deletes the entire track.
        btn_rem (QPushButton): Removes detections in a selected range.
        btn_heading (QPushButton): Estimates the heading vector for the track.
        btn_filter (QPushButton): Applies filtering to position or heading data.
        btn_selected (QRadioButton): Selects this track for editing.

    Signals:
        sig_set_track_vis (int, int): Emitted when the track's visibility is toggled.
                                      Format: (track_index, visible_flag)
    """

    groupbox_style = """
     QGroupBox {
         border: 4px solid #%s;
         border-radius: 15px;
         margin-top: 15px;
         margin-left: 15px;
         margin-right: 15px;
         margin-bottom: 15px;
         font-weight: %s;
     }
     QGroupBox::title  {
        subcontrol-origin: margin;
        subcontrol-position: top center;
    }
    """
    sig_set_track_vis = QtCore.pyqtSignal(int, int)

    fname_eye = os.path.join(os.path.dirname(__file__), "icons", "eye.svg")
    fname_eye_off = os.path.join(os.path.dirname(__file__), "icons", "eye-off.svg")
    fname_del = os.path.join(os.path.dirname(__file__), "icons", "trash-2.svg")
    fname_rem = os.path.join(os.path.dirname(__file__), "icons", "minus.svg")

    fname_heading = os.path.join(os.path.dirname(__file__), "icons", "compass.svg")
    fname_filter = os.path.join(os.path.dirname(__file__), "icons", "filter.svg")

    def __init__(self, index, parent, radio_bg, select):
        """
        Initializes a TrackEditItem with buttons and layout for managing a single track.

        Args:
            index (int): The track index this widget represents.
            parent (TrackEditLayoutBar): The container layout bar.
            radio_bg (QButtonGroup): Button group to enforce exclusive selection.
            select (bool): Whether this track should be selected initially.
        """

        QWidget.__init__(self, parent)
        layout = QGridLayout()
        self.index = index
        self._parent = parent
        self.buttons = []

        self.setTitle(f"Track {self.index}")

        # Visible
        r, c = 0, 0
        self.btn_visible = QPushButton(self)
        self.btn_visible.setToolTip("Toggle track visibility")
        self.btn_visible.setCheckable(True)
        self.btn_visible.setChecked(False)
        self.icon_eye = QtGui.QIcon(QtGui.QPixmap(self.fname_eye))
        self.icon_eye_off = QtGui.QIcon(QtGui.QPixmap(self.fname_eye_off))
        self.btn_visible.setIcon(self.icon_eye)
        self.btn_visible.clicked.connect(self.cb_btn_visible)
        self.btn_visible.setFocusPolicy(QtCore.Qt.NoFocus)
        layout.addWidget(self.btn_visible, r, c, 1, 1, QtCore.Qt.AlignHCenter)
        self.buttons.append(self.btn_visible)

        # Delete track
        c += 1
        self.btn_del = QPushButton(self)
        self.btn_del.setToolTip("Delete this track")
        self.btn_del.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_del)))
        self.btn_del.clicked.connect(self.cb_btn_del)
        self.btn_del.setFocusPolicy(QtCore.Qt.NoFocus)
        layout.addWidget(self.btn_del, r, c, 1, 1, QtCore.Qt.AlignHCenter)
        self.buttons.append(self.btn_del)

        # Remove detections
        c += 1
        self.btn_rem = QPushButton(self)
        self.btn_rem.setToolTip("Remove detections for cropped range")
        self.btn_rem.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_rem)))
        self.btn_rem.clicked.connect(self.cb_btn_rem)
        self.btn_rem.setFocusPolicy(QtCore.Qt.NoFocus)
        layout.addWidget(self.btn_rem, r, c, 1, 1, QtCore.Qt.AlignHCenter)
        self.buttons.append(self.btn_rem)

        # Estimate heading
        c += 1
        self.btn_heading = QPushButton(self)
        self.btn_heading.setToolTip("Estimate heading from direction of travel")
        self.btn_heading.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_heading)))
        self.btn_heading.clicked.connect(self.cb_btn_heading)
        self.btn_heading.setFocusPolicy(QtCore.Qt.NoFocus)
        layout.addWidget(self.btn_heading, r, c, 1, 1, QtCore.Qt.AlignHCenter)
        self.buttons.append(self.btn_heading)

        # Filter
        c += 1
        self.btn_filter = QPushButton(self)
        self.btn_filter.setToolTip("Filter track")
        self.btn_filter.setIcon(QtGui.QIcon(QtGui.QPixmap(self.fname_filter)))
        self.btn_filter.clicked.connect(self.cb_btn_filter)
        self.btn_filter.setFocusPolicy(QtCore.Qt.NoFocus)
        layout.addWidget(self.btn_filter, r, c, 1, 1, QtCore.Qt.AlignHCenter)
        self.buttons.append(self.btn_filter)

        # Select track
        c = 0
        r += 1
        self.btn_selected = QRadioButton("Select")
        self.btn_selected.setToolTip("Select track for editing")
        radio_bg.addButton(self.btn_selected)
        self.btn_selected.setFocusPolicy(QtCore.Qt.NoFocus)
        self.btn_selected.toggled.connect(self.cb_btn_selected)
        self.btn_selected.setChecked(select)
        layout.addWidget(self.btn_selected, r, c, 1, 2, QtCore.Qt.AlignHCenter)
        self.buttons.append(self.btn_selected)

        self.setLayout(layout)
        c = (color_from_index(self.index) * 255).astype(np.uint8)
        self.setStyleSheet(self.groupbox_style % (f"{c[0]:02X}{c[1]:02X}{c[2]:02X}", "normal"))

    def cb_btn_selected(self, checked):
        """
        Called when the "Select" radio button is toggled.

        Changes the styling of the widget to highlight selection and ensures visibility in scroll view.

        Args:
            checked (bool): Whether this track is now selected.
        """

        if checked:
            c = (color_from_index(self.index) * 255).astype(np.uint8)
            self.setStyleSheet(
                self.groupbox_style % (f"{c[0]:02X}{c[1]:02X}{c[2]:02X}", "bold")
            )
        else:
            c = (color_from_index(self.index) * 255).astype(np.uint8)
            self.setStyleSheet(
                self.groupbox_style % (f"{c[0]:02X}{c[1]:02X}{c[2]:02X}", "normal")
            )

        # Make sure the selected track is visible
        self._parent._parent.scroll_area.ensureWidgetVisible(self)

    def check_freq_val(self, dlg):
        """
        Validates the cutoff frequency entered in the filter dialog.

        Args:
            dlg (QLineEdit): The input field to validate.

        Returns:
            bool: True if the value is valid, False otherwise.
        """

        txt = dlg.text()
        if txt == "":
            msg = f"No cutoff frequency provided {dlg.text()}"
            QMessageBox.warning(self, "Filter Error", msg, QMessageBox.Ok)
            return False

        val = float(txt)

        if (val < dlg.validator().bottom()) or (val > dlg.validator().top()):
            msg = f"Cutoff frequency {dlg.text()} not in range "
            msg += f"[{dlg.validator().bottom()},{dlg.validator().top()}]"
            QMessageBox.warning(self, "Filter Error", msg, QMessageBox.Ok)
            return False

        return True

    def cb_btn_heading(self, checked):
        """
        Estimates the heading vector of the track using direction of motion.

        Args:
            checked (bool): Unused; included for compatibility with clicked signal.
        """

        self._parent._parent.canvas.tracks[self.index].estimate_heading()
        self._parent._parent.canvas.on_frame_change()
        self._parent.mutated()

    def cb_btn_filter(self, checked):
        """
        Opens the filter dialog and applies a low-pass filter to position and/or heading.

        Args:
            checked (bool): Unused; included for compatibility with clicked signal.
        """

        dlg = FilterDialog(self.index, self)
        if dlg.exec_():
            pass
        else:
            print("Cancel")
            return
        canvas = self._parent._parent.canvas
        order = int(dlg.filter_order.currentText())
        if dlg.filter_pos.isChecked():
            if not self.check_freq_val(dlg.freq_pos):
                return
            f_cut_hz = float(dlg.freq_pos.text())
            print(f"Filtering position with order {order} low pass at {f_cut_hz}Hz")
            canvas.tracks[self.index].filter_position(
                canvas.video.fps,
                f_cut_hz=f_cut_hz,
                order=order,
            )
        if dlg.filter_heading.isChecked():
            if not self.check_freq_val(dlg.freq_heading):
                return
            f_cut_hz = float(dlg.freq_heading.text())
            print(f"Filtering heading with order {order} low pass at {f_cut_hz}Hz")
            canvas.tracks[self.index].filter_heading(
                canvas.video.fps,
                f_cut_hz=f_cut_hz,
                order=order,
            )
        canvas.on_frame_change()
        self._parent.mutated()

    def cb_btn_visible(self, checked):
        """
        Toggles visibility of the track in the canvas.

        Args:
            checked (bool): Whether the track is now marked as visible.
        """

        self.sig_set_track_vis.emit(self.index, not checked)
        if checked:
            self.btn_visible.setIcon(self.icon_eye_off)
        else:
            self.btn_visible.setIcon(self.icon_eye)
    
    def toggle_vis_btn(self, checked):
        """
        Toggles state of vis_btn without modifying track visibility. Used for improving performance
        of showing/hiding all tracks at once.
        """
        self.btn_visible.setChecked(checked)
        if checked:
            self.btn_visible.setIcon(self.icon_eye_off)
        else:
            self.btn_visible.setIcon(self.icon_eye)


    def cb_btn_del(self, checked):
        """
        Deletes the track entirely and refreshes the canvas and layout.

        Args:
            checked (bool): Unused; included for compatibility with clicked signal.
        """

        if self._parent._parent.canvas.tracks.num_tracks == 1:
            print("cannot delete, must have at least 1 track")
            return
        
        print(f"Deleting track {self.index}")

        #remove bbox for track self.index
        if self._parent._parent.canvas.tracks.contains_bboxes:
            self._parent._parent.canvas.visuals["tracks"].remove_bbox(self.index)
        
        self._parent._parent.canvas.tracks.rem_track(self.index)
        self._parent._parent.canvas.on_frame_change()
        self._parent._parent.setup_track_edit_bar()
        self._parent.mutated()

    def cb_btn_rem(self, checked):
        """
        Removes detections from the current track in the selected frame range.

        Args:
            checked (bool): Unused; included for compatibility with clicked signal.
        """

        idx_sel_a = self._parent._parent.player_controls._idx_sel_a
        idx_sel_b = self._parent._parent.player_controls._idx_sel_b
        self._parent._parent.canvas.tracks[self.index].rem_dets(idx_sel_a, idx_sel_b)
        self._parent._parent.canvas.on_frame_change()
        self._parent.mutated()
