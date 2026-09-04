# Manufacturing OEE Conversational Analytics & Dynamic Visualization Engine

A Streamlit application that combines **Snowflake Cortex Analyst** (for natural-language to SQL querying and structured data extraction) with a **Dynamic Python Chart Generation & AST Security Engine**.

---

## 🏗️ Expected Architecture & Flow

```text
User Question
      │
      ▼
Cortex Analyst Service (NLU & Semantic Query Engine)
      │
      ▼
Generated SQL & DataFrame Result
      │
      ├───────────────────────────────┐
      │                               │
      ▼                               ▼
Textual Answer & Summary     Dynamic Visualization Planner
                                      │
                                      ▼
                             Generate Python Code
                                      │
                                      ▼
                             AST Security Validator
                                      │
                                      ▼
                             Restricted Execution Context
                                      │
                                      ▼
                             Plotly Figure (`fig`)
                                      │
                                      ▼
                             Streamlit Interface
```

---

## 💡 Key Features

1. **Conversational Analytics Interface**: Ask questions in plain English (e.g., *"Show OEE by production area"*, *"Show OEE trend over the last 12 months"*, *"Compare downtime and OEE"*).
2. **Cortex Analyst NLU**: Maps queries to semantic models (`data/semantic_model.yaml`), executes filters, and retrieves aggregated data.
3. **Dynamic Visualization Planner**: Analyzes questions and DataFrame schema/types (`df.columns`, `df.dtypes`, row counts, sample records) without hardcoded rules or fixed metric assumptions.
4. **AST Security Validation (`chart_validator.py`)**: Uses Abstract Syntax Tree (AST) static analysis to verify generated Python code before execution. Rejects forbidden imports (`os`, `sys`, `subprocess`, etc.) and dangerous calls (`open`, `eval`, `exec`).
5. **Restricted Execution Context (`chart_executor.py`)**: Executes validated Plotly Python code in a safe environment, assigning the final visualization to `fig`.
6. **Developer / Debug Mode**: Toggle developer mode in the Streamlit sidebar to inspect generated SQL queries, AST validation results, and generated Plotly Python code snippet.

---

## 🔒 Security Restrictions & Allowed Libraries

The dynamic code generator operates under strict AST and namespace constraints:

* **Allowed Libraries**: `plotly`, `plotly.express` (`px`), `plotly.graph_objects` (`go`), `pandas` (`pd`), `numpy` (`np`).
* **Forbidden Builtins**: `open`, `eval`, `exec`, `compile`, `__import__`, `getattr`, `setattr`, `delattr`, `globals`, `locals`.
* **Forbidden Modules**: `os`, `sys`, `subprocess`, `socket`, `requests`, `urllib`, `shutil`, `importlib`, etc.
* **Execution Boundary**: Code can only operate on a defensive copy of the provided DataFrame `df` and must assign the resulting Plotly `Figure` to `fig`.

---

## 🛠️ Developer & Debug Logging

Developers can enable developer logging in two ways:

1. **Streamlit Sidebar**: Toggle **🛠️ Developer / Debug Mode** in the Streamlit UI sidebar to display JSON metadata and generated Python code for each prompt turn.
2. **Console / File Logs**: The application logs dynamic charting events, validation statuses, and runtime errors to `dynamic_chart_generator` logger at `INFO` and `WARNING` levels.

---

## 🧪 Running Unit Tests

Run the full pytest suite covering data generation, Cortex Analyst queries, AST security rules, and dynamic chart generation:

```bash
python3 -m pytest tests/
```

### Covered Test Scenarios (`tests/test_dynamic_charting.py`):
- **Test 1**: Categorical comparison ("Show OEE by production area") -> Bar chart
- **Test 2**: Time series ("Show OEE trend for the last 12 months") -> Line chart
- **Test 3**: Relationship ("Compare downtime and OEE") -> Scatter plot
- **Test 4**: Production volume by site -> Categorical comparison chart
- **Test 5**: Scalar total question ("What is total production volume?") -> No chart required (`should_visualize: False`)
- **Test 6**: Empty DataFrame -> Clean handling without application failure
- **Test 7**: Malicious code injection (`import os; os.system(...)`) -> AST validation rejection
- **Test 8**: Non-existent column execution error -> Gracefully caught without breaking app

---

## 🚀 How to Run the Streamlit Application

```bash
streamlit run app.py
```
