from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .gee_service import GEEDataExtractor
from .model_service import WheatHealthPredictor

def wheat_health_map(request):
    """GET method to display the map interface"""
    return render(request, 'prediction/dashboard.html')

@csrf_exempt
def predict_wheat_health(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            geometry = data.get('geometry')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            
            # Get only band data (no indices)
            gee_data = GEEDataExtractor.extract_bands_and_indices(
                geometry, start_date, end_date)
            
            # Make prediction
            predictor = WheatHealthPredictor()
            prediction = predictor.predict(gee_data)
            
            response = {
                "band_data": gee_data,
                "prediction": prediction,
                "status": "success"
            }
            return JsonResponse(response)
            
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)})
    
    return JsonResponse({"status": "error", "message": "Only POST requests allowed"})
import json
from datetime import datetime, timedelta

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import ee
from datetime import datetime, timedelta

def point_analysis_page(request):
    """GET endpoint to display the analysis page"""
    return render(request, 'prediction/point_analysis.html')

import ee
import logging
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.http import require_GET

# Initialize Earth Engine
try:
    ee.Initialize()
except ee.EEException as e:
    logging.error(f"Failed to initialize Earth Engine: {str(e)}")

def get_indices_with_fallback(lat, lon, start_date, end_date):
    """
    Safely gets vegetation indices with proper serialization
    """
    point = ee.Geometry.Point([lon, lat])
    
    try:
        # First try with cloud filter
        collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(point)
            .filterDate(start_date, end_date)
            .sort("CLOUDY_PIXEL_PERCENTAGE"))
        
        # Check if collection is empty
        if collection.size().getInfo() == 0:
            # Fallback to unfiltered collection
            collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filterBounds(point)
                .filterDate(start_date, end_date)
                .sort("CLOUDY_PIXEL_PERCENTAGE"))
            
            if collection.size().getInfo() == 0:
                return {
                    'NDVI': None,
                    'GNDVI': None,
                    'DWSI': None,
                    'RSV1': None,
                    'data_available': False
                }
        
        # Calculate indices and immediately get values
        median_img = collection.median()
        
        def calculate_index(img, method, *args):
            """Helper to safely calculate and extract index values"""
            try:
                if method == 'nd':
                    result = img.normalizedDifference(args).reduceRegion(
                        ee.Reducer.mean(),
                        point,
                        10
                    ).getInfo()
                    return result.get('nd', None)
                elif method == 'ratio':
                    result = img.select(args[0]).divide(img.select(args[1])).reduceRegion(ee.Reducer.mean(),point,10).getInfo()
                    return result.get('constant', None)
            except:
                return None
        
        return {
            'NDVI': calculate_index(median_img, 'nd', 'B8', 'B4'),
            'GNDVI': calculate_index(median_img, 'nd', 'B8', 'B3'),
            'DWSI': calculate_index(median_img, 'nd', 'B8', 'B11'),
            'RSV1': calculate_index(median_img, 'ratio', 'B4', 'B2'),
            'data_available': True
        }
        
    except Exception as e:
        logging.error(f"Error in get_indices_with_fallback: {str(e)}")
        return {
            'NDVI': None,
            'GNDVI': None,
            'DWSI': None,
            'RSV1': None,
            'data_available': False
        }

@require_GET
def extract_indices_view(request):
    """Main endpoint with proper JSON serialization"""
    try:
        # Input validation
        lat = float(request.GET.get('lat'))
        lon = float(request.GET.get('lon'))
        start_str = request.GET.get('start_date')
        
            
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
    except Exception as e:
        return JsonResponse({'error': f'Invalid parameters: {str(e)}'}, status=400)

    response_data = []
    missing_data_count = 0

    # Time windows - biweekly then weekly
    time_windows = (
        [(start_date + timedelta(days=i), 14) for i in range(0, 126, 14)] + 
        [(start_date + timedelta(days=i), 7) for i in range(127, 178, 7)]
    )

    for begin, days in time_windows:
        end = begin + timedelta(days=days)
        try:
            indices = get_indices_with_fallback(lat, lon, begin.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
            
            response_data.append({
                'date': begin.strftime('%Y-%m-%d'),
                'NDVI': indices.get('NDVI'),
                'GNDVI': indices.get('GNDVI'),
                'DWSI': indices.get('DWSI'),
                'RSV1': indices.get('RSV1'),
                'data_available': indices.get('data_available', False)
            })
            
            if not indices['data_available']:
                missing_data_count += 1
                
        except Exception as e:
            missing_data_count += 1
            response_data.append({
                'date': begin.strftime('%Y-%m-%d'),
                'error': str(e),
                'data_available': False
            })

    # Calculate success rate
    success_rate = round(
        (len(response_data) - missing_data_count) / len(response_data) * 100, 1
    ) if len(response_data) > 0 else 0.0

    # Add metadata
    if response_data:
        response_data.append({
            '_meta': {
                'total_points': len(response_data),
                'successful_points': len(response_data) - missing_data_count,
                'missing_points': missing_data_count,
                'success_rate': f"{success_rate}%",
                'date_range': {
                    'start': response_data[0]['date'],
                    'end': response_data[-1]['date']
                }
            }
        })

    return JsonResponse(response_data, safe=False)