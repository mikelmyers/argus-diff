"""Rendering behavior that does not require a graphics context."""

from argus_diff.render import _fit_views


class _Camera:
    elevation = 0


class _Plotter:
    def __init__(self):
        self.camera = _Camera()
        self.camera_positions = []
        self.fit_panes = []
        self.active_pane = None

    def subplot(self, row, pane):
        assert row == 0
        self.active_pane = pane

    @property
    def camera_position(self):
        return None

    @camera_position.setter
    def camera_position(self, value):
        self.camera_positions.append((self.active_pane, value))

    def reset_camera(self):
        self.fit_panes.append(self.active_pane)


def test_each_revision_pane_gets_an_independent_camera_fit():
    plotter = _Plotter()

    _fit_views(plotter)

    assert plotter.camera_positions == [(0, "iso"), (1, "iso"), (2, "iso")]
    assert plotter.fit_panes == [0, 1, 2]
    assert plotter.camera.elevation == -25
