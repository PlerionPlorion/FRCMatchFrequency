import csv
import json
from collections import defaultdict

import easygui
import pandas as pd
import requests
from bokeh.io import curdoc, export_png, export_svg
from bokeh.layouts import layout
from bokeh.models import ColumnDataSource, HoverTool, WheelZoomTool
from bokeh.palettes import Spectral6
from bokeh.plotting import figure, output_notebook, show
from selenium import webdriver

# API stuff
api = 'https://www.thebluealliance.com/api/v3'
authKey = 'TCExry18I2AXAYPpU1YtahdGb5SUkOKq1ZFTjA2aHMR3ZrnZFp0sgr4v35ixFZeW' # I'm sure this is fine
options = webdriver.ChromeOptions()
options.add_argument("headless=new")
driver = webdriver.Chrome(options=options)

# Getting team number
requested_team = easygui.enterbox(msg="Please enter the team number", title='Team #', default='', strip=True, image=None, root=None)
requested_teamkey = 'frc' + requested_team

response = requests.get(api + '/team/frc' + requested_team + '/years_participated', params={"X-TBA-Auth-Key": authKey})
years = []
all_opposing_teams = []
all_allied_teams = []

# Save data to CSV
def save_to_csv(data, filename):
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Year", "Team_Key", "Count"])
        for row in data:
            writer.writerow(row)

# Prompt for year range
def get_year_range():
    while True:
        try:
            # Prompt the user for both years in one go, separated by a comma
            years_input = easygui.enterbox(msg="Enter the start year and end year separated by a dash", title='Year Range', default='1992-2024')
            
            # Split the input string by the comma to get the start and end years
            start_year_str, end_year_str = years_input.split('-')
            
            start_year = int(start_year_str.strip())
            end_year = int(end_year_str.strip())
            
            if start_year >= end_year:
                raise ValueError("End year must be greater than start year.")
            return start_year, end_year
        except ValueError as e:
            easygui.msgbox(str(e), title='Invalid Input')

start_year, end_year = get_year_range()

if response.status_code == 200:
    response_str = response.content.decode('utf-8')
    years_list = json.loads(response_str)
    filtered_years = [year for year in years_list if start_year <= year <= end_year]
    if not filtered_years:
        print("No data available for the specified year range.")
        exit()  # Exit the script if there's no data for the specified range
    for year in filtered_years:
        # Construct the URL for matches in the current year
        matches_url = f"{api}/team/frc{requested_team}/matches/{year}/simple"
        headers = {"X-TBA-Auth-Key": authKey}
        
        # Make the request for matches
        matches_response = requests.get(matches_url, headers=headers)
        
        # Append years
        years.append(year)

        if matches_response.status_code == 200:
            matches_str = matches_response.content.decode('utf-8')
            matches_list = json.loads(matches_str)
            
            # Initialize dictionaries to keep track of team appearances
            opposing_teams = defaultdict(int)
            allied_teams = defaultdict(int)
            
            for match in matches_list:
                # Extract team_keys for the blue and red alliances
                blue_teams = set(match['alliances']['blue']['team_keys'])
                red_teams = set(match['alliances']['red']['team_keys'])
                
                # print(f"Blue Teams: {blue_teams}, Red Teams: {red_teams}")  # Debugging line
                
                # Identify the alliance of requested_team
                requested_alliance = None
                if requested_teamkey in blue_teams:
                    requested_alliance = 'blue'
                elif requested_teamkey in red_teams:
                    requested_alliance = 'red'
                else:
                    print(f"Requested team {requested_team} not found in any alliance for year {year}.")
                    continue
                
                # Check if the team was part of an alliance
                if requested_alliance is None:
                    print(f"Skipping year {year} for team {requested_team} as no alliance found.")
                    continue
                
                # Update allied_teams and opposing_teams based on the actual alliance in this match
                if requested_alliance == 'red':
                    # Skip updating for requested_team itself
                    # requested_team is an allied team for this match
                    for team_key in red_teams:
                        if team_key != requested_teamkey:
                            allied_teams[team_key] = allied_teams.get(team_key, 0) + 1
                    # requested_team is an opposing team for blue alliance matches
                    for team_key in blue_teams:
                        if team_key != requested_teamkey:
                            opposing_teams[team_key] = opposing_teams.get(team_key, 0) + 1
                else:  # If the team is in the blue alliance
                    # requested_team is an opposing team for this match
                    for team_key in red_teams:
                        if team_key != requested_teamkey:
                            opposing_teams[team_key] = opposing_teams.get(team_key, 0) + 1
                    # requested_team is an allied team for other blue alliance matches
                    for team_key in blue_teams:
                        if team_key != requested_teamkey:
                            allied_teams[team_key] = allied_teams.get(team_key, 0) + 1

            
            # Save the team_keys and their counts for opposing and allied teams
            for team_key, count in opposing_teams.items():
                all_opposing_teams.append([year, team_key, count])

            for team_key, count in allied_teams.items():
                all_allied_teams.append([year, team_key, count])
            
        else:
            print(f"Failed to retrieve matches for year {year}: {matches_response.status_code}")
