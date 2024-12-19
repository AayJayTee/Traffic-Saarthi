# Import necessary libraries
import streamlit as st
import requests
import json
import folium
from streamlit_folium import st_folium
import os
from streamlit_option_menu import option_menu
from datetime import datetime
import geocoder  
import cv2 
import numpy as np
from ultralytics import YOLO
import tempfile
from io import BytesIO

# Load the YOLO model
model = YOLO("trained_model.pt")
APIKEY = "836hjeGZtIvmzl6ywJgL7IVnDoKJGeVk"
ROUTE_DATA_FILE = 'route_data.json'
USER_DATA_FILE = 'user_data.json'

def save_route_data(source, destination, coordinates, traffic_delay, eta):
    route_data = {
        'source': source,
        'destination': destination,
        'coordinates': coordinates,
        'traffic_delay': traffic_delay,
        'eta': eta
    }
    with open(ROUTE_DATA_FILE, 'w') as f:
        json.dump(route_data, f)

def load_route_data():
    if os.path.exists(ROUTE_DATA_FILE):
        with open(ROUTE_DATA_FILE, 'r') as f:
            return json.load(f)
    return None

def save_user_data(points):
    user_data = {'points': points}
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(user_data, f)

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {'points': 0}

def predict_congestion(image):
    return "Moderate congestion detected."

def save_video_for_download(video_path):
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    return video_bytes

def display_video_in_modal(video_path):
    video_html = f"""
    <html>
    <body>
        <div id="modal" style="display:none; position:fixed; z-index:999; left:0; top:0; width:100%; height:100%; background-color:rgba(0,0,0,0.8);">
            <div style="position: relative; margin: auto; top: 50%; transform: translateY(-50%);">
                <video width="800" height="600" controls autoplay>
                    <source src="{video_path}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
                <button onclick="document.getElementById('modal').style.display='none'" style="position:absolute; top:10px; right:20px; color:white; background-color:red; border:none; padding:10px;">Close</button>
            </div>
        </div>
        <script>
            function showModal() {{
                document.getElementById('modal').style.display = 'block';
            }}
            showModal();
        </script>
    </body>
    </html>
    """
    st.components.v1.html(video_html, height=700)

# Define congestion levels based on the number of detections (adjust as needed)
def classify_congestion(num_boxes):
    if num_boxes < 5:
        return "Light Congestion"
    elif num_boxes < 15:
        return "Moderate Congestion"
    else:
        return "Dense Congestion"

# Modify the predict_congestion function to classify congestion
def predict_congestion(results):
    # Count the number of bounding boxes (detections)
    num_detections = len(results[0].boxes)
    
    # Classify the congestion level
    congestion_level = classify_congestion(num_detections)
    
    return congestion_level, num_detections

# Function to save video for download
def save_video_for_download(video_path):
    with open(video_path, "rb") as f:
        video_bytes = f.read()
    return video_bytes

# Streamlit App UI for YOLO Real Time Congestion
with st.sidebar:
    selected = option_menu("Traffic Saarthi",
                           ["Home", "Route Optimization", "Yolo Real Time Congestion"],
                           default_index=0)

if selected == "Home":
    st.title("Welcome to Traffic Saarthi")
    st.write("This webapp allows you to optimize routes and get real-time congestion predictions using YOLO V6.")
    st.write("Use the sidebar to navigate to the Route Optimization page.")
    st.image("image0_0.jpg", width=600)


