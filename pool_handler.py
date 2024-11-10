from multiprocessing import Pool
import os
import time
from main import StockManager
import asyncio
import logging

stocks = ["NVDA, MSFT"]


def worker(stock_name):
    time.sleep(1)

    async def main():
        stock = StockManager(stock_name)
        try:
            # stock.login()
            stock.get_current_price()
            stock.get_stock_worth()
            stock.analyze_stock()
        except Exception as e:
            print(stock.errors)
        finally:
            stock.close()

    asyncio.run(main())


if __name__ == "__main__":
    with Pool(processes=2) as pool:
        results = []
        for i in range(len(stocks)):
            result = pool.apply_async(worker, args=(stocks[i],))
            results.append(result)
        pool.close()
        pool.join()
        print("All jobs started")
        for result in results:

            print("Job completed")
            print("Finished job", os.getpid())
            time.sleep(1)  # Sleep for 1 second to avoid overloading the API

    print("All jobs completed")
