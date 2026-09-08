# Manufacturing OEE Conversational Analytics — Script Architecture & Technical Documentation

This document provides a detailed breakdown of every script and component in the Manufacturing Overall Equipment Effectiveness (OEE) Conversational Analytics repository. It outlines the architecture, responsibilities, input/output data flows, security mechanisms, and interactions between components.

---

## 🏛️ Application Architecture Overview

The application follows a **3-Layer Architecture** integrated with Streamlit for conversational analytics and dynamic chart generation:

```text
                               ┌──────────────────────────────────────────────┐
                               │                 Streamlit UI                 │
                               │           (app.py / ui/ components)          │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ Layer 1: NLU & Structured Querying (services/cortex_analyst.py)                                       │
 │ - Parses natural language questions                                                                    │
 │ - Queries telemetry dataset (Snowflake OEE_TELEMETRY table or simulated sample)                        │
 │ - Generates SQL query, aggregated Pandas DataFrame, and executive summary text                        │
 └────────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                      │
                                                      ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ Layer 2: Dynamic Visualization Engine & Code Gen (visualization/)                                      │
 │ - Prompt Construction (`chart_prompt.py`): Builds metadata payload (dtypes, sample row)                │
 │ - Code Generation (`chart_generator.py` / `services/cortex_ai.py`): Asks Cortex AI/LLM for Plotly code │
 │ - Security Validation (`chart_validator.py`): Static AST analysis verifying safe imports & operations  │
 │ - Restricted Execution (`chart_executor.py`): Executes code in isolated namespace returning `fig`     │
 └────────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                      │
                                                      ▼
 ┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │ Layer 3: Presentation, Settings & PDF Export                                                           │
 │ - Dynamic DataFrame Metric Formatting (`ui/components.py`): Conditional green/red highlighting       │
 │ - Settings Configuration (`ui/settings_page.py`): Targets, color thresholds, logo upload, header text │
 │ - PDF Export Generator (`services/pdf_generator.py`): ReportLab export with logo, charts, and tables │
 └────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Directory Structure

```text
.
├── app.py                         # Application entry point & main Streamlit UI flow
├── config.py                      # Global configuration constants & brand definitions
├── requirements.txt               # Python package dependencies
├── README.md                      # Project overview and run instructions
├── ARCHITECTURE_AND_SCRIPTS.md   # Comprehensive technical documentation (this document)
├── assets/
│   └── just_born_logo.png         # Default company logo image
├── data/
│   ├── sample_data.py             # Telemetry dataset generator & OEE calculation helpers
│   └── semantic_model.yaml        # Cortex Analyst semantic model definition
├── services/
│   ├── snowflake_connection.py    # Environment-aware Snowflake session provider
│   ├── cortex_analyst.py          # NLU question parser & structured SQL query engine
│   ├── cortex_ai.py               # Cortex AI / LLM completion interface
│   ├── pdf_generator.py           # ReportLab PDF report generator (includes Plotly chart export)
│   └── python_validator.py        # Python code validation utilities
├── ui/
│   ├── components.py              # Shared UI elements (KPI cards, filters, DataFrame styling)
│   ├── settings_page.py           # Settings management view (targets, colors, branding)
│   └── chart_renderer.py          # Fallback Plotly chart rendering functions
├── visualization/
│   ├── __init__.py                # Package initializer
│   ├── chart_generator.py         # Visualization orchestrator
│   ├── chart_prompt.py            # Prompt construction & DataFrame metadata extraction
│   ├── chart_validator.py         # AST security validator for Python code
│   └── chart_executor.py          # Restricted Python execution engine
└── tests/
    ├── test_oee_app.py            # Core application & Cortex Analyst tests
    ├── test_settings_and_pdf.py   # Settings state & PDF report generation tests
    ├── test_dynamic_charting.py   # Dynamic chart generation & AST security tests
    └── test_snowflake_connection.py # Snowflake connection detection tests
