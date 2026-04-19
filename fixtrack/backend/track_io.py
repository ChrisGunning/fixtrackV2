import os

import h5py as h5py
import numpy as np
import pandas as pd

import fixtrack.backend.track as tk
import fixtrack.common.utils as utils


class TrackIO(object):
    @staticmethod
    def save(fname, tracks):
        """
        Takes a TrackCollection and saves it to an h5 file
        """
        fname = utils.expand_path(fname)
        num_frames = tracks.num_frames
        num_tracks = tracks.num_tracks

        with h5py.File(fname, mode="w") as h5:
            h5.create_dataset("X", shape=(num_tracks, num_frames), dtype=np.float32)
            h5.create_dataset("Y", shape=(num_tracks, num_frames), dtype=np.float32)
            h5.create_dataset("HX", shape=(num_tracks, num_frames), dtype=np.float32)
            h5.create_dataset("HY", shape=(num_tracks, num_frames), dtype=np.float32)
            h5.create_dataset("det", shape=(num_tracks, num_frames), dtype=np.uint8)

            h5["X"][()] = np.vstack([tk["pos"][:, 0] for tk in tracks])
            h5["Y"][()] = np.vstack([tk["pos"][:, 1] for tk in tracks])
            h5["HX"][()] = np.vstack([tk["vec"][:, 0] for tk in tracks])
            h5["HY"][()] = np.vstack([tk["vec"][:, 1] for tk in tracks])
            h5["det"][()] = np.vstack([tk["det"] for tk in tracks])

            if tracks.contains_bboxes:
                h5.create_dataset("Width", shape=(num_tracks, num_frames), dtype=np.float32)
                h5.create_dataset("Height", shape=(num_tracks, num_frames), dtype=np.float32)
                h5["Width"][()] = np.vstack([tk["bbox"][:, 0] for tk in tracks])
                h5["Height"][()] = np.vstack([tk["bbox"][:, 1] for tk in tracks])


    @staticmethod
    def is_h5_file(fname):
        """Check if the file is an h5 file based on extension"""
        fname = utils.expand_path(fname)
        ext = os.path.splitext(fname)[1].lower()
        return ext in ['.h5', '.hdf5']

    @staticmethod
    def is_txt_file(fname):
        """Check if the file is a txt file based on extension"""
        fname = utils.expand_path(fname)
        ext = os.path.splitext(fname)[1].lower()
        return ext in ['.txt', '.csv']

    @staticmethod
    def blank(num_frames):
        pos = np.zeros((num_frames, 3))
        tracks = [tk.Track(pos=pos)]
        return tk.TrackCollection(tracks)

    @staticmethod
    def load(fname, video_width=None, video_height=None):
        """
        Automatically detects file type and loads appropriately
        """
        fname = utils.expand_path(fname)
        assert os.path.exists(fname), f"Path '{fname}' does not exist."

        if TrackIO.is_h5_file(fname):
            return TrackIO._load_h5(fname)
        elif TrackIO.is_txt_file(fname):
            return TrackIO._load_txt(fname, video_width, video_height)
        else:
            raise ValueError(
                f"Unsupported file format for {fname}. Expected .h5, .txt, or .csv"
            )

    @staticmethod
    def _load_h5(fname):
        """
        Loads an H5 file and return a TrackCollection
        """
        fname = utils.expand_path(fname)

        assert os.path.exists(fname), f"Path '{fname}' does not exist."


        contains_bboxes = False
        with h5py.File(fname, mode="r") as h5:
            x, y = h5["X"][()], h5["Y"][()]
            xh, yh = h5["HX"][()], h5["HY"][()]

            assert x.shape == y.shape, "Different length x and y components in track"
            num_tracks, num_frames = x.shape
            assert xh.shape == yh.shape, "Different length x and y heading components in track"
            assert x.shape == xh.shape, "Num heading vecs does not match num position vecs"


            if "Width" in h5 and "Height" in h5:
                w, h = h5["Width"][()], h5["Height"][()]
                assert w.shape == h.shape, "Width and Height data are of different lenghts"
                assert x.shape == w.shape, "Num bounding boxes does not match num position vecs"
                contains_bboxes = True

            # else:
            #     w = np.zeros(x.shape)
            #     h = np.zeros(y.shape)


            print(f"Loaded track file with {num_frames} frames and {num_tracks} tracks")

            d = h5["det"][()]
            tracks = []
            for track_idx in range(num_tracks):
                pos = np.hstack(
                    [
                        x[track_idx, :].reshape(-1, 1),
                        y[track_idx, :].reshape(-1, 1),
                        np.zeros((num_frames, 1)),
                    ]
                )
                vec = np.hstack(
                    [
                        xh[track_idx, :].reshape(-1, 1),
                        yh[track_idx, :].reshape(-1, 1),
                        np.zeros((num_frames, 1)),
                    ]
                )

                bbox = None
                if contains_bboxes:
                    bbox = np.hstack(
                        [
                            w[track_idx, :].reshape(-1, 1),
                            h[track_idx, :].reshape(-1, 1),
                        ]
                    )

                vec = utils.normalize_vecs(vec)
                det = d[track_idx]
                tracks.append(tk.Track(pos=pos, vec=vec, bbox=bbox, det=det))
        return tk.TrackCollection(tracks)

    @staticmethod
    def _load_txt(fname, video_width=None, video_height=None):
        """
        Loads a txt file with tracking data and returns a TrackCollection

        Format of txt file:
        track_number, frame_num, bite_status, x_coord, y_coord, bbox_area

        Handles 'NA' values in the file and scales coordinates to video dimensions
        """
        df = pd.read_csv(fname, header=None, sep=r',\s*', engine='python')
        df.columns = ['track', 'frame', 'bite_status', 'x', 'y', 'bbox_area']

        # Convert to numeric, NAs will become np.nan
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        scale_x = 1.0
        scale_y = 1.0

        if video_width is not None and video_height is not None:
            max_x = df['x'].max()
            max_y = df['y'].max()

            if not pd.isna(max_x) and not pd.isna(max_y) and max_x > 0 and max_y > 0:
                scale_x = video_width / max_x
                scale_y = video_height / max_y

                print(f"Scaling coordinates: x by {scale_x:.3f}, y by {scale_y:.3f}")

        track_ids = df['track'].dropna().unique().astype(int)
        num_tracks = len(track_ids)

        max_frame = int(df['frame'].max())
        num_frames = max_frame

        print(f"Loaded TXT track file with {num_frames} frames and {num_tracks} tracks")

        tracks = []
        for track_idx in track_ids:
            track_data = df[df['track'] == track_idx]

            pos = np.zeros((num_frames, 3))
            vec = np.zeros((num_frames, 3))
            det = np.zeros(num_frames, dtype=np.uint8)

            for _, row in track_data.iterrows():
                if pd.isna(row['frame']):
                    continue

                frame_num = int(row['frame'])
                frame_idx = frame_num - 1

                if 0 <= frame_idx < num_frames:
                    if not pd.isna(row['x']) and not pd.isna(row['y']):
                        pos[frame_idx, 0] = row['x'] * scale_x
                        pos[frame_idx, 1] = row['y'] * scale_y
                        det[frame_idx] = 1
                    else:  # NA COORDINATES
                        det[frame_idx] = 0

            valid_pos_indices = np.where(det == 1)[0]
            if len(valid_pos_indices) > 1:
                for i in range(1, len(valid_pos_indices)):
                    curr_idx = valid_pos_indices[i]
                    prev_idx = valid_pos_indices[i - 1]

                    direction = pos[curr_idx, :2] - pos[prev_idx, :2]
                    norm = np.linalg.norm(direction)
                    if norm > 0:
                        vec[curr_idx, 0] = direction[0] / norm
                        vec[curr_idx, 1] = direction[1] / norm

                        if curr_idx - prev_idx > 1:
                            for j in range(prev_idx + 1, curr_idx):
                                vec[j] = vec[prev_idx]

            tracks.append(tk.Track(pos=pos, vec=vec, det=det))

        return tk.TrackCollection(tracks)