else:
    print("Failed to retrieve data:", response.status_code)

# save_to_csv to save both sets of data
save_to_csv(all_opposing_teams, "opposing_teams.csv")
save_to_csv(all_allied_teams, "allied_teams.csv")

# Load the data
opposing = pd.read_csv("opposing_teams.csv")
allied = pd.read_csv("allied_teams.csv")

# For allied teams
allied_aggregated = allied.groupby('Team_Key')['Count'].sum().reset_index()
allied_aggregated.rename(columns={'Count': 'Allied_Count'}, inplace=True)

# For opposing teams
opposing_aggregated = opposing.groupby('Team_Key')['Count'].sum().reset_index()
opposing_aggregated.rename(columns={'Count': 'Opposing_Count'}, inplace=True)

# Merge the DataFrames on the 'Team_Key' column
mergedTeams = pd.merge(allied_aggregated, opposing_aggregated, on='Team_Key', how='outer')

# Fill NaN values with 0 for teams that appear in one dataset but not the other
mergedTeams.fillna(0, inplace=True)

# Convert counts to integers to remove decimals
mergedTeams['Allied_Count'] = mergedTeams['Allied_Count'].astype(int)
mergedTeams['Opposing_Count'] = mergedTeams['Opposing_Count'].astype(int)

# Calculate the total count by summing the 'Allied_Count' and 'Opposing_Count' columns
mergedTeams['Count'] = mergedTeams['Allied_Count'] + mergedTeams['Opposing_Count']

mergedTeams.to_csv("combined_counts.csv", index=False)

# Remove the "frc" prefix from the 'Team_Key' column
mergedTeams['Team_Key'] = mergedTeams['Team_Key'].str.replace('frc', '')

# Group by team_key and add the counts
aggregated_data = mergedTeams.groupby('Team_Key').sum().reset_index()

# Sort the data by the number of appearances in descending order
sorted_data = aggregated_data.sort_values(by='Count', ascending=False)

# Convert to ColumnDataSource for Bokeh
source = ColumnDataSource(sorted_data)

# Create a new plot with a title and axis labels
p = figure(title="Matches With for: " + requested_team,
           x_axis_label='Team_Key',
           y_axis_label='Matches Across ' + str(start_year) + '-' + str(end_year),
           tools="pan,wheel_zoom,box_zoom,reset",
           x_range=(source.data['Team_Key']),
           y_range=(0, max(source.data['Allied_Count'])*1.1),
           width=len(source.data['Team_Key'])*15)
p.xaxis.major_label_orientation = "vertical"
p.toolbar.active_scroll = p.select_one(WheelZoomTool)

# Define hover tool
hover = HoverTool(tooltips=[
    ("Team", "@Team_Key"),
    ("Matches Against", "@Opposing_Count"),
    ("Matches With", "@Allied_Count"),
    ("Total Matches", "@Count"),
])
p.add_tools(hover)

# Add a renderer with legend and line thickness
p.vbar(top='Allied_Count', x='Team_Key', width=0.5, color=Spectral6[1], source=source,
       legend_label='Matches With')

# Customize the legend
p.legend.location = "top_left"
p.legend.click_policy="hide"  # Allows clicking on legend items to hide the corresponding data

# Show the results
curdoc().theme = 'dark_minimal'
export_png(p, filename="plot.png", webdriver=driver)
# export_svg(p, filename="plot.svg", webdriver=driver, height=max(source.data['Count'])*50)
show(p)