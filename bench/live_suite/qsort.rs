fn qsort_custom(arr: &mut [i64], low: isize, high: isize) {
    if low < high {
        let pivot = arr[high as usize];
        let mut i = low;
        for j in low..high {
            if arr[j as usize] <= pivot {
                arr.swap(i as usize, j as usize);
                i += 1;
            }
        }
        arr.swap(i as usize, high as usize);
        let pi = i;
        if pi > 0 {
            qsort_custom(arr, low, pi - 1);
        }
        qsort_custom(arr, pi + 1, high);
    }
}

fn main() {
    let n = 100000;
    let mut arr = Vec::with_capacity(n);
    for i in 0..n {
        arr.push(((i as i64 * 1664525 + 1013904223) % 1000000) as i64);
    }
    qsort_custom(&mut arr, 0, (n - 1) as isize);
    println!("Qsort Checksum: {}", arr[n / 2]);
}
