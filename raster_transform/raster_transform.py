import os
import math
import shutil

from qgis.PyQt.QtCore import Qt, QTimer, QPointF, QRectF
from qgis.PyQt.QtGui import QImage, QPainter, QIcon
from qgis.PyQt.QtWidgets import (
    QAction, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QDoubleSpinBox, QPushButton, QComboBox, QFormLayout, QToolButton
)

from qgis.core import QgsRasterLayer, QgsPointXY, QgsRectangle, QgsProject
from qgis.gui import QgsMapTool, QgsMapCanvasItem


class RasterImageItem(QgsMapCanvasItem):
    """Live transformed raster preview using QGIS' native canvas-item scaling."""

    def __init__(self, canvas, layer, image):
        super().__init__(canvas)
        self.canvas = canvas
        self.layer = layer
        self.image = image
        self.dx = 0.0
        self.dy = 0.0
        self.angle = 0.0
        self.scale = 0.10
        self.setZValue(1000000)
        self.update_rect()

    def set_transform(self, dx, dy, angle, scale):
        self.dx = float(dx)
        self.dy = float(dy)
        self.angle = float(angle)
        self.scale = max(0.010, float(scale))
        self.prepareGeometryChange()
        self.update_rect()
        self._update_rotation()
        self.update()

    def update_rect(self):
        # IMPORTANT: setRect() receives MAP UNITS. QgsMapCanvasItem then
        # converts this rectangle to screen pixels automatically whenever the
        # canvas is zoomed or panned. This is exactly the behavior of normal
        # QGIS canvas items.
        e = self.layer.extent()
        cx = (e.xMinimum() + e.xMaximum()) / 2.0 + self.dx
        cy = (e.yMinimum() + e.yMaximum()) / 2.0 + self.dy

        w = abs(e.xMaximum() - e.xMinimum()) * self.scale
        h = abs(e.yMaximum() - e.yMinimum()) * self.scale
        if w <= 0 or h <= 0:
            self.setRect(QgsRectangle())
            return

        # Keep the item rectangle UNROTATED. Rotation is handled by the
        # QGraphicsItem itself. This lets QgsMapCanvasItem resize the item
        # correctly on every zoom/pan operation.
        self.setRect(QgsRectangle(
            cx - w / 2.0, cy - h / 2.0,
            cx + w / 2.0, cy + h / 2.0
        ))

    def _update_rotation(self):
        # QGraphicsItem rotation is in screen coordinates. The negative sign
        # compensates for the canvas Y axis pointing downward.
        r = self.boundingRect()
        self.setTransformOriginPoint(r.center())
        self.setRotation(-self.angle)

    def updatePosition(self):
        # QgsMapCanvasItem calls this when the canvas extent/size changes.
        # Let QGIS recompute the item's screen-pixel size from the map-unit
        # rectangle, then restore our rotation around the new center.
        super().updatePosition()
        self._update_rotation()

    def paint(self, painter, option=None, widget=None):
        if self.image.isNull():
            return

        # At paint time the boundingRect is already in the item's LOCAL PIXEL
        # coordinates. It is resized by QgsMapCanvasItem as the map zoom
        # changes. Therefore drawing the image to this rectangle makes the
        # preview follow zoom exactly like a normal QGIS canvas item.
        r = self.boundingRect().adjusted(1.0, 1.0, -1.0, -1.0)
        if r.width() <= 0 or r.height() <= 0:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setOpacity(1.0)
        painter.drawImage(r, self.image)
        painter.restore()


