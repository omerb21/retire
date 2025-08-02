#!/usr/bin/env python
"""
Simple dashboard for fixation document generation metrics
Reads from log files and displays metrics in a web interface
"""
import re
import json
import logging
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import statistics
from typing import Dict, List, Any, Optional

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
LOG_FILE = Path("logs/app.json")
FALLBACK_ENV_VAR = "FIXATION_ALLOW_JSON_FALLBACK"

# Initialize Dash app
app = dash.Dash(__name__, title="Fixation Metrics Dashboard")


def parse_log_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a log line into a dictionary"""
    try:
        # Try parsing as JSON first
        return json.loads(line)
    except json.JSONDecodeError:
        # Fall back to regex parsing for non-JSON logs
        try:
            # Extract metrics from structured log format
            match = re.search(r'Document generation: ({.*})', line)
            if match:
                log_data = match.group(1)
                # Convert to proper JSON by replacing single quotes with double quotes
                log_data = log_data.replace("'", '"')
                return json.loads(log_data)
        except Exception:
            pass
    
    return None


def load_metrics(days: int = 7) -> List[Dict[str, Any]]:
    """
    Load metrics from log files
    
    Args:
        days: Number of days to look back
        
    Returns:
        List of metric dictionaries
    """
    metrics = []
    cutoff_date = datetime.now() - timedelta(days=days)
    
    if not LOG_FILE.exists():
        logger.warning(f"Log file {LOG_FILE} not found")
        return metrics
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                data = parse_log_line(line)
                if data and "event" in data and data["event"] == "fixation.generate":
                    # Parse timestamp
                    timestamp_str = data.get("asctime", "")
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
                        if timestamp < cutoff_date:
                            continue
                        
                        data["timestamp"] = timestamp
                        metrics.append(data)
                    except (ValueError, TypeError):
                        # Skip entries with invalid timestamps
                        continue
    except Exception as e:
        logger.error(f"Error loading metrics: {e}")
    
    return metrics


def calculate_metrics(metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate summary metrics
    
    Args:
        metrics: List of metric dictionaries
        
    Returns:
        Dictionary of summary metrics
    """
    if not metrics:
        return {
            "total_documents": 0,
            "success_rate": 0,
            "fallback_rate": 0,
            "avg_duration_ms": 0,
            "p95_duration_ms": 0,
            "documents_by_type": {},
            "documents_by_client": {},
            "fallbacks_by_type": {},
        }
    
    # Basic counts
    total = len(metrics)
    successful = sum(1 for m in metrics if m.get("ok", False))
    fallbacks = sum(1 for m in metrics if m.get("fallback", False))
    
    # Duration stats
    durations = [m.get("duration_ms", 0) for m in metrics if "duration_ms" in m]
    avg_duration = statistics.mean(durations) if durations else 0
    p95_duration = statistics.quantile(durations, 0.95) if durations else 0
    
    # Documents by type
    docs_by_type = Counter(m.get("endpoint", "unknown") for m in metrics)
    
    # Documents by client
    docs_by_client = Counter(str(m.get("client_id", "unknown")) for m in metrics)
    
    # Fallbacks by type
    fallbacks_by_type = Counter(
        m.get("endpoint", "unknown") 
        for m in metrics 
        if m.get("fallback", False)
    )
    
    return {
        "total_documents": total,
        "success_rate": (successful / total) * 100 if total > 0 else 0,
        "fallback_rate": (fallbacks / total) * 100 if total > 0 else 0,
        "avg_duration_ms": avg_duration,
        "p95_duration_ms": p95_duration,
        "documents_by_type": dict(docs_by_type),
        "documents_by_client": dict(docs_by_client),
        "fallbacks_by_type": dict(fallbacks_by_type),
    }


def create_time_series(metrics: List[Dict[str, Any]]) -> pd.DataFrame:
    """Create time series dataframe from metrics"""
    if not metrics:
        return pd.DataFrame()
    
    # Group by hour
    hourly_data = defaultdict(lambda: {"count": 0, "fallbacks": 0, "duration_sum": 0})
    
    for m in metrics:
        if "timestamp" not in m:
            continue
            
        # Round to hour
        hour = m["timestamp"].replace(minute=0, second=0, microsecond=0)
        hourly_data[hour]["count"] += 1
        
        if m.get("fallback", False):
            hourly_data[hour]["fallbacks"] += 1
            
        hourly_data[hour]["duration_sum"] += m.get("duration_ms", 0)
    
    # Convert to dataframe
    data = []
    for hour, stats in hourly_data.items():
        avg_duration = stats["duration_sum"] / stats["count"] if stats["count"] > 0 else 0
        fallback_rate = (stats["fallbacks"] / stats["count"]) * 100 if stats["count"] > 0 else 0
        
        data.append({
            "hour": hour,
            "count": stats["count"],
            "avg_duration_ms": avg_duration,
            "fallback_rate": fallback_rate
        })
    
    return pd.DataFrame(data)


