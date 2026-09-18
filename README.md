# Manufacturing OEE Conversational Analytics Application

A enterprise-grade Streamlit application for **Manufacturing OEE (Overall Equipment Effectiveness) Conversational Analytics**, powered by **Snowflake Cortex Agent REST API**, Snowflake Semantic Views, and database-backed application management.

---

## 🏗️ Application Architecture & Data Flow

```text
User Question / Suggested Chip Click
               │
               ▼
   Sidebar Navigation & Admin Verification
    (check_is_admin() via SP_TRAKSYS_IS_ADMIN)
               │
               ▼
   Snowflake Cortex Agent REST API
    (POST /api/v2/cortex/agent:run SSE Stream)
               │
               ├──► Live Status Progress Updates ("🧠 Analyzing...", "⚡ Executing SQL...", "📊 Rendering chart...")
               │
               ▼
   SSE Event Collector & Delta Stream Processor
    (collect_response() in services/cortex_agent.py)
               │
               ├───────────────────────────────┬───────────────────────────────┐
               │                               │                               │
               ▼                               ▼                               ▼
    Answer Text & Badges             Vega-Lite Chart Spec             Executed SQL & Data Table
  (format_oee_markdown())         (st.vega_lite_chart())         (Collapsible Expander Blocks)
               │                               │                               │
               └───────────────────────────────┴───────────────────────────────┘
                                               │
                                               ▼
                                  Streamlit Chat Interface
                                               │
                                               ▼
                              PDF Report Conversation Export
                             (services/pdf_generator.py)
```

---

## 💡 Key Features

### 1. 🤖 Conversational OEE Analytics via Cortex Agent
- **REST SSE Streaming Integration**: Communicates directly with Snowflake's `/api/v2/cortex/agent:run` REST endpoint using native OAuth tokens mounted in Snowflake Container Runtime (`/snowflake/session/token`) or active Snowpark session contexts.
- **Live Status Feedback**: Displays dynamic real-time progress indicators (*🧠 Analyzing question...*, *🛠️ Formulating SQL query...*, *⚡ Executing query on Snowflake...*, *✍️ Synthesizing insights...*) that automatically disappear before rendering final answer blocks.
- **Sanitized Response Formatting**:
  - Automatically cleans mojibake encoding artifacts (`Ã—` $\rightarrow$ `×`).
  - Formats section headers with relevant emoji icons (`oee-section-header`).
  - Highlights percentage metrics in clean neutral badge spans (`oee-badge-value`).
  - Deduplicates repetitive assistant response paragraphs.

### 2. 📊 Plant Performance KPI Strip
- **Database View Driven**: Queries `{DB}.{ANALYTICS_SCHEMA}.VW_OEE_KPI_CARDS` via active Snowflake session.
- **Period-over-Period Comparison**: Displays current period metrics (OEE, Availability, Performance, Quality, Downtime Hours) compared against previous period values.
- **Date Badges & Custom Delta Chips**:
  - Renders explicit comparison dates (`latest_date` vs. `previous_date`).
  - Displays direction arrows and delta chips (`up`, `down`, or `no change`).
  - Applies **inverse delta coloring** to Downtime Hours (downtime increases rendered in red).
  - Displays neutral text (`delta_color="off"`) without direction arrows when metric changes are zero (`abs(diff) < 0.05`).

### 3. ⚙️ Database-Backed Settings & Admin Management
- **Admin Privilege Access Control**: Access to the `⚙️ Settings` page is restricted strictly to active administrators verified via stored procedure `{DB}.{APP_SCHEMA}.SP_TRAKSYS_IS_ADMIN`.
- **Tabbed Settings Page (`ui/settings_page.py`)**:
  - **💡 Suggested Questions**: Add, edit question text, change display order, or soft-delete sample question chips shown at the top of the chat assistant.
  - **🖼️ Logo Management**: Upload custom PNG/JPG logo images saved directly into Snowflake DB as binary blobs (`BINARY` data type).
  - **⚙️ Connection & Agent**: Configure Semantic View Name, Warehouse Name, Cortex Analyst Tool Name, Orchestration Model Name, Historical Response Context Count, and PDF Export Filename Template.
  - **🏷️ Header & Banner**: Customize the hero banner title and subtitle displayed at the top of the main page.
  - **👥 Admin Users**: Add new admin usernames, toggle active/inactive privileges, or remove administrator records.
- **Flash Messages**: Uses session state flash messaging (`_flash()`) to render success or warning banners cleanly across Streamlit script reruns.

