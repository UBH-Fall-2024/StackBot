import asyncio
import api_class
from model import StockPricePredictor
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome import options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import os
import dotenv
import requests
import pandas as pd
import numpy as np
import logging
from datetime import datetime, time
import pytz
import time as tp
from requests.structures import CaseInsensitiveDict
import json
from selenium.common import exceptions


if os.path.exists("bot.log"):
    os.remove("bot.log")

logging.basicConfig(filename='bot.log', level=logging.INFO)

dotenv.load_dotenv()


class StockManager:
    def __init__(self, stock="NVDA"):
        self.stock = stock
        self.errors = []
        self.pending_stocks = {}
        self.predicted_closing = None
        market_tz = pytz.timezone('America/New_York')
        self.market_open = market_tz.localize(
            datetime.combine(datetime.today(), time(9, 30)))
        self.market_close = market_tz.localize(
            datetime.combine(datetime.today(), time(16, 0)))
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_experimental_option(
            "debuggerAddress", "localhost:8908")
        self.network_responses = {}
        self.previous_refresh_token = self.read_refresh_token()
        self.driver = self.open_chrome()

    def capture_network_traffic(self):
        if (self.driver.last_request):
            body = self.driver.last_request.response.body.decode('utf-8')
            data = json.loads(body)
            print(len(data))
            with open("network.txt", "w") as file:
                file.write(json.dumps(data, indent=4))
        else:
            print("No network data")

    def get_token_from_network_logs(self):
        logs = self.driver.get_log('performance')
        for entry in logs:
            log = json.loads(entry['message'])['message']
            # Look for a particular URL or part of the URL in request or response
            if log['method'] == 'Network.responseReceived':
                url = log['params']['response']['url']
                # Check if URL contains the request for the token
                if 'token' in url:
                    request_id = log['params']['requestId']
                    response_body = self.driver.execute_cdp_cmd(
                        'Network.getResponseBody', {'requestId': request_id}
                    )
                    # Parse or extract the token from response body
                    token = response_body['body']  # Adjust parsing as needed
                    print('Token:', token)
                    return token

    def read_refresh_token(self):
        with open("refreshtoken.txt", "r") as file:
            return file.read()

    def open_chrome(self):
        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.driver.execute_cdp_cmd("Network.enable", {})
        self.network_responses = {}
        url = "https://auth.investopedia.com/realms/investopedia/protocol/openid-connect/auth?client_id=finance-simulator&redirect_uri=https%3A%2F%2Fwww.investopedia.com%2Fsimulator%2Fportfolio&state=f91c3ff3-62e1-4d95-877a-ca86ef32fe92&response_mode=fragment&response_type=code&scope=openid&nonce=c1098a13-cc8a-4fa6-8823-494ee580ad7c"
        self.driver.execute_script(f"window.open('{url}', '_blank');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        tp.sleep(5)
        self.driver.get("https://www.investopedia.com/simulator/portfolio")
        tp.sleep(5)
        self.driver.switch_to.window(self.driver.window_handles[-1])
        return self.driver

    def login(self):
        tp.sleep(2)
        username_field = self.driver.find_element(By.ID, "username")
        password_field = self.driver.find_element(By.ID, "password")
        username_field.clear()
        username_field.send_keys(os.environ.get("investopedia_email"))
        password_field.send_keys(os.environ.get("investopedia_password"))
        password_field.send_keys(Keys.RETURN)
        tp.sleep(5)

    def loadDashboard(self):
        self.driver.get("https://www.investopedia.com/simulator/portfolio")
        tp.sleep(5)

    def analyze_stock(self, limit=10000):
        self.keep_a_watch()
        while True:
            if datetime.now() > time(16, 0):
                break
            self.analyze_stock(limit)
            tp.sleep(60)

    def keep_a_watch(self):
        print("Watching")
        while True:
            self.predicted_closing = self.predict_prices()
            print("Watching")
            logging.info(f"Predicted Closing: {self.predicted_closing}")
            print(f"Predicted Closing: {self.predicted_closing}")
            worth, count = self.get_stock_worth()
            self.curr_price = self.get_current_price()
            if self.predicted_closing - self.curr_price > 10:
                self.placeOrder(50, "BUY")
                break
            if self.predicted_closing - self.curr_price < -5:
                if count == 0:
                    continue
                self.placeOrder(min(count, 20), "SELL")

            if tp.time() > time(14, 0):
                if self.predicted_closing - self.curr_price > 5:
                    continue
                else:
                    self.placeOrder(count, "SELL")
                break
            tp.sleep(60)

    def get_current_price(self):
        body = {
            "operationName": "CompanyProfile",
            "variables": {
                "symbol": self.stock
            },
            "query": "query CompanyProfile($symbol: String!) {\n  readStock(symbol: $symbol) {\n    ... on Stock {\n      technical {\n        volume\n        dayHighPrice\n        dayLowPrice\n        askPrice\n        bidPrice\n        __typename\n      }\n      fundamental {\n        lowestPriceLast52Weeks\n        highestPriceLast52Weeks\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n"
        }
        response = self.request(body)
        json = response.json()
        logging.info("Current Price: " +
                     str(json["data"]["readStock"]["technical"]["askPrice"]))
        if response.status_code == 200:
            return json["data"]["readStock"]["technical"]["askPrice"]
        else:
            self.errors.append(
                f"Failed to get current price for {self.stock}. Status code: {response.status_code} {json}")
            return None

    def get_all_pending_stocks_data(self):
        body = {
            "operationName": "PendingStockTrades",
            "variables": {
                "portfolioId": "10735223",
                "holdingType": "STOCKS"
            },
            "query": "query PendingStockTrades($portfolioId: String!, $holdingType: HoldingType!) {\n  readPortfolio(portfolioId: $portfolioId) {\n    ... on PortfolioErrorResponse {\n      errorMessages\n      __typename\n    }\n    ... on Portfolio {\n      holdings(type: $holdingType) {\n        ... on CategorizedStockHoldings {\n          pendingTrades {\n            stock {\n              ... on Stock {\n                description\n                technical {\n                  lastPrice\n                  __typename\n                }\n                __typename\n              }\n              __typename\n            }\n            symbol\n            transactionTypeDescription\n            orderPriceDescription\n            tradeId\n            action\n            cancelDate\n            quantity\n            quantityType\n            transactionType\n            limit {\n              limit\n              stop\n              trailingStop {\n                percentage\n                price\n                __typename\n              }\n              __typename\n            }\n            __typename\n          }\n          __typename\n        }\n        ... on HoldingsErrorResponse {\n          errorMessages\n          __typename\n        }\n        ... on CategorizedHoldingsErrorResponse {\n          errorMessages\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n"
        }

        response = self.request(body)

        if (response.status_code != 200):
            self.errors.append(
                f"Failed to get stock worth for {self.stock}. Status code: {response.status_code}")
            # return None, 0

        json = response.json()
        trades_list = json["data"]["readPortfolio"]["holdings"]["pendingTrades"]
        for trade in trades_list:
            symbol = trade["symbol"]
            count = trade["quantity"]
            price = trade["stock"]["technical"]["lastPrice"]
            worth = count * price
            logging.info(f"Stock: {symbol}, Quantity: {
                         count}, Price: {price}, Worth: {worth}")
            if symbol in self.pending_stocks:
                temp_stock = self.pending_stocks[symbol]
                temp_stock["quantity"] += count
                temp_stock["count"] += price
                temp_stock["worth"] += worth
                self.pending_stocks[symbol] = temp_stock
            else:
                self.pending_stocks[symbol] = {
                    "quantity": count,
                    "count": price,
                    "worth": worth
                }
        logging.info(str(self.pending_stocks))

    def request(self, body):
        headers = CaseInsensitiveDict()
        url = "https://api.investopedia.com/simulator/graphql"
        headers["Authorization"] = f"Bearer {os.environ.get('access_token')}"
        headers["Content-Type"] = "application/json"

        response = requests.post(url, headers=headers, data=body)
        if response.status_code != 200:
            access_token = self.refresh_token()
            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.post(
                "https://api.investopedia.com/simulator/graphql", json=body, headers=headers)

        return response

    def refresh_token(self):
        url = "https://auth.investopedia.com/realms/investopedia/protocol/openid-connect/token"
        headers = CaseInsensitiveDict()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = f"refresh_token={
            self.previous_refresh_token}&grant_type=refresh_token&client_id=finance-simulator&="
        response = requests.post(url, headers=headers, data=data)
        os.environ["access_token"] = response.json()["access_token"]
        self.previous_refresh_token = response.json()["refresh_token"]
        os.environ["access_token"] = response.json()["access_token"]
        with open("refreshtoken.txt", "w") as file:
            file.write(response.json()["refresh_token"])
        return response.json()["access_token"]

    def get_stock_worth(self):
        self.get_all_pending_stocks_data()
        return self.pending_stocks[self.stock]["worth"], self.pending_stocks[self.stock]["quantity"]

    def previewOrder(self, quantity=1, transactionType="BUY"):
        body = {
            "operationName": "PreviewStockTrade",
            "variables": {
                "input": {
                    "expiry": {
                        "expiryType": "END_OF_DAY"
                    },
                    "limit": {
                        "limit": None
                    },
                    "portfolioId": "10735223",
                    "quantity": 10,
                    "symbol": self.stock,
                    "transactionType": "BUY"
                }
            },
            "query": "query PreviewStockTrade($input: TradeEntityInput!) {\n  previewStockTrade(stockTradeEntityInput: $input) {\n    ... on TradeDetails {\n      bill {\n        commission\n        price\n        quantity\n        total\n        __typename\n      }\n      __typename\n    }\n    ... on TradeInvalidEntity {\n      errorMessages\n      __typename\n    }\n    ... on TradeInvalidTransaction {\n      errorMessages\n      __typename\n    }\n    __typename\n  }\n}\n"
        }

        response = self.request(body)

        if response.status_code != 200:
            self.errors.append(
                f"Failed to preview order for {self.stock}. Status code: {response.status_code}")
            return None

        return response.json()

    def placeOrder(self, quantity=1, transactionType="BUY"):
        body = {
            "operationName": "StockTrade",
            "variables": {
                "input": {
                    "expiry": {
                        "expiryType": "END_OF_DAY"
                    },
                    "limit": {
                        "limit": None
                    },
                    "portfolioId": "10735223",
                    "quantity": quantity,
                    "symbol": self.stock,
                    "transactionType": transactionType
                }
            },
            "query": "mutation StockTrade($input: TradeEntityInput!) {\n  submitStockTrade(stockTradeEntityInput: $input) {\n    ... on TradeInvalidEntity {\n      errorMessages\n      __typename\n    }\n    ... on TradeInvalidTransaction {\n      errorMessages\n      __typename\n    }\n    __typename\n  }\n}\n"
        }

        logging.info(transactionType.capitalize() + "ing Stocks")
        logging.info(f"Quantity: {quantity}, Symbol: {
                     self.stock}, Transaction Type: {transactionType}")

        response = self.request(body)

        if response.status_code != 200:
            self.errors.append(
                f"Failed to place order for {self.stock}. Status code: {response.status_code}")
            return None

        return response.json()

    def predict_prices(self):
        # if (self.predicted_closing):
        #     return self.predicted_closing["predicted_closure"]
        response = api_class.getData(ticker=self.stock)
        df = response[0]
        fn = response[1]
        # os.system("cls")
        tomorrow = api_class.averageOfLastWeek(fn)

        data = [tomorrow["high"], tomorrow["low"], tomorrow["open"], tomorrow["volume"], tomorrow["adjClose"], tomorrow["adjHigh"],
                tomorrow["adjLow"], tomorrow["adjOpen"], tomorrow["adjVolume"], tomorrow["divCash"], tomorrow["splitFactor"]]
        predictor = StockPricePredictor()
        predictor.fit(df)
        predicted_close = predictor.predict(np.array([data]))
        self.predicted_closing = {
            "stock": self.stock,
            "date": datetime.today().date(),
            "predicted_close": predicted_close
        }
        return predicted_close

    def get_tomorrow_date(self):
        return time.strftime("%Y-%m-%d", time.gmtime(time.time() + 86400))

    def close(self):
        self.driver.quit()


if __name__ == "__main__":

    async def main():
        stock = StockManager()
        try:
            logging.info("Bot started")
            logging.info("Stock Created: " + stock.stock)
            # stock.login()
            logging.info("Logged in")
            stock.loadDashboard()
            logging.info("Dashboard Loaded")
            stock.refresh_token()
            # logging.info("Stock Price: " + str(stock.get_current_price()))
            # logging.info("Stock Worth: " + str(stock.get_stock_worth()))
            logging.error(
                "Stocks Error: " + str(stock.errors)
            )
            logging.info("Predicting Prices")
            logging.info("Analyzing Stock")
            stock.analyze_stock()
        except Exception as e:
            logging.error(e)
            # os.system("cls")
            print(stock.errors)
        finally:
            stock.close()
            logging.info("Bot Closed")
    asyncio.run(main())