```

---

## 📄 Detailed Script Specification

### 1. Root Application & Configuration

#### `app.py`
* **Purpose:** Primary application entry point for Streamlit.
* **Responsibilities:**
  * Configures page layout, custom CSS styling, and brand design theme.
  * Manages global `st.session_state` variables (settings, targets, metric color thresholds, header text, custom logo bytes, and chat message history).
  * Implements top-level sidebar navigation switching between **💬 Chat Assistant** and **⚙️ Settings**.
  * Executes the chat interaction loop: takes user queries, calls Cortex Analyst, invokes the dynamic chart generator, renders styled data tables, and captures history.
  * Renders the sidebar PDF export button *after* processing chat inputs to ensure the newest conversation step is included in generated exports.

#### `config.py`
* **Purpose:** Centralized configuration constants and chart type definitions.
* **Responsibilities:**
  * Defines application title (`APP_TITLE`) and icon (`APP_ICON`).
  * Specifies `SUPPORTED_CHART_TYPES` (`["line", "bar", "grouped_bar", "stacked_bar", "pie", "donut", "gauge", "scatter", "table", "kpi_card"]`).
  * Sets default target benchmarks for OEE (85%), Availability (90%), Performance (95%), and Quality (99%).

---

### 2. Data & Telemetry Services (`data/`)

#### `data/sample_data.py`
* **Purpose:** Synthetic manufacturing telemetry generator and aggregated OEE calculation engine.
* **Responsibilities:**
  * `generate_oee_dataset(num_records=1200)`: Generates a realistic telemetry DataFrame across multiple plants (e.g., Bethlehem, York, Lancaster), production lines, shifts, and product families. Computes OEE metrics:
    $$\text{OEE} = \text{Availability} \times \text{Performance} \times \text{Quality}$$
  * `calculate_aggregated_oee(df)`: Calculates weighted averages for Availability, Performance, Quality, composite OEE, total downtime hours, and unit counts across filtered subsets.

#### `data/semantic_model.yaml`
* **Purpose:** Declarative semantic model schema for Snowflake Cortex Analyst.
* **Responsibilities:**
  * Defines table definitions, logical column names, data types, aggregations, and synonyms for manufacturing terms (e.g., mapping "scrap" or "defects" to `reject_units`).

---

### 3. Core Business Services (`services/`)

#### `services/snowflake_connection.py`
* **Purpose:** Smart, environment-aware Snowflake connection management.
* **Responsibilities:**
  * `get_snowflake_session()`: Auto-detects runtime environment:
    1. **Streamlit in Snowflake (SiS):** Uses `snowflake.snowpark.context.get_active_session()`.
    2. **Local Streamlit Desktop:** Uses `st.connection("snowflake")` or `st.secrets`.
    3. **Fallback:** Returns `None` gracefully if offline, switching to simulated offline telemetry.

#### `services/cortex_analyst.py`
* **Purpose:** Natural Language Understanding (NLU) & structured data query engine.
* **Responsibilities:**
  * `process_question(question, filters)`:
    1. Parses user intent, identifying metrics (OEE, availability, downtime, quality), groupings (plant, line, shift, downtime reason), and time series keywords.
    2. Applies active sidebar filters (date range, plant, line, shift, product family).
    3. Generates SQL query string, executes aggregation on DataFrame, and constructs markdown analysis summary text.
    4. Returns a response dictionary containing `sql_query`, `data` (Pandas DataFrame), `summary_text`, and `query_type`.

#### `services/cortex_ai.py`
* **Purpose:** Interface for Snowflake Cortex AI completion functions (`SNOWFLAKE.CORTEX.COMPLETE`).
* **Responsibilities:**
  * `call_cortex_complete(prompt)`: Invokes Snowflake Cortex AI `mistral-large` model when connected to Snowflake.
  * `decide_visualization(question, analyst_response)`: Smart heuristic fallback decision engine when offline, constructing chart specifications based on data structure.

#### `services/pdf_generator.py`
* **Purpose:** Full PDF report generator powered by ReportLab.
* **Responsibilities:**
  * `generate_conversation_pdf(messages, logo_bytes, title, subtitle)`:
    * Generates a PDF report containing document header, custom logo image, title, subtitle, and current download date/timestamp.
    * Formats conversation bubbles for User and Assistant messages.
    * Converts Plotly Figure objects into high-resolution PNG images via `pio.to_image`.
    * Enforces `template="plotly_white"` and sanitizes bar trace marker fill colors to brand navy (`#242B6B`) over a solid white canvas to prevent dark/black bar rendering artifacts.
    * Renders formatted SQL queries and styled data tables as ReportLab Flowables.

#### `services/python_validator.py`
* **Purpose:** High-level code structure and safety helper functions.
* **Responsibilities:**
  * Provides supplementary code validation helpers to ensure Python code snippets adhere to safety policies.

