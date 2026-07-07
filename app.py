"""
Crop Yield Prediction System
Michael Okpara University of Agriculture, Umudike
Department of Computer Science
"""

import os
import json
import pickle
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, FloatField, SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, ValidationError
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingRegressor
import matplotlib
matplotlib.use('Agg')  # For non-GUI environments
import matplotlib.pyplot as plt
import io
import base64

# Initialize Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['UPLOAD_FOLDER'] = 'data'

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# =====================================================
# DATABASE SIMULATION (In-memory for prototype)
# In production, use a real database like MySQL or SQLite
# =====================================================

class MockDatabase:
    """Simulated database for prototype"""
    def __init__(self):
        self.users = {
            1: {'id': 1, 'email': 'farmer@example.com', 'password': 'password123', 
                'full_name': 'John Farmer', 'role': 'farmer', 'phone': '08012345678'},
            2: {'id': 2, 'email': 'admin@example.com', 'password': 'admin123',
                'full_name': 'System Admin', 'role': 'admin', 'phone': '08087654321'}
        }
        self.fields = {}
        self.soil_samples = {}
        self.management_data = {}
        self.predictions = {}
        self._id_counter = 3
        
    def get_user(self, email):
        for user in self.users.values():
            if user['email'] == email:
                return user
        return None
    
    def create_user(self, email, password, full_name, phone, role='farmer'):
        user_id = self._id_counter
        self.users[user_id] = {
            'id': user_id,
            'email': email,
            'password': generate_password_hash(password),
            'full_name': full_name,
            'role': role,
            'phone': phone
        }
        self._id_counter += 1
        return user_id
    
    def add_field(self, user_id, field_name, latitude, longitude, area, soil_type):
        field_id = len(self.fields) + 1
        self.fields[field_id] = {
            'id': field_id,
            'user_id': user_id,
            'field_name': field_name,
            'latitude': latitude,
            'longitude': longitude,
            'area_ha': area,
            'soil_type': soil_type,
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return field_id
    
    def get_user_fields(self, user_id):
        return [f for f in self.fields.values() if f['user_id'] == user_id]
    
    def save_prediction(self, field_id, predicted_yield, lower_bound, upper_bound, features, recommendations):
        pred_id = len(self.predictions) + 1
        self.predictions[pred_id] = {
            'id': pred_id,
            'field_id': field_id,
            'predicted_yield': predicted_yield,
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'features': features,
            'recommendations': recommendations,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'actual_yield': None  # To be filled after harvest
        }
        return pred_id

db = MockDatabase()

# =====================================================
# USER MODEL FOR FLASK-LOGIN
# =====================================================

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['id']
        self.email = user_data['email']
        self.password_hash = user_data.get('password')
        self.full_name = user_data['full_name']
        self.role = user_data['role']
        self.phone = user_data['phone']
    
    def check_password(self, password):
        # In this prototype, we're using plain text for simplicity
        # In production, use check_password_hash
        return self.password_hash == password

@login_manager.user_loader
def load_user(user_id):
    user_data = db.users.get(int(user_id))
    if user_data:
        return User(user_data)
    return None

# =====================================================
# FORMS
# =====================================================

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=50)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired()])
    submit = SubmitField('Register')
    
    def validate_email(self, field):
        if db.get_user(field.data):
            raise ValidationError('Email already registered.')
    
    def validate_confirm_password(self, field):
        if field.data != self.password.data:
            raise ValidationError('Passwords do not match.')

class FieldForm(FlaskForm):
    field_name = StringField('Field Name', validators=[DataRequired()])
    latitude = FloatField('Latitude', validators=[DataRequired()])
    longitude = FloatField('Longitude', validators=[DataRequired()])
    area_ha = FloatField('Area (hectares)', validators=[DataRequired(), NumberRange(min=0.1)])
    soil_type = SelectField('Soil Type', choices=[
        ('loam', 'Loam'),
        ('clay', 'Clay'),
        ('sandy', 'Sandy'),
        ('sandy_loam', 'Sandy Loam'),
        ('clay_loam', 'Clay Loam')
    ])
    submit = SubmitField('Add Field')

