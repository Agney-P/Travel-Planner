from flask import Flask, render_template, request
from datetime import datetime
import requests
import os

app = Flask(__name__)

# Dummy distance/time calculator (replace with real API if needed)
def calculate_distance_time(start, destination, mode):
    api_key = os.environ.get('ORS_API_KEY', 'eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6ImJjNTkxMmQ5ZmI1ZjRiYzdiNTY4YWNmZmY4NWY2ZjNmIiwiaCI6Im11cm11cjY0In0=')
    mode_map = {
        'Car': 'driving-car',
        'Bike': 'cycling-regular',
        'EV': 'driving-car',
        'Train': 'driving-car',  # fallback to car
        'Bus': 'driving-car'     # fallback to car
    }
    profile = mode_map.get(mode, 'driving-car')
    # Geocode start and destination to get coordinates
    def geocode(place):
        url = f'https://api.openrouteservice.org/geocode/search'
        params = {
            'api_key': api_key,
            'text': place
        }
        try:
            resp = requests.get(url, params=params)
            data = resp.json()
            print('ORS Geocode response:', data)
            coords = data['features'][0]['geometry']['coordinates']
            return coords[0], coords[1]
        except Exception as e:
            print('Geocoding error:', e)
            return None, None
    start_lon, start_lat = geocode(start)
    end_lon, end_lat = geocode(destination)
    if None in [start_lon, start_lat, end_lon, end_lat]:
        return 0, 0, None
    # Get route
    url = f'https://api.openrouteservice.org/v2/directions/{profile}'
    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }
    body = {
        "coordinates": [[start_lon, start_lat], [end_lon, end_lat]]
    }
    try:
        resp = requests.post(url, headers=headers, json=body)
        data = resp.json()
        print('ORS Routing response:', data)
        summary = data['routes'][0]['summary']
        distance = round(summary['distance'] / 1000, 2)
        duration = round(summary['duration'] / 3600, 2)
        geometry = data['routes'][0].get('geometry', None)
        return distance, duration, geometry
    except Exception as e:
        print('ORS routing error:', e)
        return 0, 0, None
# Helper: decode polyline
def decode_polyline(polyline_str):
    import polyline
    return polyline.decode(polyline_str)

# Helper: get restaurants near a point using ORS Places API
def get_restaurants_ors(lon, lat, api_key):
    url = 'https://api.openrouteservice.org/pois'
    params = {
        'api_key': api_key,
        'request': 'pois',
        'geometry': {
            'point': [lon, lat]
        },
        'filters': {
            'category_ids': [5812]
        },
        'limit': 5
    }
    try:
        resp = requests.post(url, json=params)
        try:
            data = resp.json()
        except Exception as e:
            print('ORS Places error:', e)
            print('ORS Places raw response:', resp.text)
            return []
        restaurants = []
        for feat in data.get('features', []):
            name = feat['properties'].get('name', 'Unknown')
            address = feat['properties'].get('address', {}).get('formatted', '')
            restaurants.append(f"{name} - {address}")
        return restaurants
    except Exception as e:
        print('ORS Places error:', e)
        return []

# Essentials by trip type
TRIP_ESSENTIALS = {
    'Solo': ['ID Proof', 'Clothes', 'Emergency Kit', 'Phone Charger', 'Snacks'],
    'Family': ['ID Proofs', 'Clothes', 'Medicines', 'Toys', 'Snacks', 'Emergency Kit'],
    'Friends': ['ID Proofs', 'Clothes', 'Games', 'Emergency Kit', 'Snacks'],
    'Business': ['ID Proof', 'Laptop', 'Documents', 'Formal Clothes', 'Emergency Kit'],
    'Adventure': ['ID Proof', 'Sports Gear', 'Emergency Kit', 'Snacks', 'First Aid'],
    'Honeymoon': ['ID Proofs', 'Clothes', 'Gifts', 'Emergency Kit', 'Camera']
}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        start = request.form['start']
        destination = request.form['destination']
        dates = request.form['dates']
        mode = request.form['mode']
        budget = request.form['budget']
        trip_type = request.form['trip_type']
        food_pref = request.form.get('food_pref', '').lower()
        mileage = request.form.get('mileage', None)
        fuel_type = request.form.get('fuel_type', 'petrol')

        distance, time, geometry = calculate_distance_time(start, destination, mode)
        error_msg = None
        if distance == 0:
            error_msg = "Unable to fetch distance. Please check your locations, spelling, and try again."
        maps_url = f"https://www.google.com/maps/dir/{start}/{destination}"
        fuel_url = f"https://www.google.com/maps/search/fuel+stations+near+{start}"
        hospital_url = f"https://www.google.com/maps/search/hospitals+on+route+from+{start}+to+{destination}"
        food_url_start = f"https://www.google.com/maps/search/restaurants+near+{start}"
        food_url_end = f"https://www.google.com/maps/search/restaurants+near+{destination}"
        hotel_url = f"https://www.google.com/maps/search/hotels+near+{destination}"
        essentials = TRIP_ESSENTIALS.get(trip_type, TRIP_ESSENTIALS['Solo'])

        # Fuel budget calculation (for Car/Bike/EV only)
        estimated_fuel_cost = None
        estimated_fuel_liters = None
        fuel_price_per_liter = 105 if fuel_type == 'petrol' else 95  # INR
        if mode in ["Car", "Bike", "EV"] and mileage:
            try:
                mileage_val = float(mileage)
                if mileage_val > 0 and distance > 0:
                    estimated_fuel_liters = round(distance / mileage_val, 2)
                    estimated_fuel_cost = round(estimated_fuel_liters * fuel_price_per_liter, 2)
            except Exception as e:
                estimated_fuel_cost = None
                estimated_fuel_liters = None

    # Budget estimation logic removed as per user request

        # Hotel suggestions based on food preference
        veg_hotels = ["Green Leaf", "Veggie Delight", "Shree Pure Veg", "Annapurna Veg"]
        nonveg_hotels = ["Spicy Grill", "Meat Lovers", "Chicken Palace", "Seafood Bay"]
        if food_pref == "veg":
            hotel_suggestions = veg_hotels
        elif food_pref == "non-veg" or food_pref == "nonveg":
            hotel_suggestions = nonveg_hotels
        else:
            hotel_suggestions = ["No preference selected or invalid input."]

        quote = "YOU CANNOT DISCOVER NEW OCEANS UNLESS YOU HAVE THE COURAGE TO LOSE SIGHT OF THE CORE"

        # Remove route restaurant links, only provide start/end location links
        route_restaurant_links = []

        return render_template('result.html',
            start=start,
            destination=destination,
            dates=dates,
            mode=mode,
            budget=budget,
            trip_type=trip_type,
            distance=distance,
            time=time,
            maps_url=maps_url,
            fuel_url=fuel_url,
            hospital_url=hospital_url,
            food_url_start=food_url_start,
            food_url_end=food_url_end,
            hotel_url=hotel_url,
            essentials=essentials,
            error_msg=error_msg,
            # Removed transport_budget, restaurant_budget, stay_budget
            food_pref=food_pref,
            hotel_suggestions=hotel_suggestions,
            route_restaurant_links=route_restaurant_links,
            quote=quote,
            estimated_fuel_cost=estimated_fuel_cost,
            estimated_fuel_liters=estimated_fuel_liters,
            fuel_price_per_liter=fuel_price_per_liter,
            mileage=mileage,
            fuel_type=fuel_type
        )
    else:
        return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True, port=7777)
