import time

import numpy as np
from vispy import scene

from fixtrack.backend.track_io import TrackIO
from fixtrack.backend.video_reader import VideoReader
from fixtrack.frontend.track import TrackCollectionVisual
from fixtrack.frontend.visual_wrapper import VisualCollection, VisualWrapper
from fixtrack.frontend.track_merger import TrackMergeDialog


class CanvasBase(scene.SceneCanvas):
    def __init__(self, parent, **kwargs):
        scene.SceneCanvas.__init__(self, keys="interactive", **kwargs)
        self.unfreeze()
        self.view = self.central_widget.add_view()
        self.visuals = {}
        self._parent = parent
        self.freeze()

    @staticmethod
    def _picking_vis_setup(vis, restore=False):
        if restore:
            vis.picking_vis_restore()
            vis.set_data()
        else:
            vis.picking_vis_set()
            vis.set_data_false()

    @staticmethod
    def picking_vis_setup(vis_dict, restore=False):
        for name, visual in vis_dict.items():
            if isinstance(visual, dict):
                CanvasBase.picking_vis_setup(visual, restore)
            elif isinstance(visual, list):
                vd = {i: v for i, v in enumerate(visual)}
                CanvasBase.picking_vis_setup(vd, restore)
            elif isinstance(visual, VisualCollection):
                CanvasBase._picking_vis_setup(visual, restore)
            elif isinstance(visual, VisualWrapper):
                CanvasBase._picking_vis_setup(visual, restore)

    @staticmethod
    def _hide_visual(vis):
        # Don't hide visual if it is pickable
        pickable = True
        if getattr(vis, "pickable", None) is not None:
            pickable = vis.pickable

        v = vis.visible
        if not pickable:
            vis.visible = False

        return v

    @staticmethod
    def _hide_visuals(vis_dict):
        state = {}
        for name, visual in vis_dict.items():
            if isinstance(visual, dict):
                state[name] = CanvasBase._hide_visuals(visual)
            elif isinstance(visual, list):
                vd = {i: v for i, v in enumerate(visual)}
                state[name] = CanvasBase._hide_visuals(vd)
            elif isinstance(visual, VisualCollection):
                state[name] = CanvasBase._hide_visuals(visual.visuals)
            elif hasattr(visual, "visible"):
                state[name] = CanvasBase._hide_visual(visual)
            else:
                assert False, "Object must have visible attribute" + str(type(visual))
        return state

    @staticmethod
    def _restore_visuals(vis_dict, state):
        for name, visual in vis_dict.items():
            if isinstance(visual, dict):
                CanvasBase._restore_visuals(visual, state[name])
            elif isinstance(visual, list):
                vd = {i: v for i, v in enumerate(visual)}
                CanvasBase._restore_visuals(vd, state[name])
            elif isinstance(visual, VisualCollection):
                CanvasBase._restore_visuals(visual.visuals, state[name])
            elif hasattr(visual, "visible"):
                visual.visible = state[name]
            else:
                assert False, "Object must have visible attribute" + str(type(visual))

    def render_picking(self, event):
        self.picking_vis_setup(self.visuals, restore=False)
        pos = self.transforms.canvas_transform.map(event.pos)
        rad = 5
        img = self.render(
            (pos[0] - rad, pos[1] - rad, rad * 2 + 1, rad * 2 + 1), bgcolor=(0, 0, 0, 0)
        )
        self.picking_vis_setup(self.visuals, restore=True)
        return img


