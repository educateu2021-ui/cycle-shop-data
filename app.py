import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO

# Page setup
st.set_page_config(page_title="Store Extractor to Excel", page_icon="📊", layout="wide")

st.title("📊 Store Details Extractor (HTML to Excel)")
st.markdown(
    "Upload your file (`.txt`, `.html`, etc.) containing the HTML code to extract **Name**, **Address**, **Google Map Link**, and **Contact Number** into an **Excel (`.xlsx`)** file."
)

# 1. File Uploader (accepts .txt, .html, or any text file)
uploaded_file = st.file_uploader("📂 Upload your code file (.txt, .html, etc.)", type=None)

# 2. Optional Fallback Text Area
with st.expander("Or paste your HTML code directly here"):
    pasted_html = st.text_area("Paste HTML Code:", height=200)


def extract_stores_from_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    extracted_list = []

    # Locate each store card container
    cards = soup.find_all("div", class_=lambda c: c and "bg-surface-muted" in c)
    
    # Fallback: find all h3 tags and get their parent card if container class varies slightly
    if not cards:
        h3_tags = soup.find_all("h3")
        cards = [h3.find_parent("div", class_=lambda c: c and "flex-col" in c) or h3.parent.parent for h3 in h3_tags]

    # Final fallback if single card snippet is pasted without outer wrapper
    if not cards:
        cards = [soup]

    for card in cards:
        if not card:
            continue

        # 1. Name
        h3_tag = card.find("h3")
        name = h3_tag.get_text(strip=True) if h3_tag else ""

        # 2. Address (first <p> tag inside the card)
        p_tags = card.find_all("p")
        address = p_tags[0].get_text(" ", strip=True) if len(p_tags) > 0 else ""

        # 3. Google Map Link & 4. Contact Number
        google_map_link = ""
        contact_number = ""

        for a_tag in card.find_all("a", href=True):
            href = a_tag["href"].strip()
            if href.startswith("tel:"):
                contact_number = href.replace("tel:", "").strip()
            elif "maps" in href or "goo.gl" in href or "Directions" in a_tag.get_text():
                google_map_link = href

        # Only add valid rows that have at least a store name or address
        if name or address:
            extracted_list.append({
                "Name": name,
                "Address": address,
                "Google Map Link": google_map_link,
                "Contact Number": contact_number
            })

    return extracted_list


def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Store Details")
        
        # Auto-adjust column widths for neat Excel formatting
        worksheet = writer.sheets["Store Details"]
        for idx, col in enumerate(df.columns
