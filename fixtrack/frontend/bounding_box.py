import numpy as np

from vispy import app, scene
from vispy.color import Color


class ControlPoints(scene.visuals.Compound):
    def __init__(self, parent):
        scene.visuals.Compound.__init__(self, [])
        self.unfreeze()
        self.parent = parent
        #tracking current center & size of parent shape
        self._center = [0, 0]
        self._width = 0.0
        self._height = 0.0
        self.selected_cp = None
        self.opposed_cp = None

        #list of markers used for resizing
        self.control_points = [scene.visuals.Markers(parent=self)
                               for i in range(0, 4)]
        for c in self.control_points:
            pos = np.array([[0, 0]], dtype=np.float32)

            c.set_data(pos=pos,
                       symbol="s",
                       edge_color="red",
                       size=6)
            c.interactive = True
        self.freeze()

    def update_bounds(self):
        '''
        Updates _center, _width, _height from parent shape, then repositions control points
        '''
        self._center = [0.5 * (self.parent.bounds(0)[1] +
                               self.parent.bounds(0)[0]),
                        0.5 * (self.parent.bounds(1)[1] +
                               self.parent.bounds(1)[0])]
        self._width = self.parent.bounds(0)[1] - self.parent.bounds(0)[0]
        self._height = self.parent.bounds(1)[1] - self.parent.bounds(1)[0]
        self.update_points()

    def update_points(self):
        '''
        reposition's each control point
        '''

        # print("calling update_points")

        self.control_points[0].set_data(
            pos=np.array([[self._center[0] - 0.5 * self._width,
                           self._center[1] + 0.5 * self._height]]))
        # print(np.array([[self._center[0] - 0.5 * self._width,
        #                    self._center[1] + 0.5 * self._height]]))
        self.control_points[1].set_data(
            pos=np.array([[self._center[0] + 0.5 * self._width,
                           self._center[1] + 0.5 * self._height]]))
        self.control_points[2].set_data(
            pos=np.array([[self._center[0] + 0.5 * self._width,
                           self._center[1] - 0.5 * self._height]]))
        self.control_points[3].set_data(
            pos=np.array([[self._center[0] - 0.5 * self._width,
                           self._center[1] - 0.5 * self._height]]))
        
        # print('\n')

    def get_points(self):
        '''
        returns a shallow copy of control points for reading
        '''
        return self.control_points.copy()

    def select(self, val, obj=None):
        '''
        updates visibility
        if an object is selected, updates selected control point and opposed control point
        '''
        self.visible(val)
        self.selected_cp = None
        self.opposed_cp = None

        if obj is not None:
            n_cp = len(self.control_points)
            for i in range(0, n_cp):
                c = self.control_points[i]
                if c == obj:
                    self.selected_cp = c
                    self.opposed_cp = \
                        self.control_points[int((i + n_cp / 2)) % n_cp]

    def start_move(self, start):
        None

    def move(self, end):
        '''
        called during dragging of control point. updates _width and _height based on how far
        the control point has been moved relative to _center, then updates control point positions & parent shape dimensions
        '''
        if not self.parent.editable:
            return
        if self.selected_cp is not None:
            self._width = 2 * (end[0] - self._center[0])
            self._height = 2 * (end[1] - self._center[1])
            self.update_points()
            self.parent.update_from_controlpoints()

    def visible(self, v):
        '''
        toggles visibility of all control points
        '''
        for c in self.control_points:
            c.visible = v

    def get_center(self):
        return self._center

    def set_center(self, val):
        self._center = val
        self.update_points()

    
    def resize_shape(self, center, width, height):
        self._center = center
        self._width = width
        self._height = height
        self.update_points()


class EditVisual(scene.visuals.Compound):
    def __init__(self, editable=True, selectable=True, on_select_callback=None,
                 callback_argument=None, *args, **kwargs):
        scene.visuals.Compound.__init__(self, [], *args, **kwargs)
        self.unfreeze()
        self.editable = editable
        self._selectable = selectable
        self._on_select_callback = on_select_callback
        self._callback_argument = callback_argument
        self.control_points = ControlPoints(parent=self)
        self.drag_reference = [0, 0]
        self.freeze()

    def add_subvisual(self, visual):
        scene.visuals.Compound.add_subvisual(self, visual)
        visual.interactive = True
        self.control_points.update_bounds()
        self.control_points.visible(False)

    def select(self, val, obj=None):
        if self.selectable:
            self.control_points.visible(val)
            if self._on_select_callback is not None:
                self._on_select_callback(self._callback_argument)

    def start_move(self, start):
        self.drag_reference = start[0:2] - self.control_points.get_center()

    def move(self, end):
        if self.editable:
            shift = end[0:2] - self.drag_reference
            self.set_center(shift)

    def update_from_controlpoints(self):
        None

    @property
    def selectable(self):
        return self._selectable

    @selectable.setter
    def selectable(self, val):
        self._selectable = val

    @property
    def center(self):
        return self.control_points.get_center()

    @center.setter
    # this method redirects to set_center. Override set_center in subclasses.
    def center(self, val):
        self.set_center(val)

    # override this method in subclass
    def set_center(self, val):
        self.control_points.set_center(val[0:2])

    def select_creation_controlpoint(self):
        self.control_points.select(True, self.control_points.control_points[2])


class EditRectVisual(EditVisual):
    def __init__(self, center=[0, 0], width=20, height=20, color=(1, 0, 0, .3), *args, **kwargs):
        EditVisual.__init__(self, *args, **kwargs)
        self.unfreeze()
        self.rect = scene.visuals.Rectangle(center=center, width=width,
                                            height=height,
                                            color=color,
                                            border_color="black",
                                            border_width = 2,
                                            radius=0, parent=self)
        self.rect.interactive = True

        # self.show = True

        self.display = True

        self.freeze()
        self.add_subvisual(self.rect)
        self.control_points.visible(False)

    def set_center(self, val):
        self.control_points.set_center(val[0:2])
        self.rect.center = val[0:2]



    def resize_rect(self, center, width, height, set_points=False):
        '''
        resets center, width and height

        optional: resets control points
        '''
        self.rect.center = center
        self.rect.width = width
        self.rect.height = height
        
        if set_points:
            self.control_points.resize_shape(center, width, height)
    
    
    #part of the alpha changing experiment -> prob not needed
    def set_alpha(self, a):
        color = self.rect.color.rgba
        print(self.rect.color)
        color[3] = a
        self.rect.color = color
        self.rect.update() #force redraw?
        print(self.rect.color)

        
        # r, g, b, _ = self.rect.color.rgba
        # self._visual.set_data(
        #     center=self.center,
        #     width=self.width,
        #     height=self.height,
        #     color=(r, g, b, a),
        #     border_color=self.border_color,
        #     border_width=self.border_width,
        #     radius=self.radius,
        # )

    def hide(self):
        '''
        hides rectangle by making it transparent
        '''
        self.display = False
        self.set_alpha(0)

    def show(self):
        '''
        restores opacity of rectangle
        '''
        self.display = True
        self.set_alpha(.6)



    def update_from_controlpoints(self):
        '''
        resizes rectangle based on control point positions
        '''
        try:
            self.rect.width = abs(self.control_points._width)
        except ValueError:
            None
        try:
            self.rect.height = abs(self.control_points._height)
        except ValueError:
            None

    @property
    def width(self):
        return self.rect.width
    
    @property
    def height(self):
        return self.rect.height