class PredictionForm(FlaskForm):
    field_id = SelectField('Select Field', choices=[], validators=[DataRequired()])
    variety = SelectField('Crop Variety', choices=[
        ('TZEE-W', 'TZEE-W (White)'),
        ('TZEE-Y', 'TZEE-Y (Yellow)'),
        ('SAMMAZ-15', 'SAMMAZ-15'),
        ('SAMMAZ-16', 'SAMMAZ-16'),
        ('SAMMAZ-17', 'SAMMAZ-17')
    ], validators=[DataRequired()])
    planting_date = DateField('Planting Date', format='%Y-%m-%d', validators=[DataRequired()])
    fertiliser_type = SelectField('Fertiliser Type', choices=[
        ('NPK_15-15-15', 'NPK 15-15-15'),
        ('NPK_20-10-10', 'NPK 20-10-10'),
        ('Urea', 'Urea (46% N)'),
        ('NPK_12-12-17', 'NPK 12-12-17')
    ], validators=[DataRequired()])
    fertiliser_rate = FloatField('Fertiliser Rate (kg/ha)', validators=[DataRequired(), NumberRange(min=0, max=500)])
    irrigation_type = SelectField('Irrigation Type', choices=[
        ('rainfed', 'Rain-fed (No Irrigation)'),
        ('manual', 'Manual/Hand Irrigation'),
        ('sprinkler', 'Sprinkler Irrigation'),
        ('drip', 'Drip Irrigation')
    ], validators=[DataRequired()])
    irrigation_frequency = FloatField('Irrigation Frequency (times/season)', default=0, validators=[NumberRange(min=0, max=50)])
    submit = SubmitField('Predict Yield')

# =====================================================
# MACHINE LEARNING MODEL HANDLER
# =====================================================

