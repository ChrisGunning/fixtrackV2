import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget, QListWidgetItem,
    QSpinBox, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal

import fixtrack.backend.track as tk
# Removed unused import:
# from fixtrack.common.utils import normalize_vecs


class TrackMergeDialog(QDialog):
    """Dialog for identifying and merging tracks that end/start at similar times/locations"""

    tracks_merged = pyqtSignal()

    def __init__(self, track_collection, parent=None):
        super().__init__(parent)
        self.track_collection = track_collection
        self.merge_candidates = []

        self.setWindowTitle("Track Merger")
        self.resize(800, 600)

        self.init_ui()
        self.find_merge_candidates()

    def init_ui(self):
        """Initialize the UI components"""
        layout = QVBoxLayout()
        param_group = QGroupBox("Merge Parameters")
        param_layout = QHBoxLayout()

        # Frame threshold
        frame_layout = QVBoxLayout()
        frame_layout.addWidget(QLabel("Max Frame Gap:"))
        self.frame_threshold = QSpinBox()
        self.frame_threshold.setRange(1, 50)
        self.frame_threshold.setValue(10)
        self.frame_threshold.valueChanged.connect(self.find_merge_candidates)
        frame_layout.addWidget(self.frame_threshold)
        param_layout.addLayout(frame_layout)

        # Distance threshold
        dist_layout = QVBoxLayout()
        dist_layout.addWidget(QLabel("Max Distance (px):"))
        self.dist_threshold = QSpinBox()
        self.dist_threshold.setRange(5, 200)
        self.dist_threshold.setValue(150)
        self.dist_threshold.valueChanged.connect(self.find_merge_candidates)
        dist_layout.addWidget(self.dist_threshold)
        param_layout.addLayout(dist_layout)

        # Direction similarity threshold
        dir_layout = QVBoxLayout()
        dir_layout.addWidget(QLabel("Min Direction Similarity:"))
        self.dir_threshold = QSpinBox()
        self.dir_threshold.setRange(0, 100)
        self.dir_threshold.setValue(70)
        self.dir_threshold.valueChanged.connect(self.find_merge_candidates)
        dir_layout.addWidget(self.dir_threshold)
        param_layout.addLayout(dir_layout)

        # Refresh button
        refresh_btn = QPushButton("Refresh Candidates")
        refresh_btn.clicked.connect(self.find_merge_candidates)
        param_layout.addWidget(refresh_btn)

        param_group.setLayout(param_layout)
        layout.addWidget(param_group)

        # Candidates list
        candidates_label = QLabel("Merge Candidates:")
        layout.addWidget(candidates_label)

        self.candidates_list = QListWidget()
        self.candidates_list.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.candidates_list)

        btn_layout = QHBoxLayout()

        self.merge_btn = QPushButton("Merge Selected")
        self.merge_btn.setEnabled(False)
        self.merge_btn.clicked.connect(self.merge_selected)
        btn_layout.addWidget(self.merge_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.candidates_list.itemSelectionChanged.connect(self.update_button_state)

    def update_button_state(self):
        """Update the state of merge buttons based on selection"""
        self.merge_btn.setEnabled(len(self.candidates_list.selectedItems()) > 0)

    def find_merge_candidates(self):
        """Find potential track merge candidates based on end/start"""
        self.merge_candidates = []
        self.candidates_list.clear()

        num_tracks = self.track_collection.num_tracks

        for i in range(num_tracks):
            track_i = self.track_collection[i]

            last_valid_frames_i = np.where(track_i["det"] == 1)[0]
            last_frame_i = last_valid_frames_i[-1]

            # If the frame is at the end of the video: continue
            if last_frame_i >= self.track_collection.num_frames - 5:
                continue

            last_pos_i = track_i["pos"][last_frame_i]
            # Removed unused variable: last_vec_i = track_i["vec"][last_frame_i]

            for j in range(num_tracks):
                if i == j:
                    continue

                track_j = self.track_collection[j]
                det_j = track_j["det"]

                # Find the first valid frame for track j
                first_frame_j = np.where(det_j == 1)[0][0]

                # Check if the end of track i is close to the start of track j in time
                frame_diff = first_frame_j - last_frame_i
                if 0 < frame_diff <= self.frame_threshold.value():
                    first_pos_j = track_j["pos"][first_frame_j]
                    # Removed unused variable: first_vec_j = track_j["vec"][first_frame_j]

                    dist = np.linalg.norm(last_pos_i[:2] - first_pos_j[:2])
                    print(dist)
                    if dist <= self.dist_threshold.value():
                        self.merge_candidates.append((i, j, frame_diff, dist))
                        item_text = (
                            f"Track {i+1} → Track {j+1}: Gap: {frame_diff} frames, "
                            f"Distance: {dist:.1f}px"
                        )
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, (i, j))
                        self.candidates_list.addItem(item)

        self.update_button_state()
        if not self.merge_candidates:
            QMessageBox.information(
                self, "No Candidates", "No merge candidates found with current parameters.\n"
                "Try increasing thresholds or check if tracks overlap."
            )

    def merge_tracks(self, track1_idx, track2_idx):
        """Merge two tracks into one continuous track"""
        track1 = self.track_collection[track1_idx]
        track2 = self.track_collection[track2_idx]

        pos = track1["pos"].copy()
        vec = track1["vec"].copy()
        det = track1["det"].copy()

        last_valid_frame1 = np.where(track1["det"] == 1)[0][-1]
        first_valid_frame2 = np.where(track2["det"] == 1)[0][0]

        frames_to_interpolate = list(range(last_valid_frame1 + 1, first_valid_frame2))
        if frames_to_interpolate:
            pos1 = track1["pos"][last_valid_frame1]
            pos2 = track2["pos"][first_valid_frame2]

            for i, frame in enumerate(frames_to_interpolate):
                alpha = (i + 1) / (len(frames_to_interpolate) + 1)
                pos[frame] = (1 - alpha) * pos1 + alpha * pos2
                det[frame] = 1

        # Copy track2 data after the gap
        for frame in range(first_valid_frame2, self.track_collection.num_frames):
            if track2["det"][frame] == 1:
                pos[frame] = track2["pos"][frame]
                vec[frame] = track2["vec"][frame]
                det[frame] = 1

        # Update vectors for the interpolated frames
        for i in range(1, self.track_collection.num_frames):
            if det[i] == 1 and det[i - 1] == 1:
                direction = pos[i, :2] - pos[i - 1, :2]
                norm = np.linalg.norm(direction)
                if norm > 0:
                    vec[i, 0] = direction[0] / norm
                    vec[i, 1] = direction[1] / norm

        merged_track = tk.Track(pos=pos, vec=vec, det=det)
        self.track_collection.tracks[track1_idx] = merged_track
        self.track_collection.tracks[track2_idx]["det"][:] = 0

        return merged_track

    def merge_selected(self):
        """Merge the selected track pairs"""
        selected_items = self.candidates_list.selectedItems()
        if not selected_items:
            return

        merged_pairs = []
        for item in selected_items:
            track1_idx, track2_idx = item.data(Qt.UserRole)
            self.merge_tracks(track1_idx, track2_idx)
            merged_pairs.append((track1_idx, track2_idx))

        self.remove_merged_items(merged_pairs)
        self.tracks_merged.emit()

        QMessageBox.information(
            self, "Tracks Merged", f"Successfully merged {len(merged_pairs)} track pairs."
        )

    def remove_merged_items(self, merged_pairs):
        """Remove merged items from the list and update remaining candidates"""
        merged_tracks = set()
        for t1, t2 in merged_pairs:
            merged_tracks.add(t1)
            merged_tracks.add(t2)

        new_candidates = []
        for i in range(self.candidates_list.count() - 1, -1, -1):
            item = self.candidates_list.item(i)
            t1, t2 = item.data(Qt.UserRole)

            if t1 in merged_tracks or t2 in merged_tracks:
                self.candidates_list.takeItem(i)
            else:
                new_candidates.append(self.merge_candidates[i])

        self.merge_candidates = new_candidates
        self.update_button_state()
