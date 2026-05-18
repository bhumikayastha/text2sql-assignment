import streamlit as st
from main import run_pipeline

st.set_page_config(page_title="Text-to-SQL Pipeline", layout="wide")

st.title("Text-to-SQL Pipeline")
st.markdown(
    "Use the prompt-chaining pipeline to turn natural language questions into PostgreSQL queries. "
    "The system validates, executes, and retries once if needed."
)

question = st.text_input("Enter your question:", placeholder="Example: Show all orders placed by customers in Germany")

if st.button("Run Query") and question.strip():
    with st.spinner("Generating SQL and executing query..."):
        result = run_pipeline(question)

    st.subheader("Generated SQL")
    st.code(result.get("sql", ""), language="sql")

    st.subheader("Execution Status")
    st.write({
        "Status": result.get("status"),
        "Retry needed": result.get("retry_needed"),
        "Retry success": result.get("retry_success"),
        "Row count": result.get("row_count"),
        "Error": result.get("error"),
    })

    if result.get("result"):
        st.subheader("Result Preview")
        st.dataframe(result["result"])

    st.subheader("Decomposition")
    st.json(result.get("decomposition", {}))