class YieldPredictor:
    """Handles model training, loading, and prediction"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        self.feature_names = [
            'ph', 'organic_matter', 'nitrogen', 'phosphorus', 'potassium',
            'avg_temp', 'cumulative_rainfall', 'humidity_avg', 'solar_radiation',
            'gdd', 'planting_doy', 'fert_rate', 'irrigation_freq', 'prev_yield_avg'
        ]
        self.feature_importances = {}
        self.is_trained = False
        self._load_or_train()
    
    def _load_or_train(self):
        """Load existing model or train a new one with sample data"""
        try:
            # Try to load existing model
            self.model = joblib.load('models/gbr_model.pkl')
            self.scaler = joblib.load('models/scaler.pkl')
            self.is_trained = True
            print("Model loaded successfully.")
        except:
            # Train new model with sample data
            print("No existing model found. Training new model with sample data...")
            self._train_sample_model()
    
    def _train_sample_model(self):
        """Train a Gradient Boosting model with synthetic sample data"""
        np.random.seed(42)
        n_samples = 350
        
        # Generate synthetic features
        data = {
            'ph': np.random.uniform(4.5, 7.8, n_samples),
            'organic_matter': np.random.uniform(1.2, 4.5, n_samples),
            'nitrogen': np.random.uniform(50, 250, n_samples),
            'phosphorus': np.random.uniform(10, 80, n_samples),
            'potassium': np.random.uniform(100, 400, n_samples),
            'avg_temp': np.random.uniform(25, 32, n_samples),
            'cumulative_rainfall': np.random.uniform(300, 1200, n_samples),
            'humidity_avg': np.random.uniform(45, 95, n_samples),
            'solar_radiation': np.random.uniform(12, 25, n_samples),
            'gdd': np.random.uniform(1800, 2800, n_samples),
            'planting_doy': np.random.uniform(90, 170, n_samples),
            'fert_rate': np.random.uniform(0, 400, n_samples),
            'irrigation_freq': np.random.uniform(0, 10, n_samples),
            'prev_yield_avg': np.random.uniform(1500, 4500, n_samples)
        }
        
        df = pd.DataFrame(data)
        
        # Generate target (yield) with realistic relationships
        # Yield = base + contributions from key features + noise
        base_yield = 2000
        df['yield'] = (
            base_yield
            + 0.5 * df['nitrogen']
            + 2.0 * df['cumulative_rainfall'] / 10
            + 1.5 * df['gdd'] / 10
            + 0.3 * df['prev_yield_avg']
            + 0.1 * df['fert_rate']
            + np.random.normal(0, 300, n_samples)
        )
        
        # Clip to realistic range
        df['yield'] = df['yield'].clip(1200, 5800)
        
        # Prepare features and target
        X = df[self.feature_names]
        y = df['yield']
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Gradient Boosting model
        self.model = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=4,
            random_state=42
        )
        self.model.fit(X_scaled, y)
        self.is_trained = True
        
        # Save model and scaler
        os.makedirs('models', exist_ok=True)
        joblib.dump(self.model, 'models/gbr_model.pkl')
        joblib.dump(self.scaler, 'models/scaler.pkl')
        
        # Store feature importances
        self.feature_importances = dict(zip(self.feature_names, self.model.feature_importances_))
        print("Sample model trained and saved.")
    
    def predict(self, feature_dict):
        """Make a prediction with confidence interval"""
        if not self.is_trained:
            raise ValueError("Model not trained.")
        
        # Convert to DataFrame
        df_input = pd.DataFrame([feature_dict])
        
        # Ensure all features are present
        for feat in self.feature_names:
            if feat not in df_input.columns:
                df_input[feat] = 0
        
        # Scale features
        X_scaled = self.scaler.transform(df_input[self.feature_names])
        
        # Make prediction
        prediction = self.model.predict(X_scaled)[0]
        
        # Estimate confidence interval (simplified)
        # In production, use quantile regression or bootstrap
        std_dev = 250  # Approximate standard deviation from training
        lower = prediction - 1.96 * std_dev
        upper = prediction + 1.96 * std_dev
        
        # Clip to realistic range
        prediction = max(1000, min(6000, prediction))
        lower = max(800, min(5500, lower))
        upper = max(1200, min(6500, upper))
        
        # Get feature importances
        importances = self.feature_importances.copy()
        
        return {
            'predicted_yield': round(prediction, 2),
            'lower_bound': round(lower, 2),
            'upper_bound': round(upper, 2),
            'feature_importance': importances
        }

# Initialize predictor
predictor = YieldPredictor()

# =====================================================
# RECOMMENDATION ENGINE
# =====================================================

def generate_recommendations(features, predicted_yield):
    """Generate actionable recommendations based on features and prediction"""
    recommendations = []
    
    # Check nitrogen level
    if features.get('nitrogen', 0) < 100:
        recommendations.append({
            'priority': 'high',
            'title': 'Low Soil Nitrogen',
            'description': 'Soil nitrogen is below optimal level (100 kg/ha). Consider top-dressing with Urea or NPK 20-10-10 to boost yield.'
        })
    
    # Check phosphorus
    if features.get('phosphorus', 0) < 20:
        recommendations.append({
            'priority': 'medium',
            'title': 'Low Phosphorus',
            'description': 'Phosphorus levels are low. Apply single superphosphate (SSP) or NPK 15-15-15 to improve root development and grain filling.'
        })
    
    # Check potassium
    if features.get('potassium', 0) < 150:
        recommendations.append({
            'priority': 'medium',
            'title': 'Low Potassium',
            'description': 'Potassium is below optimal. Apply muriate of potash (MOP) to improve drought tolerance and stalk strength.'
        })
    
    # Check rainfall
    if features.get('cumulative_rainfall', 0) < 500:
        recommendations.append({
            'priority': 'high',
            'title': 'Low Rainfall Forecast',
            'description': 'Seasonal rainfall is projected to be below average. Consider supplemental irrigation or drought-tolerant variety.'
        })
    
    # Check planting date
    planting_doy = features.get('planting_doy', 0)
    if planting_doy < 100 or planting_doy > 170:
        recommendations.append({
            'priority': 'medium',
            'title': 'Suboptimal Planting Date',
            'description': 'For Umudike region, optimal planting is between early April (DOY 90) and late June (DOY 170). Current planting date may affect yields.'
        })
    
    # If yield is below average (3200 kg/ha)
    if predicted_yield < 3200:
        recommendations.append({
            'priority': 'medium',
            'title': 'Yield Below Regional Average',
            'description': f'Predicted yield ({predicted_yield:.0f} kg/ha) is below the regional average of 3,200 kg/ha. Review management practices and consider soil amendments.'
        })
    
    # If no recommendations, add a positive one
    if not recommendations:
        recommendations.append({
            'priority': 'low',
            'title': 'Good Management Practices',
            'description': 'Your current practices are well-aligned for optimal yield. Continue monitoring crop health and maintain irrigation schedule.'
        })
    
    return recommendations

# =====================================================
# ROUTES
# =====================================================

@app.route('/')
def index():
    """Homepage"""
    return render_template('index.html', title='Home')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user_data = db.get_user(form.email.data)
        if user_data and user_data['password'] == form.password.data:
            user = User(user_data)
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html', form=form, title='Login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        user_id = db.create_user(
            form.email.data,
            form.password.data,
            form.full_name.data,
            form.phone.data
        )
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form, title='Register')

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    fields = db.get_user_fields(current_user.id)
    field_count = len(fields)
    
    # Get recent predictions
    recent_predictions = []
    for pred in sorted(db.predictions.values(), key=lambda x: x['date'], reverse=True)[:5]:
        field = db.fields.get(pred['field_id'])
        recent_predictions.append({
            'field_name': field['field_name'] if field else 'Unknown',
            'predicted_yield': pred['predicted_yield'],
            'date': pred['date']
        })
    
    return render_template('dashboard.html', 
                         title='Dashboard',
                         fields=fields,
                         field_count=field_count,
                         recent_predictions=recent_predictions)

@app.route('/add-field', methods=['GET', 'POST'])
@login_required
def add_field():
    """Add a new field"""
    form = FieldForm()
    if form.validate_on_submit():
        field_id = db.add_field(
            current_user.id,
            form.field_name.data,
            form.latitude.data,
            form.longitude.data,
            form.area_ha.data,
            form.soil_type.data
        )
        flash(f'Field "{form.field_name.data}" added successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('add_field.html', form=form, title='Add Field')

@app.route('/predict', methods=['GET', 'POST'])
@login_required
def predict():
    """Yield prediction form"""
    form = PredictionForm()
    
    # Populate field choices
    fields = db.get_user_fields(current_user.id)
    form.field_id.choices = [(f['id'], f['field_name']) for f in fields]
    
    if not fields:
        flash('Please add a field before making a prediction.', 'warning')
        return redirect(url_for('add_field'))
    
    if form.validate_on_submit():
        field_id = int(form.field_id.data)
        
        # Get field data
        field = db.fields.get(field_id)
        if not field:
            flash('Field not found.', 'danger')
            return redirect(url_for('predict'))
        
        # Build feature vector
        features = {
            'ph': 6.5,  # Default values for prototype
            'organic_matter': 2.8,
            'nitrogen': 140,
            'phosphorus': 35,
            'potassium': 220,
            'avg_temp': 28.5,
            'cumulative_rainfall': 750,
            'humidity_avg': 72,
            'solar_radiation': 18.5,
            'gdd': 2200,
            'planting_doy': form.planting_date.data.timetuple().tm_yday,
            'fert_rate': form.fertiliser_rate.data,
            'irrigation_freq': form.irrigation_frequency.data,
            'prev_yield_avg': 3000  # Default historical average
        }
        
        # In a real implementation, these would come from database:
        # - Soil data from soil_samples table
        # - Weather data from weather_data table
        # - Previous yield from yield_history table
        
        try:
            # Make prediction
            result = predictor.predict(features)
            
            # Generate recommendations
            recommendations = generate_recommendations(features, result['predicted_yield'])
            
            # Save prediction
            db.save_prediction(
                field_id,
                result['predicted_yield'],
                result['lower_bound'],
                result['upper_bound'],
                features,
                recommendations
            )
            
            # Render results
            return render_template('result.html',
                                 title='Prediction Results',
                                 field_name=field['field_name'],
                                 prediction=result,
                                 features=features,
                                 recommendations=recommendations,
                                 feature_names=predictor.feature_names)
            
        except Exception as e:
            flash(f'Prediction error: {str(e)}', 'danger')
            return redirect(url_for('predict'))
    
    return render_template('predict.html', form=form, title='Predict Yield')

@app.route('/history')
@login_required
def history():
    """Prediction history"""
    user_fields = [f['id'] for f in db.get_user_fields(current_user.id)]
    user_predictions = []
    
    for pred in db.predictions.values():
        if pred['field_id'] in user_fields:
            field = db.fields.get(pred['field_id'])
            pred_data = pred.copy()
            pred_data['field_name'] = field['field_name'] if field else 'Unknown'
            user_predictions.append(pred_data)
    
    # Sort by date descending
    user_predictions.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('history.html', 
                         title='Prediction History',
                         predictions=user_predictions)

@app.route('/admin')
@login_required
def admin():
    """Admin panel"""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('admin.html',
                         title='Admin Panel',
                         user_count=len(db.users),
                         field_count=len(db.fields),
                         prediction_count=len(db.predictions))

@app.route('/api/predict', methods=['POST'])
@login_required
def api_predict():
    """REST API endpoint for predictions"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Extract features
        features = {
            'ph': data.get('ph', 6.5),
            'organic_matter': data.get('organic_matter', 2.8),
            'nitrogen': data.get('nitrogen', 140),
            'phosphorus': data.get('phosphorus', 35),
            'potassium': data.get('potassium', 220),
            'avg_temp': data.get('avg_temp', 28.5),
            'cumulative_rainfall': data.get('cumulative_rainfall', 750),
            'humidity_avg': data.get('humidity_avg', 72),
            'solar_radiation': data.get('solar_radiation', 18.5),
            'gdd': data.get('gdd', 2200),
            'planting_doy': data.get('planting_doy', 140),
            'fert_rate': data.get('fert_rate', 200),
            'irrigation_freq': data.get('irrigation_freq', 5),
            'prev_yield_avg': data.get('prev_yield_avg', 3000)
        }
        
        result = predictor.predict(features)
        return jsonify({
            'success': True,
            'prediction': result
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# =====================================================
# ERROR HANDLERS
# =====================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', title='Page Not Found'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html', title='Server Error'), 500

# =====================================================
# MAIN ENTRY POINT
# =====================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)