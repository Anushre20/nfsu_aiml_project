import streamlit as st
from agent import run_agent

st.set_page_config(
    page_title="ReAct Agent",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 ReAct AI Agent")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages
for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):

        st.markdown(msg["content"])

        if msg["role"] == "assistant" and "steps" in msg:

            with st.expander("View Agent Reasoning"):

                for i, step in enumerate(msg["steps"], start=1):

                    st.markdown(f"### Step {i}")

                    st.markdown("#### Thought")
                    st.write(step["thought"])

                    st.markdown("#### Action")
                    st.code(step["action"])

                    st.markdown("#### Action Input")
                    st.code(step["action_input"])

                    st.markdown("#### Observation")
                    st.code(step["observation"])

                    st.divider()

# Chat input
prompt = st.chat_input("Ask something...")

if prompt:

    # Store and display user message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": prompt
        }
    )

    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate assistant response
    with st.chat_message("assistant"):

        thinking = st.empty()
        thinking.info("Agent is thinking...")

        result = run_agent(prompt)

        thinking.empty()

        # Handle both dict and string returns
        if isinstance(result, dict):

            answer = result["final_answer"]
            steps = result["steps"]

            st.markdown(answer)

            with st.expander("View Agent Reasoning"):

                for i, step in enumerate(steps, start=1):

                    st.markdown(f"### Step {i}")

                    st.markdown("#### Thought")
                    st.write(step["thought"])

                    st.markdown("#### Action")
                    st.code(step["action"])

                    st.markdown("#### Action Input")
                    st.code(step["action_input"])

                    st.markdown("#### Observation")
                    st.code(step["observation"])

                    st.divider()

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "steps": steps
                }
            )

        else:
            # Fallback if run_agent still returns only a string
            st.markdown(result)

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result
                }
            )