class RasterTransformTool(QgsMapTool):
    MODE_MOVE = "move"
    MODE_ROTATE = "rotate"
    MODE_SCALE = "scale"

    def __init__(self, canvas, plugin):
        super().__init__(canvas)
        self.plugin = plugin
        self.mode = self.MODE_MOVE
        self.dragging = False
        self.start_map = None
        self.start_dx = 0.0
        self.start_dy = 0.0
        self.start_angle = 0.0
        self.start_scale = 1.0
        self.start_center = None
        self.last_pos = QPointF(0, 0)
        self.edge = 55
        self.timer = QTimer()
        self.timer.setInterval(25)
        self.timer.timeout.connect(self.auto_pan)

    def set_mode(self, mode):
        self.mode = mode
        self.update_cursor()

    def update_cursor(self):
        if self.mode == self.MODE_MOVE:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self.mode == self.MODE_ROTATE:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)

    def activate(self):
        super().activate()
        self.update_cursor()

    def deactivate(self):
        self.timer.stop()
        self.dragging = False
        self.update_cursor()
        super().deactivate()

    def canvasPressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not self.plugin.ensure_preview():
            return

        self.last_pos = event.position()
        self.start_map = self.toMapCoordinates(event.position().toPoint())
        self.start_dx = self.plugin.dx
        self.start_dy = self.plugin.dy
        self.start_angle = self.plugin.angle
        self.start_scale = self.plugin.scale

        e = self.plugin.layer.extent()
        self.start_center = QgsPointXY(
            (e.xMinimum() + e.xMaximum()) / 2.0 + self.start_dx,
            (e.yMinimum() + e.yMaximum()) / 2.0 + self.start_dy
        )

        self.dragging = True
        self.timer.start()
        if self.mode == self.MODE_MOVE:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def canvasMoveEvent(self, event):
        if not self.dragging:
            return
        self.last_pos = event.position()
        self.update_transform()

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.last_pos = event.position()
        self.update_transform()
        self.timer.stop()
        self.dragging = False
        self.update_cursor()
        # After each completed manipulation, keep the transformed raster
        # centered in the map canvas. The canvas scale/zoom is left unchanged.
        self.plugin.center_transformed_raster()

    def update_transform(self):
        if not self.dragging or self.start_map is None:
            return

        p = self.toMapCoordinates(self.last_pos.toPoint())

        if self.mode == self.MODE_MOVE:
            self.plugin.set_transform(
                self.start_dx + p.x() - self.start_map.x(),
                self.start_dy + p.y() - self.start_map.y(),
                self.start_angle,
                self.start_scale
            )

        elif self.mode == self.MODE_ROTATE:
            cx = self.start_center.x()
            cy = self.start_center.y()
            a0 = math.degrees(math.atan2(self.start_map.y() - cy, self.start_map.x() - cx))
            a1 = math.degrees(math.atan2(p.y() - cy, p.x() - cx))
            self.plugin.set_transform(
                self.start_dx,
                self.start_dy,
                self.start_angle + (a1 - a0),
                self.start_scale
            )

        elif self.mode == self.MODE_SCALE:
            cx = self.start_center.x()
            cy = self.start_center.y()
            r0 = math.hypot(self.start_map.x() - cx, self.start_map.y() - cy)
            r1 = math.hypot(p.x() - cx, p.y() - cy)
            if r0 > 1e-12:
                factor = max(0.010, min(100.0, r1 / r0))
                self.plugin.set_transform(
                    self.start_dx,
                    self.start_dy,
                    self.start_angle,
                    self.start_scale * factor
                )

    def auto_pan(self):
        if not self.dragging:
            return

        canvas = self.plugin.canvas
        w = canvas.width()
        h = canvas.height()
        x = self.last_pos.x()
        y = self.last_pos.y()
        sx = 0
        sy = 0

        if x < self.edge:
            sx = -min(18, max(1, int((self.edge - x) * 0.30)))
        elif x > w - self.edge:
            sx = min(18, max(1, int((x - (w - self.edge)) * 0.30)))

        if y < self.edge:
            sy = -min(18, max(1, int((self.edge - y) * 0.30)))
        elif y > h - self.edge:
            sy = min(18, max(1, int((y - (h - y)) * 0.30)))

        if sx == 0 and sy == 0:
            return

        before = self.toMapCoordinates(self.last_pos.toPoint())
        shifted = self.last_pos.toPoint()
        shifted.setX(shifted.x() - sx)
        shifted.setY(shifted.y() - sy)
        after = self.toMapCoordinates(shifted)

        center = canvas.center()
        center.setX(center.x() + before.x() - after.x())
        center.setY(center.y() + before.y() - after.y())
        canvas.setCenter(center)
        canvas.refresh()
        self.update_transform()


