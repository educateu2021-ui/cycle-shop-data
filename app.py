import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
import requests
import re
import urllib.parse

st.set_page_config(page_title="Store & Map Extractor", page_icon="📊", layout="wide")

st.title("📊 Store & Google Maps Details Extractor")
st.markdown("Upload your `.txt` or `.html` file to extract store data and enrich it with **City, District, Pincode, and Reviews** in a second Excel sheet.")

uploaded_file = st.file_uploader("Upload your code file (.txt, .html, etc.)", type=None)
pasted_html = st.text_area("Or paste HTML Code here:", height=150)

def extract_stores(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    extracted_list = []

    cards = soup.find_all("div", class_=lambda c: c and "bg-surface-muted" in c)
    if not cards:
        h3_tags = soup.find_all("h3")
        cards = [h3.parent.parent for h3 in h3_tags if h3.parent and h3.parent.parent]
    if not cards:
        cards = [soup]

    for card in cards:
        if not card:
            continue

        h3_tag = card.find("h3")
        name = h3_tag.get_text(strip=True) if h3_tag else ""

        p_tags = card.find_all("p")
        address = p_tags[0].get_text(" ", strip=True) if len(p_tags) > 0 else ""

        google_map_link = ""
        contact_number = ""

        for a_tag in card.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.startswith("tel:"):
                contact_number = href.replace("tel:", "").strip()
            elif "maps" in href or "goo.gl" in href or "Directions" in a_tag.get_text():
                google_map_link = href

        if name or address:
            extracted_list.append({
                "Name": name,
                "Address": address,
                "Google Map Link": google_map_link,
                "Contact Number": contact_number
            })

    return extracted_list


def fetch_map_details(map_url, fallback_address=""):
    city = ""
    district = ""
    pincode = ""
    reviews = "N/A"
    resolved_url = map_url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }

    lat, lon = None, None

    # 1. Follow Google Maps short link & inspect page metadata
    if map_url and map_url.startswith("http"):
        try:
            resp = requests.get(map_url, headers=headers, timeout=10, allow_redirects=True)
            resolved_url = resp.url
            page_text = resp.text

            # Try extracting coordinates from URL: @lat,lon or !3dlat!4dlon
            coord_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', resolved_url)
            if not coord_match:
                coord_match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', resolved_url)
            if coord_match:
                lat, lon = coord_match.group(1), coord_match.group(2)

            # Try extracting Reviews / Rating from meta tags or page text
            soup_map = BeautifulSoup(page_text, "html.parser")
            meta_desc = soup_map.find("meta", attrs={"name": "description"}) or soup_map.find("meta", attrs={"property": "og:description"})
            if meta_desc and meta_desc.get("content"):
                desc_content = meta_desc["content"]
                rating_match = re.search(r'(\d\.\d)\s*★.*?(\(\d+[\d,]*\)|\d+[\d,]*\s*reviews?)', desc_content, re.I)
                if rating_match:
                    reviews = rating_match.group(0)
                elif "★" in desc_content:
                    reviews = desc_content

            if reviews == "N/A":
                rev_regex = re.search(r'(\d\.\d)\s*\(\s*(\d+[\d,]*)\s*\)', page_text)
                if rev_regex:
                    reviews = f"{rev_regex.group(1)} ⭐ ({rev_regex.group(2)} reviews)"

            # Try finding 6-digit Indian Pincode in URL or meta description
            unquoted_url = urllib.parse.unquote(resolved_url)
            pin_match = re.search(r'\b([1-8]\d{5})\b', unquoted_url)
            if pin_match:
                pincode = pin_match.group(1)
        except Exception:
            pass

    # 2. If coordinates were found in the Google Map link, get exact City, District, Pincode
    if lat and lon:
        try:
            nom_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
            nom_resp = requests.get(nom_url, headers={"User-Agent": "StoreExtractorStreamlitApp/1.0"}, timeout=10)
            if nom_resp.status_code == 200:
                addr_data = nom_resp.json().get("address", {})
                city = addr_data.get("city") or addr_data.get("town") or addr_data.get("village") or addr_data.get("suburb") or ""
                district = addr_data.get("state_district") or addr_data.get("county") or ""
                if not pincode:
                    pincode = addr_data.get("postcode", "")
        except Exception:
            pass

    # 3. Fallback: Parse City/District/Pincode from the text address if still empty
    if not pincode and fallback_address:
        pin_fallback = re.search(r'\b([1-8]\d{5})\b', fallback_address)
        if pin_fallback:
            pincode = pin_fallback.group(1)

    if (not city or not district) and fallback_address:
        parts = [p.strip() for p in fallback_address.split(",") if p.strip()]
        if len(parts) >= 1 and not district:
            district = re.sub(r'\b\d{6}\b', '', parts[-1]).strip()
        if len(parts) >= 2 and not city:
            city = parts[-2].strip()
        elif not city:
            city = district

    return {
        "City": city,
        "District": district,
        "Pincode": pincode,
        "Reviews": reviews,
        "Full Map URL": resolved_url
    }


html_data = ""
if uploaded_file is not None:
    html_data = uploaded_file.read().decode("utf-8", errors="ignore")
elif pasted_html.strip():
    html_data = pasted_html

if html_data:
    base_results = extract_stores(html_data)

    if base_results:
        df_basic = pd.DataFrame(base_results)
        st.success(f"Extracted {len(df_basic)} store(s) from HTML!")
        st.subheader("Sheet 1: Store Details")
        st.dataframe(df_basic, use_container_width=True)

        # Button to check Google Map links and build Sheet 2
        if st.button("🌐 Check Google Map Links (Extract City, District, Pincode & Reviews)", type="primary"):
            enriched_rows = []
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i, row in enumerate(base_results):
                status_text.text(f"Checking link {i+1} of {len(base_results)}: {row['Name']}...")
                map_info = fetch_map_details(row["Google Map Link"], row["Address"])
                
                enriched_rows.append({
                    "Name": row["Name"],
                    "Address":
