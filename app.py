from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime
from bd import get_db_connection

app = Flask(__name__)



@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Películas con toda la info (para el select y la galería)
    cur.execute('SELECT film_id, title, release_year, rating, image, description FROM film ORDER BY title')
    films = [
        {
            'id': row[0],
            'title': row[1],
            'year': row[2],
            'rating': row[3],
            'image': row[4] if row[4] else f'https://via.placeholder.com/150/FF69B4/FFFFFF?text={row[1]}',
            'description': row[5],
        }
        for row in cur.fetchall()
    ]
    # Obtener todos los clientes
    cur.execute('SELECT customer_id, first_name, last_name, email FROM customer;')
    customers = [
        {'id': row[0], 'name': f"{row[1]} {row[2]}", 'email': row[3]}
        for row in cur.fetchall()
    ]

  
    conn.close()
    
    return render_template('index.html', films=films, rentalStatus=None)

    
    cur.close()
    conn.close()


    return render_template('index.html', films=films, customers=customers, selectedCustomer=None, rentalStatus=None)

@app.route('/customers/<int:customer_id>')
def search_customer_by_id(customer_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute('''
        SELECT customer_id, first_name, last_name 
        FROM customer 
        WHERE customer_id = %s
    ''', (customer_id,))

    row = cur.fetchone()
    
    cur.close()
    conn.close()

    if row:
        customer = {'id': row[0], 'name': f"{row[1]} {row[2]}"}
        return jsonify(customer)
    else:
        return jsonify({'error': 'Customer not found'}), 404


@app.route('/inventory/<int:film_id>')
def get_inventory(film_id):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT i.inventory_id 
        FROM inventory i
        LEFT JOIN rental r ON i.inventory_id = r.inventory_id AND r.return_date IS NULL
        WHERE i.film_id = %s AND r.rental_id IS NULL
    ''', (film_id,))
    
    inventory_items = [row[0] for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return jsonify({'available': len(inventory_items) > 0, 'inventory_ids': inventory_items})

@app.route('/create_rental', methods=['POST'])
def create_rental():
    customer_id = request.form['customer_id']
    inventory_id = request.form['inventory_id']
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT staff_id FROM staff LIMIT 1')
    staff_id = cur.fetchone()[0]
    
    try:
        cur.execute('''
            INSERT INTO rental 
            (rental_date, inventory_id, customer_id, return_date, staff_id, last_update)
            VALUES (NOW(), %s, %s, NULL, %s, NOW())
        ''', (inventory_id, customer_id, staff_id))
        
        cur.execute('SELECT LAST_INSERT_ID()')
        rental_id = cur.fetchone()[0]
        
        cur.execute('''
            SELECT rental_rate FROM film f
            JOIN inventory i ON f.film_id = i.film_id
            WHERE i.inventory_id = %s
        ''', (inventory_id,))
        
        rental_rate = cur.fetchone()[0]
        
        cur.execute('''
            INSERT INTO payment
            (customer_id, staff_id, rental_id, amount, payment_date, last_update)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
        ''', (customer_id, staff_id, rental_id, rental_rate))
        
        conn.commit()
        message = "Rental created successfully!"
        success = True
    except Exception as e:
        conn.rollback()
        message = f"Error creating rental: {str(e)}"
        success = False
    finally:
        cur.close()
        conn.close()
    
    return jsonify({
    'success': success, 
    'message': message if message else "⚠️ Algo salió mal, pero no sabemos qué."
})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