class TransformDialog(QDialog):
    def __init__(self, plugin):
        super().__init__(plugin.iface.mainWindow())
        self.plugin = plugin
        self.setWindowTitle("Raster Transform")
        self.setMinimumWidth(360)

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Live-Transformation des ausgewählten Rasters"))
        form = QFormLayout()

        self.dx = QDoubleSpinBox(); self.dx.setRange(-1e12, 1e12); self.dx.setDecimals(4); self.dx.setSuffix(" Karteneinheiten")
        self.dy = QDoubleSpinBox(); self.dy.setRange(-1e12, 1e12); self.dy.setDecimals(4); self.dy.setSuffix(" Karteneinheiten")
        self.angle = QDoubleSpinBox(); self.angle.setRange(-36000, 36000); self.angle.setDecimals(2); self.angle.setSuffix(" °")
        self.scale = QDoubleSpinBox(); self.scale.setRange(0.010, 100.0); self.scale.setDecimals(3); self.scale.setSingleStep(0.010); self.scale.setValue(0.10); self.scale.setSuffix(" ×")

        form.addRow("X-Verschiebung:", self.dx)
        form.addRow("Y-Verschiebung:", self.dy)
        form.addRow("Drehwinkel:", self.angle)
        form.addRow("Skalierung:", self.scale)
        root.addLayout(form)

        mode_row = QHBoxLayout(); mode_row.addWidget(QLabel("Mausmodus:"))
        self.mode = QComboBox()
        self.mode.addItem("Verschieben", RasterTransformTool.MODE_MOVE)
        self.mode.addItem("Drehen", RasterTransformTool.MODE_ROTATE)
        self.mode.addItem("Skalieren", RasterTransformTool.MODE_SCALE)
        self.mode.currentIndexChanged.connect(self.mode_changed)
        mode_row.addWidget(self.mode); root.addLayout(mode_row)

        self.dx.valueChanged.connect(self.values_changed)
        self.dy.valueChanged.connect(self.values_changed)
        self.angle.valueChanged.connect(self.values_changed)
        self.scale.valueChanged.connect(self.values_changed)

        buttons = QHBoxLayout()
        self.reset_btn = QPushButton("Zurücksetzen")
        self.cancel_btn = QPushButton("Abbrechen")
        self.apply_btn = QPushButton("Übernehmen")
        self.reset_btn.clicked.connect(self.plugin.reset_transform)
        self.cancel_btn.clicked.connect(self.reject)
        self.apply_btn.clicked.connect(self.plugin.apply_transform)
        buttons.addWidget(self.reset_btn); buttons.addWidget(self.cancel_btn); buttons.addStretch(); buttons.addWidget(self.apply_btn)
        root.addLayout(buttons)
        self.refresh_values()

    def refresh_values(self):
        for widget, value in ((self.dx, self.plugin.dx), (self.dy, self.plugin.dy), (self.angle, self.plugin.angle), (self.scale, self.plugin.scale)):
            widget.blockSignals(True); widget.setValue(value); widget.blockSignals(False)

    def values_changed(self):
        self.plugin.set_transform(self.dx.value(), self.dy.value(), self.angle.value(), self.scale.value())

    def mode_changed(self):
        self.plugin.tool.set_mode(self.mode.currentData())


class RasterTransformPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.action = None
        self.tool = None
        self.dialog = None
        self.layer = None
        self.item = None
        self.image = None
        self.dx = 0.0
        self.dy = 0.0
        self.angle = 0.0
        self.scale = 0.010
        self.old_opacity = 1.0
        self.original_state = None
        self.created_outputs = set()
        # Exact map-canvas view to restore when Raster Transform is switched off.
        self.saved_canvas_extent = None
        self.previous_map_tool = None

    def initGui(self):
        # Stylisches eigenes Werkzeug-Icon statt eines reinen Text-Buttons.
        icon_path = os.path.join(os.path.dirname(__file__), "icon.svg")
        self.action = QAction(QIcon(icon_path), "Raster Transform", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setToolTip("Raster Transform – verschieben, drehen und skalieren")
        self.action.setStatusTip("Raster verschieben, drehen und skalieren")
        self.action.triggered.connect(self.toggle)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&Raster Transform", self.action)

        # Das konkrete QToolButton des Plugins bekommt einen dezenten
        # Mouse-over-/Aktiv-Effekt, ohne das Erscheinungsbild anderer
        # QGIS-Werkzeuge zu verändern.
        self.toolbar_button = None
        for button in self.iface.mainWindow().findChildren(QToolButton):
            if button.defaultAction() == self.action:
                self.toolbar_button = button
                button.setToolTip("Raster Transform – verschieben, drehen und skalieren")
                button.setIconSize(button.iconSize())
                button.setStyleSheet("""
                    QToolButton {
                        border: 1px solid transparent;
                        border-radius: 5px;
                        padding: 3px;
                        margin: 1px;
                    }
                    QToolButton:hover {
                        border: 1px solid rgba(70, 140, 220, 150);
                        background: rgba(70, 140, 220, 45);
                    }
                    QToolButton:checked {
                        border: 1px solid rgba(50, 120, 200, 210);
                        background: rgba(50, 120, 200, 75);
                    }
                    QToolButton:checked:hover {
                        background: rgba(50, 120, 200, 105);
                    }
                """)
                break

        self.tool = RasterTransformTool(self.canvas, self)

    def unload(self):
        if self.canvas.mapTool() == self.tool:
            self.canvas.unsetMapTool(self.tool)
        self.close_preview()
        if self.action:
            self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu("&Raster Transform", self.action)

    def toggle(self, checked):
        if checked:
            # Remember the current view only for internal reference. It is
            # never restored when the tool is switched off.
            self.saved_canvas_extent = QgsRectangle(self.canvas.extent())
            self.previous_map_tool = self.canvas.mapTool()
            # If a preview already exists, keep its source layer. Do NOT
            # reinterpret the currently selected/new TIFF as the preview.
            if self.item is None and not self.ensure_preview():
                self.action.setChecked(False)
                return

            self.canvas.setMapTool(self.tool)
            # Put the raster in the middle when transformation starts.
            self.center_transformed_raster()
            if self.dialog is None:
                self.dialog = TransformDialog(self)
            self.dialog.show(); self.dialog.raise_(); self.dialog.activateWindow()
        else:
            if self.canvas.mapTool() == self.tool:
                self.canvas.unsetMapTool(self.tool)
            if self.previous_map_tool is not None and self.previous_map_tool != self.tool:
                self.canvas.setMapTool(self.previous_map_tool)
            self.previous_map_tool = None

            # IMPORTANT: Never restore the view from before the transformation.
            # The user wants the final transformed raster and its current zoom
            # position to remain visible after Raster Transform is switched off.
            self.close_preview()
            self.saved_canvas_extent = None
            self.canvas.refresh()
            if self.dialog:
                self.dialog.close()

    def selected_raster(self):
        layer = self.iface.activeLayer()
        return layer if isinstance(layer, QgsRasterLayer) else None

    def source_path(self, layer):
        source = layer.source()
        if "|" in source:
            source = source.split("|", 1)[0]
        if source.lower().startswith("file:///"):
            source = source[8:]
            if not source.startswith("\\\\"):
                source = "/" + source
        return os.path.normpath(source)

    def ensure_preview(self):
        # Once a preview is active, always keep its original source layer.
        if self.item is not None and self.layer is not None:
            return True

        layer = self.selected_raster()
        if layer is None:
            QMessageBox.information(self.iface.mainWindow(), "Raster Transform", "Bitte zuerst den Raster-Layer im Layerfenster auswählen.")
            return False

        path = self.source_path(layer)
        image = QImage(path)
        if image.isNull():
            QMessageBox.warning(self.iface.mainWindow(), "Raster Transform", "Das Rasterbild konnte nicht geladen werden.\n\nQuelle:\n" + path)
            return False

        self.layer = layer
        self.image = image
        self.old_opacity = layer.opacity()
        self.dx = self.dy = self.angle = 0.0

        # Start deliberately below 1.0. The original 1.000 start was too
        # large for the user's workflow. More importantly, this value is a
        # GEOGRAPHIC scale factor only; zooming the QGIS canvas must never
        # change it. QgsMapCanvasItem handles the screen-size change.
        self.scale = 0.10

        self.original_state = (self.dx, self.dy, self.angle, self.scale)

        layer.setOpacity(0.0)
        self.item = RasterImageItem(self.canvas, layer, image)
        self.set_transform(0, 0, 0, self.scale)
        return True

    def set_transform(self, dx, dy, angle, scale):
        if self.item is None:
            return
        self.dx = float(dx); self.dy = float(dy); self.angle = float(angle); self.scale = max(0.010, float(scale))
        self.item.set_transform(self.dx, self.dy, self.angle, self.scale)
        if self.dialog:
            self.dialog.refresh_values()
        self.canvas.refresh()

    def transformed_center(self):
        """Return the current transformed raster center in map coordinates."""
        if self.layer is None:
            return None
        e = self.layer.extent()
        return QgsPointXY(
            (e.xMinimum() + e.xMaximum()) / 2.0 + self.dx,
            (e.yMinimum() + e.yMaximum()) / 2.0 + self.dy
        )

    def center_transformed_raster(self):
        """Center the transformed raster without changing the current zoom."""
        center = self.transformed_center()
        if center is None:
            return
        self.canvas.setCenter(center)
        self.canvas.refresh()

    def reset_transform(self):
        if self.original_state is not None:
            self.set_transform(*self.original_state)

    def _transformed_geotransform(self, ds):
        """Return a new affine geotransform without touching pixel data."""
        gt = ds.GetGeoTransform(can_return_null=True)

        width = ds.RasterXSize
        height = ds.RasterYSize
        if width <= 0 or height <= 0:
            raise RuntimeError("Ungültige Rasterabmessungen.")

        # Some otherwise perfectly usable rasters (for example TIFFs created
        # from an image without embedded world-file information) have no GDAL
        # GeoTransform. QGIS can nevertheless know their geographic extent
        # from the layer/provider. In that case derive the affine transform
        # from the QGIS layer extent. This does NOT resample or alter pixels;
        # it only supplies the missing spatial reference for the original
        # pixel matrix.
        if gt is None:
            extent = self.layer.extent()
            if extent.isEmpty() or not extent.isFinite():
                raise RuntimeError(
                    "Das Ausgangsraster besitzt keine gültige GeoTransform "
                    "und QGIS liefert auch keine gültige Rasterausdehnung."
                )
            px = extent.width() / float(width)
            py = extent.height() / float(height)
            if px == 0.0 or py == 0.0:
                raise RuntimeError("Die räumliche Ausdehnung des Ausgangsrasters ist ungültig.")
            gt = (extent.xMinimum(), px, 0.0, extent.yMaximum(), 0.0, -py)

        # Geographic center of the raster in the source affine coordinate system.
        cx = gt[0] + gt[1] * (width / 2.0) + gt[2] * (height / 2.0)
        cy = gt[3] + gt[4] * (width / 2.0) + gt[5] * (height / 2.0)
        cx += self.dx
        cy += self.dy

        s = self.scale
        a = math.radians(self.angle)
        c = math.cos(a)
        sn = math.sin(a)

        # Apply scale + rotation to the original pixel basis vectors.
        vx_x = gt[1] * s
        vx_y = gt[4] * s
        vy_x = gt[2] * s
        vy_y = gt[5] * s

        rvx_x = c * vx_x - sn * vx_y
        rvx_y = sn * vx_x + c * vx_y
        rvy_x = c * vy_x - sn * vy_y
        rvy_y = sn * vy_x + c * vy_y

        # New world coordinate of pixel (0,0).
        origin_x = cx - rvx_x * (width / 2.0) - rvy_x * (height / 2.0)
        origin_y = cy - rvx_y * (width / 2.0) - rvy_y * (height / 2.0)

        return (origin_x, rvx_x, rvy_x, origin_y, rvx_y, rvy_y)

    def apply_transform(self):
        """Create a GeoTIFF by copying original pixels and changing only georeferencing."""
        if self.layer is None:
            return

        from qgis.PyQt.QtWidgets import QFileDialog
        output, _ = QFileDialog.getSaveFileName(
            self.iface.mainWindow(),
            "Transformiertes, georeferenziertes Raster speichern",
            os.path.join(os.path.expanduser("~"), "raster_transformiert.tif"),
            "GeoTIFF (*.tif *.tiff)"
        )
        if not output:
            return
        if not output.lower().endswith((".tif", ".tiff")):
            output += ".tif"

        path = self.source_path(self.layer)
        if not os.path.isfile(path):
            QMessageBox.critical(self.iface.mainWindow(), "Raster Transform", "Die Original-Rasterdatei ist keine direkt lesbare Datei:\n\n" + path)
            return

        try:
            from osgeo import gdal, osr

            src = gdal.Open(path, gdal.GA_ReadOnly)
            if src is None:
                raise RuntimeError("GDAL konnte das Originalraster nicht öffnen.")

            new_gt = self._transformed_geotransform(src)
            driver = gdal.GetDriverByName("GTiff")
            if driver is None:
                raise RuntimeError("Der GDAL-GeoTIFF-Treiber ist nicht verfügbar.")

            # CreateCopy copies the original raster pixels, datatype, bands and
            # metadata. No scaling, rotation, interpolation or resampling occurs.
            options = ["COMPRESS=DEFLATE", "PREDICTOR=2", "BIGTIFF=IF_SAFER"]
            dst = driver.CreateCopy(output, src, strict=0, options=options)
            if dst is None:
                raise RuntimeError("Das GeoTIFF konnte nicht erzeugt werden.")

            dst.SetGeoTransform(new_gt)

            projection = src.GetProjection()
            if projection:
                dst.SetProjection(projection)
            elif self.layer.crs().isValid():
                srs = osr.SpatialReference()
                srs.ImportFromWkt(self.layer.crs().toWkt())
                dst.SetProjection(srs.ExportToWkt())

            # Preserve GCP/RPC metadata if present through CreateCopy; only
            # the affine georeferencing is intentionally replaced by the transform.
            dst.FlushCache()
            dst = None
            src = None

            new_layer = QgsRasterLayer(output, os.path.splitext(os.path.basename(output))[0], "gdal")
            if not new_layer.isValid():
                raise RuntimeError("Die TIFF-Datei wurde erstellt, konnte aber nicht als Raster-Layer geladen werden.")

            # Remember the CURRENT view.  This is the view the user should
            # keep after the output has been created -- including its zoom.
            final_canvas_extent = QgsRectangle(self.canvas.extent())

            QgsProject.instance().addMapLayer(new_layer)
            self.created_outputs.add(os.path.normcase(os.path.abspath(output)))

            # The newly written GeoTIFF is now the real layer.  Do not keep the
            # old raster as the active layer and do not let the preview survive.
            # Otherwise switching the tool off would reveal the original raster
            # again and make it look as if QGIS had jumped back.
            new_layer.setOpacity(1.0)
            self.iface.setActiveLayer(new_layer)

            # Remove the temporary QImage preview and restore only the
            # original layer's opacity.  The newly created GeoTIFF remains
            # the active layer.
            self.close_preview()

            # Keep exactly the map view which existed when saving started.
            # The new TIFF is now a normal QgsRasterLayer, so subsequent
            # zooming/panning is handled by QGIS itself.
            self.canvas.setExtent(final_canvas_extent)
            new_layer.triggerRepaint()
            self.canvas.refresh()

            # Saving completes the transformation. End the temporary map
            # tool automatically, but NEVER change the active layer or map
            # extent. This prevents the original source raster from becoming
            # visible/active again when the user switches Raster Transform off.
            if self.action and self.action.isChecked():
                self.action.blockSignals(True)
                self.action.setChecked(False)
                self.action.blockSignals(False)
                self.toggle(False)
                self.iface.setActiveLayer(new_layer)
                self.canvas.setExtent(final_canvas_extent)
                self.canvas.refresh()

            QMessageBox.information(
                self.iface.mainWindow(),
                "Raster Transform 4.5",
                "Fertig!\n\n"
                "Das neue GeoTIFF wurde erstellt und als neuer Raster-Layer geladen.\n\n"
                "Wichtig:\n"
                "• Originalpixel unverändert übernommen\n"
                "• keine Skalierung der Pixel\n"
                "• kein Resampling\n"
                "• keine Bildrotation\n"
                "• Verschiebung, Skalierung und Drehung nur über die GeoTIFF-Georeferenzierung\n\n"
                "Datei:\n" + output
            )

        except Exception as exc:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Raster Transform",
                "Das georeferenzierte TIFF konnte nicht erstellt werden.\n\n" + str(exc)
            )

    def close_preview(self):
        if self.item is not None:
            try:
                self.canvas.scene().removeItem(self.item)
            except Exception:
                pass

        if self.layer is not None:
            try:
                self.layer.setOpacity(self.old_opacity)
                self.layer.triggerRepaint()
            except Exception:
                pass

        self.item = None
        self.layer = None
        self.image = None
        self.dx = self.dy = self.angle = 0.0
        self.scale = 0.10
        self.original_state = None
        self.canvas.refresh()
