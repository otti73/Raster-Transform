# Raster Transform

**Raster Transform** ist eine QGIS-4-Erweiterung zum interaktiven Verschieben, Drehen und Skalieren von Rasterlayern, ohne die Originalpixel durch Resampling zu verändern.

## Funktionen

- Raster interaktiv verschieben
- Raster drehen und skalieren
- Live-Vorschau
- Ergebnis als neuer GeoTIFF speichern
- Kein Resampling beim Export
- Rastergröße, Bandstruktur und Datentyp erhalten
- Transformation über die affine GeoTIFF-Georeferenzierung speichern
- Transformierten GeoTIFF nach dem Speichern als aktiven Layer in QGIS verwenden

## Voraussetzungen

- QGIS 4.x
- das von QGIS bereitgestellte GDAL
- keine zusätzlichen Python-Pakete erforderlich

## Installation

Nach der Freigabe kann Raster Transform direkt über den QGIS-Plugin-Manager installiert werden. Für Tests kann die ZIP-Datei über **Erweiterungen → Erweiterungen verwalten und installieren → Aus ZIP installieren** installiert werden.

## Verwendung

1. Einen Rasterlayer in QGIS laden.
2. **Raster Transform** aktivieren.
3. Raster verschieben, drehen oder skalieren.
4. Das Ergebnis als neuen GeoTIFF speichern.

Das Originalraster bleibt unverändert. Die Original-Pixelmatrix wird beim Export nicht resampelt; die räumliche Transformation wird in der affinen Georeferenzierung gespeichert.

## Lizenz

Raster Transform steht unter der **GNU General Public License Version 2 oder einer späteren Version**. Siehe `LICENSE`.

## Autor

**Copilot**

GitHub: https://github.com/otti73/Raster-Transform

## Support

Fehler und Funktionswünsche: https://github.com/otti73/Raster-Transform/issues
