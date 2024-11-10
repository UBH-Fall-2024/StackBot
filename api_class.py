import requests
import os
import datetime
import dotenv
import pandas as pd
import math
import numpy as np


dotenv.load_dotenv()


def validday(days):
    return days - ((math.floor(days / 7)) * 2)


def marketopen(current_datetime=datetime.datetime.now()):
    # Get the current date, day of the week, and time
    current_day = current_datetime.strftime('%A')  # e.g., 'Monday', 'Tuesday'
    current_time = current_datetime.time()

    target_days = ['Monday', 'Wednesday']
    start_time = datetime.time(9, 30)
    end_time = datetime.time(16, 0)                 # Start time is 9:00 AM

    return current_day in target_days and start_time <= current_time <= end_time


def averageOfLastWeek(filename):
    dataframe = pd.read_csv(filename)
    lastweek = dataframe.head(7)
    lastweek = lastweek.drop(lastweek.columns[0], axis=1)
    lastweek = lastweek.mean()
    return lastweek


def getData(ticker, params={
    # yesterday's date
    "startDate": str((datetime.datetime.now() - datetime.timedelta(days=365)).strftime("%Y-%m-%d")),
    "endDate": str(datetime.datetime.now().strftime("%Y-%m-%d")),
    # Can be 'daily', 'weekly', or 'monthly' depending on the desired frequency of the data.
    "resampleFreq": "daily"
}):
    filename = f"{ticker}-{params["startDate"]}-{params["endDate"]}.csv"
    if (not os.path.exists(filename)):

        # Load the API key from the environment
        API_KEY = os.getenv("tingo_api")
        # Define the headers with the API key
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Token {API_KEY}'
        }

        # Define the endpoint and parameters
        endpoint = f'https://api.tiingo.com/tiingo/daily/{ticker}/prices'

        # Make the request
        response = requests.get(endpoint, headers=headers, params=params)

        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            df = pd.DataFrame(data)
            df = df.iloc[::-1]
            # drop date
            df = df.drop(df.columns[0], axis=1)

            df.to_csv(f"temp_datasets/{filename}", index=False)

        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
        return [df, f"temp_datasets/{filename}"]

    else:
        print("File already exists.")
        df = pd.DataFrame(pd.read_csv(filename))
        return [df, filename]
