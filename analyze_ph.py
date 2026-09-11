import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

def fetch_calgary_water_data(dataset_id, parameter="pH", site_pattern="Bearspaw", days=365):
    """
    Fetches historical water quality data from the City of Calgary Open Data API (SODA).
    """
    base_url = f"https://data.calgary.ca/resource/{dataset_id}.json"
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%S.000")
    
    # SODA Query (SoQL)
    # We use a dictionary for params to ensure proper URL encoding by requests
    params = {
        "$where": f"parameter='{parameter}' AND sample_site like '%{site_pattern}%' AND sample_date > '{start_date_str}'",
        "$limit": 10000
    }
    
    response = requests.get(base_url, params=params)
    if response.status_code != 200:
        print(f"Error fetching data from {dataset_id}: {response.status_code}")
        print(response.text)
        return pd.DataFrame()
    
    data = response.json()
    if not data:
        print(f"No data found for {dataset_id} with site {site_pattern}")
        return pd.DataFrame()
        
    df = pd.DataFrame(data)
    
    # Clean up types
    df['sample_date'] = pd.to_datetime(df['sample_date'])
    df['numeric_result'] = pd.to_numeric(df['numeric_result'], errors='coerce')
    
    return df

def analyze_ph():
    print("Fetching historical data from Watershed dataset (y8as-bmzj)...")
    df_hist = fetch_calgary_water_data("y8as-bmzj", site_pattern="Bearspaw", days=365)
    
    print("Fetching recent sensor data from Sonde dataset (kc8x-fu3f)...")
    # Sondes are real-time, focusing on the last 30 days for 'current' state
    df_sonde = fetch_calgary_water_data("kc8x-fu3f", site_pattern="Bearspaw", days=30)
    
    if df_hist.empty and df_sonde.empty:
        print("No data found. Exiting.")
        return

    # Combine for analysis
    all_data = pd.concat([df_hist, df_sonde], ignore_index=True).sort_values('sample_date')
    
    # Save to CSV
    csv_path = "calgary_ph_data.csv"
    all_data.to_csv(csv_path, index=False)
    print(f"Data saved to {csv_path}")
    
    # Identify trends
    all_data['month'] = all_data['sample_date'].dt.strftime('%Y-%m')
    monthly_avg = all_data.groupby('month')['numeric_result'].mean().reset_index()
    
    # Hot Tub Sweet Spot (7.5)
    target_ph = 7.5
    current_ph = all_data.iloc[-1]['numeric_result'] if not all_data.empty else None
    current_date = all_data.iloc[-1]['sample_date'] if not all_data.empty else None
    
    print(f"Current pH (Bearspaw): {current_ph} as of {current_date}")
    
    # Plotting
    fig = px.line(all_data, x='sample_date', y='numeric_result', color='sample_site',
                  title="Calgary Water pH Trend (Bearspaw Area) - Last 1 Year",
                  labels={'sample_date': 'Date', 'numeric_result': 'pH Value', 'sample_site': 'Sample Site'},
                  template="plotly_dark")
    
    # Add target line
    fig.add_hline(y=target_ph, line_dash="dash", line_color="green", 
                  annotation_text="Hot Tub Sweet Spot (7.5)", annotation_position="bottom right")
    
    # Add current context
    fig.update_layout(
        hovermode="x unified",
        yaxis_range=[7, 10], # pH range typical for Calgary is 7.5-8.5
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    html_path = "calgary_ph_analysis.html"
    fig.write_html(html_path)
    print(f"Interactive chart saved to {html_path}")
    
    # Recommendation Logic
    best_months = monthly_avg[monthly_avg['numeric_result'] < 8.2]['month'].tolist()
    
    print("\n--- Summary ---")
    print(f"Latest reading: {current_ph} ({current_date.strftime('%Y-%m-%d')})")
    if current_ph < 8.0:
        print("Status: EXCELLENT. pH is currently close to your target!")
    elif current_ph < 8.5:
        print("Status: MODERATE. pH is slightly high but typical for Calgary.")
    else:
        print("Status: HIGH. You might want to wait or use pH reducer.")
        
    print("\nHistorical Trends:")
    print(f"Average monthly pH values: {monthly_avg}")
    if best_months:
        print(f"Best months historically (Lower pH): {', '.join(best_months)}")
    else:
        print("Historical pH is consistently above 8.2.")

if __name__ == "__main__":
    analyze_ph()
