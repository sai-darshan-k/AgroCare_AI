document.addEventListener('DOMContentLoaded', () => {
    // Fetch and display products from API
    fetch('/e-market/api/products')
      .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
        return response.json();
      })
      .then(products => {
        const productList = document.getElementById('product-list');
        products.forEach(product => {
          const card = document.createElement('div');
          card.className = 'product-card';
          card.innerHTML = `
            <h3 class="product-title">${product.name}</h3>
            <p>Price: $${product.price}</p>
            <p>Farmer: ${product.farmer}</p>
            <button onclick="addToCart('${product.name}', ${product.price})">Add to Cart</button>
          `;
          productList.appendChild(card);
        });
      })
      .catch(error => {
        document.getElementById('product-list').innerHTML = '<p>Error loading products.</p>';
        console.error('Fetch error:', error);
      });
  
    // Simulate cart (using localStorage for simplicity)
    let cart = JSON.parse(localStorage.getItem('cart')) || [];
  
    window.addToCart = function(productName, price) {
      if (!document.cookie.includes('user')) {  // Simplified check; use Flask session in production
        document.getElementById('login-modal').style.display = 'block';
        return;
      }
      cart.push({ name: productName, price: parseFloat(price) });
      localStorage.setItem('cart', JSON.stringify(cart));
      alert(`Added ${productName} to your cart! Total items: ${cart.length}`);
    };
  
    window.closeLogin = function() {
      document.getElementById('login-modal').style.display = 'none';
    };
  
    // Product Data with Categories and 20% Savings
    const products = [
      // Vegetables
      { name: 'Fresh Tomatoes', price: '₹40', unit: 'kg', image: 'static/images/tomato.jpg', tag: 'Organic', farmer: 'Ramesh Patel', category: 'vegetables', shopPrice: '₹50' },
      { name: 'Potatoes', price: '₹24', unit: 'kg', image: 'static/images/potato.jpg', tag: 'Fresh', farmer: 'Sita Devi', category: 'vegetables', shopPrice: '₹30' },
      { name: 'Carrots', price: '₹32', unit: 'kg', image: 'static/images/carrot.jpg', tag: 'Seasonal', farmer: 'Vikram Singh', category: 'vegetables', shopPrice: '₹40' },
      { name: 'Spinach', price: '₹20', unit: 'kg', image: 'static/images/spinach.jpg', tag: 'Organic', farmer: 'Priya Sharma', category: 'vegetables', shopPrice: '₹25' },
      // Fruits
      { name: 'Green Apples', price: '₹120', unit: 'kg', image: 'static/images/apple.jpg', tag: 'Fresh', farmer: 'Anil Kumar', category: 'fruits', shopPrice: '₹150' },
      { name: 'Bananas', price: '₹48', unit: 'dozen', image: 'static/images/banana.jpg', tag: 'Seasonal', farmer: 'Meena Rani', category: 'fruits', shopPrice: '₹60' },
      { name: 'Mangoes', price: '₹80', unit: 'kg', image: 'static/images/mango.jpg', tag: 'Organic', farmer: 'Rahul Verma', category: 'fruits', shopPrice: '₹100' },
      { name: 'Oranges', price: '₹64', unit: 'kg', image: 'static/images/orange.jpg', tag: 'Fresh', farmer: 'Kiran Patel', category: 'fruits', shopPrice: '₹80' },
      // Grains & Pulses
      { name: 'Organic Rice', price: '₹80', unit: 'kg', image: 'static/images/rice.jpg', tag: 'Organic', farmer: 'Sita Devi', category: 'grains', shopPrice: '₹100' },
      { name: 'Wheat Flour', price: '₹40', unit: 'kg', image: 'static/images/wheat.jpg', tag: 'Fresh', farmer: 'Vikram Singh', category: 'grains', shopPrice: '₹50' },
      { name: 'Lentils', price: '₹96', unit: 'kg', image: 'static/images/lentils.jpg', tag: 'Organic', farmer: 'Ramesh Patel', category: 'grains', shopPrice: '₹120' },
      // Dairy Products
      { name: 'Farm Milk', price: '₹40', unit: 'ltr', image: 'static/images/milk.jpg', tag: 'Dairy', farmer: 'Priya Sharma', category: 'dairy', shopPrice: '₹50' },
      { name: 'Paneer', price: '₹200', unit: 'kg', image: 'static/images/paneer.jpg', tag: 'Fresh', farmer: 'Anil Kumar', category: 'dairy', shopPrice: '₹250' },
      { name: 'Curd', price: '₹48', unit: 'kg', image: 'static/images/curd.jpg', tag: 'Organic', farmer: 'Meena Rani', category: 'dairy', shopPrice: '₹60' },
      // Spices
      { name: 'Turmeric Powder', price: '₹160', unit: 'kg', image: 'static/images/turmeric.jpg', tag: 'Organic', farmer: 'Rahul Verma', category: 'spices', shopPrice: '₹200' },
      { name: 'Red Chili Powder', price: '₹200', unit: 'kg', image: 'static/images/chili.jpg', tag: 'Fresh', farmer: 'Kiran Patel', category: 'spices', shopPrice: '₹250' },
      // Seeds & Farming Tools
      { name: 'Sunflower Seeds', price: '₹120', unit: 'kg', image: 'static/images/sunflower.jpg', tag: 'Organic', farmer: 'Sita Devi', category: 'seeds', shopPrice: '₹150' },
      { name: 'Hand Trowel', price: '₹80', unit: 'piece', image: 'static/images/trowel.jpg', tag: 'Tool', farmer: 'Vikram Singh', category: 'seeds', shopPrice: '₹100' },
      // Organic Products (cross-category)
      { name: 'Organic Honey', price: '₹240', unit: 'kg', image: 'static/images/honey.jpg', tag: 'Organic', farmer: 'Ramesh Patel', category: 'organic', shopPrice: '₹300' },
      { name: 'Organic Jaggery', price: '₹80', unit: 'kg', image: 'static/images/jaggery.jpg', tag: 'Organic', farmer: 'Priya Sharma', category: 'organic', shopPrice: '₹100' },
    ];
  
    // Dynamic Product Loading with Filtering
    const productGrids = document.querySelectorAll('.product-grid, .products-grid');
    productGrids.forEach(grid => {
      function renderProducts(category = 'all') {
        grid.innerHTML = ''; // Clear existing products
        const filteredProducts = category === 'all' ? products : products.filter(p => p.category === category);
        filteredProducts.forEach(product => {
          const productCard = document.createElement('div');
          productCard.classList.add('product-card');
          productCard.innerHTML = `
            <div class="product-image">
              <img src="${product.image}" alt="${product.name}">
              <span class="product-tag">${product.tag}</span>
            </div>
            <div class="product-details">
              <h3 class="product-title">${product.name}</h3>
              <div class="product-info">
                <span class="product-price">${product.price}</span>
                <span class="product-unit">per ${product.unit}</span>
              </div>
              <div class="farmer-name">
                <i class="fas fa-user"></i> ${product.farmer}
              </div>
              <div class="savings">
                Shop Price: ${product.shopPrice} - <span>You save 20%</span>
              </div>
              <div class="product-actions">
                <button class="btn primary-btn" onclick="addToCart('${product.name}', ${parseFloat(product.price.replace('₹', ''))} )">Add to Cart</button>
                <button class="wishlist-btn"><i class="fas fa-heart"></i></button>
              </div>
            </div>
          `;
          grid.appendChild(productCard);
        });
        updateCategoryTitle(category); // Update the title
      }
  
      // Initial render: All products
      renderProducts('all');
  
      // Category filtering from navigation and sidebar
      const categoryLinks = document.querySelectorAll('.main-nav a, .category-list a');
      categoryLinks.forEach(link => {
        link.addEventListener('click', (e) => {
          e.preventDefault();
          const category = new URLSearchParams(link.search).get('category') || 'all';
          renderProducts(category);
          categoryLinks.forEach(l => l.classList.remove('active'));
          link.classList.add('active');
        });
      });
    });
  
    // Update product category title
    function updateCategoryTitle(category) {
      const titleElement = document.getElementById('product-category-title');
      const currentCategory = document.getElementById('current-category');
      if (titleElement && currentCategory) {
        const title = category === 'all' ? 'All Products' : category.charAt(0).toUpperCase() + category.slice(1);
        titleElement.textContent = title;
        currentCategory.textContent = title;
      }
    }
  
    // Search functionality
    const searchBar = document.getElementById('search-bar');
    const searchBtn = document.getElementById('search-btn');
    const searchPopup = document.getElementById('search-popup');
    const popupMessage = document.getElementById('popup-message');
  
    if (searchBtn && searchBar) {
      searchBtn.addEventListener('click', () => {
        performSearch(searchBar.value.trim());
      });
  
      searchBar.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          performSearch(searchBar.value.trim());
        }
      });
    }
  
    function performSearch(query) {
      if (!query) return;
  
      const lowerQuery = query.toLowerCase();
      const foundProduct = products.find(product => 
        product.name.toLowerCase().includes(lowerQuery)
      );
  
      if (foundProduct) {
        const productCards = document.querySelectorAll('.product-card');
        productCards.forEach(card => {
          if (card.querySelector('.product-title').textContent.toLowerCase().includes(lowerQuery)) {
            card.scrollIntoView({ behavior: 'smooth', block: 'center' });
            card.style.border = '2px solid green';
            setTimeout(() => card.style.border = '', 3000);
          }
        });
      } else {
        popupMessage.textContent = `Sorry, "${query}" is not available right now.`;
        searchPopup.style.display = 'block';
      }
    }
  
    window.closePopup = function() {
      searchPopup.style.display = 'none';
    };
  
    // Menu Toggle for Mobile (if applicable)
    const menuToggle = document.getElementById('menuToggle');
    const mainNav = document.querySelector('.main-nav');
    if (menuToggle && mainNav) {
      menuToggle.addEventListener('click', () => {
        mainNav.classList.toggle('active');
      });
    }
  
    // Hero Slider Functionality (if applicable)
    const slider = document.querySelector('.hero-slider');
    if (slider) {
      const slides = document.querySelectorAll('.slide');
      const dots = document.querySelectorAll('.slider-dots .dot');
      const prevArrow = document.querySelector('.prev-arrow');
      const nextArrow = document.querySelector('.next-arrow');
      let currentSlide = 0;
  
      function updateSlide(index) {
        slides.forEach((slide, i) => {
          slide.classList.toggle('active', i === index);
        });
        dots.forEach((dot, i) => {
          dot.classList.toggle('active', i === index);
        });
      }
  
      nextArrow.addEventListener('click', () => {
        currentSlide = (currentSlide + 1) % slides.length;
        updateSlide(currentSlide);
      });
  
      prevArrow.addEventListener('click', () => {
        currentSlide = (currentSlide - 1 + slides.length) % slides.length;
        updateSlide(currentSlide);
      });
  
      dots.forEach((dot, index) => {
        dot.addEventListener('click', () => {
          currentSlide = index;
          updateSlide(currentSlide);
        });
      });
  
      setInterval(() => {
        currentSlide = (currentSlide + 1) % slides.length;
        updateSlide(currentSlide);
      }, 5000);
    }
  
    // Registration Form Tabs (if applicable)
    const optionTabs = document.querySelectorAll('.option-tab');
    const registerForms = document.querySelectorAll('.register-forms form');
    if (optionTabs.length && registerForms.length) {
      optionTabs.forEach(tab => {
        tab.addEventListener('click', () => {
          optionTabs.forEach(t => t.classList.remove('active'));
          registerForms.forEach(f => f.classList.remove('active'));
          tab.classList.add('active');
          document.getElementById(`${tab.dataset.type}-form`).classList.add('active');
        });
      });
    }
  });