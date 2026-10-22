import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO
import requests
import re
import urllib.parse

st.set_page_config(page_title="Store & Map Extractor", layout="wide")
st.title("Store & Google Maps Details Extractor")

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
        gmap, phone = "", ""

        for a_tag in card.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.startswith("tel:"):
                phone = href.replace("tel:", "").strip()
            elif "maps" in href or "goo.gl" in href or "Directions" in a_tag.get_text():
                gmap = href

        if name or address:
            row = dict(Name=name, Address=address, Google_Map_Link=gmap, Contact_Number=phone)
            extracted_list.append(row)
    return extracted_list

def fetch_map_details(map_url, fallback_address=""):
    city, district, pincode, reviews = "", "", "", "N/A"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    lat, lon = None, None

    if map_url and map_url.startswith("http"):
        try:
            resp = requests.get(map_url, headers=headers, timeout=10, allow_redirects=True)
            r_url = resp.url
            text = resp.text

            c_match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', r_url) or re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', r_url)
            if c_match:
                lat, lon = c_match.group(1), c_match.group(2)

            soup_m = BeautifulSoup(text, "html.parser")
            meta = soup_m.find("meta", attrs={"name": "description"}) or soup_m.find("meta", attrs={"property": "og:description"})
            if meta and meta.get("content"):
                desc = meta["content"]
                r_match = re.search(r'(\d\.\d)\s*★.*?(\(\d+[\d,]*\)|\d+[\d,]*\s*reviews?)', desc, re.I)
                if r_match:
                    reviews = r_match.group(0)
                elif "★" in desc:
                    reviews = desc

            if reviews == "N/A":
                rev_reg = re.search(r'(\d\.\d)\s*\(\s*(\d+[\d,]*)\s*\)', text)
                if rev_reg:
                    reviews = f"{rev_reg.group(1)} Stars ({rev_reg.group(2)} reviews)"

            p_match = re.search(r'\b([1-8]\d{5})\b', urllib.parse.unquote(r_url))
            if p_match:
                pincode = p_match.group(1)
        except Exception:
            pass

    if lat and lon:
        try:
            n_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
            n_resp = requests.get(n_url, headers={"User-Agent": "StoreApp/1.0"}, timeout=10)
            if n_resp.status_code == 200:
                addr = n_resp.json().get("address", {})
                city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("suburb") or ""
                district = addr.get("state_district") or addr.get("county") or ""
                if not pincode:
                    pincode = addr.get("postcode", "")
        except Exception:
            pass

    if not pincode and fallback_address:
        pf = re.search(r'\b([1-8]\d{5})\b', fallback_address)
        if pf:
            pincode = pf.group(1)

    if (not city or not district) and fallback_address:
        parts = [p.strip() for p in fallback_address.split(",") if p.strip()]
        if len(parts) >= 1 and not district:
            district = re.sub(r'\b\d{6}\b', '', parts[-1]).strip()
        if len(parts) >= 2 and not city:
            city = parts[-2].strip()
        elif not city:
            city = district

    return dict(City=city, District=district, Pincode=pincode, Reviews=reviews)

html_data = uploaded_file.read().decode("utf-8", errors="ignore") if uploaded_file else pasted_html.strip()

if html_data:
    base_results = extract_stores(html_data)
    if base_results:
        df_basic = pd.DataFrame(base_results)
        st.subheader("Sheet 1: Store Details")
        st.dataframe(df_basic, use_container_width=True)

        if st.button("Check Google Map Links (Extract City, District, Pincode & Reviews)", type="primary"):
            enriched_rows = []
            bar = st.progress(0)
            for i, r in enumerate(base_results):
                info = fetch_map_details(r["Google_Map_Link"], r["Address"])
                combined = dict(r, **info)
                enriched_rows.append(combined)
                bar.progress((i + 1) / len(base_results))
            st.session_state["df_enriched"] = pd.DataFrame(enriched_rows)

        if "df_enriched" in st.session_state:
            st.subheader("Sheet 2: Map Details")
            st.dataframe(st.session_state["df_enriched"], use_container_width=True)

        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            df_basic.to_excel(writer, index=False, sheet_name="Store Details")
            if "df_enriched" in st.session_state:
                st.session_state["df_enriched"].to_excel(writer, index=False, sheet_name="Map Details")

        st.download_button("Download Excel (.xlsx)", data=out.getvalue(), file_name="stores.xlsx")
# END OF FILE
