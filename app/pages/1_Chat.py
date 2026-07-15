import httpx
import streamlit as st
from components.chat_message import (
    render_assistant_message,
    render_user_message,
)

st.set_page_config(page_title="Chat - Pliris BA Bot", page_icon="💬", layout="wide")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

# Page header
st.markdown("# 💬 Chat with your Documents")
st.markdown(
    "Ask questions about your business documents and get AI-powered answers with citations."
)

# Chat interface
for message in st.session_state.messages:
    if message["role"] == "user":
        render_user_message(message["content"])
    elif message["role"] == "assistant":
        render_assistant_message(
            message["content"],
            citations=message.get("citations"),
            confidence=message.get("confidence"),
        )

# Chat input
if prompt := st.chat_input("Ask a question about your documents..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    render_user_message(prompt)

    # Get response from API
    with st.spinner("Searching and generating response..."):
        try:

            async def get_response():
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "http://localhost:8000/api/chat",
                        json={
                            "message": prompt,
                            "conversation_id": st.session_state.conversation_id,
                        },
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    return response.json()

            # For simplicity in Streamlit, we'll use sync request
            with httpx.Client() as client:
                api_response = client.post(
                    "http://localhost:8000/api/chat",
                    json={"message": prompt, "conversation_id": st.session_state.conversation_id},
                    timeout=60.0,
                )
                api_response.raise_for_status()
                data = api_response.json()

            # Update conversation ID
            st.session_state.conversation_id = data.get("conversation_id")

            # Add assistant response to chat history
            assistant_message = {
                "role": "assistant",
                "content": data.get("response", ""),
                "citations": data.get("citations", []),
                "confidence": data.get("confidence", 0.0),
            }
            st.session_state.messages.append(assistant_message)

            # Render assistant response
            render_assistant_message(
                assistant_message["content"],
                citations=assistant_message["citations"],
                confidence=assistant_message["confidence"],
            )

        except httpx.HTTPError as e:
            st.error(f"Error communicating with API: {e}")
        except Exception as e:
            st.error(f"An error occurred: {e}")

# Clear conversation button
if st.button("Clear Conversation"):
    st.session_state.messages = []
    st.session_state.conversation_id = None
    st.rerun()
