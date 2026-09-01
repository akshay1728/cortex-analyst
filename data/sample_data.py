"""Sample Data Generator for Manufacturing OEE Analytics.

Generates realistic manufacturing telemetry and production data including:
- Date, Plant, Line, Shift, Product Family, Product Name
- Production metrics: Planned Hours, Downtime Hours, Operating Hours
- Quantity metrics: Target Units, Actual Units, Good Units, Reject Units
- OEE Components: Availability, Performance, Quality, OEE %
- Downtime reasons and categorization
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_oee_dataset(days: int = 90, seed: int = 42) -> pd.DataFrame:
    """Generate a realistic dataset for manufacturing OEE analysis."""
    np.random.seed(seed)

    plants = ["Plant Alpha (Detroit)", "Plant Beta (Austin)", "Plant Gamma (Stuttgart)"]
    plant_lines = {
        "Plant Alpha (Detroit)": ["Line 1 (Assembly)", "Line 2 (Machining)"],
        "Plant Beta (Austin)": ["Line 1 (Stamping)", "Line 2 (Electronics)"],
        "Plant Gamma (Stuttgart)": ["Line 1 (Robotics)", "Line 2 (Final Assembly)"]
    }
    shifts = ["Shift 1 (Day)", "Shift 2 (Evening)", "Shift 3 (Night)"]
    products = [
        {"family": "Electric Motors", "name": "EM-500", "target_rate": 120},
        {"family": "Electric Motors", "name": "EM-750", "target_rate": 90},
        {"family": "Power Inverters", "name": "PI-200", "target_rate": 150},
        {"family": "Power Inverters", "name": "PI-400", "target_rate": 110},
        {"family": "Battery Modules", "name": "BM-10K", "target_rate": 80},
        {"family": "Battery Modules", "name": "BM-20K", "target_rate": 60},
    ]

    downtime_reasons = [
        "Unplanned Machine Breakdown",
        "Tool Change & Setup",
        "Material Shortage",
        "Quality Hold / Inspection",
        "Operator Absence",
        "Minor Stoppage / Sensor Jam",
        "No Downtime"
    ]

    start_date = datetime.now() - timedelta(days=days)
    records = []

    for day_offset in range(days):
        current_date = (start_date + timedelta(days=day_offset)).strftime("%Y-%m-%d")

        for plant in plants:
            for line in plant_lines[plant]:
                for shift in shifts:
                    prod = products[np.random.choice(len(products))]
                    planned_hours = 8.0

                    # Plant & Line performance factor
                    if "Alpha" in plant:
                        base_avail, base_perf, base_qual = 0.88, 0.92, 0.97
                    elif "Beta" in plant:
                        base_avail, base_perf, base_qual = 0.82, 0.89, 0.95
                    else:
                        base_avail, base_perf, base_qual = 0.91, 0.94, 0.98

                    # Introduce random variation
                    avail_factor = max(0.5, min(0.99, np.random.normal(base_avail, 0.08)))
                    downtime_hours = round(planned_hours * (1.0 - avail_factor), 2)
                    operating_hours = round(planned_hours - downtime_hours, 2)

                    if downtime_hours > 0.5:
                        dt_reason = np.random.choice(downtime_reasons[:-1], p=[0.35, 0.25, 0.15, 0.15, 0.05, 0.05])
                    else:
                        dt_reason = "No Downtime"

                    target_rate = prod["target_rate"]
                    ideal_units = int(operating_hours * target_rate)

                    perf_factor = max(0.6, min(1.05, np.random.normal(base_perf, 0.06)))
                    total_units = int(ideal_units * perf_factor)

                    qual_factor = max(0.7, min(0.999, np.random.normal(base_qual, 0.03)))
                    good_units = int(total_units * qual_factor)
                    reject_units = max(0, total_units - good_units)

                    # Calculated metrics
                    actual_avail = round((operating_hours / planned_hours) * 100, 2) if planned_hours > 0 else 0
                    actual_perf = round((total_units / (operating_hours * target_rate)) * 100, 2) if (operating_hours * target_rate) > 0 else 0
                    actual_qual = round((good_units / total_units) * 100, 2) if total_units > 0 else 0
                    actual_oee = round((actual_avail * actual_perf * actual_qual) / 10000, 2)

                    records.append({
                        "date": current_date,
                        "plant": plant,
                        "line": line,
                        "shift": shift,
                        "product_family": prod["family"],
                        "product": prod["name"],
                        "planned_hours": planned_hours,
                        "downtime_hours": downtime_hours,
                        "operating_hours": operating_hours,
                        "downtime_reason": dt_reason,
                        "target_rate": target_rate,
                        "total_units": total_units,
                        "good_units": good_units,
                        "reject_units": reject_units,
                        "availability": actual_avail,
                        "performance": actual_perf,
                        "quality": actual_qual,
                        "oee": actual_oee
                    })

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df


def calculate_aggregated_oee(df: pd.DataFrame) -> dict:
    """Calculate overall OEE metrics correctly from raw aggregated telemetry."""
    if df.empty:
        return {
            "oee": 0.0,
            "availability": 0.0,
            "performance": 0.0,
            "quality": 0.0,
            "total_planned_hours": 0.0,
            "total_downtime_hours": 0.0,
            "total_operating_hours": 0.0,
            "total_units": 0,
            "good_units": 0,
            "reject_units": 0
        }

    planned_hours = df["planned_hours"].sum()
    downtime_hours = df["downtime_hours"].sum()
    operating_hours = df["operating_hours"].sum()
    total_units = df["total_units"].sum()
    good_units = df["good_units"].sum()
    reject_units = df["reject_units"].sum()

    # Calculate ideal target units for operating hours
    ideal_units = (df["operating_hours"] * df["target_rate"]).sum()

    availability = (operating_hours / planned_hours * 100) if planned_hours > 0 else 0.0
    performance = (total_units / ideal_units * 100) if ideal_units > 0 else 0.0
    quality = (good_units / total_units * 100) if total_units > 0 else 0.0
    oee = (availability * performance * quality) / 10000.0

    return {
        "oee": round(oee, 2),
        "availability": round(availability, 2),
        "performance": round(performance, 2),
        "quality": round(quality, 2),
        "total_planned_hours": round(planned_hours, 1),
        "total_downtime_hours": round(downtime_hours, 1),
        "total_operating_hours": round(operating_hours, 1),
        "total_units": int(total_units),
        "good_units": int(good_units),
        "reject_units": int(reject_units)
    }


if __name__ == "__main__":
    df = generate_oee_dataset()
    print(f"Generated {len(df)} records.")
    print("Summary Metrics:", calculate_aggregated_oee(df))
