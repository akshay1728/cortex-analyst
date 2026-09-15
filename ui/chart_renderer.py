"""Plotly Chart Renderer for Validated Chart Specifications."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import Dict, Any

class ChartRenderer:
    @staticmethod
    def render_chart(spec: Dict[str, Any], df: pd.DataFrame):
        """Render Plotly figure based on validated chart specification."""
        chart_type = spec.get("chart_type", "table")
        config = spec.get("config", {})
        title = spec.get("title", "")

        if df is None or df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data available for rendering", showarrow=False, font=dict(size=16))
            return fig

        if chart_type == "line":
            x_col = config.get("x_axis", df.columns[0])
            y_col = config.get("y_axis", df.columns[1] if len(df.columns) > 1 else df.columns[0])
            color = config.get("primary_color", "#1f77b4")

            fig = px.line(
                df,
                x=x_col,
                y=y_col,
                title=title,
                markers=True,
                line_shape="spline"
            )
            fig.update_traces(line_color=color, line_width=3)
            fig.update_layout(hovermode="x unified", margin=dict(l=20, r=20, t=50, b=20))
            return fig

        elif chart_type in ["bar", "grouped_bar", "stacked_bar"]:
            x_col = config.get("x_axis", df.columns[0])
            y_col = config.get("y_axis", df.columns[1] if len(df.columns) > 1 else df.columns[0])
            color = config.get("primary_color", "#242B6B")

            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                title=title,
                text_auto=".1f",
                color_discrete_sequence=[color]
            )
            fig.update_traces(marker_color=color, textfont_color="white")
            fig.update_layout(xaxis_title=x_col, yaxis_title=y_col, margin=dict(l=20, r=20, t=50, b=20))
            return fig

        elif chart_type in ["pie", "donut"]:
            cat_col = config.get("category_col", df.columns[0])
            val_col = config.get("value_col", df.columns[1] if len(df.columns) > 1 else df.columns[0])
            hole = 0.4 if chart_type == "donut" else 0.0

            fig = px.pie(
                df,
                names=cat_col,
                values=val_col,
                title=title,
                hole=hole,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig.update_traces(textinfo="percent+label")
            fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
            return fig

        elif chart_type == "gauge":
            val_col = config.get("value_col", df.columns[0])
            if val_col in df.columns:
                val = float(df[val_col].iloc[0]) if not df.empty else 0.0
            else:
                val = float(df.iloc[0, 0]) if not df.empty else 0.0

            target = config.get("target_value", 85.0)

            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=val,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': title, 'font': {'size': 20}},
                delta={'reference': target, 'increasing': {'color': "green"}, 'decreasing': {'color': "red"}},
                gauge={
                    'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                    'bar': {'color': "#2b5c8f"},
                    'bgcolor': "white",
                    'borderwidth': 2,
                    'bordercolor': "gray",
                    'steps': [
                        {'range': [0, 65], 'color': '#ffcccc'},
                        {'range': [65, 85], 'color': '#fff2cc'},
                        {'range': [85, 100], 'color': '#d9ead3'}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': target
                    }
                }
            ))
            fig.update_layout(margin=dict(l=30, r=30, t=60, b=30))
            return fig

        elif chart_type == "scatter":
            x_col = config.get("x_axis", df.columns[0])
            y_col = config.get("y_axis", df.columns[1] if len(df.columns) > 1 else df.columns[0])

            fig = px.scatter(
                df,
                x=x_col,
                y=y_col,
                title=title,
                size_max=15
            )
            fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))
            return fig

        else:
            # Table or generic view handled directly in UI
            return None