class VideoCanvas(CanvasBase):
    def __init__(self, parent, fname_video=None, fname_track=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.unfreeze()
        assert fname_video is not None, "Must provide a valid video file"
        self.video = VideoReader(fname_video)

        self.fname_tracks = fname_track
        self.fname_video = fname_video
        if self.fname_tracks is None:
            self.tracks = TrackIO.blank(self.video.num_frames)
        else:
            self.tracks = TrackIO.load(
                fname_track, video_width=self.video.width, video_height=self.video.height
            )

        self.frame_num = 0

        n = min(self.tracks.num_frames, self.video.num_frames)
        if self.video.num_frames != n:
            print(f"WARN: mismatched video and track lengths: {self.video.num_frames} != {n}")
            self.video.num_frames = n

        self.view.camera = scene.PanZoomCamera(aspect=1, up="-z")
        self.view.camera.rect = (0, 0, self.video.width, self.video.height)
        self.view.camera.flip = (False, True, False)

        self._parent = parent

        # Add video visual
        self.visuals["img"] = VisualWrapper(scene.visuals.Image(parent=self.view.scene))
        self.visuals["img"].transform = scene.STTransform(translate=[0.0, 0.0, -3.0])

        self.visuals["tracks"] = TrackCollectionVisual(self.tracks, parent=self)

        self.ts = time.time()

        self.freeze()

    def mutated(self, b=True):
        self._parent.mutated.emit(b)

    def toggle_cam(self):
        if isinstance(self.view.camera, scene.PanZoomCamera):
            self.view.camera = "turntable"
        else:
            self.view.camera = "panzoom"

    def on_frame_change(self, frame_num=None):
        # start_time = time.time()
        if frame_num is not None:
            self.frame_num = frame_num

        # frame_fetch_start = time.time()
        img = self.video.get_frame(self.frame_num)
        # frame_fetch_end = time.time()

        # set_data_start = time.time()
        self.visuals["img"].set_data(img)
        # set_data_end = time.time()

        # camera_start = time.time()
        if not isinstance(self.view.camera, scene.cameras.PanZoomCamera):
            idx_track = self._parent.track_edit_bar.idx_selected()
            if self.tracks[idx_track]["det"][self.frame_num]:
                self.view.camera.center = self.tracks[idx_track]["pos"][self.frame_num
                                                                        ] + [0.0, 0.0, 20.0]
                vec = self.tracks[idx_track]["vec"][self.frame_num]
                ang = np.arctan2(vec[1], vec[0])
                self.view.camera.azimuth = ang * 180.0 / np.pi - 90.0
        # camera_end = time.time()

        # update_start = time.time()
        self.update()
        # update_end = time.time()

        # tracks_start = time.time()
        self.visuals["tracks"].on_frame_change(frame_num)
        # tracks_end = time.time()

        # end_time = time.time()
        # target_frame_time = 1.0 / self.video.fps if hasattr(self.video, 'fps') else 0
        # lag = (end_time - start_time) - target_frame_time if target_frame_time > 0 else 0
        # lag = max(0, lag)
        # print(f"Frame {self.frame_num} timing:")
        # print(f"  Get frame: {(frame_fetch_end - frame_fetch_start)*1000:.2f}ms")
        # print(f"  Set data: {(set_data_end - set_data_start)*1000:.2f}ms")
        # print(f"  Camera adjust: {(camera_end - camera_start)*1000:.2f}ms")
        # print(f"  Update view: {(update_end - update_start)*1000:.2f}ms")
        # print(f"  Tracks update: {(tracks_end - tracks_start)*1000:.2f}ms")
        # print(f"  Total time: {(end_time - start_time)*1000:.2f}ms")
        # print(f"  Target frame time: {target_frame_time*1000:.2f}ms")
        # print(f"  Lag: {lag*1000:.2f}ms")

    def show_track_merger(self):
        if not hasattr(self, 'track_merger_dialog') or self.track_merger_dialog is None:
            self.unfreeze()
            self.track_merger_dialog = TrackMergeDialog(self.tracks, parent=self._parent)
            self.freeze()
            self.track_merger_dialog.tracks_merged.connect(self.on_tracks_merged)

        self.track_merger_dialog.show()
        self.track_merger_dialog.raise_()
        self.track_merger_dialog.activateWindow()

    def on_tracks_merged(self):
        self.on_frame_change(self.frame_num)
        self.mutated(True)

    def on_mouse_press(self, event):
        img = self.render_picking(event)
        for v in self.visuals.values():
            if hasattr(v, "on_mouse_press"):
                v.on_mouse_press(event, img)

    def on_mouse_release(self, event):
        img = self.render_picking(event)
        for v in self.visuals.values():
            if hasattr(v, "on_mouse_release"):
                v.on_mouse_release(event, img)

    def on_mouse_move(self, event):
        img = self.render_picking(event)
        for v in self.visuals.values():
            if hasattr(v, "on_mouse_move"):
                v.on_mouse_move(event, img)

    def on_key_press(self, event):
        # Forward the Qt event to the parent
        if len(event.modifiers) and ("Control" in event.modifiers):
            self.view.camera.interactive = False
            if event.key == 'M':
                self.show_track_merger()
                return
        self._parent.keyPressEvent(event._native)

    def on_key_release(self, event):
        # Forward the Qt event to the parent
        self.view.camera.interactive = True
        self._parent.keyReleaseEvent(event._native)
