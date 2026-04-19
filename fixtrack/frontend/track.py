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

    #TODO: create self.visuals["bounding_boxes"] = instance of custom bounding box class
        #the bounding box class should be pickable (inherit pickeable base)
    def __init__(self, tracks, parent=None, enabled=True, visible=True):
        super(TrackCollectionVisual,
              self).__init__(parent=parent, enabled=enabled, visible=visible)
        self.tracks = tracks
        self.show_pos = True

        self.parent = parent

        #cache data! (will need to get bound box data too)
        self.pos, self.seg, self.vec = self.get_data()

        #stores if data (markers, bboxes, segments) should be displayed
        self.force_display_all = True

        if self.tracks.contains_bboxes:
            self.init_bboxes(frame=0)

        self.selected_control_point = None
        self.mouse_start_pos = [0, 0]


        # self.visuals["bboxes"] =

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
    


    #TODO: remove frame parameter? we always init at frame 0?
    def init_bboxes(self, frame):
        '''
        initializes a bounding box for each track at frame frame
        '''
        self.current_boxes = []
        for i in range(self.tracks.num_tracks):
            self.add_bbox(frame, i)
    
    def add_bbox(self, frame = None, i = None):
        '''
        adds a new bounding box at for the ith track
        if i is not specified, (it is because a new track was introduced)
        '''
        if frame is None:
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
        self.current_boxes.append(rect)

        for i in range(len(self.current_boxes)):
            self.current_boxes[i].rect.color = colors[i]
        


    def remove_bbox(self, i = None):        
        if i is None:
            i = self.tracks.num_tracks-1
        else:
            assert i >= 0 and i < self.tracks.num_tracks, f"cannot delete bbox for track {i}"

        bbox = self.current_boxes[i]
        if bbox is not None:
            bbox.parent = None  # Remove from scene
        self.current_boxes.pop(i)  # Remove from list

        #recolor boxes
        colors = color_from_index(range(len(self.current_boxes)))
        colors[:, 3] = .6 #specify alpha
        for i in range(len(self.current_boxes)):
            self.current_boxes[i].rect.color = colors[i]



    def draw_bboxes(self, frame):
        '''
        draws bounding boxes for all tracks at the frame frame
        updates control point marker positions for the selected track only
        '''
        for i in range(self.tracks.num_tracks):
            track = self.tracks[i]
            w, h = track["bbox"][frame][0], track["bbox"][frame][1]

            bbox = self.current_boxes[i]

            # TODO: don't directly change visibility tag, just color clear

            #hide boxes without data
            if w <= 0 or h <= 0:
                bbox.visible = False
                continue
            #show valid data only if forced
            elif self.force_display_all and bbox.visible == False:
                bbox.visible = True


            center = track["pos"][frame][:2]
            if i == self.selected_track:
                bbox.resize_rect(center, w, h, set_points=True)
                self.current_boxes[self.selected_track].control_points.visible(True)
            else:
                bbox.resize_rect(center, w, h, set_points=False)


    #TODO: only refetch data when it has been modified (keep dirty tag?)
    def on_frame_change(self, frame_num=None, refresh_data=True, draw_bboxes = True):

        start = time.time()
        #redraw all data when data is edited (still extremely costly... possible to only redraw edited data only - pass as optional argument indexes of tracks edited)
        if refresh_data:
            # print("refreshing data at frame " + str(frame_num))
            self.pos, self.seg, self.vec = self.get_data()
            self.visuals["markers"].set_data(self.pos)
            self.visuals["headings"].set_data(self.vec)
            self.visuals["traces"].visual.set_data(pos=self.seg, color=self.cmap_seg_func(self.seg)) #only changes w/ data updates

            #no redraw for toggling, yes redraw for reposition boxes        
            if draw_bboxes and self.tracks.contains_bboxes:
                self.draw_bboxes(self.frame_num)

            end = time.time()
            # print(f"on_frame_change took: {end - start:.4f} seconds")
            return

        #given frame num when playing video
        # if frame_num is not None and self.tracks.num_visible_tracks > 0: #part of filtering only visible tracks
        

        if frame_num is not None:
             #highlighting marker / dot on current frame

            # #TODO: calls to set_data are very expensive just for a single visual update.
            self.visuals["markers"].set_selected(frame_num)
            self.visuals["markers"].set_data(self.pos)

            if self.tracks.contains_bboxes:
                self.draw_bboxes(frame_num)


        end = time.time()
        print(f"on_frame_change took: {end - start:.4f} seconds")



    def slot_set_track_vis(self, idx, vis):
        """
        Slot function for toggling visiblity of a single track

        Args:
            idx (int): index of track to toggle
            vis (bool): new visibility state
        """
        self.tracks[idx].visible = vis
        if self.tracks.contains_bboxes:
            self.current_boxes[idx].visible = vis
        self.on_frame_change(draw_bboxes=False)


    def set_all_track_vis(self, indices, vis):
        """
        Sets the visibility state for specificed tracks

        Args:
            indices (list): list of track indices to toggle
            vis (bool): new visibility state
        """
        #update class var
        self.force_display_all = vis

        for i in indices:
            self.tracks[i].visible = vis
            if self.tracks.contains_bboxes:
                self.current_boxes[i].visible = vis
        self.on_frame_change(draw_bboxes=False)
    
    
    def set_all_bbox_vis(self, indices, vis):
        '''
        Sets visibility for all bboxes to vis (if dataset contains bboxes)
        '''
        self.force_display_all = vis

        for i in indices:
            if self.tracks.contains_bboxes:
                self.current_boxes[i].visible = vis
        self.on_frame_change()


    def track_address_from_vec_idx(self, vec_idx):
        track_idx = vec_idx // self.tracks.num_frames
        frame_idx = vec_idx % self.tracks.num_frames
        return track_idx, frame_idx


    #TODO: retrieve width + height data as well
    def get_data(self, vec_len=25):
        """
        Get position, segment, and heading vector data.

        Args:
            vec_len (int): Length to scale the heading vectors. Default is 25.

        Returns:
            tuple: A tuple of three NumPy arrays:
                - pos (ndarray): Marker positions, shape (N, 3).
                - seg (ndarray): Segments connecting markers, shape (M, 3).
                - vec (ndarray): Heading vectors (start and end points), shape (2N, 3).
        """
        #original version: returns all tracks (even those toggled OFF! -> expensive set_data for invisible tracks)
        pos = np.vstack([track["pos"] for track in self.tracks])
        seg = np.vstack([np.repeat(track["pos"], 2, axis=0)[1:-1] for track in self.tracks])
        v = normalize_vecs(np.vstack([track["vec"] for track in self.tracks]))
        vec = np.zeros((2 * len(pos), 3))
        vec[0::2] = pos
        vec[1::2] = pos + v * vec_len
        return pos, seg, vec
    
    def cmap_pos_func(self, data, alpha=0.5):
        '''
        Returns colors for all position markers

        To color visible tracks, 20 unique colors are used in rotation
        Non-visible tracks are colored transparent (alpha = 0)
        '''
        c = color_from_index(range(self.tracks.num_tracks)) #unique colors for indices
        c_ctrl = [0.0, 1.0, 0.0, alpha] #what is being colored green?
        c[:, 3] = alpha #syntax: all rows, col 3 = alpha
        assert (len(data) % self.tracks.num_tracks) == 0
        frames_per_track = len(data) // self.tracks.num_tracks
        colors = np.empty((len(data), 4))
        colors[:, 3] = alpha
        if "markers" in self.visuals:
            self.visuals["markers"].multi_sel = [] #reset multi selection list
        for track_idx, track in enumerate(self.tracks):
            frame_idx = track_idx * frames_per_track
            colors[frame_idx:frame_idx + frames_per_track] = c[track_idx]
            colors[np.where(track["ctr"])[0] + frame_idx] = c_ctrl #control points are drawn in green
            if "markers" in self.visuals:
                self.visuals["markers"].multi_sel.append(frame_idx + self.frame_num)
            det = track["det"]
            colors[frame_idx:frame_idx + frames_per_track][:, 3] *= det #alpha val 0 if not detected
            colors[frame_idx:frame_idx + frames_per_track][:, 3] *= track.visible #alpha val 0 if not visible

            #coloring only selected range of frames
            if hasattr(self._parent._parent, "player_controls"):
                idx_a = self._parent._parent.player_controls._idx_sel_a
                idx_b = self._parent._parent.player_controls._idx_sel_b + 1
                colors[frame_idx:frame_idx + frames_per_track][:idx_a, 3] *= 0 #transparent before index a
                colors[frame_idx:frame_idx + frames_per_track][idx_b:, 3] *= 0 #transparent after index b
        return colors

    def cmap_seg_func(self, data, alpha=0.5):
        c = color_from_index(range(self.tracks.num_tracks))
        c[:, 3] = alpha
        assert (len(data) % self.tracks.num_tracks) == 0
        chunk_len = len(data) // self.tracks.num_tracks
        colors = np.empty((len(data), 4))
        colors[:, 3] = alpha
        for track_idx, track in enumerate(self.tracks):
            frame_idx = track_idx * chunk_len
            det = np.repeat(track["det"], 2)

            colors[frame_idx:frame_idx + chunk_len] = c[track_idx]
            colors[frame_idx:frame_idx + chunk_len][:, 3] *= det[1:-1]
            colors[frame_idx:frame_idx + chunk_len][:, 3] *= det[0:-2]
            colors[frame_idx:frame_idx + chunk_len][:, 3] *= det[2:]

            colors[frame_idx:frame_idx + chunk_len][:, 3] *= track.visible

            if hasattr(self._parent._parent, "player_controls"):
                idx_a = self._parent._parent.player_controls._idx_sel_a
                idx_b = self._parent._parent.player_controls._idx_sel_b + 1
                colors[frame_idx:frame_idx + chunk_len][:idx_a * 2, 3] *= 0
                colors[frame_idx:frame_idx + chunk_len][idx_b * 2:, 3] *= 0
        return colors

    def cmap_vec_func(self, data, alpha=0.5):
        c = color_from_index(range(self.tracks.num_tracks))
        c[:, 3] = alpha
        assert (len(data) % self.tracks.num_tracks) == 0
        chunk_len = len(data) // self.tracks.num_tracks
        colors = np.empty((len(data), 4))
        colors[:, 3] = alpha
        for track_idx, track in enumerate(self.tracks):
            frame_idx = track_idx * chunk_len
            det = np.repeat(track["det"], 2)
            colors[frame_idx:frame_idx + chunk_len] = c[track_idx]
            colors[frame_idx + 2 * self.frame_num] = [1.0, 0.0, 0.0, 1.0]
            colors[frame_idx + 2 * self.frame_num + 1] = [1.0, 0.0, 0.0, 1.0]
            colors[frame_idx:frame_idx + chunk_len][:, 3] *= det
            colors[frame_idx:frame_idx + chunk_len][:, 3] *= track.visible
            if hasattr(self._parent._parent, "player_controls"):
                idx_a = self._parent._parent.player_controls._idx_sel_a
                idx_b = self._parent._parent.player_controls._idx_sel_b + 1
                colors[frame_idx:frame_idx + chunk_len][:idx_a * 2, 3] *= 0
                colors[frame_idx:frame_idx + chunk_len][idx_b * 2:, 3] *= 0
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


        print(self.visuals["markers"].idx_clicked)


        #handle bbox control points
        if self.tracks.contains_bboxes and self.selected_track is not None and self.selected_track < len(self.current_boxes):
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
                print("calling add_detection for track " + str(idx_track))
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

            print("attempting removal for track: " + str(idx_track))

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
        



        #TODO: when resizing, save the data to self.tracks[self.selected_track]

        # track = self.tracks[i]
        # w, h = track["bbox"][frame][0], track["bbox"][frame][1]


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

                # print("resized track " + str(self.selected_track) + " to " + str(w) + ", " + str(h))

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