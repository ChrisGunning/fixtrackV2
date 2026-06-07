import numpy as np
from PyQt5 import QtCore
from vispy import scene, util

from fixtrack.common.utils import color_from_index, normalize_vecs
from fixtrack.frontend.pickable_line import PickableLine
from fixtrack.frontend.pickable_markers import PickableMarkers
from fixtrack.frontend.visual_wrapper import VisualCollection, VisualWrapper

from fixtrack.frontend.bounding_box import ControlPoints, EditRectVisual


import time

class TrackCollectionVisual(VisualCollection):
    """
    A visual collection consisting of a line, pickable markers, and heading vectors
    """

    sig_frame_change = QtCore.pyqtSignal(int)

    def __init__(self, tracks, parent=None, enabled=True, visible=True):
        super(TrackCollectionVisual,
              self).__init__(parent=parent, enabled=enabled, visible=visible)
        
        self.tracks = tracks
        self.parent = parent
        self.visible_tracks = set()
        self.pos, self.seg, self.vec = self.get_data()

        #{key: track_ID, value: EditRectVisual (bbox)}
        self.current_boxes = {}

        #stores if data (markers, bboxes, segments) should be displayed
        self.force_display_all = True

        self.selected_control_point = None
        self.mouse_start_pos = [0, 0]

        #caches index of currently selected track
        self.selected_track = None

        #velocity vectors
        self.visuals["headings"] = PickableLine(
            parent=self.parent.view.scene,
            data=self.vec,
            pickable=True,
            selectable=False,
            hoverable=True,
            vis_args={
                "width": 10,
                "color_hover": [0, 0, 0, 0.85],
                "color_select": [1, 0, 0, 0.85]
            },
            cmap_func=self.cmap_vec_func,
        )

        #(x, y) positions
        self.visuals["markers"] = PickableMarkers(
            parent=self.parent.view.scene,
            data=self.pos,
            pickable=True,
            selectable=False,
            hoverable=True,
            vis_args={
                "size": 15,
                "color_hover": [1, 0, 0, 0.5],
                "color_select": [1, 1, 0, 0.5],
            },
            select_scale=2.5,
            cmap_func=self.cmap_pos_func,
        )
        self.visuals["markers"].sig_point_clicked.connect(self.slot_marker_clicked)


        #segments connecting (x, y) markers?
        self.visuals["traces"] = VisualWrapper(
            scene.visuals.Line(
                self.seg,
                connect="segments",
                color=self.cmap_seg_func(self.seg),
                width=5,
                parent=self.parent.view.scene
            ),
            segs=self.seg,
            width=10,
            connect="segments",
        )
        self._sync_visuals()
        self.set_data()

    @property
    def frame_num(self):
        return self._parent.frame_num

    def add_bbox(self, i=None):

            frame = self.frame_num #ie current frame
            if i is None:
                i = self.tracks.num_tracks-1 #adding new track (+1 not needed, 0 indexing)

            colors = color_from_index(range(self.tracks.num_tracks))
            colors[:, 3] = .6 #specify alpha
            vis = True

            track = self.tracks[i]
            w, h = track["bbox"][frame][0], track["bbox"][frame][1]

            if w <= 0 or h <= 0:
                    w = h = 1
                    vis = False

            rect = EditRectVisual(
                center = track["pos"][frame][:2],
                width = w,
                height = h,
                color = colors[i],
                parent = self.parent.view.scene,
            )

            rect.visible = vis
            self.current_boxes[i] = rect


    def draw_bboxes(self, frame):
        '''
        draws bounding boxes for all VISIBLE tracks at the frame frame
        '''

        if not self.tracks.contains_bboxes:
            return

        # Update/create boxes for visible tracks
        for idx in self.visible_tracks:

            if idx not in self.current_boxes:
                self.add_bbox(idx)

            track = self.tracks[idx]
            bbox = self.current_boxes[idx]

            w, h = track["bbox"][frame][0], track["bbox"][frame][1]

            # Hide if bbox data doesn't exist
            if w <= 0 or h <= 0:
                bbox.visible = False

                # hide control points too
                if hasattr(bbox, "control_points"):
                    bbox.control_points.visible(False)

                continue

            center = track["pos"][frame][:2]

            # Valid bbox data -> always show
            bbox.visible = True

            if idx == self.selected_track:
                bbox.resize_rect(center, w, h, set_points=True)

                if hasattr(bbox, "control_points"):
                    bbox.control_points.visible(True)

            else:
                bbox.resize_rect(center, w, h, set_points=False)

                if hasattr(bbox, "control_points"):
                    bbox.control_points.visible(False)

        # Remove boxes for tracks that are no longer visible
        for idx in list(self.current_boxes.keys()):
            if idx not in self.visible_tracks:

                bbox = self.current_boxes[idx]

                if hasattr(bbox, "control_points"):
                    bbox.control_points.parent = None

                bbox.parent = None
                del self.current_boxes[idx]

    def on_frame_change(self, frame_num=None, refresh_data=True, draw_bboxes = True):

        if refresh_data:
            self.pos, self.seg, self.vec = self.get_data()

            self.visuals["markers"].set_data(self.pos)
            self.visuals["headings"].set_data(self.vec)
            self.visuals["traces"].visual.set_data(pos=self.seg, color=self.cmap_seg_func(self.seg)) #only changes w/ data updates

            #no redraw for toggling, yes redraw for reposition boxes
            if self.tracks.contains_bboxes:
                self.draw_bboxes(self.frame_num)
            
            return

        if frame_num is not None:
             #highlighting marker / dot on current frame
            self.visuals["markers"].set_selected(frame_num)
            self.visuals["markers"].set_data(self.pos)

            if self.tracks.contains_bboxes:
                self.draw_bboxes(frame_num)


    def slot_set_track_vis(self, idx, vis):
            """
            Slot function for toggling visiblity of a single track
            """
            if idx not in range(self.tracks.num_tracks):
                return
            
            if vis:
                self.visible_tracks.add(idx)
            elif idx in self.visible_tracks:
                self.visible_tracks.remove(idx)

            self.tracks[idx].visible = vis
            self.draw_bboxes(self.frame_num)
            if self.tracks.contains_bboxes and idx in self.current_boxes:
                self.current_boxes[idx].visible = vis
            self.on_frame_change()


    def set_all_track_visibilities(self, indices, vis):
        """
        Sets the visibility state for specificed tracks
        """
        #update class var
        self.force_display_all = vis

        for i in indices:

            if vis:
                self.visible_tracks.add(i)
            else:
                self.visible_tracks.discard(i)

            self.tracks[i].visible = vis

        if "markers" in self.visuals:
            self.visuals["markers"].multi_sel = []

        self.on_frame_change()
    
    
    def set_all_bbox_vis(self, indices, vis):
        '''
        Sets visibility for all bboxes to vis (if dataset contains bboxes)
        '''
        for i in indices:

            if i not in self.current_boxes:
                continue

            self.current_boxes[i].visible = vis

            if hasattr(self.current_boxes[i], "control_points"):
                self.current_boxes[i].control_points.visible(
                    vis and i == self.selected_track
                )

        self.parent.view.update()



    def track_address_from_vec_idx(self, vec_idx):
        '''
        returns track ID
        '''
        visual_track_idx = vec_idx // self.tracks.num_frames
        frame_idx = vec_idx % self.tracks.num_frames

        if len(self._display_track_ids) == 0:
            return None, frame_idx

        track_idx = self._display_track_ids[visual_track_idx]

        return track_idx, frame_idx
    

    def _get_empty_data(self, vec_len=25):
            '''
            Returns dummy data (prevent crashes on empty data)
            '''
            n_frames = len(self.tracks[0])

            pos = np.zeros((n_frames, 3), dtype=np.float32)

            seg = np.repeat(pos, 2, axis=0)[1:-1]

            vec = np.zeros((2 * n_frames, 3), dtype=np.float32)
            vec[0::2] = pos
            vec[1::2] = pos
            vec[1::2, 0] += vec_len

            return pos, seg, vec

    def get_data(self, vec_len=25):
        """
        Get position, segment, and heading vector data.
        """
        visible_ids = sorted(self.visible_tracks)
        self._display_track_ids = visible_ids

        if not visible_ids:
            return self._get_empty_data(vec_len)

        tracks = [self.tracks[i] for i in visible_ids]


        pos = np.vstack([track["pos"] for track in tracks])
        seg = np.vstack([
            np.repeat(track["pos"], 2, axis=0)[1:-1]
            for track in tracks
        ])

        v = normalize_vecs(np.vstack([track["vec"] for track in tracks]))

        vec = np.empty((2 * len(pos), 3))
        vec[0::2] = pos
        vec[1::2] = pos + v * vec_len

        return pos, seg, vec


    def _get_display_tracks(self):
        """
        Returns (display_ids, display_tracks)

        display_ids:
            original track ids in the backend

        display_tracks:
            track objects corresponding to currently rendered data
        """
        display_ids = getattr(self, "_display_track_ids", [])

        tracks = [
            self.tracks[idx]
            for idx in display_ids
        ]

        return display_ids, tracks

    def cmap_pos_func(self, data, alpha=0.5):

        if len(data) == 0:
            return np.zeros((0, 4), dtype=np.float32)

        display_ids, display_tracks = self._get_display_tracks()

        if len(display_ids) == 0:
            return np.zeros((len(data), 4), dtype=np.float32)

        all_colors = color_from_index(range(self.tracks.num_tracks))
        all_colors[:, 3] = alpha

        c_ctrl = [0.0, 1.0, 0.0, alpha]

        frames_per_track = len(data) // len(display_ids)

        colors = np.empty((len(data), 4))
        colors[:, 3] = alpha

        if "markers" in self.visuals:
            self.visuals["markers"].multi_sel = []

        for visual_idx, (track_id, track) in enumerate(
            zip(display_ids, display_tracks)
        ):

            frame_idx = visual_idx * frames_per_track

            colors[
                frame_idx:frame_idx + frames_per_track
            ] = all_colors[track_id]

            colors[
                np.where(track["ctr"])[0] + frame_idx
            ] = c_ctrl

            if "markers" in self.visuals:
                self.visuals["markers"].multi_sel.append(
                    frame_idx + self.frame_num
                )

            det = track["det"]

            colors[
                frame_idx:frame_idx + frames_per_track
            ][:, 3] *= det

            if hasattr(self._parent._parent, "player_controls"):
                idx_a = self._parent._parent.player_controls._idx_sel_a
                idx_b = self._parent._parent.player_controls._idx_sel_b + 1

                colors[
                    frame_idx:frame_idx + frames_per_track
                ][:idx_a, 3] *= 0

                colors[
                    frame_idx:frame_idx + frames_per_track
                ][idx_b:, 3] *= 0

        return colors
    

    def cmap_seg_func(self, data, alpha=0.5):

        if len(data) == 0:
            return np.zeros((0, 4), dtype=np.float32)

        display_ids, display_tracks = self._get_display_tracks()

        if len(display_ids) == 0:
            return np.zeros((len(data), 4), dtype=np.float32)

        all_colors = color_from_index(range(self.tracks.num_tracks))
        all_colors[:, 3] = alpha

        chunk_len = len(data) // len(display_ids)

        colors = np.empty((len(data), 4))
        colors[:, 3] = alpha

        for visual_idx, (track_id, track) in enumerate(
            zip(display_ids, display_tracks)
        ):

            frame_idx = visual_idx * chunk_len

            det = np.repeat(track["det"], 2)

            colors[
                frame_idx:frame_idx + chunk_len
            ] = all_colors[track_id]

            colors[
                frame_idx:frame_idx + chunk_len
            ][:, 3] *= det[1:-1]

            colors[
                frame_idx:frame_idx + chunk_len
            ][:, 3] *= det[:-2]

            colors[
                frame_idx:frame_idx + chunk_len
            ][:, 3] *= det[2:]

            if hasattr(self._parent._parent, "player_controls"):
                idx_a = self._parent._parent.player_controls._idx_sel_a
                idx_b = self._parent._parent.player_controls._idx_sel_b + 1

                colors[
                    frame_idx:frame_idx + chunk_len
                ][:idx_a * 2, 3] *= 0

                colors[
                    frame_idx:frame_idx + chunk_len
                ][idx_b * 2:, 3] *= 0

        return colors
    
    def cmap_vec_func(self, data, alpha=0.5):

        if len(data) == 0:
            return np.zeros((0, 4), dtype=np.float32)

        display_ids, display_tracks = self._get_display_tracks()

        if len(display_ids) == 0:
            return np.zeros((len(data), 4), dtype=np.float32)

        all_colors = color_from_index(range(self.tracks.num_tracks))
        all_colors[:, 3] = alpha

        chunk_len = len(data) // len(display_ids)

        colors = np.empty((len(data), 4))
        colors[:, 3] = alpha

        for visual_idx, (track_id, track) in enumerate(
            zip(display_ids, display_tracks)
        ):

            frame_idx = visual_idx * chunk_len

            det = np.repeat(track["det"], 2)

            colors[
                frame_idx:frame_idx + chunk_len
            ] = all_colors[track_id]

            current_vec_idx = frame_idx + 2 * self.frame_num

            if current_vec_idx + 1 < len(colors):
                colors[current_vec_idx] = [1.0, 0.0, 0.0, 1.0]
                colors[current_vec_idx + 1] = [1.0, 0.0, 0.0, 1.0]

            colors[
                frame_idx:frame_idx + chunk_len
            ][:, 3] *= det

            if hasattr(self._parent._parent, "player_controls"):
                idx_a = self._parent._parent.player_controls._idx_sel_a
                idx_b = self._parent._parent.player_controls._idx_sel_b + 1

                colors[
                    frame_idx:frame_idx + chunk_len
                ][:idx_a * 2, 3] *= 0

                colors[
                    frame_idx:frame_idx + chunk_len
                ][idx_b * 2:, 3] *= 0

        return colors


    def slot_marker_clicked(
        self, id_clicked, idx_sel, idx_sel_prev, idx_clicked, idx_hover, modifiers
    ):
        '''
        Updates UI to select the track belonging to the clicked marker
        Updates video to the frame at which marker was clicked
        '''
        idx_track, idx_frame = self.track_address_from_vec_idx(idx_clicked)
        self._parent._parent.track_edit_bar.track_widgets[idx_track].btn_selected.animateClick()
        self._parent._parent.top_level_ctrls.cb_marker_clicked(idx_track, idx_frame, modifiers)
        self._parent._parent.player_controls.set_frame_num(idx_frame)

         #bbox resize markers visible for the selected track
        if self.tracks.contains_bboxes and self.selected_track != idx_track and idx_track < len(self.current_boxes):
            if self.selected_track is not None and self.selected_track < len(self.current_boxes):
                self.current_boxes[self.selected_track].control_points.visible(False)
        
        self.selected_track = idx_track

        if self.tracks.contains_bboxes:
            if self.selected_track < len(self.current_boxes):
                self.current_boxes[self.selected_track].control_points.visible(True)
            self.draw_bboxes(idx_frame) #forced redraw for control points


    def marker_clicked(self, click_pos, cp_container, radius = 5):
        '''
        Checks if a control point for cp_container has been clicked

        Args:
            click_pos () : mouse click position
            cp_container (EditRectVisual) : a bbox
        '''
        for i, cp in enumerate(cp_container.control_points):
            # each cp is a Markers visual with 1 point
            cp_pos = cp._data['a_position'][0]  # (x, y, z) in data coords

            dx, dy = click_pos[0] - cp_pos[0], click_pos[1] - cp_pos[1]
            if dx * dx + dy * dy <= (radius ** 2):   # radius = 5 (data coords)
                return cp        
        return None


    def on_mouse_press(self, event, img):
        edit_bar = self._parent._parent.track_edit_bar
        top_level_ctrls = self._parent._parent.top_level_ctrls
        interp_l = top_level_ctrls.btn_interp_l.isChecked()
        interp_r = top_level_ctrls.btn_interp_r.isChecked()
        for v in self.visuals.values():
            if hasattr(v, "on_mouse_press"):
                v.on_mouse_press(event, img)
        c0 = self.visuals["markers"].idx_clicked >= 0
        c1 = self.visuals["headings"].idx_clicked >= 0

        #handle bbox control points
        if self.tracks.contains_bboxes and self.selected_track is not None:

            cp_container = self.current_boxes[self.selected_track].control_points
            cp_container.visible(True)

            # convert mouse click from screen to data coordinates
            tr = self.parent.scene.node_transform(self.parent.view.scene)
            pos_data = tr.map(event.pos)

            selected = self.marker_clicked(pos_data, cp_container)

            # clear out old selection
            if self.selected_control_point is not None:
                self.selected_control_point.select(False)
                self.selected_control_point = None

            # if clicked on a control point
            if event.button == 1 and selected is not None:
                self.selected_control_point = cp_container

                # map click into the control point's local system
                tr = self.parent.scene.node_transform(cp_container)
                pos_local = tr.map(event.pos)

                cp_container.select(True, obj=selected)
                cp_container.start_move(pos_local)
                self.mouse_start_pos = event.pos

            else:
                self.selected_control_point = None


        #Shift + left click, neither marker nor header clicked => add data
        if (util.keys.SHIFT in event.modifiers) and (event.button == 1) and not (c0 or c1):
            if not isinstance(self._parent.view.camera, scene.PanZoomCamera):
                return
            click_pos = self._parent.view.camera.transform.imap(event.pos)[:3]

            idx_track = edit_bar.idx_selected()

            if idx_track >= 0:
                #add pos, vec data for track idx_track at the current frame
                self.tracks.add_det(
                    idx_track, self.frame_num, click_pos, interp_l=interp_l, interp_r=interp_r
                )
                self._parent.mutated()
                self._parent.on_frame_change()


        #Shift + right click, either marker or header clicked => remove data
        elif (util.keys.SHIFT in event.modifiers) and (event.button == 2) and (c0 or c1):
            idx_track, idx_frame = self.track_address_from_vec_idx(
                max(self.visuals["headings"].idx_clicked, self.visuals["markers"].idx_clicked)
            )

            if self.tracks[idx_track]["ctr"][idx_frame]:
                self.tracks[idx_track].rem_ctrl_pt(idx_frame)
            else:
                self.tracks.rem_det(idx_track, idx_frame)

                #clear out bbox
                if self.tracks.contains_bboxes and self.selected_track is not None:
                    track = self.tracks[self.selected_track]
                    track["bbox"][self.frame_num][0], track["bbox"][self.frame_num][1] = 0, 0


                self.visuals["headings"].deselect()
                self.visuals["markers"].deselect()
            self._parent.mutated()
            self._parent.on_frame_change()

    def on_mouse_release(self, event, img):
        for v in self.visuals.values():
            if hasattr(v, "on_mouse_release"):
                v.on_mouse_release(event, img)
        self._mouse_down = False
        self._parent.view.camera.interactive = True

    def on_mouse_move(self, event, img):
        top_level_ctrls = self._parent._parent.top_level_ctrls
        interp_l = top_level_ctrls.btn_interp_l.isChecked()
        interp_r = top_level_ctrls.btn_interp_r.isChecked()

        #other visuals custom react to mouse movement
        for v in self.visuals.values():
            if hasattr(v, "on_mouse_move"):
                v.on_mouse_move(event, img)

        click_pos = self._parent.view.camera.transform.imap(event.pos)[:3]
        if not isinstance(self._parent.view.camera, scene.PanZoomCamera):
            return
        
        if event.button == 1:
            if self.selected_control_point is not None:
                self.parent.view.camera._viewbox.events.mouse_move.disconnect(
                    self.parent.view.camera.viewbox_mouse_event)
                # update transform to selected object
                tr = self.parent.scene.node_transform(self.selected_control_point)
                pos = tr.map(event.pos)

                self.selected_control_point.move(pos[0:2])

                #write new bbox data to backend (ie track instance)
                w = self.current_boxes[self.selected_track].width
                h = self.current_boxes[self.selected_track].height
                track = self.tracks[self.selected_track]
                track["bbox"][self.frame_num][0], track["bbox"][self.frame_num][1] = w, h

            else:
                self.parent.view.camera._viewbox.events.mouse_move.connect(
                    self.parent.view.camera.viewbox_mouse_event)
        else:
            None


        trail = event.trail()
        #Shift + left click
        if (util.keys.SHIFT in event.modifiers) and (event.button == 1):

            #edit heading (direction) vector
            if (self.visuals["headings"].idx_clicked >= 0) and (trail is not None):
                idx_track, idx_frame = self.track_address_from_vec_idx(
                    self.visuals["headings"].idx_clicked
                )
                if not self._mouse_down:
                    self._mouse_down = True
                    self.tracks.tracks[idx_track].add_undo_event()
                track_pos = self.tracks.tracks[idx_track]["pos"][idx_frame]
                vec = click_pos - track_pos
                vec = normalize_vecs(vec)
                self.tracks.tracks[idx_track].move_vec(
                    idx_frame, vec, interp_l=interp_l, interp_r=interp_r
                )
                self._parent.mutated()
                self._parent.on_frame_change()

            #edit position marker
            elif (self.visuals["markers"].idx_clicked >= 0) and (trail is not None):
                idx_track, idx_frame = self.track_address_from_vec_idx(
                    self.visuals["markers"].idx_clicked
                )
                if not self._mouse_down:
                    self._mouse_down = True
                    self.tracks.tracks[idx_track].add_undo_event()
                self.tracks.tracks[idx_track].move_pos(
                    idx_frame, click_pos, interp_l=interp_l, interp_r=interp_r
                )
                self._parent.mutated()
                self._parent.on_frame_change()