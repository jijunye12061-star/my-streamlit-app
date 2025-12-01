import streamlit as st
import pandas as pd

st.title("🎉 Hello Streamlit!")
st.write("这是我的第一个 Streamlit 应用")

name = st.text_input("请输入你的名字")
if name:
    st.write(f"你好，{name}！")

if st.button("点我"):
    st.balloons()
