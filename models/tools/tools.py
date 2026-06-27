import os
import time
import functools
import psutil


def measure_resources(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        proceso = psutil.Process(os.getpid())
        start_cpu_usage = proceso.cpu_percent(interval=None)
        start_memory_usage = proceso.memory_info().rss
        result = func(*args, **kwargs)
        end_cpu_usage = proceso.cpu_percent(interval=None)
        end_memory_usage = proceso.memory_info().rss
        print(f'CPU usage: {end_cpu_usage - start_cpu_usage:.2f}%')
        print(f'Memory usage: {(end_memory_usage - start_memory_usage) / (1024 * 1024):.2f} MB')
        return result
    return wrapper


def measure_execute_time(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        print(f"Execution time: {end - start:.6f} seconds")
        return result
    return wrapper