elif selected == "Route Optimization":
    st.title("Route Optimization")
    saved_route = load_route_data()
    user_data = load_user_data()

    use_current_location = st.checkbox("Use current location as source")
    source = ""

    if use_current_location:
        g = geocoder.ip('me')  # Attempt to get the user's current location using their IP
        if g.ok and g.latlng:
            source_lat, source_lon = g.latlng
            # Reverse geocode to get a readable address
            reverse_geocode_url = f"https://api.tomtom.com/search/2/reverseGeocode/{source_lat},{source_lon}.json?key={APIKEY}"
            reverse_response = requests.get(reverse_geocode_url)
            reverse_data = reverse_response.json()

            if 'addresses' in reverse_data and len(reverse_data['addresses']) > 0:
                source = reverse_data['addresses'][0]['address']['freeformAddress']
            else:
                st.error("Could not find a human-readable address for the current location.")
                source = "Unknown Location"
        else:
            st.error("Could not determine current location. Please check your internet connection or try again later.")
            source_lat, source_lon = None, None
    else:
        source = st.text_input("Enter source location:", value=saved_route['source'] if saved_route else "")

    # Input for destination
    destination = st.text_input("Enter destination location:", value=saved_route['destination'] if saved_route else "")

    if st.button("Find Route"):
        if not destination:
            st.error("Please enter a destination.")
        else:
            def geocode_address(address):
                geocode_url = f"https://api.tomtom.com/search/2/geocode/{address}.json?key={APIKEY}"
                response = requests.get(geocode_url)
                data = response.json()
                if 'results' in data and len(data['results']) > 0:
                    position = data['results'][0]['position']
                    return position['lat'], position['lon']
                else:
                    st.error(f"Location not found: {address}")
                    return None, None

            # Check if using current location or user-entered source
            if use_current_location and source_lat is not None and source_lon is not None:
                # If using current location, the lat and lon are already obtained
                pass  # No need to assign again
            else:
                source_lat, source_lon = geocode_address(source)

            destination_lat, destination_lon = geocode_address(destination)

            # Ensure both lat/lon pairs are valid before requesting a route
            if source_lat is not None and destination_lat is not None:
                route_url = f"https://api.tomtom.com/routing/1/calculateRoute/{source_lat},{source_lon}:{destination_lat},{destination_lon}/json?key={APIKEY}"
                route_response = requests.get(route_url)
                route_data = route_response.json()

                if 'routes' in route_data and len(route_data['routes']) > 0:
                    route = route_data['routes'][0]['legs'][0]
                    traffic_delay = route['summary']['trafficDelayInSeconds']
                    arrival_time = route['summary']['arrivalTime']

                    try:
                        eta = datetime.fromisoformat(arrival_time[:-1]).strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        st.error("Error parsing arrival time.")
                        eta = "Unavailable"

                    coordinates = [[point['latitude'], point['longitude']] for point in route['points']]
                    m = folium.Map(location=[source_lat, source_lon], zoom_start=6)
                    folium.Marker(location=[source_lat, source_lon], popup='Source').add_to(m)
                    folium.Marker(location=[destination_lat, destination_lon], popup='Destination').add_to(m)
                    folium.PolyLine(coordinates, color='blue').add_to(m)

                    st_folium(m, width=700, height=500)
                    st.write(f"Traffic Delay: {traffic_delay} seconds")
                    st.write(f"Estimated Time of Arrival (ETA): {eta}")

                    user_data['points'] += 10
                    save_user_data(user_data['points'])
                    save_route_data(source, destination, coordinates, traffic_delay, eta)
                else:
                    st.error("No route found between the specified locations.")

    # Display previously saved route if it exists
    if saved_route:
        st.subheader("Previously Saved Route")
        st.write(f"Source: {saved_route['source']}")
        st.write(f"Destination: {saved_route['destination']}")
        st.write(f"Traffic Delay: {saved_route['traffic_delay']} seconds")

        m_saved = folium.Map(location=saved_route['coordinates'][0], zoom_start=6)
        folium.Marker(location=saved_route['coordinates'][0], popup='Source').add_to(m_saved)
        folium.Marker(location=saved_route['coordinates'][-1], popup='Destination').add_to(m_saved)
        folium.PolyLine(saved_route['coordinates'], color='blue').add_to(m_saved)

        st_folium(m_saved, width=700, height=500)

elif selected == "Yolo Real Time Congestion":
    st.title("YOLO Real-Time Congestion Prediction")

    uploaded_file = st.file_uploader("Upload a video or image for congestion prediction", type=["jpg", "jpeg", "png", "mp4"], key="congestion_uploader")
    
    if uploaded_file is not None:
        if uploaded_file.type in ["image/jpg", "image/jpeg", "image/png"]:
            # If an image is uploaded, process the image
            img = np.array(bytearray(uploaded_file.read()), dtype=np.uint8)
            img = cv2.imdecode(img, 1)
            
            # Run YOLO model on the image
            results = model.predict(img)

            # Count detections and classify congestion
            congestion_level, num_detections = predict_congestion(results)
            
            # Display the image with bounding boxes
            st.image(results[0].plot(), caption=f"{congestion_level} ({num_detections} vehicles detected)", use_container_width=True)
            st.write(f"Congestion Level: {congestion_level}")
            st.write(f"Number of Vehicles Detected: {num_detections}")

        elif uploaded_file.type == "video/mp4":
            # Save uploaded video to a temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
                tmp_file.write(uploaded_file.read())
                video_path = tmp_file.name

            st.video(video_path)  # Display original video
            st.write("Processing the video for congestion prediction...")

            if st.button("Predict Congestion", key="predict_video"):
                # Open the video file
                cap = cv2.VideoCapture(video_path)
                
                # Check if video opened successfully
                if not cap.isOpened():
                    st.error("Error opening video file.")

                # Get video properties
                frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(cap.get(cv2.CAP_PROP_FPS))

                # Create temporary output file
                output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

                # Define video writer
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))

                total_detections = 0
                frame_count = 0

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break

                    # Run YOLOv8 model on the frame
                    results = model.predict(frame)

                    # Count detections and accumulate total
                    _, num_detections = predict_congestion(results)
                    total_detections += num_detections
                    frame_count += 1

                    # Visualize results on the frame
                    annotated_frame = results[0].plot()

                    # Write the annotated frame to the output video
                    out.write(annotated_frame)

                cap.release()
                out.release()

                # Calculate average detections per frame
                avg_detections_per_frame = total_detections / frame_count if frame_count > 0 else 0
                
                # Classify congestion based on average detections per frame
                congestion_level = classify_congestion(avg_detections_per_frame)
                
                st.success(f"Video processing complete. {congestion_level} ({avg_detections_per_frame:.2f} vehicles per frame on average).")

                # Provide a download link for the processed video
                video_bytes = save_video_for_download(output_path)
                st.download_button(
                    label="Download Processed Video",
                    data=video_bytes,
                    file_name="processed_video.mp4",
                    mime="video/mp4"
                )
