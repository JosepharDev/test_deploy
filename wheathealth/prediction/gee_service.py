import ee
import json
from django.conf import settings

# Initialize GEE (make sure to set up authentication)
class GEEDataExtractor:
    @staticmethod
    def initialize():
        try:
            ee.Initialize(project='certain-catcher-430110-v2')
        except Exception as e:
            print("Please authenticate Earth Engine first")
            print(e)
            raise
    @staticmethod
    def extract_bands_and_indices(geometry, start_date, end_date):
        GEEDataExtractor.initialize()

        # Convert to EE geometry
        ee_geometry = ee.Geometry(geometry)
        point = ee_geometry.centroid()

        # Load Sentinel-2 data
        collection = (ee.ImageCollection('COPERNICUS/S2_SR')
            .filterBounds(ee_geometry)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            .select(['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12']))

        image = collection.median()

        # Scale by 10,000
        image = image.divide(10000)

        # Calculate vegetation indices
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        gndvi = image.normalizedDifference(['B8', 'B3']).rename('GNDVI')
        npc_i = image.normalizedDifference(['B4', 'B2']).rename('NPCI')
        dwsi = image.expression('(B8A - B11) / (B8A + B11)', {
            'B8A': image.select('B8A'),
            'B11': image.select('B11')
        }).rename('DWSI')
        rvsi = image.expression('(B3 - B2) / (B3 + B2)', {
            'B2': image.select('B2'),
            'B3': image.select('B3')
        }).rename('RVSI')

        # Combine all bands and indices into one image
        combined = image.addBands([ndvi, gndvi, npc_i, dwsi, rvsi])

        # Extract values at point
        values = combined.reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=point,
            scale=10,
            maxPixels=1e9
        ).getInfo()

        # Return values with a fallback
        return {
    'area_values': values or {},  # Fallback if empty
    'band_info': {
        # Spectral bands with exact wavelengths from your requirements
        'B2': {'name': 'Blue', 'wavelength': 496.6, 'type': 'spectral'},
        'B3': {'name': 'Green', 'wavelength': 560, 'type': 'spectral'},
        'B4': {'name': 'Red', 'wavelength': 664.5, 'type': 'spectral'},
        'B5': {'name': 'Red Edge 1', 'wavelength': 703.9, 'type': 'spectral'},
        'B6': {'name': 'Red Edge 2', 'wavelength': 740.2, 'type': 'spectral'},
        'B7': {'name': 'Red Edge 3', 'wavelength': 782.5, 'type': 'spectral'},
        'B8': {'name': 'NIR', 'wavelength': 835.1, 'type': 'spectral'},
        'B8A': {'name': 'Red Edge 4', 'wavelength': 864.8, 'type': 'spectral'},
        'B11': {'name': 'SWIR 1', 'wavelength': 1613.7, 'type': 'spectral'},
        'B12': {'name': 'SWIR 2', 'wavelength': 2202.4, 'type': 'spectral'},
        
        # Vegetation indices (no wavelength)
        'NDVI': {'name': 'NDVI', 'type': 'index'},
        'GNDVI': {'name': 'Green NDVI', 'type': 'index'},
        'NPCI': {'name': 'NPCI', 'type': 'index'},
        'DWSI': {'name': 'DWSI', 'type': 'index'},
        'RVSI': {'name': 'RVSI', 'type': 'index'}
    }
}
