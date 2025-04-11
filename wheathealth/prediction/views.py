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