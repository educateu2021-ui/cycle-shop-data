import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Store Extractor to Excel", page_icon="📊", layout="wide")

st.title("📊 Store Details Extractor (HTML to Excel)")
st.markdown("Upload your `.txt` or `.html` file containing the code to extract **Name**, **Address**, **Google Map Link**, and **Contact Number** into Excel.")

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

html_data = ""
if uploaded_file is not None:
    html_data = uploaded_file.read().decode("utf-8", errors="ignore")
elif pasted_html.strip():
    html_data = pasted_html

if html_data:
    results = extract_stores(html_data)

    if results:
        df = pd.DataFrame(results)
        st.success(f"Successfully extracted {len(df)} store(s)!")
        st.dataframe(df, use_container_width=True)

        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Store Details")

        st.download_button(
            label="📥 Download Excel (.xlsx)",
            data=output.getvalue(),
            file_name="extracted_stores.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.warning("No store data found in the provided HTML.")
