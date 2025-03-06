from flask import Blueprint, jsonify, render_template, request, session, redirect, url_for
from functools import wraps

# Create Blueprint for e-commerce
e_market_routes = Blueprint('e_market', __name__, static_folder='static', template_folder='templates')

# Simulate user login (using Flask session for simplicity)
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('e_market.login'))
        return f(*args, **kwargs)
    return decorated_function

# Dummy products (replace with database query later)
PRODUCTS = [
    {"name": "Tomatoes", "price": 1, "farmer": "Raj"},
    {"name": "Potatoes", "price": 0.8, "farmer": "Priya"}
]

# Kissan E-Market page
@e_market_routes.route('/kissan-e-market')
def kissan_e_market():
    return render_template('kissan_e_market.html', products=PRODUCTS)

# API for product data (for JS to fetch if needed)
@e_market_routes.route('/api/products')
def get_products():
    return jsonify(PRODUCTS)

# Login/Registration page (simplified)
@e_market_routes.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_type = request.form['user_type']
        if username and password:  # Simple validation
            session['user'] = {'username': username, 'type': user_type}
            return redirect(url_for('e_market.kissan_e_market'))
        return "Invalid login/register, try again.", 400
    return render_template('login.html', action='login')

@e_market_routes.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_type = request.form['user_type']
        if username and password:  # Simple validation
            session['user'] = {'username': username, 'type': user_type}
            return redirect(url_for('e_market.kissan_e_market'))
        return "Invalid registration, try again.", 400
    return render_template('login.html', action='register')

# Logout (optional)
@e_market_routes.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('e_market.kissan_e_market'))

# Add to cart (protected route)
@e_market_routes.route('/add-to-cart/<product_name>', methods=['POST'])
@login_required
def add_to_cart(product_name):
    if 'cart' not in session:
        session['cart'] = []
    product = next((p for p in PRODUCTS if p['name'] == product_name), None)
    if product:
        session['cart'].append(product)
        return jsonify({"message": f"Added {product_name} to your cart! Total items: {len(session['cart'])}"})
    return jsonify({"error": "Product not found"}), 404