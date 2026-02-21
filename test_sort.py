import streamlit as st
from streamlit_sortables import sort_items

st.title("Test")
items = [
    {"header": "List", "items": ["<b>Item 1</b> - $100", "<i>Item 2</i> - $200"]}
]
res = sort_items(items)
st.write(res)
