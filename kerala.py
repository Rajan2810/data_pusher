import streamlit as st
import socket
import requests
from datetime import datetime
import pytz
import pandas as pd
import re

# ===== Session State Initialization for Logging and Authentication =====
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'errors' not in st.session_state:
    st.session_state.errors = []
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# ===== Helper Functions =====
def check_credentials(username, password):
    # Modify these credentials as needed.
    return username == "admin" and password == "Sangwan@2002"

def log_activity(action, status, details):
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    st.session_state.logs.append({
        "Timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
        "Action": action,
        "Status": status,
        "Details": details
    })

def log_error(action, error_message):
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    st.session_state.errors.append({
        "Timestamp": now.strftime('%Y-%m-%d %H:%M:%S'),
        "Action": action,
        "Error": error_message
    })

def compute_nmea_checksum(data: str) -> str:
    """Compute the NMEA checksum by XORing all characters in the data string."""
    chksum = 0
    for char in data:
        chksum ^= ord(char)
    return format(chksum, '02X')

# ===== TCP Packet Builder Functions =====
def build_packet_type1(imei, lat, lon):
    """
    Packet 1 Format:
    $EPB,EMR,<IMEI>,NM,<DATE><TIME>,A,<LAT>,N,<LON>,E,0060,000.00,00.000,G,VRN_TMP22,0000000000*XX
    """
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    date_str = now.strftime('%d%m%Y')  # ddmmyyyy
    time_str = now.strftime('%H%M%S')   # hhmmss
    data = f"EPB,EMR,{imei},NM,{date_str}{time_str},A,{lat},N,{lon},E,0060,000.00,00.000,G,VRN_TMP22,0000000000"
    checksum = compute_nmea_checksum(data)
    return f"${data}*{checksum}"

def build_packet_type2(imei, lat, lon):
    """
    Packet 2 Format:
    $PVT,LIT1,AIS01.0,EA,11,L,<IMEI>,VRN_TMP22,1,<DATE>,<TIME>,<LAT>,N,<LON>,E,000.00,50,23,44,
    0.42,0.79,airtel,1,1,26.5,3.8,0,C,26,405,55,0233,34AE55,39295,323,31,39295,55,27,
    3676,451,25,0,0,0,0001,01,000035,14*XX
    """
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    date_str = now.strftime('%d%m%Y')
    time_str = now.strftime('%H%M%S')
    data = (f"PVT,LIT1,AIS01.0,EA,11,L,{imei},VRN_TMP22,1,{date_str},{time_str},{lat},N,{lon},E,"
            "000.00,50,23,44,0.42,0.79,airtel,1,1,26.5,3.8,0,C,26,405,55,0233,34AE55,39295,323,"
            "31,39295,55,27,3676,451,25,0,0,0,0001,01,000035,14")
    checksum = compute_nmea_checksum(data)
    return f"${data}*{checksum}"

def build_packet_type3(imei, lat, lon):
    """
    Packet 3 Format:
    $EPB,SEM,<IMEI>,NM,<DATE><TIME>,A,<LAT>,N,<LON>,E,0060,000.00,00.000,G,VRN_TMP22,0000000000*XX
    """
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    date_str = now.strftime('%d%m%Y')
    time_str = now.strftime('%H%M%S')
    data = f"EPB,SEM,{imei},NM,{date_str}{time_str},A,{lat},N,{lon},E,0060,000.00,00.000,G,VRN_TMP22,0000000000"
    checksum = compute_nmea_checksum(data)
    return f"${data}*{checksum}"

# ===== HTTP Packet Builder =====
def build_http_packet(imei, latitude, longitude):
    """Build an HTTP packet using current date/time."""
    now = datetime.now(pytz.timezone('Asia/Kolkata'))
    date_str = now.strftime('%d%m%Y')
    time_str = now.strftime('%H%M%S')
    return (f"NRM{imei}01L1{date_str}{time_str}0{latitude}N0{longitude}E404x950D2900"
            "DC06A72000.00000.0053001811M0827.00airtel")

