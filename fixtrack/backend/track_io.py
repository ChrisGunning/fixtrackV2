import os

import h5py as h5py
import numpy as np

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
    def blank(num_frames):
        pos = np.zeros((num_frames, 3))
        tracks = [tk.Track(pos=pos)]
        return tk.TrackCollection(tracks)

    @staticmethod
    def load(fname):
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