---

### 4. Dynamic Visualization Engine (`visualization/`)

#### `visualization/chart_prompt.py`
* **Purpose:** Prompt engineering and metadata extraction for dynamic chart code generation.
* **Responsibilities:**
  * `extract_df_metadata(df)`: Extracts column names, data types, row counts, and exactly 1 sample record without hardcoded column assumptions.
  * `build_visualization_prompt(...)`: Formulates instructions for LLM code generation, enforcing Plotly Express (`px`) usage and output JSON schema.

#### `visualization/chart_validator.py`
* **Purpose:** Abstract Syntax Tree (AST) static analysis security engine.
* **Responsibilities:**
  * `validate_python_code(code_str)`: Parses code into an AST tree (`ast.parse`) and inspects every node:
    * **Allowed Modules:** `plotly`, `plotly.express`, `plotly.graph_objects`, `pandas`, `numpy`.
    * **Forbidden Imports/Calls:** Rejects `os`, `sys`, `subprocess`, `open`, `eval`, `exec`, `__import__`, `globals`, `locals`, and filesystem/network access.
    * **Variable Enforcement:** Verifies that code assigns output to `fig`.

#### `visualization/chart_executor.py`
* **Purpose:** Safe code execution in an isolated namespace.
* **Responsibilities:**
  * `execute_chart_code(code_str, df)`: Executes validated code in a restricted dictionary namespace containing only approved modules (`px`, `go`, `pd`, `np`) and a defensive copy of `df`. Returns the generated `fig` object upon success.

#### `visualization/chart_generator.py`
* **Purpose:** Main orchestrator for dynamic chart generation.
* **Responsibilities:**
  * `generate_chart(question, dataframe, ...)`: Coordinates prompt building, LLM code generation (or smart heuristic fallback), AST validation, and restricted execution. Handles edge cases (empty DataFrames or single scalar values) by skipping unnecessary charts.

---

### 5. User Interface Modules (`ui/`)

#### `ui/components.py`
* **Purpose:** Shared UI components and table formatting functions.
* **Responsibilities:**
  * `render_sidebar_filters(df)`: Multi-select sidebar filters for Date, Plant, Line, Shift, and Product Family.
  * `render_kpi_cards(kpis, targets)`: Interactive KPI summary cards showing OEE, Availability, Performance, Quality, and Downtime vs. target thresholds.
  * `render_sample_questions(callback)`: Clickable sample question buttons.
  * `style_dataframe_metrics(df, metric_colors)`: Applies pandas CSS styling to highlight metric cells (OEE, Availability, Performance, Quality) with custom pass/fail colors based on threshold settings when enabled.

#### `ui/settings_page.py`
* **Purpose:** Settings management interface view.
* **Responsibilities:**
  * `render_settings_page()`: Renders interactive configuration controls in collapsed expanders (`expanded=False`):
    1. **Target Benchmark Settings:** Numeric inputs for OEE, Availability, Performance, and Quality targets.
    2. **Metric Color Formatting:** Toggle switches, threshold inputs, and color pickers for pass/fail highlighting.
    3. **Company Logo Settings:** File uploader for custom PNG/JPG logo and reset button.
    4. **Header Banner Settings:** Text inputs for custom banner title and subtitle.
    5. **Save Settings Button:** Primary button persisting session state changes and invoking `st.rerun()`.

#### `ui/chart_renderer.py`
* **Purpose:** Fallback declarative renderer for structured chart specifications.
* **Responsibilities:**
  * `ChartRenderer.render_chart(spec, df)`: Generates line, bar, pie/donut, gauge, or scatter Plotly figures when explicit JSON chart specs are provided.

---

### 6. Automated Unit Tests (`tests/`)

* **`tests/test_oee_app.py`:** Tests dataset generation, OEE calculations, Cortex Analyst query routing, filter application, and summary text output.
* **`tests/test_settings_and_pdf.py`:** Tests settings state initializations, `style_dataframe_metrics()` threshold styling, and PDF generation with Plotly chart figures.
* **`tests/test_dynamic_charting.py`:** Tests dynamic chart planning across query types (categorical, time series, scatter), scalar skip rules, AST security validation (rejection of malicious `os.system` injections), and restricted execution.
* **`tests/test_snowflake_connection.py`:** Tests smart environment detection for Snowflake sessions across local and cloud environments.