### 4. 📄 Conversation PDF Export
- **Custom Branding**: Exports the full conversation thread to a PDF report featuring company logo, custom banner title, subtitle, and download timestamp.
- **Rich Elements**: Renders markdown formatted text, executed SQL code blocks, high-resolution chart images, and structured data tables using ReportLab.
- **Dynamic Date Filenames**: Auto-replaces placeholders in settings templates (e.g., `OEE_Conversation_Report_{YYYYMMDD}.pdf` $\rightarrow$ `OEE_Conversation_Report_20260301.pdf`).

### 5. 📉 Interactive Vega-Lite Charting
- **Self-Contained Spec Rendering**: Renders chart specifications returned by Cortex Agent using `st.vega_lite_chart()` with multi-color categorical palettes and mouseover pop-out hover animations.
- **Time-Series Continuous Line Safeguards**: Automatically detects date/time temporal fields and prevents them from being assigned as nominal color fields on line/area charts, eliminating timestamp epoch legends and broken line charts.

---

## 🐍 Detailed Python Module & File Breakdown

### 1. `app.py` (Main Application Entry Point & Router)
- **Role**: Coordinates session state, page configuration, custom CSS injection, sidebar navigation, user authentication checks, and layout orchestration.
- **Key Functions & Responsibilities**:
  - Sets up global Streamlit configuration (`st.set_page_config`) and applies enterprise brand styles (`BRAND` CSS theme).
  - Initializes database settings, custom branding logo, and suggested questions from Snowflake stored procedures on startup.
  - Verifies whether the logged-in user has active admin privileges via `check_is_admin()` and conditionally displays the `⚙️ Settings` navigation radio button.
  - Loads Plant Performance Overview KPI metrics from Snowflake view `{DB}.{ANALYTICS_SCHEMA}.VW_OEE_KPI_CARDS` and passes them to `render_kpi_cards()`.
  - Manages chat prompt state (`st.chat_input`, button callbacks via `on_click=set_pending_question`), auto-scrolls to the conversation section when queries run, and invokes `call_agent()` and `collect_response()` with live progress callbacks.
  - Renders sidebar export options for downloading full conversation reports as styled PDFs.

---

### 2. `config.py` (Application Configuration Constants)
- **Role**: Centralizes database parameters, schema names, chart type lists, and supported metric definitions.
- **Key Variables**:
  - `APP_TITLE`, `APP_ICON`: UI branding defaults.
  - `DB`, `APP_SCHEMA`, `TRACKSYS_SCHEMA`, `ANALYTICS_SCHEMA`: Environmental schema names (`JBEDW_DEV`, `APPS`, `STAGE_TRAKSYS`, `ANALYTICS_OPERATIONS`) directly exported for stored procedure call formatting `{DB}.{APP_SCHEMA}.SP_TRAKSYS_*`.
  - `SUPPORTED_CHART_TYPES`: Allowed chart types (`line`, `bar`, `grouped_bar`, `stacked_bar`, `pie`, `donut`, `gauge`, `scatter`, `heatmap`, `table`).
  - `METRICS`: Dictionary mapping OEE metric keys (`oee`, `availability`, `performance`, `quality`, `downtime_hours`) to display labels.

---

### 3. `services/cortex_agent.py` (Cortex Agent Integration & SSE Stream Handler)
- **Role**: Handles REST API communication with Snowflake Cortex Agent, SSE event streaming, message text formatting, and Vega-Lite chart rendering.
- **Key Functions & Responsibilities**:
  - `get_agent_auth_config()`: Resolves Snowflake host and OAuth tokens mounted in Snowflake Container Runtime (`/snowflake/session/token`) or active Snowpark connections.
  - `call_agent(messages)`: Constructs payload JSON with orchestration model (`claude-sonnet-4-5`), semantic view resource, warehouse, and tools (`cortex_analyst_text_to_sql`, `sql_exec`, `data_to_chart`). Sends `POST` requests to `https://{host}/api/v2/cortex/agent:run` with SSE streaming (`stream=True`). Truncates chat history based on setting `history_count` to ensure context windows always begin cleanly with a `user` message.
  - `collect_response(events, status_callback)`: Processes SSE streaming events. Invokes `status_callback` with user progress updates (*🧠 Analyzing question...*, *🛠️ Formulating SQL query...*, *⚡ Executing query on Snowflake...*, *✍️ Synthesizing insights...*). Filters out internal agent scratchpad reasoning/thinking events (`response.thinking`). Extracts answer deltas (`response.text.delta`), queried tool result DataFrames (`response.table`), chart specs (`response.chart`), and follow-up queries (`response.suggested_queries`).
  - `format_oee_markdown(text)`: Converts standalone section titles into styled headers with emoji icons (`oee-section-header`) and wraps percentage values in neutral badge spans (`oee-badge-value`).
  - `clean_encoding_artifacts(text)`: Replaces mojibake encoding glitches (`Ã—` $\rightarrow$ `×`, `â` $\rightarrow$ `–`).
  - `deduplicate_paragraphs(text)`: Removes duplicate repeated paragraphs from assistant outputs.
  - `render_chart(spec_or_fig, df, key)`: Formats and displays Vega-Lite JSON specs via `st.vega_lite_chart()`. Enforces multi-color categorical scale ranges (`#242B6B`, `#E15241`, `#A63A96`, `#E0A438`), donut inner radius formatting (`innerRadius=55`), hover selection parameters, and safeguards time-series line charts against nominal color field assignments.