# Define layout
app.layout = html.Div([
    html.H1("Fixation Document Generation Metrics", style={"textAlign": "center"}),
    
    html.Div([
        html.Label("Time Range:"),
        dcc.Dropdown(
            id="time-range",
            options=[
                {"label": "Last 24 Hours", "value": 1},
                {"label": "Last 7 Days", "value": 7},
                {"label": "Last 30 Days", "value": 30}
            ],
            value=7
        )
    ], style={"width": "200px", "margin": "20px"}),
    
    # Summary cards
    html.Div([
        html.Div([
            html.H3("Total Documents"),
            html.H2(id="total-documents", children="0")
        ], className="summary-card"),
        
        html.Div([
            html.H3("Success Rate"),
            html.H2(id="success-rate", children="0%")
        ], className="summary-card"),
        
        html.Div([
            html.H3("Fallback Rate"),
            html.H2(id="fallback-rate", children="0%")
        ], className="summary-card"),
        
        html.Div([
            html.H3("Avg Response Time"),
            html.H2(id="avg-duration", children="0 ms")
        ], className="summary-card"),
        
        html.Div([
            html.H3("P95 Response Time"),
            html.H2(id="p95-duration", children="0 ms")
        ], className="summary-card"),
    ], style={"display": "flex", "justifyContent": "space-around", "margin": "20px"}),
    
    # Charts
    html.Div([
        html.Div([
            html.H3("Documents by Type"),
            dcc.Graph(id="docs-by-type")
        ], style={"width": "50%"}),
        
        html.Div([
            html.H3("Documents by Client"),
            dcc.Graph(id="docs-by-client")
        ], style={"width": "50%"})
    ], style={"display": "flex"}),
    
    html.Div([
        html.Div([
            html.H3("Fallbacks by Type"),
            dcc.Graph(id="fallbacks-by-type")
        ], style={"width": "50%"}),
        
        html.Div([
            html.H3("Response Time Trend"),
            dcc.Graph(id="duration-trend")
        ], style={"width": "50%"})
    ], style={"display": "flex"}),
    
    # Document count trend
    html.Div([
        html.H3("Document Generation Trend"),
        dcc.Graph(id="doc-trend")
    ]),
    
    # Auto-refresh
    dcc.Interval(
        id="interval-component",
        interval=60 * 1000,  # Refresh every minute
        n_intervals=0
    )
])


@app.callback(
    [
        Output("total-documents", "children"),
        Output("success-rate", "children"),
        Output("fallback-rate", "children"),
        Output("avg-duration", "children"),
        Output("p95-duration", "children"),
        Output("docs-by-type", "figure"),
        Output("docs-by-client", "figure"),
        Output("fallbacks-by-type", "figure"),
        Output("duration-trend", "figure"),
        Output("doc-trend", "figure")
    ],
    [
        Input("interval-component", "n_intervals"),
        Input("time-range", "value")
    ]
)
def update_metrics(n_intervals, days):
    """Update all metrics based on selected time range"""
    metrics = load_metrics(days=days)
    summary = calculate_metrics(metrics)
    time_series = create_time_series(metrics)
    
    # Create figures
    docs_by_type_fig = px.pie(
        names=list(summary["documents_by_type"].keys()),
        values=list(summary["documents_by_type"].values()),
        title="Documents by Type"
    )
    
    docs_by_client_fig = px.bar(
        x=list(summary["documents_by_client"].keys()),
        y=list(summary["documents_by_client"].values()),
        title="Documents by Client"
    )
    docs_by_client_fig.update_layout(xaxis_title="Client ID", yaxis_title="Document Count")
    
    fallbacks_by_type_fig = px.pie(
        names=list(summary["fallbacks_by_type"].keys()),
        values=list(summary["fallbacks_by_type"].values()),
        title="Fallbacks by Type"
    )
    
    # Time series charts
    if not time_series.empty:
        duration_trend_fig = px.line(
            time_series, 
            x="hour", 
            y="avg_duration_ms",
            title="Average Response Time Trend"
        )
        duration_trend_fig.update_layout(xaxis_title="Time", yaxis_title="Avg Duration (ms)")
        
        doc_trend_fig = px.line(
            time_series, 
            x="hour", 
            y="count",
            title="Document Count Trend"
        )
        doc_trend_fig.update_layout(xaxis_title="Time", yaxis_title="Document Count")
    else:
        duration_trend_fig = go.Figure()
        duration_trend_fig.update_layout(title="No data available")
        
        doc_trend_fig = go.Figure()
        doc_trend_fig.update_layout(title="No data available")
    
    return (
        f"{summary['total_documents']}",
        f"{summary['success_rate']:.1f}%",
        f"{summary['fallback_rate']:.1f}%",
        f"{summary['avg_duration_ms']:.1f} ms",
        f"{summary['p95_duration_ms']:.1f} ms",
        docs_by_type_fig,
        docs_by_client_fig,
        fallbacks_by_type_fig,
        duration_trend_fig,
        doc_trend_fig
    )


if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
