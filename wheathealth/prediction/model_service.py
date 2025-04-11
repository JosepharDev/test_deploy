import joblib
import numpy as np
from pathlib import Path

# Assuming you have a trained model saved
MODEL_PATH = Path(__file__).parent.parent / 'models' / 'random_forest_cropland_model.pkl'

class WheatHealthPredictor:
    def __init__(self):
        self.model = self._load_model()
        
    def _load_model(self):
        try:
            return joblib.load(MODEL_PATH)
        except Exception as e:
            print(f"Error loading model: {e}")
            return None
    
    def preprocess_features(self, gee_data):
        """
        Convert GEE data to model input format using only the specified bands
        """
        area_values = gee_data['area_values']
        
        # Create feature array in the exact order your model expects
        features = np.array([
            area_values.get('B2', 0),   # Blue
            area_values.get('B3', 0),   # Green
            area_values.get('B4', 0),   # Red
            area_values.get('B5', 0),   # Red Edge 1
            area_values.get('B6', 0),   # Red Edge 2
            area_values.get('B7', 0),   # Red Edge 3
            area_values.get('B8', 0),   # NIR
            area_values.get('B8A', 0),  # Red Edge 4
            area_values.get('B11', 0),  # SWIR 1
            area_values.get('B12', 0), # SWIR 2
            area_values.get('NDVI', 0),  # NDVI
            area_values.get('GNDVI', 0),   # GNDVI
            area_values.get('NPCI', 0),   #  NPCI
            area_values.get('DWSI', 0),   # DWSI
            area_values.get('RVSI', 0),   # RVSI
            
        ]).reshape(1, -1)
        
        return features
    
    def predict(self, gee_data):
        if not self.model:
            return {"error": "Model not loaded"}
        
        features = self.preprocess_features(gee_data)
        prediction = self.model.predict(features)
        probabilities = self.model.predict_proba(features)
        
        return {
            "prediction": int(prediction[0]),
            "confidence": float(probabilities[0][prediction[0]]),
            "probabilities": {
                "healthy": float(probabilities[0][1]),
                "unhealthy": float(probabilities[0][0])
            },
            "band_values": gee_data['area_values']
        }