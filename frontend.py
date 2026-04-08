import streamlit as st
import requests
import pandas as pd
import json

# Setup the page configuration
st.set_page_config(page_title="Clinic AI Assistant", page_icon="🏥", layout="centered")
st.title("🏥 Clinic AI Database Assistant")
st.write("Ask me anything about patients, doctors, or revenue!")

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # If there's a SQL query saved in the history, display it
        if "sql" in message and message["sql"]:
            st.code(message["sql"], language="sql")
        
        # If there's data, display it as a table
        if "df" in message and not message["df"].empty:
            st.dataframe(message["df"])
            
        # If there's a chart, display it
        if "chart" in message and message["chart"]:
            # Streamlit handles Plotly JSON specs natively
            st.plotly_chart(json.loads(message["chart"]), use_container_width=True)

# Accept user input
if prompt := st.chat_input("e.g., How many patients do we have?"):
    
    # 1. Add user message to chat history and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Add assistant response
    with st.chat_message("assistant"):
        with st.spinner("Analyzing database..."):
            try:
                # Send the prompt to your FastAPI server
                response = requests.post(
                    "http://localhost:8000/chat",
                    json={"question": prompt}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "error" in data:
                        st.error(f"Error: {data['error']} \n\n Details: {data.get('details', '')}")
                    else:
                        # Display Text Message
                        st.markdown(data["message"])
                        
                        # Display SQL
                        if data.get("sql_query"):
                            st.code(data["sql_query"], language="sql")
                        
                        # Build and Display DataFrame
                        df = pd.DataFrame()
                        if data.get("rows"):
                            df = pd.DataFrame(data["rows"], columns=data["columns"])
                            st.dataframe(df)
                        
                        # Display Chart
                        chart_data = data.get("chart")
                        if chart_data:
                            # Parse the JSON string from the API into a dictionary for Streamlit
                            st.plotly_chart(json.loads(chart_data), use_container_width=True)

                        # Save the assistant's full response to history
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": data["message"],
                            "sql": data.get("sql_query"),
                            "df": df,
                            "chart": chart_data
                        })
                else:
                    st.error(f"Backend returned status code: {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ Could not connect to the FastAPI server. Please ensure `python main.py` is running in another terminal.")