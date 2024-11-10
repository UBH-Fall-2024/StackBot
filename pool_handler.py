from multiprocessing import Pool
import os
import time

def worker(job_id):
    time.sleep(1)  # Simulating some work
    return f"Job {job_id} done by PID: {os.getpid()}"

def collect_result(result):
    print(f"Collected result: {result}")

if __name__ == "__main__":
    with Pool(processes=4) as pool:
        results = []
        for i in range(10):
            result = pool.apply_async(worker, args=(i,), callback=collect_result)
            results.append(result)
        
        # Wait for all asynchronous tasks to complete
        for result in results:
            result.wait()
    
    print("All jobs completed")