---

### 4. `services/settings_service.py` (Database Settings & Admin Persistence)
- **Role**: Executes stored procedures on Snowflake database to manage application parameters, suggested questions, and admin users.
- **Key Functions & Responsibilities**:
  - `check_is_admin(username)`: Invokes `{DB}.{APP_SCHEMA}.SP_TRAKSYS_IS_ADMIN(username)` to verify if the active user possesses active admin rights.
  - `load_admin_users_from_db()`, `save_admin_user_to_db(username, is_active)`, `delete_admin_user_from_db(username)`: Invokes admin stored procedures (`SP_TRAKSYS_GET_ADMIN_USERS`, `SP_TRAKSYS_SAVE_ADMIN_USER`, `SP_TRAKSYS_DELETE_ADMIN_USER`).
  - `load_app_settings_from_db()`, `save_app_setting_to_db(key, val)`: Manages configuration key-value strings stored in `REF_TRAKSYS_SETTINGS` via `SP_TRAKSYS_GET_APP_SETTINGS` and `SP_TRAKSYS_SAVE_APP_SETTING`.
  - `save_app_logo_to_db(logo_bytes)`: Converts binary image bytes to hexadecimal strings and persists them as native Snowflake `BINARY` blobs via `SP_TRAKSYS_SAVE_APP_SETTING_BLOB`.
  - `load_suggested_questions_from_db()`, `save_suggested_question_to_db(q_id, text, order)`, `delete_suggested_question_from_db(q_id)`: Manages suggested sample question chips via `SP_TRAKSYS_GET_QUESTIONS`, `SP_TRAKSYS_SAVE_QUESTION`, and `SP_TRAKSYS_DELETE_QUESTION`.
  - `_row_val()`: Provides case-insensitive column lookups for DataFrame result rows returned by Snowflake stored procedures.

---

### 5. `services/snowflake_connection.py` (Smart Snowflake Environment Detection)
- **Role**: Auto-detects Snowflake runtime environments and establishes active connections.
- **Key Functions & Responsibilities**:
  - `get_snowflake_session()`: First checks for Streamlit in Snowflake active session (`snowflake.snowpark.context.get_active_session()`). If unavailable, attempts container token detection or falls back to Snowpark session connection.
  - `get_snowflake_token()`: Reads container runtime OAuth tokens mounted at `/snowflake/session/token`.

---

### 6. `services/pdf_generator.py` (ReportLab PDF Export Engine)
- **Role**: Formats and builds downloadable PDF conversation reports.
- **Key Functions & Responsibilities**:
  - `generate_conversation_pdf(messages, logo_bytes, title, subtitle)`: Uses ReportLab `SimpleDocTemplate` and `Paragraph` flowables to build multi-page PDF documents.
  - Embeds custom company logo images, document headers, subtitle, and dynamic date timestamps.
  - Iterates through chat turns, converting markdown text to HTML, formatting SQL query blocks in code styling, converting Vega-Lite/Plotly chart specs into high-resolution PNG images via PIL/Vega-Altair, and rendering data tables.

---