# ===== Communication Functions =====
def send_tcp_packet(ip, port, packet):
    """Send a TCP packet using the socket module."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
            tcp_socket.connect((ip, port))
            tcp_socket.sendall(packet.encode('utf-8'))
        return f"✅ TCP packet sent successfully!"
    except Exception as e:
        return f"❌ Error sending TCP packet: {e}"

def send_http_data(api_url, data):
    """Send data via HTTP POST request."""
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        response = requests.post(api_url, data=data, headers=headers)
        response.raise_for_status()
        try:
            response_json = response.json()
            return f"✅ HTTP data sent successfully!", response_json
        except ValueError:
            return f"✅ HTTP data sent successfully!", response.text
    except requests.exceptions.RequestException as e:
        return f"❌ HTTP request failed: {e}", None

def extract_data_from_format(data_format):
    """Extract IMEI, latitude, and longitude from a provided format string.
       Markers: '#<15-digit IMEI>#' and '#<lat>,N,' and ',N,<lon>,E,'"""
    try:
        imei = re.search(r'#(\d{15})#', data_format).group(1)
        lat = re.search(r'#(\d+\.\d+),N,', data_format).group(1)
        lon = re.search(r',N,(\d+\.\d+),E,', data_format).group(1)
        lat = f"{float(lat):09.6f}"
        lon = f"{float(lon):09.6f}"
        return imei, lat, lon
    except AttributeError:
        st.error('Invalid format. Please ensure the markers are correctly placed.')
        log_error("Extract Data", "Invalid format provided")
        return None, None, None

# ===== Endpoint Mappings (Hidden from the user) =====
# TCP endpoints for various states
tcp_endpoints = {
    "Chhattisgarh": {"ip": "164.100.64.209", "port": 6004},
    "Bihar": {"ip": "164.100.64.230", "port": 9031},
    "Uttarakhand": {"ip": "103.116.27.26", "port": 9999},
    "Chandigarh": {"ip": "164.100.64.250", "port": 9031},
    "Maharashtra": {"ip": "103.91.244.23", "port": 4030},
    "Jammu": {"ip": "164.52.220.32", "port": 2049},
    "maharashtra_mining":{"ip":"43.205.159.137", "port":20006},
    "MP":{"ip":"164.52.211.243","port":8123},
    "Goa_Emergency":{"ip":"164.100.64.247","port":9032},
    "Goa_Primary":{"ip":"164.100.64.226","port":9031}
}

# HTTP endpoints for manual data sender (for Kerala and West Bengal)
http_endpoints = {
    "Kerala": "http://103.135.130.119:80",
    "West Bengal": "http://117.221.20.174:80?vltdata",
}

# ===== Main App =====
st.title("Complete Packet Sender Dashboard")

# ---------- Authentication ----------
if not st.session_state.logged_in:
    st.subheader("Please Login")
    username = st.text_input('Username', key="login_username")
    password = st.text_input('Password', type='password', key="login_password")
    if st.button('Login', key="login_button"):
        if check_credentials(username, password):
            st.session_state.logged_in = True
            st.success('Login successful!')
            log_activity("Login", "Success", f"User {username} logged in.")
        else:
            st.error('Invalid credentials')
            log_activity("Login", "Failed", f"Invalid login attempt for {username}.")
    st.stop()

# ---------- Tabs for Functionality ----------
tab_tcp, tab_http, tab_logs = st.tabs(["TCP Packet Sender", "HTTP Manual Data Sender", "Activity Logs"])

# --- Tab 1: TCP Packet Sender ---
with tab_tcp:
    st.header("TCP Packet Sender (Endpoints Hidden)")
    state_tcp = st.selectbox("Select State (TCP)", list(tcp_endpoints.keys()), key="tcp_state")
    packet_type = st.selectbox("Select Packet Type", ["Packet 1", "Packet 2", "Packet 3"], key="tcp_packet_type")
    
    # Input fields for parameters with unique keys
    imei = st.text_input("IMEI (15 digits)", value="864568069779867", max_chars=15, key="tcp_imei")
    lat = st.text_input("Latitude", value="21.258842", key="tcp_lat")
    lon = st.text_input("Longitude", value="81.559883", key="tcp_lon")
    
    if st.button("Send TCP Packet", key="tcp_send"):
        if len(imei) != 15 or not imei.isdigit():
            st.error("IMEI must be a 15-digit number.")
            log_error("TCP Packet Sender", f"Invalid IMEI: {imei}")
        else:
            # Build the selected packet using current date/time
            if packet_type == "Packet 1":
                packet = build_packet_type1(imei, lat, lon)
            elif packet_type == "Packet 2":
                packet = build_packet_type2(imei, lat, lon)
            elif packet_type == "Packet 3":
                packet = build_packet_type3(imei, lat, lon)
            else:
                packet = ""
            
            endpoint = tcp_endpoints[state_tcp]
            result = send_tcp_packet(endpoint["ip"], endpoint["port"], packet)
            if "✅" in result:
                st.success(result)
                log_activity("TCP Packet Sender", "Success", f"State: {state_tcp}, Type: {packet_type}")
            else:
                st.error(result)
                log_error("TCP Packet Sender", result)

# --- Tab 2: HTTP Manual Data Sender ---
with tab_http:
    st.header("HTTP Manual Data Sender")
    state_http = st.selectbox("Select State (HTTP)", list(http_endpoints.keys()), key="http_state")
    api_url = http_endpoints[state_http]
    st.write(f"Using API endpoint for {state_http}.")
    
    input_method = st.selectbox("Input Method", ["Manual Entry", "Extract from Format"], key="http_input_method")
    
    if input_method == "Manual Entry":
        imei_list = st.text_area("IMEIs (comma-separated, each 15 digits)", key="http_imei_list")
        latitude = st.text_input("Latitude", value="21.258842", key="http_lat")
        longitude = st.text_input("Longitude", value="81.559883", key="http_lon")
    else:
        data_format = st.text_area("Data Format (include markers: '#<15-digit IMEI>#', '#<lat>,N,' and ',N,<lon>,E,')", key="http_data_format")
    
    if st.button("Send HTTP Data", key="http_send"):
        if input_method == "Extract from Format":
            imei_http, latitude, longitude = extract_data_from_format(data_format)
            if not imei_http or not latitude or not longitude:
                st.error("Failed to extract data from format.")
                log_activity("HTTP Data Sender", "Failed", "Extraction error")
                st.stop()
            imei_list = imei_http  # Extraction mode: single IMEI
        else:
            imei_list = [x.strip() for x in imei_list.split(",") if x.strip()]
        
        for imei in (imei_list if isinstance(imei_list, list) else [imei_list]):
            if len(imei) != 15 or not imei.isdigit():
                st.error(f"IMEI must be a 15-digit number: {imei}")
                log_activity("HTTP Data Sender", "Failed", f"Invalid IMEI: {imei}")
                continue
            packet_http = build_http_packet(imei, latitude, longitude)
            data_payload = {'vltdata': packet_http}
            result_http, response_content = send_http_data(api_url, data_payload)
            if "✅" in result_http:
                st.success(f"{result_http} for IMEI: {imei}")
                st.write(f"Packet Sent: {packet_http}")
                log_activity("HTTP Data Sender", "Success", f"IMEI: {imei}, Packet: {packet_http}")
                if response_content:
                    if isinstance(response_content, dict):
                        st.json(response_content)
                    else:
                        st.write(response_content)
            else:
                st.error(f"HTTP data send failed for IMEI: {imei}")
                log_error("HTTP Data Sender", f"IMEI: {imei}, Error: {result_http}")

# --- Tab 3: Activity & Error Logs ---
with tab_logs:
    st.header("Activity & Error Logs")
    if st.session_state.logs:
        df_logs = pd.DataFrame(st.session_state.logs)
        st.subheader("Activity Logs")
        st.dataframe(df_logs)
        csv_logs = df_logs.to_csv(index=False).encode('utf-8')
        st.download_button("Download Activity Logs (CSV)", data=csv_logs, file_name='activity_logs.csv', mime='text/csv')
        text_logs = df_logs.to_string(index=False)
        st.download_button("Download Activity Logs (Text)", data=text_logs, file_name='activity_logs.txt', mime='text/plain')
    else:
        st.info("No activity logs yet.")
        
    if st.session_state.errors:
        df_errors = pd.DataFrame(st.session_state.errors)
        st.subheader("Error Logs")
        st.dataframe(df_errors)
        csv_errors = df_errors.to_csv(index=False).encode('utf-8')
        st.download_button("Download Error Logs (CSV)", data=csv_errors, file_name='error_logs.csv', mime='text/csv')
        text_errors = df_errors.to_string(index=False)
        st.download_button("Download Error Logs (Text)", data=text_errors, file_name='error_logs.txt', mime='text/plain')
    else:
        st.info("No error logs yet.")
