from flask import Flask, render_template, request, send_file
from flask_bootstrap import Bootstrap
from playwright.sync_api import sync_playwright
import pandas as pd
from bs4 import BeautifulSoup

app = Flask(__name__, static_url_path='/static')
bootstrap = Bootstrap(app)

def extract_data(page, query_string):
    url = f'https://safer.fmcsa.dot.gov/query.asp?searchtype=ANY&query_type=queryCarrierSnapshot&query_param=MC_MX&query_string={query_string}'
    page.goto(url)

    # Allow some time for dynamic content to load (you may need to adjust this)
    page.wait_for_timeout(5000)

    # Get the page content after JavaScript execution
    html_content = page.content()

    # Use BeautifulSoup for parsing
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract 'Entity Type'
    entity_type_element = soup.find('th', string='Entity Type:')
    entity_type = entity_type_element.find_next('td').get_text(strip=True) if entity_type_element else ''

    # Check if 'Entity Type' is 'CARRIER'
    if entity_type == 'CARRIER':
        # Extract 'Operating Status'
        operating_status_element = soup.find('th', string='Operating Status:')
        operating_status = operating_status_element.find_next('td').get_text(strip=True) if operating_status_element else ''

        # Check if 'Operating Status' is 'AUTHORIZED' or 'AUTHORIZED FOR Property'
        if operating_status in ['AUTHORIZED', 'AUTHORIZED FOR Property']:
            # Continue with data extraction and processing
            relevant_data = {}

            for field in ['Legal Name', 'Physical Address', 'Phone', 'MC/MX/FF Number(s)']:
                field_element = soup.find('th', string=f'{field}:')
                if field_element:
                    field_value = field_element.find_next('td').get_text(strip=True)
                    relevant_data[field] = field_value

            # Extract 'Vehicle' and 'Driver' values corresponding to 'Inspections'
            inspections_row = soup.find('th', string=lambda text: 'Inspections' in text if text else None)
            if inspections_row:
                vehicle_value = inspections_row.find_next('td', {'align': 'center', 'class': 'queryfield'}).get_text(strip=True)
                driver_value = inspections_row.find_next('td', {'align': 'center', 'class': 'queryfield'}).find_next('td', {'align': 'center', 'class': 'queryfield'}).get_text(strip=True)

                relevant_data['Vehicle'] = vehicle_value
                relevant_data['Driver'] = driver_value
            else:
                print(f"Skipping page {query_string} as 'Inspections' row not found")

            # Extract 'General_Freight' value
            general_freight_element = soup.find('td', string='General Freight')
            general_freight_value = general_freight_element.find_next('td').find_next('font').get_text(strip=True) if general_freight_element else ''
            relevant_data['General_Freight_Output'] = 'Yes' if general_freight_value else 'No'

            # Check if 'General_Freight' is present
            if 'General_Freight' in relevant_data and relevant_data['General_Freight_Output'] == 'Yes':
                print(f"Output: Yes for {query_string}")
            else:
                print(f"Output: No for {query_string}")

            # Remove unwanted data
            relevant_data.pop('Hazmat', None)
            relevant_data.pop('IEP', None)

            return relevant_data
        else:
            print(f"Skipping page {query_string} as Operating Status is not AUTHORIZED")
            return None
    else:
        print(f"Skipping page {query_string} as Entity Type is not CARRIER")
        return None

# Define route for the home page
@app.route('/')
def index():
    return render_template('index.html', data=None, csv_path=None)

@app.route('/extract', methods=['POST'])
def extract():
    start_query = int(request.form['start_query'])
    end_query = int(request.form['end_query'])

    with sync_playwright() as p:
        all_data = []

        for query_number in range(start_query, end_query + 1):
            try:
                browser = p.chromium.launch(headless=True)

                # Create a new context
                context = browser.new_context()

                # Create a new page
                page = context.new_page()

                data = extract_data(page, str(query_number))
                if data:
                    all_data.append(data)

                # Close the context
                context.close()

            except Exception as e:
                print(f"Skipping page {query_number}: {e}")

        df = pd.DataFrame(all_data)

        # Convert DataFrame to list of dictionaries
        data_dict = df.to_dict(orient='records')

        # Save the DataFrame to a temporary CSV file
        temp_csv_path = 'temp_data.csv'
        df.to_csv(temp_csv_path, index=False)

        print("Data extraction completed.")

    return render_template('index.html', data=data_dict, csv_path=temp_csv_path)

@app.route('/download/<path:csv_path>')
def download(csv_path):
    return send_file(csv_path, as_attachment=True, attachment_filename='all_carrier_data.csv')

@app.route('/details/<query_number>')
def details(query_number):
    # Add logic to fetch additional details for the specified query_number
    # For example, you can query a database or use another web scraping function
    additional_details = {
        'Query Number': query_number,
        'Additional Detail 1': 'Value 1',
        'Additional Detail 2': 'Value 2',
        # Add more details as needed
    }

    return render_template('details.html', additional_details=additional_details)

if __name__ == '__main__':
    app.run(debug=False)