### 7. `ui/settings_page.py` (Tabbed Settings Management Interface)
- **Role**: Provides administrative settings controls divided across tabs.
- **Key Functions & Responsibilities**:
  - Renders tabbed interface: `💡 Suggested Questions`, `🖼️ Logo`, `⚙️ Connection & Agent`, `🏷️ Header & Banner`, and `👥 Admin Users`.
  - Uses `_flash(kind, message)` and `_render_flash()` to stash notification messages in session state across Streamlit script reruns.
  - Clears widget keys (`sq_text_in_`, `sq_order_in_`) when reloading questions from the database to force input fields to refresh with database rows.
  - Provides inputs for managing sample questions, uploading PNG/JPG logo images, modifying Cortex Agent DB parameters, setting hero banner text, and toggling active/inactive status for admin usernames.

---

### 8. `ui/components.py` (Custom UI Widgets & Styling)
- **Role**: Renders custom HTML/CSS KPI summary cards, suggested question buttons, and metric table conditional formatting.
- **Key Functions & Responsibilities**:
  - `render_kpi_cards(kpi_data, brand)`: Uses custom HTML/CSS grid layout (`_KPI_CSS`, `.kpi-strip`, `.kpi-grid`, `.kpi-cell`) to render OEE, Availability, Performance, Quality, and Downtime Hours cards. Shows comparison date subtitles (`latest_date`, `previous_date`), period progress bars, and delta chips (`up`, `down`, or `flat`). Formats Downtime Hours as rounded integers and applies inverse delta coloring for downtime increases.
  - `render_sample_questions(on_click_callback)`: Dynamically loads sample question buttons from `st.session_state.suggested_questions_list` and renders them as compact pill buttons (`use_container_width=False`) with Streamlit `on_click` callbacks.
  - `style_dataframe_metrics(df, metric_colors)`: Applies pandas CSS styling to highlight data table metric columns matching user-configured color thresholds when enabled.

---

### 9. `visualization/chart_generator.py` (Dynamic Fallback Chart Engine)
- **Role**: Generates fallback Plotly figure specifications when data DataFrames are returned without explicit Vega-Lite specs.
- **Key Functions & Responsibilities**:
  - `generate_chart(question, df)`: Inspects DataFrame column types and constructs appropriate Plotly bar, line, pie, or scatter figures formatted with brand navy color palettes (`#242B6B`).

---

## 🛢️ Database Objects & Stored Procedures

The database initialization script (`data/init_settings_db.sql`) manages settings, questions, and admin users via dedicated tables and stored procedures:

### Database Tables (`{DB}.{APP_SCHEMA}`)
1. **`REF_TRAKSYS_QUESTIONS`**: Stores suggested question text, display order, active flag, and `CREATED_BY`/`UPDATED_BY` audit tracking.
2. **`REF_TRAKSYS_SETTINGS`**: Stores key-value configuration strings and binary logo blobs (`SETTING_BLOB BINARY`).
3. **`REF_TRAKSYS_ADMIN_USERS`**: Stores admin usernames (`USERNAME VARCHAR PRIMARY KEY`), active status (`IS_ACTIVE BOOLEAN`), and audit fields.

### Stored Procedures (`{DB}.{APP_SCHEMA}`)
- `SP_TRAKSYS_GET_APP_SETTINGS()`: Returns key-value pairs and logo blob indicators.
- `SP_TRAKSYS_SAVE_APP_SETTING(P_KEY, P_VAL, P_USER)`: Merges setting string values.
- `SP_TRAKSYS_SAVE_APP_SETTING_BLOB(P_KEY, P_BLOB, P_USER)`: Merges binary image blobs.
- `SP_TRAKSYS_GET_QUESTIONS()`: Returns active suggested questions ordered by `DISPLAY_ORDER`.
- `SP_TRAKSYS_SAVE_QUESTION(P_ID, P_TEXT, P_ORDER, P_USER)`: Inserts or updates suggested questions.
- `SP_TRAKSYS_DELETE_QUESTION(P_ID, P_USER)`: Soft-deletes suggested questions.
- `SP_TRAKSYS_IS_ADMIN(P_USERNAME)`: Returns `BOOLEAN` indicating if the user has active admin privileges.
- `SP_TRAKSYS_GET_ADMIN_USERS()`: Returns all admin user records.
- `SP_TRAKSYS_SAVE_ADMIN_USER(P_USERNAME, P_ACTIVE, P_USER)`: Adds or updates admin users.
- `SP_TRAKSYS_DELETE_ADMIN_USER(P_USERNAME, P_USER)`: Removes an admin user.

---

## 🚀 How to Run the Application

Ensure dependencies are installed:

```bash
pip install -r requirements.txt
```

Launch the Streamlit application:

```bash
streamlit run app.py
```
