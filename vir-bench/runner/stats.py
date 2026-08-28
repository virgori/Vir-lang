import math

def calculate_stats(timings_ms):
    if not timings_ms:
        return {}
    
    sorted_t = sorted(timings_ms)
    n = len(sorted_t)
    
    # Min, Max, Mean
    min_val = sorted_t[0]
    max_val = sorted_t[-1]
    mean_val = sum(sorted_t) / n
    
    # Median
    if n % 2 == 1:
        median_val = sorted_t[n // 2]
    else:
        median_val = (sorted_t[n // 2 - 1] + sorted_t[n // 2]) / 2.0
        
    # P95
    p95_idx = int(math.ceil(0.95 * n)) - 1
    p95_val = sorted_t[min(p95_idx, n - 1)]
    
    # Standard deviation
    variance = sum((x - mean_val) ** 2 for x in sorted_t) / n
    stddev = math.sqrt(variance)
    
    return {
        "count": n,
        "min_ms": min_val,
        "max_ms": max_val,
        "mean_ms": mean_val,
        "median_ms": median_val,
        "p95_ms": p95_val,
        "stddev_ms": stddev
    }

def format_stats(stats):
    if not stats:
        return "N/A"
    return f"median={stats['median_ms']:.3f}ms, p95={stats['p95_ms']:.3f}ms, stddev={stats['stddev_ms']:.3f}ms (n={stats['count']})"
