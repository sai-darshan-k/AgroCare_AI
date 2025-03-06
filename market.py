
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request, session, redirect, url_for
from functools import wraps

# Create Blueprint for e-commerce
e_market_routes = Blueprint('market', __name__, static_folder='static', template_folder='templates')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kissan_e_market_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kissan_market.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    user_type = db.Column(db.String(10), nullable=False)  # 'farmer' or 'consumer'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # For farmers
    farm_name = db.Column(db.String(100))
    location = db.Column(db.String(200))
    phone = db.Column(db.String(15))
    
    def __repr__(self):
        return f'<User {self.username}>'

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(200))
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Product {self.name}>'

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    
    def __repr__(self):
        return f'<Cart Item {self.id}>'

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Order {self.id}>'

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    
    def __repr__(self):
        return f'<OrderItem {self.id}>'

# Routes
@e_market_routes.route('/emarket')
def emarket():
    return render_template('emarket.html', products=products)  # NameError: 'products' is not defined

@e_market_routes.route('/products.html')
def redirect_products_html():
    return redirect(url_for('products'))

@e_market_routes.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user_type = request.form.get('user_type')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if user already exists
        user_exists = User.query.filter_by(email=email).first()
        if user_exists:
            flash('Email already registered')
            return redirect(url_for('register'))
        
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            user_type=user_type
        )
        
        # If farmer, add additional details
        if user_type == 'farmer':
            new_user.farm_name = request.form.get('farm_name')
            new_user.location = request.form.get('location')
            new_user.phone = request.form.get('phone')
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful. Please login.')
        return redirect(url_for('login'))
    
    # Get the 'type' query parameter from the URL
    user_type = request.args.get('type', 'consumer')  # Default to 'consumer' if no type is provided
    return render_template('register.html', user_type=user_type)

@e_market_routes.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_type'] = user.user_type
            
            flash('Login successful')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password')
    
    return render_template('login.html')

@e_market_routes.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_type', None)
    flash('You have been logged out')
    return redirect(url_for('home'))

@e_market_routes.route('/farmer/dashboard')
def farmer_dashboard():
    if 'user_id' not in session or session['user_type'] != 'farmer':
        flash('Please login as a farmer to access this page')
        return redirect(url_for('login'))
    
    farmer_id = session['user_id']
    products = Product.query.filter_by(farmer_id=farmer_id).all()
    return render_template('farmer_dashboard.html', products=products)

@e_market_routes.route('/farmer/add_product', methods=['GET', 'POST'])
def add_product():
    if 'user_id' not in session or session['user_type'] != 'farmer':
        flash('Please login as a farmer to access this page')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        quantity = int(request.form.get('quantity'))
        category = request.form.get('category')
        image_url = request.form.get('image_url')
        
        new_product = Product(
            name=name,
            description=description,
            price=price,
            quantity=quantity,
            category=category,
            image_url=image_url,
            farmer_id=session['user_id']
        )
        
        db.session.add(new_product)
        db.session.commit()
        
        flash('Product added successfully')
        return redirect(url_for('farmer_dashboard'))
    
    return render_template('add_product.html')

@e_market_routes.route('/products')
def products():
    category = request.args.get('category')
    if category:
        products = Product.query.filter_by(category=category).all()
    else:
        products = Product.query.all()
    
    return render_template('products.html', products=products)

@e_market_routes.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    farmer = User.query.get(product.farmer_id)
    return render_template('product_detail.html', product=product, farmer=farmer)

@e_market_routes.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash('Please login to add items to cart')
        return redirect(url_for('login'))
    
    cart_item = Cart.query.filter_by(user_id=session['user_id'], product_id=product_id).first()
    
    if cart_item:
        cart_item.quantity += 1
    else:
        new_cart_item = Cart(
            user_id=session['user_id'],
            product_id=product_id,
            quantity=1
        )
        db.session.add(new_cart_item)
    
    db.session.commit()
    flash('Item added to cart')
    return redirect(url_for('cart'))

@e_market_routes.route('/cart')
def cart():
    if 'user_id' not in session:
        flash('Please login to view your cart')
        return redirect(url_for('login'))
    
    cart_items = Cart.query.filter_by(user_id=session['user_id']).all()
    total = 0
    cart_products = []
    
    for item in cart_items:
        product = Product.query.get(item.product_id)
        total += product.price * item.quantity
        cart_products.append({
            'cart_id': item.id,
            'product': product,
            'quantity': item.quantity
        })
    
    return render_template('cart.html', cart_products=cart_products, total=total)

@e_market_routes.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('Please login to checkout')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        cart_items = Cart.query.filter_by(user_id=session['user_id']).all()
        
        if not cart_items:
            flash('Your cart is empty')
            return redirect(url_for('cart'))
        
        total = 0
        for item in cart_items:
            product = Product.query.get(item.product_id)
            total += product.price * item.quantity
        
        new_order = Order(
            user_id=session['user_id'],
            total_amount=total,
            status='pending'
        )
        db.session.add(new_order)
        db.session.flush()
        
        for item in cart_items:
            product = Product.query.get(item.product_id)
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=product.price
            )
            db.session.add(order_item)
            
            # Update product quantity
            product.quantity -= item.quantity
            
            # Delete cart item
            db.session.delete(item)
        
        db.session.commit()
        flash('Order placed successfully')
        return redirect(url_for('orders'))
    
    return render_template('checkout.html')

@e_market_routes.route('/orders')
def orders():
    if 'user_id' not in session:
        flash('Please login to view your orders')
        return redirect(url_for('login'))
    
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=orders)

@e_market_routes.route('/order/<int:order_id>')
def order_detail(order_id):
    if 'user_id' not in session:
        flash('Please login to view order details')
        return redirect(url_for('login'))
    
    order = Order.query.get_or_404(order_id)
    
    if order.user_id != session['user_id'] and session['user_type'] != 'farmer':
        flash('You do not have permission to view this order')
        return redirect(url_for('orders'))
    
    order_items = OrderItem.query.filter_by(order_id=order.id).all()
    items = []
    
    for item in order_items:
        product = Product.query.get(item.product_id)
        items.append({
            'product': product,
            'quantity': item.quantity,
            'price': item.price
        })
    
    return render_template('order_detail.html', order=order, items=items)
