def classFactory(iface):
    from .raster_transform import RasterTransformPlugin
    return RasterTransformPlugin(iface)
