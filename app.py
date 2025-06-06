from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pandas as pd
import numpy as np
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import os
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Initialize Supabase client
supabase: Client = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_KEY')
)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Simple User class
class User(UserMixin):
    def __init__(self, id, email, password):
        self.id = id
        self.email = email
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    try:
        response = supabase.table('users').select('*').eq('id', user_id).execute()
        if response.data:
            user_data = response.data[0]
            return User(user_data['id'], user_data['email'], user_data['password'])
    except Exception as e:
        print(f"Error loading user: {str(e)}")
    return None

# Load model and scaler
try:
    kmeans = joblib.load("models/kmeans_model.pkl")
    scaler = joblib.load("models/scaler.pkl")
    print("ML models loaded successfully")
except Exception as e:
    print(f"Error loading models: {str(e)}")
    exit(1)

# Data storage for visualization
data_store = []

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template("index.html", prediction=None, images=None)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            response = supabase.table('users').select('*').eq('email', email).execute()
            if response.data and check_password_hash(response.data[0]['password'], password):
                user = User(response.data[0]['id'], email, response.data[0]['password'])
                login_user(user)
                return redirect(url_for('dashboard'))
            flash('Invalid email or password')
        except Exception as e:
            flash('Error during login')
            print(f"Login error: {str(e)}")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Check if user exists
            response = supabase.table('users').select('*').eq('email', email).execute()
            if response.data:
                flash('Email already registered')
                return redirect(url_for('register'))
            
            # Create new user
            hashed_password = generate_password_hash(password)
            response = supabase.table('users').insert({
                'email': email,
                'password': hashed_password
            }).execute()
            
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Error during registration')
            print(f"Registration error: {str(e)}")
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/about')
def about():
    return render_template("about.html")

@app.route('/contact')
def contact():
    return render_template("contact.html")

@app.route('/predict', methods=['POST'])
@login_required
def predict():
    try:
        age = int(request.form.get("age", 0))
        income = int(request.form.get("income", 0))
        score = int(request.form.get("score", 0))
        
        if not all([age > 0, income > 0, 0 < score <= 100]):
            raise ValueError("Invalid input values")
        
        data = np.array([[age, income, score]])
        data_scaled = scaler.transform(data)
        cluster = kmeans.predict(data_scaled)[0]
        
        data_store.append({"Age": age, "Income": income, "Score": score, "Cluster": cluster})
        
        os.makedirs('static', exist_ok=True)
        images = generate_visualizations()
        
        return render_template("index.html", 
                             prediction=f"Customer belongs to Cluster {cluster}", 
                             images=images)
    except Exception as e:
        flash(f'Error processing your request: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))

def generate_visualizations():
    if not data_store:
        return None

    df = pd.DataFrame(data_store)
    images = {}

    try:
        # 1. Income vs. Spending Score
        plt.figure(figsize=(8, 6))
        sns.scatterplot(x="Income", y="Score", hue="Cluster", data=df, palette="viridis", s=100)
        plt.title("Income vs. Spending Score")
        plt.xlabel("Annual Income (k$)")
        plt.ylabel("Spending Score (1-100)")
        img_path1 = os.path.join('static', 'income_vs_score.png')
        plt.savefig(img_path1, bbox_inches='tight', dpi=100)
        plt.close()
        images["income_vs_score"] = 'income_vs_score.png'

        # 2. Age vs. Spending Score
        plt.figure(figsize=(8, 6))
        sns.scatterplot(x="Age", y="Score", hue="Cluster", data=df, palette="coolwarm", s=100)
        plt.title("Age vs. Spending Score")
        plt.xlabel("Age")
        plt.ylabel("Spending Score (1-100)")
        img_path2 = os.path.join('static', 'age_vs_score.png')
        plt.savefig(img_path2, bbox_inches='tight', dpi=100)
        plt.close()
        images["age_vs_score"] = 'age_vs_score.png'

        # 3. Age vs. Income
        plt.figure(figsize=(8, 6))
        sns.scatterplot(x="Age", y="Income", hue="Cluster", data=df, palette="Set1", s=100)
        plt.title("Age vs. Income")
        plt.xlabel("Age")
        plt.ylabel("Annual Income (k$)")
        img_path3 = os.path.join('static', 'age_vs_income.png')
        plt.savefig(img_path3, bbox_inches='tight', dpi=100)
        plt.close()
        images["age_vs_income"] = 'age_vs_income.png'

        # 4. Cluster Distribution
        plt.figure(figsize=(8, 6))
        sns.countplot(x="Cluster", data=df, palette="pastel")
        plt.title("Cluster Distribution")
        plt.xlabel("Cluster")
        plt.ylabel("Number of Customers")
        img_path4 = os.path.join('static', 'cluster_distribution.png')
        plt.savefig(img_path4, bbox_inches='tight', dpi=100)
        plt.close()
        images["cluster_distribution"] = 'cluster_distribution.png'

    except Exception as e:
        print(f"Error generating visualizations: {str(e)}")
        return None

    return images

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    app.run(debug=True)