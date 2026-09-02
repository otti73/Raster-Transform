Raster Transform 4.5.2 – QGIS 4.2+

Wichtige Änderungen gegenüber 4.4:
- Das Speichern erzeugt das TIFF direkt aus dem Originalraster mit GDAL CreateCopy.
- Die Originalpixel werden 1:1 übernommen.
- Keine Bildskalierung.
- Kein Resampling.
- Keine Rotation der Pixel.
- Pixelanzahl, Bandanzahl und Datentyp des Ausgangsrasters bleiben erhalten.
- Verschiebung, Skalierung und Drehung werden ausschließlich über die affine GeoTIFF-Geotransformation abgebildet.
- Das CRS des Ausgangsrasters wird übernommen.
- Das neu erzeugte TIFF bleibt sichtbar.
- Nach dem Speichern bleibt der ursprüngliche Quelllayer der aktive Transformationslayer.
- Ein bereits erzeugtes TIFF wird beim erneuten Aktivieren nicht versehentlich als Vorschau übernommen.
- Beim Ausschalten wird nur der ursprünglich transformierte Quelllayer wiederhergestellt.

Bedienung:
1. Originalen Raster-Layer auswählen.
2. Raster Transform aktivieren.
3. Verschieben / Drehen / Skalieren auswählen.
4. Mit linker Maustaste transformieren oder Werte im Dialog ändern.
5. Übernehmen erzeugt ein neues GeoTIFF.

Hinweis:
Die Skalierung ändert in 4.5.2 die geografische Größe des Rasters, nicht seine Pixelauflösung.
Eine Drehung verändert ebenfalls nur die affine Georeferenzierung; die Pixelmatrix wird nicht neu berechnet.


Version 4.5.4: Nach dem Speichern bleibt das neue GeoTIFF aktiv; die aktuelle Kartenposition und der aktuelle Zoom werden beibehalten. Beim Ausschalten wird nicht mehr auf die ursprüngliche Kartenansicht zurückgesprungen. Das neue GeoTIFF ist ein normaler QGIS-Rasterlayer und folgt anschließend Zoom und Pan des Kartenfensters.
