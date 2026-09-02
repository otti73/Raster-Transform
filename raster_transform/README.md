# Raster Transform

**Raster Transform** is a QGIS 4 plugin for interactively moving, rotating and scaling raster layers without resampling the original raster pixels.

## Features

- Move a raster interactively
- Rotate and scale a raster
- Live preview
- Save as a new GeoTIFF
- No resampling during export
- Preserve raster dimensions, bands and data type
- Store the transformation in the GeoTIFF affine georeferencing
- Keep the transformed GeoTIFF active in QGIS after saving

## Requirements

- QGIS 4.x
- GDAL supplied with QGIS
- No additional Python package is required

## Installation

After approval, Raster Transform can be installed from the QGIS Plugin Manager. For testing, use **Plugins → Manage and Install Plugins → Install from ZIP**.

## Usage

1. Add a raster layer to QGIS.
2. Activate **Raster Transform**.
3. Move, rotate or scale the raster.
4. Save the result as a new GeoTIFF.

The original raster remains unchanged. The exported file keeps the original pixel matrix; the spatial transformation is written to its affine georeferencing.

## License

Raster Transform is released under the **GNU General Public License v2.0 or later**. See `LICENSE`.

## Author

**Copilot**

GitHub: https://github.com/otti73/Raster-Transform

## Support

Bug reports and feature requests: https://github.com/otti73/Raster-Transform/issues

If Raster Transform is useful to you, sponsorship helps fund maintenance and further development.
