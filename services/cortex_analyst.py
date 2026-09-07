"""Cortex Analyst Service for OEE Analytics.

Simulates Snowflake Cortex Analyst NLU query interface:
1. Accepts natural language user question and active filters.
2. Queries structured OEE dataset using semantic model schema.
3. Performs intelligent query parsing, aggregation, grouping, and filtering.
4. Returns structured query response containing query SQL, data summary, and Pandas DataFrame.
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, Any, List, Tuple
from data.sample_data import calculate_aggregated_oee

class CortexAnalystService:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def process_question(self, question: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Parse natural language question, apply filters, and execute query on structured dataset."""
        df_filtered = self._apply_filters(self.df, filters)
        q_lower = question.lower().strip()

        # Determine intent & grouping
        group_col, group_name = self._determine_grouping(q_lower)
        metric_col, metric_name, agg_func = self._determine_metric(q_lower)
        time_trend = self._check_time_trend(q_lower)

        # Execute query aggregation logic
        if time_trend:
            sql_query, result_df, summary_text = self._handle_time_series_query(df_filtered, metric_col, metric_name, q_lower)
            query_type = "trend"
        elif group_col:
            sql_query, result_df, summary_text = self._handle_grouped_query(df_filtered, group_col, group_name, metric_col, metric_name, agg_func)
            query_type = "breakdown"
        else:
            sql_query, result_df, summary_text = self._handle_summary_kpi_query(df_filtered, metric_col, metric_name)
            query_type = "summary"

        return {
            "question": question,
            "sql_query": sql_query,
            "data": result_df,
            "summary_text": summary_text,
            "query_type": query_type,
            "metric_col": metric_col,
            "group_col": group_col if group_col else ("date" if time_trend else None),
            "record_count": len(result_df)
        }

    def _apply_filters(self, df: pd.DataFrame, filters: Dict[str, Any] = None) -> pd.DataFrame:
        if not filters:
            return df

        filtered = df.copy()
        if filters.get("plants") and "All" not in filters["plants"]:
            filtered = filtered[filtered["plant"].isin(filters["plants"])]

        if filters.get("lines") and "All" not in filters["lines"]:
            filtered = filtered[filtered["line"].isin(filters["lines"])]

        if filters.get("shifts") and "All" not in filters["shifts"]:
            filtered = filtered[filtered["shift"].isin(filters["shifts"])]

        if filters.get("product_families") and "All" not in filters["product_families"]:
            filtered = filtered[filtered["product_family"].isin(filters["product_families"])]

        if filters.get("date_range") and len(filters["date_range"]) == 2:
            start_d, end_d = filters["date_range"]
            filtered = filtered[(filtered["date"] >= pd.to_datetime(start_d)) & (filtered["date"] <= pd.to_datetime(end_d))]

        return filtered

    def _determine_grouping(self, question: str) -> Tuple[str, str]:
        if "by plant" in question or "across plant" in question or "per plant" in question or "plant performance" in question or "which plant" in question:
            return "plant", "Plant"
        if "by line" in question or "across line" in question or "per line" in question or "which line" in question:
            return "line", "Line"
        if "by shift" in question or "across shift" in question or "per shift" in question or "which shift" in question:
            return "shift", "Shift"
        if "by product family" in question or "product family" in question or "family" in question:
            return "product_family", "Product Family"
        if "by product" in question or "per product" in question or "across product" in question or "which product" in question:
            return "product", "Product"
        if "downtime" in question or "reason" in question or "breakdown" in question or "cause" in question:
            return "downtime_reason", "Downtime Reason"
        return None, None

    def _determine_metric(self, question: str) -> Tuple[str, str, str]:
        if "availability" in question:
            return "availability", "Availability (%)", "mean"
        if "performance" in question:
            return "performance", "Performance (%)", "mean"
        if "quality" in question:
            return "quality", "Quality (%)", "mean"
        if "downtime" in question or "stop" in question or "breakdown" in question:
            return "downtime_hours", "Downtime (Hours)", "sum"
        if "reject" in question or "defect" in question or "scrap" in question:
            return "reject_units", "Defective Units", "sum"
        if "good unit" in question or "good count" in question or "good product" in question:
            return "good_units", "Good Units", "sum"
        if "total unit" in question or "volume" in question or "produced" in question:
            return "total_units", "Total Units", "sum"
        # Default OEE
        return "oee", "OEE (%)", "mean"

    def _check_time_trend(self, question: str) -> bool:
        time_keywords = ["trend", "over time", "daily", "weekly", "history", "timeline", "by date", "day by day", "month"]
        return any(kw in question for kw in time_keywords)

    def _handle_time_series_query(self, df: pd.DataFrame, metric_col: str, metric_name: str, question: str) -> Tuple[str, pd.DataFrame, str]:
        sql_query = f"SELECT DATE_TRUNC('day', date) AS date, AVG({metric_col}) AS {metric_col} FROM oee_telemetry GROUP BY 1 ORDER BY 1 ASC"

        grouped = df.groupby(df["date"].dt.strftime("%Y-%m-%d"))[metric_col].mean().reset_index()
        grouped[metric_col] = grouped[metric_col].round(2)
        grouped.rename(columns={"date": "Date", metric_col: metric_name}, inplace=True)

        if grouped.empty:
            return sql_query, grouped, "No telemetry data recorded for the selected time range."

        latest_val = grouped[metric_name].iloc[-1]
        mean_val = grouped[metric_name].mean()
        max_idx = grouped[metric_name].idxmax()
        min_idx = grouped[metric_name].idxmin()
        max_row = grouped.iloc[max_idx]
        min_row = grouped.iloc[min_idx]

        unit_str = "%" if "%" in metric_name else " units"

        summary = (
            f"### 📈 Executive Analysis: {metric_name} Trend Over Time\n\n"
            f"- **Period Average**: **{mean_val:.2f}{unit_str}** across {len(grouped)} recorded time intervals.\n"
            f"- **Peak Recorded Performance**: **{max_row[metric_name]}{unit_str}** on `{max_row['Date']}`.\n"
            f"- **Lowest Recorded Performance**: **{min_row[metric_name]}{unit_str}** on `{min_row['Date']}`.\n"
            f"- **Latest Status**: **{latest_val}{unit_str}** recorded on `{grouped['Date'].iloc[-1]}`.\n\n"
            f"**Key Finding**: The time series illustrates temporal variation in **{metric_name}**. "
            f"Investigate dip dates (e.g., `{min_row['Date']}`) for potential unmonitored equipment maintenance or unplanned line stops."
        )
        return sql_query, grouped, summary

    def _handle_grouped_query(self, df: pd.DataFrame, group_col: str, group_name: str, metric_col: str, metric_name: str, agg_func: str) -> Tuple[str, pd.DataFrame, str]:
        sql_func = "AVG" if agg_func == "mean" else "SUM"
        sql_query = f"SELECT {group_col}, {sql_func}({metric_col}) AS {metric_col} FROM oee_telemetry GROUP BY 1 ORDER BY {metric_col} DESC"

        if agg_func == "mean":
            res = df.groupby(group_col)[metric_col].mean().reset_index()
        else:
            res = df.groupby(group_col)[metric_col].sum().reset_index()

        res[metric_col] = res[metric_col].round(2)
        res = res.sort_values(by=metric_col, ascending=False)
        res.rename(columns={group_col: group_name, metric_col: metric_name}, inplace=True)

        if res.empty:
            return sql_query, res, "No data available for the requested grouping."

        top_item = res.iloc[0]
        bottom_item = res.iloc[-1]
        avg_val = res[metric_name].mean()
        unit_str = "%" if "%" in metric_name else (" hrs" if "Hours" in metric_name else " units")

        summary = (
            f"### 📊 Breakdown Analysis: {metric_name} by {group_name}\n\n"
            f"- **Top Performing Segment**: **{top_item[group_name]}** leading with **{top_item[metric_name]}{unit_str}**.\n"
            f"- **Lowest Performing Segment**: **{bottom_item[group_name]}** trailing at **{bottom_item[metric_name]}{unit_str}**.\n"
            f"- **Segment Group Average**: **{avg_val:.2f}{unit_str}** across all {len(res)} evaluated categories.\n\n"
            f"**Strategic Takeaway**: Standardize operating practices from **{top_item[group_name]}** to elevate performance across lower-performing segments like **{bottom_item[group_name]}**."
        )
        return sql_query, res, summary

    def _handle_summary_kpi_query(self, df: pd.DataFrame, metric_col: str, metric_name: str) -> Tuple[str, pd.DataFrame, str]:
        sql_query = "SELECT AVG(oee) AS oee, AVG(availability) AS availability, AVG(performance) AS performance, AVG(quality) AS quality, SUM(downtime_hours) AS downtime_hours FROM oee_telemetry"

        agg_oee = calculate_aggregated_oee(df)

        summary_df = pd.DataFrame([{
            "OEE (%)": agg_oee["oee"],
            "Availability (%)": agg_oee["availability"],
            "Performance (%)": agg_oee["performance"],
            "Quality (%)": agg_oee["quality"],
            "Total Downtime (hrs)": agg_oee["total_downtime_hours"],
            "Total Units": agg_oee["total_units"],
            "Good Units": agg_oee["good_units"],
            "Defective Units": agg_oee["reject_units"]
        }])

        summary = (
            f"### 🏭 Overall Plant OEE Performance Summary\n\n"
            f"- **Composite OEE**: **{agg_oee['oee']}%** (World Class Benchmark is 85%).\n"
            f"  - **Availability Factor**: **{agg_oee['availability']}%** (Target: 90%)\n"
            f"  - **Performance Factor**: **{agg_oee['performance']}%** (Target: 95%)\n"
            f"  - **Quality Factor**: **{agg_oee['quality']}%** (Target: 99%)\n"
            f"- **Downtime Impact**: Total cumulative equipment downtime is **{agg_oee['total_downtime_hours']} hours**.\n"
            f"- **Production Totals**: Produced **{agg_oee['good_units']:,}** good units out of **{agg_oee['total_units']:,}** total units (**{agg_oee['reject_units']:,}** scrap units).\n\n"
            f"**Operational Advice**: Focus bottleneck elimination on Availability loss due to downtime hours to boost overall site OEE."
        )
        return sql_query, summary_df, summary
