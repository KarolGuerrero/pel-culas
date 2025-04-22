from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime
from bd import get_db_connection

app = Flask(__name__)

@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()

    store_id = request.args.get('store_id', type=int)
    
    if store_id is not None:
        # Películas disponibles en la tienda seleccionada
        cur.execute('''
            SELECT f.film_id, f.title, f.release_year, f.rating, f.image, f.description
            FROM film f
            JOIN inventory i ON f.film_id = i.film_id
            LEFT JOIN rental r 
                ON i.inventory_id = r.inventory_id AND r.return_date IS NULL
            WHERE i.store_id = %s
            GROUP BY f.film_id
            HAVING COUNT(i.inventory_id) > COUNT(r.rental_id)
            ORDER BY f.title
        ''', (store_id,))

    else:
        # Todas las películas sin filtrar (por si no se seleccionó tienda)
        cur.execute('SELECT film_id, title, release_year, rating, image, description FROM film ORDER BY title')

    films = [
        {
            'film_id': row[0],
            'title': row[1],
            'release_year': row[2],
            'rating': row[3],
            'image': row[4] if row[4] else f'https://via.placeholder.com/150/FF69B4/FFFFFF?text={row[1]}',
            'description': row[5],
        }
        for row in cur.fetchall()
    ]

    # Obtener las tiendas disponibles para el selector
    cur.execute('SELECT DISTINCT store_id FROM inventory ORDER BY store_id')
    stores = [row[0] for row in cur.fetchall()]

    cur.close()
    conn.close()

    return render_template(
        'index.html',
        films=films,
        stores=stores,
        selected_store=store_id,
        rentalStatus=None
    )


@app.route('/api/films')
def get_films_by_store():
    store_id = request.args.get('store_id', type=int)
    if store_id is None:
        return jsonify([])

    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT f.film_id, f.title
        FROM film f
        JOIN inventory i ON f.film_id = i.film_id
        LEFT JOIN rental r 
            ON i.inventory_id = r.inventory_id AND r.return_date IS NULL
        WHERE i.store_id = %s
        GROUP BY f.film_id
        HAVING COUNT(i.inventory_id) > COUNT(r.rental_id)
        ORDER BY f.title
    ''', (store_id,))


    films = [{'film_id': row[0], 'title': row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(films)


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

def is_film_already_rented_in_store(film_id, store_id, conn):
    cur = conn.cursor()
    cur.execute('''
        SELECT 1
        FROM inventory i
        JOIN rental r ON i.inventory_id = r.inventory_id
        WHERE i.film_id = %s AND i.store_id = %s AND r.return_date IS NULL
        LIMIT 1
    ''', (film_id, store_id))
    result = cur.fetchone()
    cur.close()
    return result is not None


@app.route('/create_rental', methods=['POST'])
def create_rental():
    customer_id = request.form['customer_id']
    inventory_id = request.form['inventory_id']
    
    conn = get_db_connection()
    cur = conn.cursor()

    # Obtener info de la película y la tienda
    cur.execute('''
        SELECT film_id, store_id FROM inventory WHERE inventory_id = %s
    ''', (inventory_id,))
    row = cur.fetchone()
    if not row:
        return jsonify({'success': False, 'message': 'Inventario no encontrado'})

    film_id, store_id = row

    # Validar si ya se alquiló esta película en esa tienda
    if is_film_already_rented_in_store(film_id, store_id, conn):
        return jsonify({'success': False, 'message': '⚠️ Esta película ya fue alquilada y no ha sido devuelta.'})

    # Continuar con el proceso normal
    cur.execute('SELECT staff_id FROM staff LIMIT 1')
    staff_id = cur.fetchone()[0]

    try:
        cur.execute('''
            INSERT INTO rental 
            (rental_date, inventory_id, customer_id, return_date, staff_id, last_update)
            VALUES (NOW(), %s, %s, NULL, %s, NOW())
        ''', (inventory_id, customer_id, staff_id))

        cur.execute('SELECT rental_rate FROM film f JOIN inventory i ON f.film_id = i.film_id WHERE i.inventory_id = %s', (inventory_id,))
        rental_rate = cur.fetchone()[0]

        cur.execute('''
            INSERT INTO payment
            (customer_id, staff_id, rental_id, amount, payment_date, last_update)
            VALUES (%s, %s, LAST_INSERT_ID(), %s, NOW(), NOW())
        ''', (customer_id, staff_id, rental_rate))

        conn.commit()
        message = "✅ Renta creada con éxito"
        success = True
    except Exception as e:
        conn.rollback()
        message = f"❌ Error creando la renta: {str(e)}"
        success = False
    finally:
        cur.close()
        conn.close()

    return jsonify({'success': success, 'message': message})



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
