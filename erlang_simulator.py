import streamlit as st

st.title("Contact Center Erlang Simulation")

st.sidebar.header("Simulation Parameters")
num_agents = st.sidebar.slider("Number of Agents", 1, 200, 50)
call_volume = st.sidebar.number_input("Hourly Call Volume", min_value=1, value=300)
aht = st.sidebar.number_input("Average Handling Time (seconds)", min_value=1, value=180)

st.write(f"**Number of Agents:** {num_agents}")
st.write(f"**Hourly Call Volume:** {call_volume}")
st.write(f"**Average Handling Time:** {aht} seconds")
