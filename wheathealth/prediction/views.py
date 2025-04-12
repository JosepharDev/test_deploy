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
    point = ee.Geometry.Polygon([[
        [-4.756572600555413, 34.07453831656702],
        [-4.756926653333988, 34.074120635290505],
        [-4.757060763342107, 34.073920681323614],
        [-4.757044669342034, 34.073685179882744],
        [-4.757087584686272, 34.073187512848925],
        [-4.757087584686272, 34.07292090430669],
        [-4.756443854522698, 34.07284980855373],
        [-4.754115688976768, 34.07253656361696],
        [-4.751787539672844, 34.07225882279766],
        [-4.7517231665838855, 34.07273427588901],
        [-4.7518089973449635, 34.07340524253599],
        [-4.753579255294793, 34.07354743304995],
        [-4.754222985458367, 34.07372517085677],
        [-4.756572600555413, 34.07453831656702]
    ]])

    try:
        # First try with cloud filter
        collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(point)
            .filterDate(start_date, end_date)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
        )

        # Check if collection is empty
        if collection.size().getInfo() == 0:
            # Fallback to collection with higher cloud cover
            collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(point).filterDate(start_date, end_date).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))  # Increased cloud threshold

            if collection.size().getInfo() == 0:
                # Final fallback - no cloud filter
                collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                    .filterBounds(point)
                    .filterDate(start_date, end_date)
                )

                if collection.size().getInfo() == 0:
                    return {
                        'NDVI': None,
                        'GNDVI': None,
                        'DWSI': None,
                        'RSV1': None,
                        'data_available': False
                    }

        # Calculate median image
        median_img = collection.median()

        # Cloud masking using the QA60 band (bit 10)
        qa60 = median_img.select(['QA60']).toInt()
        cloud_mask = qa60.bitwiseAnd(1 << 10).eq(0)  # Mask out clouds (if QA60 bit is 0)

        # Apply cloud mask to the median image
        cloud_free_img = median_img.updateMask(cloud_mask)

        # --- helper function ---
        def calculate_index(img, method, *args):
            try:
                if method == 'nd':
                    result = img.normalizedDifference(args).rename('nd').reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=point,
                        scale=10,
                        bestEffort=True
                    ).getInfo()
                    return result.get('nd', None)
                elif method == 'ratio':
                    result = img.select(args[0]).divide(img.select(args[1])).rename('ratio').reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=point,
                        scale=10,
                        bestEffort=True
                    ).getInfo()
                    return result.get('ratio', None)
            except Exception as e:
                print(f"Error calculating index: {e}")
                return None

        # --- Final return with calculated indices ---
        return {
            'NDVI': calculate_index(cloud_free_img, 'nd', 'B8', 'B4'),
            'GNDVI': calculate_index(cloud_free_img, 'nd', 'B8', 'B3'),
            'DWSI': calculate_index(cloud_free_img, 'nd', 'B8', 'B11'),
            'RSV1': calculate_index(cloud_free_img, 'ratio', 'B4', 'B2'),
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
        [(start_date + timedelta(days=i), 7) for i in range(0, 126, 7)] + 
        [(start_date + timedelta(days=i), 14) for i in range(127, 178, 14)]
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
        print(response_data)

    return JsonResponse(response_data, safe=False)